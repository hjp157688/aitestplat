# -*- coding: utf-8 -*-
"""用例 AI 修改/补充后台任务 worker。

与禅道同步任务同模式：视图只创建 TestCaseAiTask 并 start_ai_task(task)，
实际工作在本模块的 run_ai_task 中线程内执行，前端通过 ai-task/<task_id>/ 轮询。

AI 调用统一走 apps.ai 网关（ConfigResolver + AIClient.chat_sync，daemon 线程安全）。
提示词类型 testcase_modifier / testcase_supplement 由 seed_prompts 种子化。
"""
from __future__ import annotations

import json
import logging
import uuid

from django.utils import timezone

from apps.ai.client import AIClient
from apps.ai.resolver import ConfigResolver
from apps.ai.prompt_registry import get_prompt_content

from .models import TestCase, TestCaseAiTask, TestCaseVersion
from .services import snapshot_case_version, ensure_baseline_version

logger = logging.getLogger('apps.testcases.ai_tasks')

# AI 优先级(P0-P3) → 用例优先级
PRIORITY_MAP = {'P0': 'critical', 'P1': 'high', 'P2': 'medium', 'P3': 'low'}


def start_ai_task(task):
    """在新线程中启动 AI 任务（与禅道同步任务同模式）。"""
    import threading

    def _run():
        try:
            run_ai_task(task)
        except Exception as e:  # noqa: BLE001
            logger.exception('AI task %s crashed', task.task_id)
            TestCaseAiTask.objects.filter(task_id=task.task_id).update(
                status='failed', error_message=str(e), completed_at=timezone.now(),
            )

    threading.Thread(target=_run, daemon=True).start()


def run_ai_task(task):
    """执行 AI 任务：按 mode 分发，结果/异常落任务状态。"""
    TestCaseAiTask.objects.filter(task_id=task.task_id).update(status='running')
    try:
        if task.mode == 'modify':
            created_ids, summary = _run_modify(task)
        else:
            created_ids, summary = _run_supplement(task)
        TestCaseAiTask.objects.filter(task_id=task.task_id).update(
            status='succeeded', created_cases=created_ids,
            error_message='', completed_at=timezone.now(),
        )
        logger.info('AI task %s succeeded: %s', task.task_id, summary)
    except Exception as e:  # noqa: BLE001
        TestCaseAiTask.objects.filter(task_id=task.task_id).update(
            status='failed', error_message=str(e), completed_at=timezone.now(),
        )


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _load_ai_config():
    """解析 writer 角色活跃配置，未配置时抛出用户可读错误。"""
    config = ConfigResolver.active(role='writer')
    if not config:
        raise Exception('未找到可用的 AI 模型配置（writer 角色），请先在配置中心配置')
    return config


def _call_ai(system_prompt: str, user_message: str, config) -> str:
    """非流式调用 AI（daemon 线程安全），返回原始文本。"""
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_message},
    ]
    result = AIClient.chat_sync(config, messages, scenario='testcase_ai_task')
    return result['choices'][0]['message']['content']


def _extract_json_objects(content: str) -> list[str]:
    """从文本中提取所有已闭合的顶层 JSON 对象。

    字符串感知的花括号深度扫描（与 requirement_analysis.views._extract_json_objects
    同一实现）：跳过字符串内的 {}/转义。思考型模型会在正文输出推理文字、
    JSON 对象可能粘在句子末尾或 pretty-print 多行，行级解析必漏，靠此兜底。
    """
    out = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, c in enumerate(content):
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    out.append(content[start:i + 1].strip())
                    start = -1
    return out


def _parse_case_lines(content: str) -> list[dict]:
    """解析 AI 返回的用例：JSON 数组 / JSONL / 夹在推理文字中的任意对象均可。"""
    content = (content or '').strip()
    if not content:
        return []

    # 优先整体解析（AI 有时返回纯 JSON 数组）
    try:
        whole = json.loads(content)
        if isinstance(whole, list):
            return [obj for obj in whole if isinstance(obj, dict)]
        if isinstance(whole, dict):
            return [whole]
    except (json.JSONDecodeError, ValueError):
        pass

    # 兜底一：花括号深度扫描，提取夹在推理文字里的全部顶层对象
    # （思考型模型会先输出推理过程再给 JSON，且对象可能粘在句子末尾，行级解析必漏）
    cases = []
    for seg in _extract_json_objects(content):
        obj = _load_case_object(seg)
        if obj is not None:
            cases.append(obj)
    if cases:
        return cases

    # 兜底二：json_repair 修复截断/损坏的 JSON（GLM 思考吃掉 max_tokens 时末尾对象不闭合，
    # 扫描器拿不到闭合对象；json_repair 能处理散文环绕 + 截断补全）
    try:
        import json_repair

        repaired = json_repair.loads(content)
    except Exception:  # noqa: BLE001
        return []
    if isinstance(repaired, dict):
        return [repaired] if (repaired.get('title') or repaired.get('编号') is not None) else []
    if isinstance(repaired, list):
        return [obj for obj in repaired if isinstance(obj, dict)]
    return []


def _load_case_object(seg: str):
    """单个 JSON 段：json.loads 失败时用 json_repair 修复（尾逗号/缺引号等轻度损坏）。"""
    try:
        obj = json.loads(seg)
    except (json.JSONDecodeError, ValueError):
        try:
            import json_repair

            obj = json_repair.loads(seg)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(obj, dict) and (obj.get('title') or obj.get('编号') is not None):
        return obj
    return None


def _case_payload(case: TestCase) -> dict:
    """用例 → AI 输入结构（编号=数据库 id，保证回写定位）。"""
    try:
        steps = json.loads(case.steps) if case.steps else []
    except (json.JSONDecodeError, ValueError):
        steps = []
    return {
        '编号': case.id,
        'title': case.title,
        'precondition': case.preconditions,
        'steps': steps,
        'priority': {'low': 'P3', 'medium': 'P2', 'high': 'P1', 'critical': 'P0'}.get(case.priority, 'P2'),
    }


def _apply_ai_case(case: TestCase, item: dict, note: str = '') -> None:
    """把 AI 输出的一条用例写回 TestCase（内容字段），并落 ai_modified 版本。"""
    steps = item.get('steps') or []
    case.title = (item.get('title') or case.title).strip()
    case.preconditions = (item.get('precondition') or '').strip()
    if isinstance(steps, list) and steps:
        case.steps = json.dumps(steps, ensure_ascii=False)
    mapped = PRIORITY_MAP.get((item.get('priority') or '').upper())
    if mapped:
        case.priority = mapped
    case.save()
    snapshot_case_version(case, source='ai_modified', note=note)


def _run_modify(task: TestCaseAiTask):
    cases = list(TestCase.objects.filter(id__in=task.case_ids))
    if not cases:
        raise Exception('目标用例不存在或已被删除')

    config = _load_ai_config()
    system_prompt = get_prompt_content(
        'testcase_modifier',
        default='你是资深测试专家，根据用户意见修改给定测试用例，只输出修改后的用例。',
    )
    user_message = (
        f'## 修改意见\n{task.note}\n\n## 待修改用例（JSON 数组，编号为用例ID）\n'
        + json.dumps([_case_payload(c) for c in cases], ensure_ascii=False, indent=1)
        + '\n\n请按 JSONL 输出修改后的全部用例（每行一个 JSON 对象，字段：编号/title/precondition/steps[{desc,expect}]/priority），编号保持不变，不要输出其他内容。'
    )

    content = _call_ai(system_prompt, user_message, config)
    items = _parse_case_lines(content)
    if not items:
        logger.warning('AI modify task %s 无法解析的原始输出: %.800s', task.task_id, content)
        raise Exception('AI 未返回可解析的用例内容，请重试')

    by_id = {c.id: c for c in cases}
    modified = 0
    for item in items:
        case = by_id.get(item.get('编号'))
        if not case:
            continue
        # 老用例无版本记录时先补录初版（修改前内容），保证 AI 修改前后可对比
        ensure_baseline_version(case, created_by=task.created_by)
        _apply_ai_case(case, item, note=task.note)
        modified += 1
    if modified == 0:
        raise Exception('AI 返回的用例编号均无法匹配目标用例，请重试')
    return [], f'已修改 {modified} 条用例'


def _run_supplement(task: TestCaseAiTask):
    if not task.requirement_id and not task.requirement_text:
        raise Exception('缺少需求上下文，无法补充用例')

    existing = list(
        TestCase.objects.filter(requirement_id=task.requirement_id) if task.requirement_id
        else TestCase.objects.none()
    )
    config = _load_ai_config()
    system_prompt = get_prompt_content(
        'testcase_supplement',
        default='你是资深测试专家，根据需求与已有用例补充缺失的测试用例，只输出新增用例。',
    )
    user_parts = [f'## 需求描述\n{task.requirement_text}']
    if existing:
        user_parts.append(
            '## 已有用例（不要重复，编号为用例ID）\n'
            + json.dumps([_case_payload(c) for c in existing], ensure_ascii=False, indent=1)
        )
    user_parts.append(f'## 补充要求\n{task.note or "补充需求中尚未覆盖的测试场景"}')
    user_parts.append(
        '请输出需要新增的用例，JSONL 格式（每行一个 JSON 对象，字段：编号/title/precondition/steps[{desc,expect}]/priority），编号可留空，不要输出已有用例，不要输出其他内容。'
    )

    content = _call_ai(system_prompt, '\n\n'.join(user_parts), config)
    items = _parse_case_lines(content)
    if not items:
        logger.warning('AI supplement task %s 无法解析的原始输出: %.800s', task.task_id, content)
        raise Exception('AI 未返回可解析的新用例，请重试')

    created_ids = []
    for item in items:
        steps = item.get('steps') or []
        case = TestCase(
            project=task.project,
            requirement=task.requirement,
            author=task.created_by,
            title=(item.get('title') or '').strip() or '未命名补充用例',
            preconditions=(item.get('precondition') or '').strip(),
            steps=json.dumps(steps, ensure_ascii=False) if isinstance(steps, list) else '[]',
            priority=PRIORITY_MAP.get((item.get('priority') or '').upper(), 'medium'),
            test_type='functional',
            status='draft',
            tags=['ai'],
        )
        # 创建信号按这些临时属性落 v1（source=ai_supplemented）
        case._snapshot_source = 'ai_supplemented'
        case._snapshot_note = task.note or ''
        case._snapshot_user = task.created_by
        case.save()
        created_ids.append(case.id)

    if not created_ids:
        raise Exception('补充任务未产生任何新用例')
    return created_ids, f'已补充 {len(created_ids)} 条用例'
