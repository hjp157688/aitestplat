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
    """启动执行会话线程（执行编排见 run_session）。"""
    thread = threading.Thread(target=_run_session_safe, args=(session_id,), daemon=True)
    thread.start()


def start_execution_tasks(case_ids, environment_id, user_id):
    """为一批用例创建会话与执行记录并启动线程，返回 session_id。"""
    environment = AutomationEnvironment.objects.get(pk=environment_id)
    session = AutomationExecutionSession.objects.create(
        project=environment.project, environment=environment, triggered_by_id=user_id)
    cases = AutomationCase.objects.filter(pk__in=case_ids).order_by('id')
    for case in cases:
        AutomationExecution.objects.create(
            case=case, session=session, environment=environment, triggered_by_id=user_id)
    start_session(session.pk)
    return session.pk


def _run_session_safe(session_id):
    try:
        # 守护线程入口先清理陈旧连接；不放 run_session，避免测试事务内被误关
        close_old_connections()
        run_session(session_id)
    except Exception as exc:
        logger.exception('automation session %s crashed', session_id)
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            status='failed', error=str(exc), finished_at=timezone.now())


def run_session(session_id):
    """会话主流程：可选登录一次 -> 逐条串行执行 -> 收尾。"""
    session = (AutomationExecutionSession.objects
               .select_related('environment')
               .prefetch_related('executions__case')
               .get(pk=session_id))
    environment = session.environment
    AutomationExecutionSession.objects.filter(pk=session_id).update(
        status='logging_in', started_at=timezone.now())

    storage_state = None
    if environment.login_url:
        ok, log, state = run_browser_task(
            automation_services.build_login_task_description(environment),
            case_name=f'登录-{environment.name}',
        )
        if not ok:
            AutomationExecutionSession.objects.filter(pk=session_id).update(
                status='failed', login_status='failed',
                error=f'登录失败：{log}'[:2000], finished_at=timezone.now())
            AutomationExecution.objects.filter(session_id=session_id).update(
                status='failed', error='会话登录失败，未执行', finished_at=timezone.now())
            return
        storage_state = state
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            login_status='success', storage_state=state)
    else:
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            login_status='not_required')

    AutomationExecutionSession.objects.filter(pk=session_id).update(status='running')
    for execution in session.executions.order_by('id'):
        _run_single_execution(execution, environment, storage_state)
    AutomationExecutionSession.objects.filter(pk=session_id).update(
        status='done', finished_at=timezone.now())


def _run_single_execution(execution, environment, storage_state):
    AutomationExecution.objects.filter(pk=execution.pk).update(
        status='running', started_at=timezone.now())
    case = execution.case
    task_description = automation_services.build_case_task_description(case, environment)
    try:
        ok, log, _state = run_browser_task(
            task_description, case_name=case.title, storage_state=storage_state)
    except Exception as exc:
        AutomationExecution.objects.filter(pk=execution.pk).update(
            status='failed', error=str(exc)[:2000], finished_at=timezone.now())
        return
    AutomationExecution.objects.filter(pk=execution.pk).update(
        status='success' if ok else 'failed',
        log=(log or '')[:20000],
        finished_at=timezone.now())


def run_browser_task(task_description, case_name, storage_state=None):
    """同步执行一段 browser-use 任务。

    返回 (是否成功, 日志文本, storage_state)。storage_state 仅在任务成功后尝试导出。
    """
    from apps.ui_automation.ai_agent import BrowserAgent

    agent = BrowserAgent(case_name=case_name, storage_state=storage_state)
    log_lines = []

    def callback(payload):
        if isinstance(payload, dict):
            # ai_base.py emit_callback 的日志载荷键是 content（兼容 message/description）
            message = (payload.get('message') or payload.get('content')
                       or payload.get('description') or '')
        else:
            message = str(payload)
        if message:
            log_lines.append(str(message))

    try:
        result = asyncio.run(agent.run_task(task_description, callback=callback))
    except Exception as exc:
        return False, '\n'.join(log_lines + [f'执行异常: {exc}']), None
    state = asyncio.run(agent.export_storage_state())
    # run_task 返回 browser-use 的 AgentHistoryList：is_successful() / is_done() 是方法，
    # is_successful() 在未完成时返回 None，此时按 is_done() 判定（未完成视为失败）
    is_success = None
    is_successful = getattr(result, 'is_successful', None)
    if callable(is_successful):
        is_success = is_successful()
    if is_success is None:
        is_done = getattr(result, 'is_done', None)
        is_success = is_done() if callable(is_done) else bool(is_done)
    return bool(is_success), '\n'.join(log_lines), state
