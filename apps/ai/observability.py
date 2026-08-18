# -*- coding: utf-8 -*-
"""
AI 调用可观测发射器。

- set_scenario() : contextvar，高层调用方标记当前场景（如 writer / requirement_parse）
- emit()        : 落一条 AiCallRecord；任何异常都只记 warning，绝不阻断 AI 调用
- estimate_cost(): 按 AiModelPricing 稀疏表估算成本（无行则返回 None）
"""
import contextvars
import logging
from typing import Optional

from .models import AiCallRecord

logger = logging.getLogger('apps.ai.observability')

_scenario: contextvars.ContextVar = contextvars.ContextVar('ai_scenario', default=None)

# 与客户端对齐的默认场景名（供调用方复用）
SCENARIO_WRITER = 'writer'
SCENARIO_REVIEW = 'review'
SCENARIO_REQUIREMENT_PARSE = 'requirement_parse'
SCENARIO_KNOWLEDGE_STRUCTURE = 'knowledge_structure'
SCENARIO_KNOWLEDGE_SECTION = 'knowledge_section'
SCENARIO_KNOWLEDGE_RERANK = 'knowledge_rerank'
SCENARIO_EMBEDDING = 'embedding'
SCENARIO_API_TESTCASE = 'api_testcase_generator'
SCENARIO_BROWSER_USE_TASK = 'browser_use_task'
SCENARIO_BROWSER_USE_BREAKDOWN = 'browser_use_breakdown'
SCENARIO_LIST_MODELS = 'list_models'
SCENARIO_TEST_CONNECTION = 'test_connection'


def set_scenario(scenario: Optional[str] = None):
    """设置当前上下文的 AI 场景（contextvar），返回 reset 签名。"""
    return _scenario.set(scenario)


def reset_scenario(token) -> None:
    """恢复上一场景。"""
    _scenario.reset(token)


def get_scenario() -> Optional[str]:
    return _scenario.get()


def estimate_tokens(text: Optional[str]) -> int:
    """API 未返回 usage 时的估算方式（中文 1 字 ≈ 1 token 的宽松近似）。"""
    if not text:
        return 0
    return max(1, len(str(text)) // 2)


def estimate_cost(provider: str, model_name: str,
                  prompt_tokens: Optional[int], completion_tokens: Optional[int]):
    """按稀疏单价表估算成本（美元）。查不到单价返回 None。"""
    if prompt_tokens is None and completion_tokens is None:
        return None
    try:
        from .models import AiModelPricing
        rows = list(AiModelPricing.objects.filter(provider=provider or ''))
        if not rows:
            return None
        best = None
        # 优先子串匹配：model_keyword 是 model_name 子串
        if model_name:
            for row in rows:
                if row.model_keyword and row.model_keyword in model_name:
                    best = row
                    break
        # 兜底行（model_keyword=''）
        if best is None:
            best = next((r for r in rows if not r.model_keyword), None)
        if best is None:
            return None
        prompt = (prompt_tokens or 0) / 1_000_000 * float(best.input_per_million)
        completion = (completion_tokens or 0) / 1_000_000 * float(best.output_per_million)
        return round(prompt + completion, 6)
    except Exception as e:  # 成本估算失败不影响调用
        logger.warning(f'estimate_cost failed: {e!r}')
        return None


def emit(provider: str = '', model_name: str = '', role: str = '',
         status: str = 'success', latency_ms: Optional[int] = None,
         scenario: Optional[str] = None,
         prompt_tokens: Optional[int] = None,
         completion_tokens: Optional[int] = None,
         cost_estimate: Optional[float] = None,
         error_message: str = '',
         config_id: Optional[int] = None,
         created_by_id: Optional[int] = None) -> None:
    """落一条 AI 调用记录。绝不因观察层异常阻断业务调用。"""
    try:
        if cost_estimate is None and status == 'success':
            cost_estimate = estimate_cost(provider, model_name, prompt_tokens, completion_tokens)
        total = None
        if prompt_tokens or completion_tokens:
            total = (prompt_tokens or 0) + (completion_tokens or 0)
        AiCallRecord.objects.create(
            provider=provider or '',
            model_name=model_name or '',
            role=role or '',
            scenario=(scenario or _scenario.get() or 'general'),
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_estimate=cost_estimate,
            error_message=(error_message or '')[:2000],
            config_id=config_id,
            created_by_id=created_by_id,
        )
    except Exception as e:
        logger.warning(f'emit AiCallRecord failed (non-fatal): {e!r}')


async def emit_async(provider: str = '', model_name: str = '', role: str = '',
                     status: str = 'success', latency_ms: Optional[int] = None,
                     scenario: Optional[str] = None,
                     prompt_tokens: Optional[int] = None,
                     completion_tokens: Optional[int] = None,
                     cost_estimate: Optional[float] = None,
                     error_message: str = '',
                     config_id: Optional[int] = None,
                     created_by_id: Optional[int] = None) -> None:
    """异步上下文内的落库版本（thread_sensitive 默认主线程、保持同一事务）。"""
    from asgiref.sync import sync_to_async
    try:
        await sync_to_async(emit)(
            provider=provider, model_name=model_name, role=role, status=status,
            latency_ms=latency_ms, scenario=scenario,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cost_estimate=cost_estimate, error_message=error_message,
            config_id=config_id, created_by_id=created_by_id,
        )
    except Exception as e:
        logger.warning(f'emit_async failed (non-fatal): {e!r}')
