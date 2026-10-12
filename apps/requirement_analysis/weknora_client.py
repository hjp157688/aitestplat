# -*- coding: utf-8 -*-
"""WeKnora 外部知识库客户端 (httpx, sync)

封装 WeKnora REST API(/api/v1)。WeKnora 自带文档解析/分块/向量库/rerank/智能体，
本模块只做 HTTP 调用,不实现任何知识库逻辑。失败统一抛 WeKnoraError。

核心方法:
- list_agents()          GET /agents                    拉取智能体列表(配置中心下拉)
- create_session()       POST /sessions                 创建会话(纯容器)
- agent_answer(...)      POST /agent-chat/{sid} (SSE)   取"基于知识库的智能体回答"注入生成
- knowledge_search(...)  POST /knowledge-search         低层分块检索(配置中心测试/预览用)
- test_connection(...)   探活 + 可选拉智能体列表校验 key

鉴权头: X-API-Key
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

API_BASE = '/api/v1'
DEFAULT_BASE_URL = 'http://localhost:8080'


class WeKnoraError(Exception):
    """WeKnora API 错误"""

    def __init__(self, code, message):
        self.code = code
        super().__init__(f'WeKnora error {code}: {message}')


class WeKnoraClient:
    """WeKnora REST 客户端(sync);全平台唯一调用入口"""

    def __init__(self, base_url=None, api_key='', timeout=30):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')
        self.api_key = api_key or ''
        self.timeout = timeout or 30

    def _http_timeout(self):
        """connect 独立设短超时。

        WeKnora 服务不可达（丢包不拒连）时，TCP 连接要等 OS 级 ~75s 才报
        ETIMEDOUT，生成流程会卡死在知识注入阶段；connect 限 5s 快速失败降级，
        read 沿用配置的完整超时（agent 检索+回答可能较慢）。
        """
        return httpx.Timeout(self.timeout, connect=min(5.0, self.timeout))

    # ---------- 内部 ----------
    def _headers(self):
        return {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
        }

    def _request(self, method, path, *, params=None, json=None):
        url = f'{self.base_url}{API_BASE}{path}'
        with httpx.Client(timeout=self._http_timeout()) as client:
            resp = client.request(method, url, params=params, json=json, headers=self._headers())
        body = None
        try:
            body = resp.json()
        except Exception:
            pass
        if not (200 <= resp.status_code < 300) or not isinstance(body, dict) or body.get('success') is False:
            raise self._error(resp.status_code, body)
        return body.get('data')

    @staticmethod
    def _read_error_content(body):
        if isinstance(body, dict):
            err = body.get('error')
            if isinstance(err, dict):
                return err.get('message') or err.get('code') or ''
            return err or ''
        return body or ''

    @classmethod
    def _error(cls, status, body):
        message = cls._read_error_content(body)
        code = status
        if isinstance(body, dict) and isinstance(body.get('error'), dict):
            code = body['error'].get('code') or status
        return WeKnoraError(code, message or f'HTTP {status}')

    # ---------- 智能体 / 会话 ----------
    def list_agents(self):
        """返回智能体列表 [{id, name, description, config, is_builtin, avatar}]"""
        data = self._request('GET', '/agents')
        return data or []

    def create_session(self, title=''):
        """创建会话容器,返回 session_id"""
        data = self._request('POST', '/sessions', json={'title': title or ''})
        sid = (data or {}).get('id') or (data or {}).get('session_id')
        if not sid:
            raise WeKnoraError(-1, 'create_session: 响应缺少 session id')
        return sid

    def agent_answer(self, query, agent_id, knowledge_base_ids=None):
        """基于智能体(其绑定知识库)回答问题。

        Returns:
            dict: {
                'answer':      最终回答文本,
                'references':  [引用列表]（来自 SSE references 事件）,
                'steps':       [思考/检索过程事件]（thinking/tool_call/tool_result/error，
                               用于前端"思考过程 vs 结果"分开展示，风格对齐 WeKnora）
            }
            references 每项: {id, title, filename, chunk_index, score}
        """
        session_id = self.create_session(title='aitestplat-tcgen')
        url = f'{self.base_url}{API_BASE}/agent-chat/{session_id}'
        payload = {'query': query, 'agent_enabled': True, 'agent_id': agent_id}
        if knowledge_base_ids:
            payload['knowledge_base_ids'] = list(knowledge_base_ids)

        events = []
        try:
            with httpx.Client(timeout=self._http_timeout()) as client:
                with client.stream('POST', url, json=payload, headers=self._headers()) as resp:
                    if resp.status_code != 200:
                        # 非流式错误体：FatalError 常见于 key/空间/agent 校验失败
                        text = (resp.read() or b'').decode('utf-8', 'ignore')
                        raise self._error(resp.status_code, self._safe_json(text))
                    for raw in resp.iter_lines():
                        line = (raw or '').strip()
                        if not line.startswith('data:'):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        try:
                            events.append(json.loads(data))
                        except Exception:
                            continue
        except WeKnoraError:
            raise
        except Exception as e:  # 连接/超时等
            raise WeKnoraError(-1, f'agent_chat failed: {e}')

        answer_parts = []
        refs = []
        steps = []
        seen_refs = set()
        for evt in events:
            if not isinstance(evt, dict):
                continue
            rt = evt.get('response_type')
            if rt == 'answer':
                content = evt.get('content') or ''
                if content:
                    answer_parts.append(content)
            elif rt == 'references':
                for r in evt.get('knowledge_references') or []:
                    rid = r.get('id')
                    if rid in seen_refs:
                        continue
                    seen_refs.add(rid)
                    refs.append({
                        'id': rid,
                        'title': r.get('knowledge_title', ''),
                        'filename': r.get('knowledge_filename', ''),
                        'chunk_index': r.get('chunk_index'),
                        'score': r.get('score'),
                    })
            elif rt in ('agent_query', 'thinking'):
                content = (evt.get('content') or '').strip()
                if content:
                    steps.append({'type': 'thinking', 'content': content})
            elif rt == 'tool_call':
                d = evt.get('data') or {}
                steps.append({
                    'type': 'tool_call',
                    'name': d.get('tool_name') or 'tool',
                    'arguments': d.get('arguments') or '',
                })
            elif rt == 'tool_result':
                content = evt.get('content') or ''
                if content:
                    steps.append({'type': 'tool_result', 'content': content})
            elif rt == 'error':
                steps.append({'type': 'error',
                              'content': evt.get('content') or evt.get('message') or ''})
        answer = ''.join(answer_parts).strip()
        if not answer:
            logger.warning('WeKnora agent_answer 返回空回答 (agent=%s)', agent_id)
        return {'answer': answer, 'references': refs, 'steps': steps}

    # ---------- 低层检索(测试/预览) ----------
    def knowledge_search(self, query, knowledge_base_ids=None):
        """POST /knowledge-search,返回命中的分块列表(不改写、不经 LLM)。

        返回 [{id, content, knowledge_title, knowledge_filename, score, ...}]
        """
        payload = {'query': query}
        if knowledge_base_ids:
            payload['knowledge_base_ids'] = list(knowledge_base_ids)
        data = self._request('POST', '/knowledge-search', json=payload)
        return data or []

    # ---------- 连接测试 ----------
    def test_connection(self, check_agents=False):
        """探活并返回 (ok, message, agents?)。失败返回 (False, 错误信息) 不抛异常。"""
        try:
            status, body = self._probe()
            if status != 200 or not isinstance(body, dict) or body.get('success') is False:
                return False, self._read_error_content(body) or f'HTTP {status}'
            result = {'status': status}
            if check_agents:
                agents = self.list_agents()
                result['agents'] = agents
            return True, result
        except WeKnoraError as e:
            return False, str(e)
        except Exception as e:
            return False, f'连接失败: {e}'

    def _probe(self):
        url = f'{self.base_url}{API_BASE}/agents'
        with httpx.Client(timeout=self._http_timeout()) as client:
            resp = client.get(url, headers=self._headers())
        body = None
        try:
            body = resp.json()
        except Exception:
            pass
        return resp.status_code, body

    @staticmethod
    def _safe_json(text):
        try:
            return json.loads(text)
        except Exception:
            return text


# 模块级实例:由调用方传入连接(WeKnoraConfig.get_solo())
