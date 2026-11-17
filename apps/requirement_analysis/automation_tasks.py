"""自动化用例的转化与执行异步任务（daemon 线程模式）。

参照 apps/testcases/ai_tasks.py 的 start_ai_task 模式：视图只创建记录并
启动线程，任务内部自行落状态；测试在 start_* 入口或 _run_browser_task 层 mock。
"""
import asyncio
import json
import logging
import threading

from django.db import close_old_connections
from django.utils import timezone

from apps.ai.client import AIClient
from apps.ai.prompt_registry import get_prompt_content_raw
from apps.ai.resolver import ConfigResolver

from . import automation_services
from .models import (
    AutomationCase,
    AutomationEnvironment,
    AutomationExecution,
    AutomationExecutionSession,
)

logger = logging.getLogger(__name__)


def _run_with_bounded_teardown(coro, teardown_timeout=3.0):
    """asyncio.run 的替代：收尾阶段对残留任务只做有界等待。

    asyncio.run 退出前会 cancel 所有残留任务并 gather 等到底——第三方库
    （实测 browser-use 依赖 bubus 的 EventBus._run_loop）吞掉 CancelledError
    不退出时，整个执行线程就永久卡死（登录 agent 早已完成、日志全打完，
    会话却停在 logging_in）。改为：主协程完成后取消残留任务最多等
    teardown_timeout 秒，超时直接关闭事件循环，保证本函数必然返回。
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro)
        return result
    finally:
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in pending:
                t.cancel()
            if pending:
                # asyncio.wait 超时返回 (done, pending)，不抛错
                loop.run_until_complete(
                    asyncio.wait(pending, timeout=teardown_timeout))
            loop.run_until_complete(
                asyncio.wait_for(loop.shutdown_asyncgens(), teardown_timeout))
        except Exception:
            pass
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def _mask_password(text, environment):
    """脱敏文本中的环境登录密码（I1）。"""
    password = getattr(environment, 'password', None) if environment else None
    if text and password:
        text = text.replace(password, '******')
    return text


def _kill_local_browser_by_cdp(cdp_endpoint):
    """按调试端口兜底杀掉本机自动化 Chrome。

    browser.kill() 经 bubus 事件总线派发 SaveStorageStateEvent；首个事件循环
    被有界收尾强关后总线队列已 shutdown，kill 会抛 QueueShutDown 杀不掉进程，
    只能按 chrome 启动参数里的调试端口直接杀（仅本地拉起的浏览器）。
    """
    from urllib.parse import urlsplit
    try:
        port = urlsplit(cdp_endpoint or '').port
    except ValueError:
        port = None
    if not port:
        return
    import subprocess
    subprocess.run(['pkill', '-f', f'remote-debugging-port={port}'], check=False)


async def export_state_via_cdp(cdp_endpoint, step_timeout=10.0):
    """直连 chrome 调试端口导出登录态（cookies + localStorage + sessionStorage）。

    playwright 的 storage_state() 只含 cookies 与 localStorage，**不含
    sessionStorage**；而 uap-ui 这类系统把鉴权 token（bearer）存在 sessionStorage
    ——缺了它，注入登录态后用例仍会落登录页被迫重新登录。browser-use watchdog
    的 origins 注入原生支持 sessionStorage（init script 形式），故逐页收集后
    并入对应 origin。连接失败抛异常，由调用方决定如何兜底。

    每个待等待的 CDP 操作都套 asyncio.wait_for：登录刚成功时主页常在跳转/
    渲染中，storage_state / evaluate 可能永远等不到 CDP 响应（线上实测卡死
    整个登录会话），超时抛错让调用方走兜底或跳过该页。
    """
    from urllib.parse import urlsplit

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(cdp_endpoint, timeout=10000)
        try:
            if not browser.contexts:
                return None
            state = await asyncio.wait_for(
                browser.contexts[0].storage_state(), timeout=step_timeout)
            origins = {o.get('origin'): o for o in state.setdefault('origins', [])}
            for page in browser.contexts[0].pages:
                parts = urlsplit(page.url or '')
                if not parts.netloc:
                    continue  # about:blank 等无 origin 页面
                origin = f'{parts.scheme}://{parts.netloc}'
                try:
                    raw = await asyncio.wait_for(
                        page.evaluate(
                            'JSON.stringify(Object.fromEntries('
                            'Object.entries(window.sessionStorage)))'),
                        timeout=step_timeout)
                except Exception:
                    continue  # 页面已销毁/跨域跳转/超时，跳过
                try:
                    items = json.loads(raw) if raw else {}
                except ValueError:
                    items = {}
                if not items:
                    continue
                entry = origins.setdefault(origin, {'origin': origin})
                if len(entry.get('sessionStorage', [])) < len(items):
                    entry['sessionStorage'] = [
                        {'name': k, 'value': v} for k, v in items.items()]
            state['origins'] = list(origins.values())
            return state
        finally:
            await browser.close()  # 仅断开 CDP 连接，不杀浏览器
    finally:
        await pw.stop()


def _summarize_failure(case, environment, log):
    """执行失败后用 AI 总结原因存到用例，下次执行注入任务描述。

    总结失败不影响执行流程本身；密码先脱敏再发给模型，总结结果同样脱敏后落库。
    """
    try:
        config = ConfigResolver.active(role='reviewer')
    except Exception as exc:
        logger.warning('automation failure summary %s: no reviewer config: %s', case.pk, exc)
        return
    if not config:
        return
    step_lines = '\n'.join(
        f"{s.get('index')}. {s.get('action', '')}" for s in (case.steps or []))
    try:
        messages = [
            {'role': 'system',
             'content': get_prompt_content_raw('automation_failure_summary')},
            {'role': 'user', 'content': (
                f'用例标题：{case.title}\n'
                f'用例步骤：\n{step_lines or "无"}\n\n'
                f'执行日志（末尾部分）：\n{_mask_password((log or "")[-3000:], environment)}')},
        ]
        result = AIClient.chat_sync(config, messages, scenario='automation_failure_summary')
        summary = (result['choices'][0]['message']['content'] or '').strip()
        summary = _mask_password(summary, environment)
        if summary:
            AutomationCase.objects.filter(pk=case.pk).update(
                last_failure_summary=summary[:2000])
    except Exception as exc:
        logger.warning('automation failure summary %s failed: %s', case.pk, exc)


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
        # 内联转化的用例：steps 草稿由视图落在 steps 字段（{index, action, verify}），
        # 直接按原文转写；预期作为 verify 行并入步骤文本，环境变量与 source_obj 路径一致
        lines = []
        for s in (case.steps or []):
            line = f"{s.get('index')}. {s.get('action', '')}"
            if s.get('verify'):
                line += f"\n   预期结果：{s.get('verify')}"
            lines.append(line)
        source_data = {
            'title': case.title,
            'precondition': case.precondition,
            'steps_text': '\n'.join(lines),
            'expected_text': '',
            'priority': '',
        }
        environment = (AutomationEnvironment.objects
                       .filter(project=case.project, is_active=True).first())
        variable_keys = [v.get('key') for v in (environment.variables if environment else []) if v.get('key')]
        messages = automation_services.build_conversion_messages(source_data, variable_keys)
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
    login_browser = None
    login_cdp = getattr(environment, 'cdp_url', None) or None
    if environment.login_url:
        ok, log, state, detail = run_browser_task(
            automation_services.build_login_task_description(environment),
            case_name=f'登录-{environment.name}',
            keep_alive=True,
            cdp_url=getattr(environment, 'cdp_url', None),
            enable_screenshot=getattr(environment, 'enable_screenshot', True),
            close_browser=False,
        )
        if not ok:
            AutomationExecutionSession.objects.filter(pk=session_id).update(
                status='failed', login_status='failed',
                error=f'登录失败：{_mask_password(log, environment)}'[:2000],
                finished_at=timezone.now())
            AutomationExecution.objects.filter(session_id=session_id).update(
                status='failed', error='会话登录失败，未执行', finished_at=timezone.now())
            return
        login_cdp = detail.get('cdp_url') or login_cdp
        # uap-ui 类系统把鉴权 token 存 sessionStorage 且与服务端会话绑定，
        # storage_state 注入无法还原（已实测）；复用仍存活的登录浏览器
        # （CDP attach）才能带走全部会话状态。远端浏览器（环境配了 cdp_url）
        # 是用户自己的 Chrome，绝不能在会话收尾时 kill。
        login_browser = detail.get('browser_session') if not environment.cdp_url else None
        if state is None and not login_cdp:
            # 护栏：既没有可复用的共享浏览器，登录态也导不出（跨事件循环失效/
            # 会话已关），视为登录失败，整批不执行——不允许静默降级裸跑
            AutomationExecutionSession.objects.filter(pk=session_id).update(
                status='failed', login_status='failed',
                error='登录态导出失败，请检查浏览器环境'[:2000],
                finished_at=timezone.now())
            AutomationExecution.objects.filter(session_id=session_id).update(
                status='failed', error='会话登录失败，未执行', finished_at=timezone.now())
            return
        storage_state = state
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            login_status='success', storage_state=state)
    else:
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            login_status='not_required')

    try:
        AutomationExecutionSession.objects.filter(pk=session_id).update(status='running')
        for execution in session.executions.order_by('id'):
            # 共享登录浏览器时 storage_state 无意义（状态就在浏览器里），不传
            _run_single_execution(
                execution, environment,
                storage_state=None if login_cdp else storage_state,
                cdp_url=login_cdp)
        AutomationExecutionSession.objects.filter(pk=session_id).update(
            status='done', finished_at=timezone.now())
    finally:
        # 会话收尾杀掉本地登录浏览器；远端浏览器（用户 Chrome）不在清理范围。
        # kill 同样走有界收尾：browser-use 内部任务吞取消时不允许卡死收尾线程。
        # kill 经 bubus 总线派发事件，循环强关后队列已 shutdown 会抛
        # QueueShutDown 杀不掉进程，须按调试端口兜底杀
        if login_browser is not None:
            try:
                _run_with_bounded_teardown(login_browser.kill())
            except Exception as exc:
                logger.warning('automation session %s: kill login browser failed (%s), '
                               'fallback to process kill', session_id, exc)
                _kill_local_browser_by_cdp(login_cdp or environment.cdp_url)


def _run_single_execution(execution, environment, storage_state, cdp_url=None):
    AutomationExecution.objects.filter(pk=execution.pk).update(
        status='running', started_at=timezone.now())
    case = execution.case
    task_description = automation_services.build_case_task_description(
        case, environment,
        logged_in=execution.session.login_status == 'success')
    try:
        ok, log, _state, detail = run_browser_task(
            task_description, case_name=case.title, storage_state=storage_state,
            cdp_url=cdp_url,
            enable_screenshot=getattr(environment, 'enable_screenshot', True))
    except Exception as exc:
        AutomationExecution.objects.filter(pk=execution.pk).update(
            status='failed', error=_mask_password(str(exc)[:2000], environment),
            finished_at=timezone.now())
        _summarize_failure(case, environment, str(exc))
        return
    _persist_execution_detail(execution, case, environment, ok, log, detail)
    AutomationExecution.objects.filter(pk=execution.pk).update(
        status='success' if ok else 'failed',
        log=_mask_password((log or '')[:20000], environment),
        finished_at=timezone.now())
    if not ok:
        _summarize_failure(case, environment, log)


def _persist_execution_detail(execution, case, environment, ok, log, detail):
    """把结构化步骤写入执行记录；同步维护用例上的成功路径记忆与失败总结。

    detail 文本统一脱敏：执行记录面向项目成员展示，成功路径会注入后续任务描述。
    """
    result_detail = []
    success_trace = []
    for entry in (detail or {}).get('result_detail', []):
        entry = dict(entry)
        for key in ('actions', 'thinking', 'evaluation', 'next_goal', 'error', 'result'):
            value = entry.get(key)
            if isinstance(value, list):
                entry[key] = [_mask_password(v, environment) for v in value]
            elif value:
                entry[key] = _mask_password(value, environment)
        result_detail.append(entry)
    for item in (detail or {}).get('success_trace', []):
        success_trace.append({
            'url': item.get('url', ''),
            'actions': [_mask_password(a, environment) for a in (item.get('actions') or [])],
        })
    AutomationExecution.objects.filter(pk=execution.pk).update(
        result_detail=result_detail)
    updates = {}
    if ok:
        # 成功路径覆盖记录；顺带清空上次的失败总结
        if success_trace:
            updates['success_trace'] = success_trace
        updates['last_failure_summary'] = ''
    if updates:
        AutomationCase.objects.filter(pk=case.pk).update(**updates)


def run_browser_task(task_description, case_name, storage_state=None, keep_alive=False,
                     cdp_url=None, enable_screenshot=True, close_browser=True):
    """同步执行一段 browser-use 任务。

    运行、登录态导出与浏览器收尾收拢在同一个 asyncio 事件循环里。
    keep_alive=True（登录执行）时浏览器会话在 agent 运行后保持存活，
    导出 storage_state 之后再由 _cleanup_browser 显式关闭——否则 agent
    运行结束会自动 reset 会话，CDP 连接销毁后导出必然失败。
    cdp_url 非空时连接远端浏览器（如用户本地 Chrome 经隧道暴露），不在本机启动。
    enable_screenshot=False 时跳过逐页截图与 GIF（环境级开关），速度更快内存更省。
    close_browser=False（登录执行）时不清理浏览器，把存活会话经 detail 交还
    调用方复用（共享登录态），由调用方在合适时机 kill。
    返回 (ok, log, storage_state, detail)，detail 为结构化执行明细：
    {'result_detail': [...], 'success_trace': [...], 'cdp_url': ...,
     'browser_session': 存活会话（仅 keep_alive 且未清理时）}。
    """
    from apps.ui_automation.ai_agent import BrowserAgent

    agent = BrowserAgent(case_name=case_name, storage_state=storage_state,
                         keep_alive=keep_alive, cdp_url=cdp_url,
                         enable_screenshot=enable_screenshot)
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

    async def _cleanup_browser():
        # browser_use 0.10.1 关闭 API（已核对源码）：BrowserSession.kill() 杀掉
        # 浏览器进程、stop() 仅保留进程重置状态；Agent.close() 会按 keep_alive
        # 决定是否 kill。BrowserAgent 只把 browser_session 暴露在实例上，故在此
        # 优先 kill，其次 stop，避免残留 chrome 进程。
        # 远端浏览器（cdp_url）是用户自己的 Chrome，只能 stop() 断开 CDP，绝不能 kill。
        if not close_browser:
            return  # 登录执行：会话交还调用方复用，由其在会话收尾时清理
        session = getattr(agent, 'browser_session', None)
        if session is None:
            return
        if cdp_url:
            closer = getattr(session, 'stop', None)
        else:
            closer = getattr(session, 'kill', None) or getattr(session, 'stop', None)
        if not callable(closer):
            return
        try:
            await closer()
        except Exception as exc:
            log_lines.append(f'浏览器清理异常: {exc}')

    async def _export_state_via_cdp():
        """兜底：agent 会话 reset 后 CDP 数据被清空，直连 chrome 调试端口导出登录态。

        keep_alive 只保证浏览器进程存活；browser-use 0.10.1 的 reset 仍会清掉
        自身会话的 CDP client（export_storage_state 报 Root CDP client not
        initialized）。本地启动的 chrome 端口随机（Linux 被 ai_base 补丁固定为
        9222，macOS 随机），故优先用 run 期间观测到的端点；远端浏览器（cdp_url）
        则复用其地址，经隧道同样可达。
        """
        try:
            # 优先用 run 期间观测到的真实端点（本地浏览器端口随机，
            # 且 reset 后 session.cdp_url 已被清空，只能靠事前记录）
            cdp_endpoint = (getattr(agent, '_observed_cdp_url', None)
                            or cdp_url or 'http://127.0.0.1:9222')
            return await export_state_via_cdp(cdp_endpoint)
        except Exception as exc:
            log_lines.append(f'CDP 导出登录态失败: {exc}')
            return None

    async def _run_and_export():
        try:
            result = await agent.run_task(task_description, callback=callback)
            # 仅 keep_alive 会话（登录执行）可导出：普通用例执行的会话随 agent
            # 结束被 reset，导出只会拿到 None 且刷警告
            state = None
            if keep_alive:
                # 统一走 CDP 导出：browser-use 自身的 export_storage_state 只含
                # cookies/localStorage，且焦点恢复失败时抛错；uap-ui 类系统的
                # 鉴权 token 存 sessionStorage，必须经 CDP 逐页收集补全。
                # CDP 不可达时退回 agent 自身导出（聊胜于无）。
                state = await _export_state_via_cdp()
                if state is None:
                    # 兜底同样套超时：任何导出路径挂起都不允许卡死会话
                    try:
                        state = await asyncio.wait_for(
                            agent.export_storage_state(), timeout=10)
                    except Exception as exc:
                        log_lines.append(f'agent 导出登录态失败: {exc}')
                        state = None
            return result, state
        finally:
            await _cleanup_browser()

    try:
        result, state = _run_with_bounded_teardown(_run_and_export())
    except Exception as exc:
        empty_detail = {'result_detail': [], 'success_trace': []}
        return False, '\n'.join(log_lines + [f'执行异常: {exc}']), None, empty_detail
    # run_task 返回 browser-use 的 AgentHistoryList：is_successful() / is_done() 是方法，
    # is_successful() 在未完成时返回 None，此时按 is_done() 判定（未完成视为失败）
    is_success = None
    is_successful = getattr(result, 'is_successful', None)
    if callable(is_successful):
        is_success = is_successful()
    if is_success is None:
        is_done = getattr(result, 'is_done', None)
        is_success = is_done() if callable(is_done) else bool(is_done)
    try:
        detail = {
            'result_detail': automation_services.extract_execution_detail(result),
            'success_trace': automation_services.extract_success_trace(result),
            'cdp_url': getattr(agent, '_observed_cdp_url', None) or cdp_url,
            # 登录执行（close_browser=False）时交还存活会话，供调用方共享登录态
            'browser_session': (getattr(agent, 'browser_session', None)
                                if keep_alive and not close_browser else None),
        }
    except Exception as exc:
        # 明细提取失败不影响执行结果本身
        logger.warning('automation detail extraction failed: %s', exc)
        detail = {'result_detail': [], 'success_trace': [],
                  'cdp_url': getattr(agent, '_observed_cdp_url', None) or cdp_url,
                  'browser_session': None}
    return bool(is_success), '\n'.join(log_lines), state, detail
