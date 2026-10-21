"""自动化用例的转化与执行异步任务（daemon 线程模式）。

参照 apps/testcases/ai_tasks.py 的 start_ai_task 模式：视图只创建记录并
启动线程，任务内部自行落状态；测试在 start_* 入口或 _run_browser_task 层 mock。
"""
import asyncio
import logging
import threading

from django.db import close_old_connections
from django.utils import timezone

from apps.ai.client import AIClient
from apps.ai.resolver import ConfigResolver

from . import automation_services
from .models import (
    AutomationCase,
    AutomationEnvironment,
    AutomationExecution,
    AutomationExecutionSession,
)

logger = logging.getLogger(__name__)


def start_conversion_tasks(case_ids):
    """批量启动 AI 转写线程，每个用例一个 daemon 线程。"""
    for case_id in case_ids:
        thread = threading.Thread(target=_run_conversion_safe, args=(case_id,), daemon=True)
        thread.start()


def _run_conversion_safe(case_id):
    try:
        # 守护线程入口先清理陈旧连接；不放 run_conversion，避免测试事务内被误关
        close_old_connections()
        run_conversion(case_id)
    except Exception as exc:
        logger.exception('automation conversion %s crashed', case_id)
        AutomationCase.objects.filter(pk=case_id).update(
            convert_status='failed', convert_error=str(exc))


def run_conversion(case_id):
    """单条自动化用例的 AI 转写：抽取来源 -> 调 AI -> 解析落库。"""
    AutomationCase.objects.filter(pk=case_id).update(convert_status='processing', convert_error='')

    config = ConfigResolver.active(role='writer')
    if config is None:
        AutomationCase.objects.filter(pk=case_id).update(
            convert_status='failed', convert_error='未配置可用的 writer 模型，请在配置中心设置')
        return

    case = (AutomationCase.objects
            .select_related('source_generated_case', 'source_test_case', 'project')
            .get(pk=case_id))
    source_type = case.source_type
    if source_type == 'generated' and case.source_generated_case:
        source_obj = case.source_generated_case
    elif source_type == 'testcase' and case.source_test_case:
        source_obj = case.source_test_case
    else:
        # 内联转化的用例：内容已在前端提交的 steps 草稿里，直接按原文转写
        source_data = {
            'title': case.title,
            'precondition': case.precondition,
            'steps_text': '\n'.join(
                f"{s.get('index')}. {s.get('action', '')}" for s in (case.steps or [])) or '',
            'expected_text': '',
            'priority': '',
        }
        messages = automation_services.build_conversion_messages(source_data)
        _convert_with_ai(case, config, messages)
        return

    source_data = automation_services.extract_source_data(source_type, source_obj)
    environment = (AutomationEnvironment.objects
                   .filter(project=case.project, is_active=True).first())
    variable_keys = [v.get('key') for v in (environment.variables if environment else []) if v.get('key')]
    messages = automation_services.build_conversion_messages(source_data, variable_keys)
    _convert_with_ai(case, config, messages)


def _convert_with_ai(case, config, messages):
    try:
        result = AIClient.chat_sync(config, messages, scenario='automation_case_converter')
        steps = automation_services.parse_conversion_result(
            result['choices'][0]['message']['content'])
    except Exception as exc:
        logger.warning('automation conversion %s failed: %s', case.pk, exc)
        AutomationCase.objects.filter(pk=case.pk).update(
            convert_status='failed', convert_error=str(exc))
        return
    AutomationCase.objects.filter(pk=case.pk).update(
        steps=steps, convert_status='done', convert_error='')


def start_session(session_id):
    """启动执行会话线程（执行编排见 run_session，Task 6 实现）。"""
    raise NotImplementedError('Task 6 实现')


def start_execution_tasks(case_ids, environment_id, user_id):
    """为若干用例创建会话并启动执行（由视图调用；Task 6 实现主体）。"""
    raise NotImplementedError('Task 6 实现')
