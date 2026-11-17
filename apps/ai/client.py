# -*- coding: utf-8 -*-
"""
统一 AI 客户端 —— 全平台唯一真正发请求的模块。

提供：
- chat      : 异步非流式 /chat/completions
- chat_stream: 异步流式（保留自动续写语义：MAX_CONTINUATIONS=5 + 「请继续输出」）
- embeddings: 异步 /embeddings
- list_models: 异步 GET /models 模型探测
- chat_sync : 同步版（供守护线程调用方，如 api_testing 的接口用例生成）
- test_connection: 同步连通性探测（tokenizer/embedding -> /embeddings，其余 -> /chat/completions）

每个方法统一走「build_headers/build_url（apps.ai.auth）→ 发请求 → 解析 usage → emit()」，
成功与失败都会落 AiCallRecord。
"""
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Dict, Optional, Any

import httpx
from asgiref.sync import sync_to_async

from .auth import build_headers, build_url
from . import observability

logger = logging.getLogger('apps.ai.client')

# 超时配置（与原 requirement_analysis.AIModelService 一致：连接 60s / 读取 900s）
TIMEOUT = httpx.Timeout(connect=60.0, read=900.0, write=60.0, pool=60.0)

# 流式续写次数上限（与旧实现一致，防止死循环）
MAX_CONTINUATIONS = 5

# provider_extra 中不透传进请求体的保留键（api_version 供 Azure build_url/build_headers 使用）
_PROVIDER_EXTRA_RESERVED = {'api_version'}

# 逐行解析后的 usage 可能出现在最后一个 SSE chunk（部分提供商开启 include_usage 时才有）
_ROLES_EMBEDDING_PROBE = ('tokenizer', 'embedding')


class _OverlapTrimmer:
    """续写轮重叠消除器。

    截断自动续写时，模型常无视"不要重复"指令从中间重发已有内容（逐字节一致）。
    本类缓冲续写轮开头 ANCHOR 字符作锚点，在前文全文中定位模型实际恢复点，
    裁掉重叠部分后放行——callback 与 yield 拿到的都是裁剪后内容。

    - 锚点匹配到 → 进入跳过/放行状态（重叠可能长于已缓冲部分，跨 chunk 跳完）
    - 缓冲 MAX_BUFFER 仍无锚点 → 判定全新内容，整段放行
    - 流结束 flush() 放行残余缓冲，保证不丢内容

    重发内容与已有内容并非逐字节一致时锚点会 miss（漏裁），落库侧的
    dedupe_test_cases 标题级去重仍是最后防线。
    """

    ANCHOR = 30       # 恢复点判定所需的最小匹配长度（{"case_id":" 仅13字符，30可带到用例标识）
    MAX_BUFFER = 150  # 无锚点时最多缓冲这么多字符就按全新内容放行（干净续写的延迟上限）

    def __init__(self, previous_text: str = ''):
        self.emitted = previous_text or ''
        self._buffer = ''
        self._expect_pos = None   # 校验模式：chunk 字符应与 emitted[_expect_pos] 一致
        self._pass_through = False

    def feed(self, chunk: str) -> str:
        """喂入一个 chunk，返回应放行的文本（可能为空串）。"""
        if self._pass_through:
            self.emitted += chunk
            return chunk
        if self._expect_pos is not None:
            return self._feed_verifying(chunk)
        self._buffer += chunk
        if len(self._buffer) < self.ANCHOR:
            return ''
        anchor = self._buffer[:self.ANCHOR]
        p = self.emitted.rfind(anchor)
        if p >= 0:
            # 校验式跳过：锚点起逐字符比对前文，分叉立即转为放行
            # （模型可能只重发到前文中途就分叉，重叠长度不可信，逐字符校验才安全）
            self._expect_pos = p + self.ANCHOR
            rest = self._buffer[self.ANCHOR:]
            self._buffer = ''
            return self._feed_verifying(rest) if rest else ''
        if len(self._buffer) >= self.MAX_BUFFER:
            emit = self._buffer
            self.emitted += emit
            self._buffer = ''
            self._pass_through = True
            return emit
        return ''

    def _feed_verifying(self, text: str) -> str:
        """校验模式：与 emitted[_expect_pos] 逐字符比对，一致则吞掉（属重叠），
        首个不一致处（或越过前文末尾）起全部放行。"""
        out = []
        i = 0
        while i < len(text):
            if self._expect_pos < len(self.emitted) and text[i] == self.emitted[self._expect_pos]:
                self._expect_pos += 1
                i += 1
                continue
            rest = text[i:]
            self.emitted += rest
            out.append(rest)
            self._pass_through = True
            self._expect_pos = None
            break
        return ''.join(out)

    def flush(self) -> str:
        """流结束时放行残余缓冲（本轮内容短于锚点/上限且未匹配到锚点）。"""
        if self._pass_through or not self._buffer:
            return ''
        emit = self._buffer
        self.emitted += emit
        self._buffer = ''
        return emit


class AIClient:
    """统一 AI 模型客户端。"""

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    @staticmethod
    def _provider_display(config) -> str:
        """提供商展示名（容错：SimpleNamespace 无 get_model_type_display 时回退）。"""
        try:
            display = config.get_model_type_display()
            if display:
                return display
        except Exception:
            pass
        from .providers import provider_display_name
        return provider_display_name(getattr(config, 'model_type', '') or 'other')

    @staticmethod
    def _api_version(config) -> Optional[str]:
        """"从 provider_extra 读取 Azure api-version（Phase B 前该字段可能不存在）。"""
        try:
            extra = getattr(config, 'provider_extra', None) or {}
            if isinstance(extra, dict):
                return extra.get('api_version') or None
        except Exception:
            pass
        return None

    @staticmethod
    def _request_parts(config, messages, max_tokens, stream):
        """构建 (provider, provider_name, url, headers, data) 五元组。"""
        provider = getattr(config, 'model_type', 'other') or 'other'
        api_key = getattr(config, 'api_key', None)
        api_version = AIClient._api_version(config)
        actual_max_tokens = max_tokens if max_tokens is not None else getattr(config, 'max_tokens', 4096)

        data = {
            'model': getattr(config, 'model_name', ''),
            'messages': messages,
            'temperature': getattr(config, 'temperature', 0.7),
            'top_p': getattr(config, 'top_p', 0.9),
            'stream': stream,
        }
        # max_tokens 为空/0 表示不限制：不传该字段，由服务端按模型输出上限
        if actual_max_tokens:
            data['max_tokens'] = actual_max_tokens
        # provider_extra 其余键透传进请求体（如 SGLang/GLM 的 chat_template_kwargs、
        # 深度思考开关等提供商私有参数），保留键除外
        extra = getattr(config, 'provider_extra', None) or {}
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in _PROVIDER_EXTRA_RESERVED:
                    data[k] = v
        return (
            provider,
            AIClient._provider_display(config),
            build_url(getattr(config, 'base_url', ''), '/chat/completions', provider, api_version),
            build_headers(provider, api_key, api_version),
            data,
        )

    @staticmethod
    def _emit(config, provider, model_name, role, scenario, status, latency_ms,
              prompt_tokens=None, completion_tokens=None, error_message=''):
        observability.emit(
            provider=provider,
            model_name=model_name,
            role=role,
            status=status,
            latency_ms=latency_ms,
            scenario=scenario,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error_message=error_message,
            config_id=getattr(config, 'id', None),
        )

    @staticmethod
    def _parse_usage(result) -> (Optional[int], Optional[int]):
        usage = (result or {}).get('usage') or {}
        prompt_tokens = usage.get('prompt_tokens') if isinstance(usage, dict) else None
        completion_tokens = usage.get('completion_tokens') if isinstance(usage, dict) else None
        return prompt_tokens, completion_tokens

    # ------------------------------------------------------------------
    # 异步：chat（非流式）
    # ------------------------------------------------------------------
    @staticmethod
    async def chat(config, messages, max_tokens: int = None,
                   scenario: Optional[str] = None, retries: int = 0) -> Dict[str, Any]:
        """调用 OpenAI 兼容 /chat/completions（非流式）。"""
        provider, provider_name, url, headers, data = AIClient._request_parts(
            config, messages, max_tokens, stream=False)
        role = getattr(config, 'role', '')
        model_name = getattr(config, 'model_name', '')
        start = time.monotonic()

        async def _done(status, **kw):
            # 异步上下文内写库需经 sync_to_async（thread_sensitive 默认主线程、同事务可见）
            await sync_to_async(AIClient._emit)(
                config, provider, model_name, role,
                scenario or observability.get_scenario() or 'general',
                status, round((time.monotonic() - start) * 1000), **kw)

        try:
            logger.info(f"=== API调用详情 === url={url}, model={model_name}, "
                        f"max_tokens={data.get('max_tokens', '不限')}, temperature={data['temperature']}, top_p={data['top_p']}")
            async with httpx.AsyncClient(timeout=TIMEOUT, http2=False) as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    logger.error(f"API调用返回错误: Status={response.status_code}, Body={response.text}")
                response.raise_for_status()
                result = response.json()
            prompt_tokens, completion_tokens = AIClient._parse_usage(result)
            await _done('success', prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            return result
        except httpx.HTTPStatusError as e:
            error_msg = f"{provider_name} API返回错误 {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            await _done('failed', error_message=str(e.response.status_code))
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            logger.error(f"{provider_name} API请求超时: {repr(e)}")
            await _done('failed', error_message='timeout')
            raise Exception(f"{provider_name} API请求超时，请稍后再试或检查网络连接")
        except Exception as e:
            logger.error(f"{provider_name} API调用失败: {repr(e)}")
            await _done('failed', error_message=str(e) or repr(e))
            raise Exception(f"{provider_name} API调用失败: {str(e) or repr(e)}")

    # ------------------------------------------------------------------
    # 异步：chat_stream（流式 + 自动续写，语义与旧实现逐字一致）
    # ------------------------------------------------------------------
    @staticmethod
    async def chat_stream(config, messages, callback=None,
                          max_tokens: int = None,
                          scenario: Optional[str] = None) -> AsyncIterator[str]:
        """流式调用 /chat/completions，支持截断自动续写（最多 MAX_CONTINUATIONS 次）。"""
        provider = getattr(config, 'model_type', 'other') or 'other'
        provider_name = AIClient._provider_display(config)
        model_name = getattr(config, 'model_name', '')
        role = getattr(config, 'role', '')
        actual_max_tokens = max_tokens if max_tokens is not None else getattr(config, 'max_tokens', 4096)

        current_messages = list(messages)  # 浅拷贝
        emitted_text = ''  # 跨续写轮累计已放行的可见内容（供重叠裁剪定位恢复点）
        continuation_count = 0
        final_prompt_tokens = None
        final_completion_tokens = None
        start = time.monotonic()

        while continuation_count <= MAX_CONTINUATIONS:
            # 请求体统一走 _request_parts（含 provider_extra 透传）；messages 每轮随续写变化
            _, _, url, headers, data = AIClient._request_parts(
                config, current_messages, actual_max_tokens, stream=True)

            logger.info(f"发起流式请求 (第{continuation_count + 1}次), messages数量: {len(current_messages)}")
            chunk_content_buffer = ""
            round_content_chars = 0   # 本轮可见输出字符数
            round_reasoning_chars = 0  # 本轮思考(delta.reasoning/reasoning_content)字符数
            finish_reason = None
            # 续写轮启用重叠裁剪：模型常无视"不要重复"指令重发已有内容，
            # callback/yield 只放行裁剪后内容（首轮无前文，直接放行）
            trimmer = _OverlapTrimmer(emitted_text) if continuation_count > 0 else None

            try:
                async with httpx.AsyncClient(timeout=TIMEOUT, http2=False) as client:
                    async with client.stream('POST', url, headers=headers, json=data) as response:
                        if response.status_code != 200:
                            error_detail = await response.aread()
                            error_msg = error_detail.decode('utf-8')
                            logger.error(f"流式API调用返回错误: Status={response.status_code}, Body={error_msg}")
                            response.raise_for_status()

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            if line.startswith('data: '):
                                data_str = line[6:]
                                if data_str.strip() == '[DONE]':
                                    break
                                try:
                                    chunk_data = json.loads(data_str)
                                    if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                        choice = chunk_data['choices'][0]
                                        delta = choice.get('delta', {})
                                        finish_reason = choice.get('finish_reason', None)
                                        # 思考内容（GLM/SGLang 用 delta.reasoning，部分用
                                        # reasoning_content）：属于推理过程，不计入可见输出
                                        reasoning = (delta.get('reasoning')
                                                     or delta.get('reasoning_content') or '')
                                        if reasoning:
                                            round_reasoning_chars += len(reasoning)
                                        content = delta.get('content', '')

                                        if content:
                                            chunk_content_buffer += content
                                            round_content_chars += len(content)
                                            emit = trimmer.feed(content) if trimmer else content
                                            if emit:
                                                if callback:
                                                    await callback(emit)
                                                yield emit

                                        if finish_reason:
                                            pass  # 末尾统一处理
                                    # 部分提供商在流式末端返回 usage
                                    usage = chunk_data.get('usage')
                                    if isinstance(usage, dict):
                                        if usage.get('prompt_tokens'):
                                            final_prompt_tokens = usage['prompt_tokens']
                                        if usage.get('completion_tokens'):
                                            final_completion_tokens = usage['completion_tokens']
                                except json.JSONDecodeError:
                                    continue

                # 本轮流结束：放行裁剪器残余缓冲，维护跨轮已放行全文
                if trimmer:
                    tail = trimmer.flush()
                    if tail:
                        if callback:
                            await callback(tail)
                        yield tail
                    emitted_text = trimmer.emitted
                else:
                    emitted_text += chunk_content_buffer

                # 本次请求结束：检查 finish_reason
                if finish_reason == 'length':
                    if round_content_chars == 0:
                        # max_tokens 预算被思考(reasoning)全部吃掉、零可见输出：
                        # 续写只会重新思考再耗光预算（实测 GLM-5.3-flash 连续 6 次全零），
                        # 直接报错并给出处置指引，而不是盲目续写 MAX_CONTINUATIONS 次。
                        logger.error(
                            f"流式生成被截断且零可见输出: reasoning_chars={round_reasoning_chars}, "
                            f"max_tokens={actual_max_tokens}, model={model_name}")
                        raise Exception(
                            f"{provider_name} 流式生成耗尽 token 预算但没有任何可见输出"
                            f"（思考消耗 {round_reasoning_chars} 字符，"
                            f"max_tokens={'不限' if not actual_max_tokens else actual_max_tokens}）。"
                            f"请在模型配置的「提供商扩展参数」中关闭思考，"
                            f'例如 {{"chat_template_kwargs": {{"enable_thinking": false}}}}，'
                            f"或调整 max_tokens 后重试。")
                    logger.warning(
                        f"检测到生成被截断 (finish_reason='length')，准备自动续写。当前已续写 {continuation_count} 次。")
                    continuation_count += 1

                    # 将本次生成的内容作为 assistant 回复加入历史
                    if current_messages[-1]['role'] == 'assistant':
                        current_messages[-1]['content'] += chunk_content_buffer
                    else:
                        current_messages.append({"role": "assistant", "content": chunk_content_buffer})

                    # 防多次续写堆叠重复的 user 指令
                    if current_messages[-1]['role'] != 'user':
                        current_messages.append(
                            {"role": "user", "content": "请继续输出剩余的内容，不要重复已输出的部分，紧接着上文继续。"})
                    continue
                else:
                    logger.info(f"流式生成正常结束 (finish_reason={finish_reason})")
                    break
            except Exception as e:
                logger.error(f"流式请求异常: {e}")
                if final_prompt_tokens is None and final_completion_tokens is None:
                    await sync_to_async(AIClient._emit)(
                        config, provider, model_name, role,
                        scenario or observability.get_scenario() or 'general',
                        'failed', round((time.monotonic() - start) * 1000),
                        error_message=str(e) or repr(e))
                raise e

        await sync_to_async(AIClient._emit)(
            config, provider, model_name, role,
            scenario or observability.get_scenario() or 'general',
            'success', round((time.monotonic() - start) * 1000),
            prompt_tokens=final_prompt_tokens, completion_tokens=final_completion_tokens)

    # ------------------------------------------------------------------
    # 异步：embeddings
    # ------------------------------------------------------------------
    @staticmethod
    async def embeddings(config, texts, scenario: Optional[str] = None):
        """调用 OpenAI 兼容 /embeddings 生成向量。"""
        provider = getattr(config, 'model_type', 'other') or 'other'
        provider_name = AIClient._provider_display(config)
        model_name = getattr(config, 'model_name', '')
        role = getattr(config, 'role', '')
        api_key = getattr(config, 'api_key', None)
        api_version = AIClient._api_version(config)
        url = build_url(getattr(config, 'base_url', ''), '/embeddings', provider, api_version)
        headers = build_headers(provider, api_key, api_version)
        data = {'model': model_name, 'input': texts}
        start = time.monotonic()

        async def _done(status, **kw):
            await sync_to_async(AIClient._emit)(
                config, provider, model_name, role,
                scenario or observability.get_scenario() or 'general',
                status, round((time.monotonic() - start) * 1000), **kw)

        try:
            logger.info(f"调用 embedding API: {url}, 模型: {model_name}, 文本数: {len(texts)}")
            async with httpx.AsyncClient(timeout=TIMEOUT, http2=False) as client:
                response = await client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"Embedding API 返回错误: Status={response.status_code}, Body={error_detail}")
                    response.raise_for_status()
                result = response.json()
            embeddings = [item['embedding'] for item in result.get('data', [])]
            prompt_tokens, completion_tokens = AIClient._parse_usage(result)
            await _done('success', prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            return embeddings
        except httpx.HTTPStatusError as e:
            error_msg = f"{provider_name} Embedding API 返回错误 {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            await _done('failed', error_message=str(e.response.status_code))
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            logger.error(f"{provider_name} Embedding API 请求超时: {repr(e)}")
            await _done('failed', error_message='timeout')
            raise Exception(f"{provider_name} Embedding API 请求超时")
        except Exception as e:
            logger.error(f"{provider_name} Embedding API 调用失败: {repr(e)}")
            await _done('failed', error_message=str(e) or repr(e))
            raise Exception(f"{provider_name} Embedding API 调用失败: {str(e) or repr(e)}")

    # ------------------------------------------------------------------
    # 异步：list_models
    # ------------------------------------------------------------------
    @staticmethod
    async def list_models(config, scenario: Optional[str] = None):
        """获取当前配置下可用的模型列表。"""
        provider = getattr(config, 'model_type', 'other') or 'other'
        provider_name = AIClient._provider_display(config)
        model_name = getattr(config, 'model_name', '')
        role = getattr(config, 'role', '')
        api_key = getattr(config, 'api_key', None)
        api_version = AIClient._api_version(config)
        url = build_url(getattr(config, 'base_url', ''), '/models', provider, api_version)
        headers = build_headers(provider, api_key, api_version)
        start = time.monotonic()

        async def _done(status, **kw):
            await sync_to_async(AIClient._emit)(
                config, provider, model_name, role,
                scenario or observability.get_scenario() or 'general',
                status, round((time.monotonic() - start) * 1000), **kw)

        try:
            logger.info(f"获取模型列表，URL: {url}")
            async with httpx.AsyncClient(timeout=TIMEOUT, http2=False) as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"获取模型列表失败: Status={response.status_code}, Body={error_detail}")
                response.raise_for_status()
                payload = response.json()
            raw_models = payload.get('data', []) if isinstance(payload, dict) else payload
            model_ids = []
            for item in raw_models or []:
                if isinstance(item, dict):
                    model_id = item.get('id') or item.get('model') or item.get('name')
                    if model_id:
                        model_ids.append(str(model_id))
                elif isinstance(item, str):
                    model_ids.append(item)
            unique_model_ids = list(dict.fromkeys(model_ids))
            logger.info(f"获取模型列表成功，共{len(unique_model_ids)}个模型")
            await _done('success')
            return unique_model_ids
        except httpx.HTTPStatusError as e:
            error_msg = f"{provider_name} 获取模型列表失败 {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            await _done('failed', error_message=str(e.response.status_code))
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            logger.error(f"{provider_name} 获取模型列表超时: {repr(e)}")
            await _done('failed', error_message='timeout')
            raise Exception(f"{provider_name} 获取模型列表超时，请检查网络连接或API地址是否正确")
        except Exception as e:
            logger.error(f"{provider_name} 获取模型列表失败: {repr(e)}")
            await _done('failed', error_message=str(e) or repr(e))
            raise Exception(f"{provider_name} 获取模型列表失败: {str(e) or repr(e)}")

    # ------------------------------------------------------------------
    # 同步：chat_sync（守护线程内调用，避免事件循环纠缠）
    # ------------------------------------------------------------------
    @staticmethod
    def chat_sync(config, messages, max_tokens: int = None,
                  scenario: Optional[str] = None) -> Dict[str, Any]:
        """同步版非流式 chat，供 daemon 线程调用方（如 api_testing 接口用例生成）。"""
        provider, provider_name, url, headers, data = AIClient._request_parts(
            config, messages, max_tokens, stream=False)
        role = getattr(config, 'role', '')
        model_name = getattr(config, 'model_name', '')
        start = time.monotonic()

        def _done(status, **kw):
            AIClient._emit(config, provider, model_name, role,
                           scenario or observability.get_scenario() or 'general',
                           status, round((time.monotonic() - start) * 1000), **kw)

        try:
            with httpx.Client(timeout=TIMEOUT, http2=False) as client:
                response = client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    logger.error(f"API调用返回错误: Status={response.status_code}, Body={response.text}")
                response.raise_for_status()
                result = response.json()
            prompt_tokens, completion_tokens = AIClient._parse_usage(result)
            _done('success', prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
            return result
        except httpx.HTTPStatusError as e:
            error_msg = f"{provider_name} API返回错误 {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            _done('failed', error_message=str(e.response.status_code))
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            logger.error(f"{provider_name} API请求超时: {repr(e)}")
            _done('failed', error_message='timeout')
            raise Exception(f"{provider_name} API请求超时，请稍后再试或检查网络连接")
        except Exception as e:
            logger.error(f"{provider_name} API调用失败: {repr(e)}")
            _done('failed', error_message=str(e) or repr(e))
            raise Exception(f"{provider_name} API调用失败: {str(e) or repr(e)}")

    # ------------------------------------------------------------------
    # 同步：test_connection（连通性探测）
    # ------------------------------------------------------------------
    @staticmethod
    def test_connection(config, timeout: int = 30) -> Dict[str, Any]:
        """探测配置连通性。tokenizer/embedding 角色走 /embeddings，其余走 /chat/completions。"""
        provider = getattr(config, 'model_type', 'other') or 'other'
        provider_name = AIClient._provider_display(config)
        model_name = getattr(config, 'model_name', '')
        role = getattr(config, 'role', '')
        api_key = getattr(config, 'api_key', None)
        api_version = AIClient._api_version(config)
        base_url = getattr(config, 'base_url', '')

        try:
            if role in _ROLES_EMBEDDING_PROBE:
                url = build_url(base_url, '/embeddings', provider, api_version)
                headers = build_headers(provider, api_key, api_version)
                data = {'model': model_name, 'input': ['connectivity-probe']}
            else:
                url = build_url(base_url, '/chat/completions', provider, api_version)
                headers = build_headers(provider, api_key, api_version)
                data = {
                    'model': model_name,
                    'messages': [{'role': 'user', 'content': 'Reply with OK.'}],
                    'max_tokens': 16,
                    'temperature': 0,
                    'stream': False,
                }

            start = time.monotonic()
            # httpx>=0.28 的 Timeout 不再接受 (connect, read, write, pool) 四个位置参数,须用关键字形式
            with httpx.Client(timeout=httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout),
                              http2=False) as client:
                response = client.post(url, headers=headers, json=data)
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"连接测试失败: Status={response.status_code}, Body={error_detail[:500]}")
                response.raise_for_status()
                result = response.json()
            AIClient._emit(config, provider, model_name, role, 'test_connection', 'success',
                           round((time.monotonic() - start) * 1000))
            return {'success': True, 'message': '连接成功', 'response': result}
        except Exception as e:
            error_msg = f"{provider_name} 连接失败: {str(e) or repr(e)}"
            logger.error(error_msg)
            if getattr(config, 'id', None) is not None:
                AIClient._emit(config, provider, model_name, role, 'test_connection', 'failed',
                               round((time.monotonic() - start) * 1000) if 'start' in locals() else None,
                               error_message=error_msg[:500])
            return {'success': False, 'message': error_msg}
