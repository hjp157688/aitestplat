"""执行编排与会话/记录 API 测试（mock BrowserAgent 层）。"""
import asyncio
import json
import time
from unittest import mock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis import automation_tasks
from apps.requirement_analysis.models import (
    AutomationCase,
    AutomationEnvironment,
    AutomationExecution,
    AutomationExecutionSession,
)

User = get_user_model()


class ExecuteApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('exec-user', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name='执行项目', owner=self.user)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='默认环境', base_url='https://x.com',
            login_url='https://x.com/login', username='admin', password='pw')
        self.env_no_login = AutomationEnvironment.objects.create(
            project=self.project, name='免登环境', base_url='https://x.com')
        self.case1 = AutomationCase.objects.create(
            project=self.project, title='用例1', convert_status='done',
            steps=[{'index': 1, 'action': '打开 {{base_url}}', 'verify': ''}])
        self.case2 = AutomationCase.objects.create(
            project=self.project, title='用例2', convert_status='done', steps=[])

    @mock.patch('apps.requirement_analysis.automation_tasks.start_session')
    def test_single_execute_creates_session_and_execution(self, mock_start):
        resp = self.client.post(
            f'/api/requirement-analysis/automation-cases/{self.case1.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 202)
        session = AutomationExecutionSession.objects.get(pk=resp.json()['session_id'])
        self.assertEqual(session.environment, self.env)
        self.assertEqual(session.executions.count(), 1)
        mock_start.assert_called_once_with(session.pk)

    @mock.patch('apps.requirement_analysis.automation_tasks.start_session')
    def test_batch_execute_creates_one_session_many_executions(self, mock_start):
        resp = self.client.post(
            '/api/requirement-analysis/automation-cases/batch-execute/',
            {'ids': [self.case1.id, self.case2.id], 'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 202)
        session = AutomationExecutionSession.objects.get(pk=resp.json()['session_id'])
        self.assertEqual(session.executions.count(), 2)
        mock_start.assert_called_once()

    def test_execute_rejects_env_from_other_project(self):
        other = Project.objects.create(name='别的项目', owner=self.user)
        foreign_env = AutomationEnvironment.objects.create(project=other, name='外部环境')
        resp = self.client.post(
            f'/api/requirement-analysis/automation-cases/{self.case1.id}/execute/',
            {'environment_id': foreign_env.id}, format='json')
        self.assertEqual(resp.status_code, 400)


class RunSessionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('orch-user', password='x')
        self.project = Project.objects.create(name='编排项目', owner=self.owner)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='默认环境', base_url='https://x.com')
        self.case1 = AutomationCase.objects.create(project=self.project, title='用例1', steps=[])
        self.case2 = AutomationCase.objects.create(project=self.project, title='用例2', steps=[])
        self.session = AutomationExecutionSession.objects.create(
            project=self.project, environment=self.env)
        AutomationExecution.objects.create(case=self.case1, session=self.session, environment=self.env)
        AutomationExecution.objects.create(case=self.case2, session=self.session, environment=self.env)

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_run_session_executes_all_and_marks_done(self, mock_task):
        mock_task.return_value = (True, 'step log', None, {'result_detail': [], 'success_trace': []})
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        self.assertEqual(self.session.login_status, 'not_required')
        executions = list(self.session.executions.order_by('id'))
        self.assertEqual([e.status for e in executions], ['success', 'success'])
        self.assertEqual(executions[0].log, 'step log')

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_one_case_failure_does_not_block_others(self, mock_task):
        mock_task.side_effect = [(False, 'boom', None, {'result_detail': [], 'success_trace': []}),
                            (True, 'ok', None, {'result_detail': [], 'success_trace': []})]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        statuses = [e.status for e in self.session.executions.order_by('id')]
        self.assertEqual(statuses, ['failed', 'success'])

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_login_failure_fails_whole_session(self, mock_task):
        self.env.login_url = 'https://x.com/login'
        self.env.save()
        mock_task.return_value = (False, '登录页打不开', None, {'result_detail': [], 'success_trace': []})
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'failed')
        self.assertEqual(self.session.login_status, 'failed')
        self.assertEqual(
            set(self.session.executions.values_list('status', flat=True)), {'failed'})

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_login_success_exports_storage_state(self, mock_task):
        self.env.login_url = 'https://x.com/login'
        self.env.save()
        # 第 1 次调用是登录任务（返回 storage_state），后续是用例执行
        detail = {'result_detail': [], 'success_trace': []}
        mock_task.side_effect = [
            (True, '登录成功', {'cookies': [{'name': 'sid'}]}, detail),
            (True, 'ok', None, detail),
            (True, 'ok', None, detail),
        ]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.login_status, 'success')
        self.assertEqual(self.session.storage_state, {'cookies': [{'name': 'sid'}]})
        self.assertEqual(
            [e.status for e in self.session.executions.order_by('id')], ['success', 'success'])

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_login_error_masks_password_in_session_error(self, mock_task):
        self.env.login_url = 'https://x.com/login'
        self.env.password = 's3cretPw!'
        self.env.save()
        mock_task.return_value = (False, '提交了密码 s3cretPw! 但登录失败', None,
                                  {'result_detail': [], 'success_trace': []})
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'failed')
        self.assertNotIn('s3cretPw!', self.session.error)
        self.assertIn('******', self.session.error)


class _FakeResult:
    """仿真 browser-use AgentHistoryList 的最小接口。"""

    def __init__(self, success=True):
        self._success = success

    def is_successful(self):
        return self._success

    def is_done(self):
        return True


class _FakeAgent:
    """仿真 BrowserAgent：run_task 成功、可选泄漏日志、可配置导出结果。"""

    def __init__(self, state=None, leak='', cdp_url=None):
        self._state = state
        self._leak = leak
        self.cdp_url = cdp_url

    async def run_task(self, task_description, callback=None):
        if callback and self._leak:
            callback({'type': 'log', 'content': self._leak})
        return _FakeResult(True)

    async def export_storage_state(self):
        return self._state


class BrowserAgentSessionTests(TestCase):
    """mock BrowserAgent 层验证 C1 登录态导出护栏与 I1 密码脱敏。"""

    def setUp(self):
        self.owner = User.objects.create_user('agent-user', password='x')
        self.project = Project.objects.create(name='代理项目', owner=self.owner)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='登录环境', base_url='https://x.com',
            login_url='https://x.com/login', username='admin', password='s3cretPw!')
        self.case = AutomationCase.objects.create(project=self.project, title='用例1', steps=[])
        self.session = AutomationExecutionSession.objects.create(
            project=self.project, environment=self.env)
        AutomationExecution.objects.create(
            case=self.case, session=self.session, environment=self.env)

    @mock.patch('playwright.async_api.async_playwright',
                side_effect=RuntimeError('tests must not touch a real CDP endpoint'))
    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_login_state_export_none_fails_whole_session(self, mock_agent_cls, mock_pw):
        """登录任务成功但 storage_state 导出为 None → 整批失败，不裸跑。

        同时封堵 CDP 兜底导出：若本机 9222 恰有调试 Chrome 在跑，兜底会真连并反转结果。
        """
        mock_agent_cls.return_value = _FakeAgent(state=None)
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'failed')
        self.assertEqual(self.session.login_status, 'failed')
        self.assertIn('登录态导出失败', self.session.error)
        self.assertEqual(
            set(self.session.executions.values_list('status', flat=True)), {'failed'})

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_login_state_export_dict_persists_storage_state(self, mock_agent_cls):
        """export_storage_state 返回 dict → 登录成功且登录态落库、用例执行成功。"""
        state = {'cookies': [{'name': 'sid', 'value': 'abc'}]}
        mock_agent_cls.return_value = _FakeAgent(state=state)
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        self.assertEqual(self.session.login_status, 'success')
        self.assertEqual(self.session.storage_state, state)
        self.assertEqual(
            [e.status for e in self.session.executions.order_by('id')], ['success'])

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_execution_log_masks_password(self, mock_agent_cls):
        """执行日志中出现密码时落库前被替换为 ******。"""
        mock_agent_cls.return_value = _FakeAgent(
            state={'cookies': []}, leak='输入密码 s3cretPw! 完成登录')
        automation_tasks.run_session(self.session.pk)
        execution = self.session.executions.first()
        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, 'success')
        self.assertNotIn('s3cretPw!', execution.log)
        self.assertIn('******', execution.log)

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_run_browser_task_returns_exported_state_in_single_loop(self, mock_agent_cls):
        """C1：运行与导出在同一事件循环；仅 keep_alive 会话（登录执行）导出登录态。"""
        state = {'cookies': [{'name': 'sid'}]}
        mock_agent_cls.return_value = _FakeAgent(state=state)
        ok, log, exported, _detail = automation_tasks.run_browser_task('任务', case_name='单测', keep_alive=True)
        self.assertTrue(ok)
        self.assertEqual(exported, state)
        mock_agent_cls.assert_called_once_with(
            case_name='单测', storage_state=None, keep_alive=True, cdp_url=None,
            enable_screenshot=True)

        # 普通用例执行（keep_alive=False）：会话随 agent 结束被 reset，不导出
        mock_agent_cls.return_value = _FakeAgent(state=state)
        ok2, _log, exported2, _detail2 = automation_tasks.run_browser_task('任务', case_name='单测')
        self.assertTrue(ok2)
        self.assertIsNone(exported2)

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_run_browser_task_passes_cdp_url(self, mock_agent_cls):
        """cdp_url 透传给 BrowserAgent：远端浏览器（用户本地 Chrome）不在本机启动。"""
        mock_agent_cls.return_value = _FakeAgent(state=None)
        ok, _log, _state, _detail = automation_tasks.run_browser_task(
            '任务', case_name='单测', cdp_url='http://127.0.0.1:9222')
        self.assertTrue(ok)
        mock_agent_cls.assert_called_once_with(
            case_name='单测', storage_state=None, keep_alive=False,
            cdp_url='http://127.0.0.1:9222', enable_screenshot=True)

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_run_session_uses_environment_cdp_url(self, mock_agent_cls):
        """环境配置 cdp_url 时，登录与用例执行均连接远端浏览器。"""
        self.env.cdp_url = 'http://127.0.0.1:9222'
        self.env.save()
        mock_agent_cls.return_value = _FakeAgent(
            state={'cookies': [{'name': 'sid'}]})
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        kwargs = mock_agent_cls.call_args.kwargs
        self.assertEqual(kwargs.get('cdp_url'), 'http://127.0.0.1:9222')

    @mock.patch('playwright.async_api.async_playwright')
    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_cdp_fallback_prefers_observed_endpoint(self, mock_agent_cls, mock_pw_cls):
        """export 失败走 CDP 兜底时，优先用 run 期间观测到的真实端点。

        本地启动的 Chrome 端口随机（macOS），reset 后 session.cdp_url 已被清空，
        只能靠 run 期间记录的 _observed_cdp_url；不能写死 9222。
        """
        agent = _FakeAgent(state=None)
        agent._observed_cdp_url = 'ws://127.0.0.1:61323/devtools/browser/abc'
        mock_agent_cls.return_value = agent

        state = {'cookies': [{'name': 'sid', 'value': 'x'}]}
        pw = mock.MagicMock()
        pw.stop = mock.AsyncMock()
        # async_playwright() 本身是同步调用，start() 才是 await
        mock_pw_cls.return_value.start = mock.AsyncMock(return_value=pw)
        browser = mock.MagicMock()
        browser.contexts = [mock.MagicMock()]
        browser.close = mock.AsyncMock()
        browser.contexts[0].storage_state = mock.AsyncMock(return_value=state)
        pw.chromium.connect_over_cdp = mock.AsyncMock(return_value=browser)

        ok, _log, exported, _detail = automation_tasks.run_browser_task(
            '任务', case_name='单测', keep_alive=True)
        self.assertTrue(ok)
        self.assertEqual(exported, state)
        endpoint = pw.chromium.connect_over_cdp.call_args.args[0]
        self.assertEqual(endpoint, 'ws://127.0.0.1:61323/devtools/browser/abc')


class ExecutionDetailPersistenceTests(TestCase):
    """结构化执行明细、成功路径记忆与失败总结的落库行为。"""

    def setUp(self):
        self.owner = User.objects.create_user('detail-user', password='x')
        self.project = Project.objects.create(name='明细项目', owner=self.owner)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='环境A', base_url='https://x.com',
            username='admin', password='s3cretPw!')
        self.case = AutomationCase.objects.create(
            project=self.project, title='用例D', steps=[{'index': 1, 'action': '打开首页'}],
            last_failure_summary='旧失败原因')
        self.session = AutomationExecutionSession.objects.create(
            project=self.project, environment=self.env)
        self.execution = AutomationExecution.objects.create(
            case=self.case, session=self.session, environment=self.env)

    @staticmethod
    def _detail():
        return {
            'result_detail': [
                {'index': 1, 'url': 'https://x.com', 'title': '首页',
                 'actions': ["输入: 's3cretPw!'"], 'thinking': '填密码 s3cretPw!',
                 'evaluation': '', 'next_goal': '', 'error': '', 'result': '', 'duration': 1.0},
            ],
            'success_trace': [{'url': 'https://x.com', 'actions': ["输入: 's3cretPw!'"]}],
        }

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_success_persists_trace_and_clears_failure_summary(self, mock_task):
        mock_task.return_value = (True, 'ok', None, self._detail())
        automation_tasks.run_session(self.session.pk)
        self.execution.refresh_from_db()
        self.case.refresh_from_db()
        # 明细已脱敏落库
        self.assertEqual(len(self.execution.result_detail), 1)
        self.assertEqual(self.execution.result_detail[0]['actions'], ["输入: '******'"])
        self.assertEqual(self.execution.result_detail[0]['thinking'], '填密码 ******')
        # 成功路径记忆覆盖（含脱敏）；失败总结清空
        self.assertEqual(self.case.success_trace[0]['actions'], ["输入: '******'"])
        self.assertEqual(self.case.last_failure_summary, '')

    @mock.patch.object(automation_tasks, '_summarize_failure')
    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_failure_triggers_summary_and_keeps_trace(self, mock_task, mock_summary):
        mock_task.return_value = (False, 'boom', None, self._detail())
        automation_tasks.run_session(self.session.pk)
        self.execution.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(self.execution.status, 'failed')
        self.assertEqual(self.execution.result_detail[0]['actions'], ["输入: '******'"])
        mock_summary.assert_called_once()
        # 失败不动用例上的成功路径记忆与失败总结（总结由 _summarize_failure 覆盖写入）
        self.assertEqual(self.case.success_trace, [])

    @mock.patch('apps.ai.client.AIClient.chat_sync')
    @mock.patch('apps.ai.resolver.ConfigResolver.active')
    @mock.patch('apps.ai.prompt_registry.get_prompt_content_raw',
                return_value='system prompt')
    def test_failure_summary_generated_and_masked(self, mock_prompt, mock_active, mock_ai):
        mock_active = mock_active_obj = mock.Mock()
        mock_active.return_value = mock_active_obj
        mock_ai.return_value = {
            'choices': [{'message': {'content': '密码 s3cretPw! 输入到了错误输入框'}}]}
        automation_tasks._summarize_failure(self.case, self.env, '日志含 s3cretPw!')
        self.case.refresh_from_db()
        self.assertIn('******', self.case.last_failure_summary)
        self.assertNotIn('s3cretPw!', self.case.last_failure_summary)
        user_msg = mock_ai.call_args.args[1][1]['content']
        self.assertNotIn('s3cretPw!', user_msg)

    @mock.patch('apps.ai.resolver.ConfigResolver.active', return_value=None)
    def test_failure_summary_skips_without_config(self, mock_active):
        automation_tasks._summarize_failure(self.case, self.env, '日志')
        self.case.refresh_from_db()
        self.assertEqual(self.case.last_failure_summary, '旧失败原因')

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_run_session_passes_enable_screenshot(self, mock_task):
        self.env.enable_screenshot = False
        self.env.save()
        mock_task.return_value = (True, 'ok', None, {'result_detail': [], 'success_trace': []})
        automation_tasks.run_session(self.session.pk)
        for call in mock_task.call_args_list:
            self.assertFalse(call.kwargs.get('enable_screenshot'))


class ExecutionDeleteApiTests(TestCase):
    """执行记录删除：与模块其他写接口一致，登录用户即可删（无项目隔离）。"""

    def setUp(self):
        self.user = User.objects.create_user('del-user', password='x')
        self.stranger = User.objects.create_user('stranger', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name='删除项目', owner=self.user)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='环境', base_url='https://x.com')
        self.case = AutomationCase.objects.create(project=self.project, title='用例X', steps=[])
        self.session = AutomationExecutionSession.objects.create(
            project=self.project, environment=self.env)
        self.execution = AutomationExecution.objects.create(
            case=self.case, session=self.session, environment=self.env)

    def test_delete_execution(self):
        resp = self.client.delete(
            f'/api/requirement-analysis/automation-executions/{self.execution.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(
            AutomationExecution.objects.filter(pk=self.execution.id).exists())

    def test_delete_missing_execution_returns_404(self):
        resp = self.client.delete(
            '/api/requirement-analysis/automation-executions/999999/')
        self.assertEqual(resp.status_code, 404)

    def test_delete_last_success_record_clears_success_trace(self):
        """删光成功记录后清空成功路径记忆，保证下次执行等价于第一次。"""
        AutomationExecution.objects.filter(pk=self.execution.pk).update(status='success')
        self.case.success_trace = [{'url': 'https://x.com/a', 'actions': ['点击: 登录']}]
        self.case.save(update_fields=['success_trace'])

        resp = self.client.delete(
            f'/api/requirement-analysis/automation-executions/{self.execution.id}/')

        self.assertEqual(resp.status_code, 204)
        self.case.refresh_from_db()
        self.assertEqual(self.case.success_trace, [])

    def test_delete_last_failed_record_clears_failure_summary(self):
        """删光失败记录后清空失败总结，避免下次执行仍注入历史失败原因。"""
        AutomationExecution.objects.filter(pk=self.execution.pk).update(status='failed')
        self.case.last_failure_summary = '登录超时'
        self.case.save(update_fields=['last_failure_summary'])

        resp = self.client.delete(
            f'/api/requirement-analysis/automation-executions/{self.execution.id}/')

        self.assertEqual(resp.status_code, 204)
        self.case.refresh_from_db()
        self.assertEqual(self.case.last_failure_summary, '')

    def test_delete_one_of_many_success_records_keeps_trace(self):
        """仍有剩余成功记录时保留成功路径记忆（记忆与记录保持一致）。"""
        AutomationExecution.objects.filter(pk=self.execution.pk).update(status='success')
        other = AutomationExecution.objects.create(
            case=self.case, session=self.session, environment=self.env, status='success')
        self.case.success_trace = [{'url': 'https://x.com/a', 'actions': ['点击: 登录']}]
        self.case.save(update_fields=['success_trace'])

        resp = self.client.delete(
            f'/api/requirement-analysis/automation-executions/{other.id}/')

        self.assertEqual(resp.status_code, 204)
        self.case.refresh_from_db()
        self.assertEqual(self.case.success_trace,
                         [{'url': 'https://x.com/a', 'actions': ['点击: 登录']}])


class BoundedTeardownTests(TestCase):
    """asyncio.run 收尾会永久等待吞掉 CancelledError 的残留任务（线上实测
    bubus EventBus._run_loop 取消不退出，卡死整个登录线程）。收尾必须有界。"""

    def test_returns_result_despite_uncancellable_leftover_task(self):
        """残留任务吞 CancelledError 时，仍按时返回主协程结果，不永久卡死。"""

        async def stubborn():
            while True:
                try:
                    await asyncio.sleep(3600)
                except asyncio.CancelledError:
                    continue  # 吞取消，永不退出（模拟 bubus EventBus._run_loop）

        async def coro():
            asyncio.create_task(stubborn())
            return 42

        start = time.monotonic()
        result = automation_tasks._run_with_bounded_teardown(coro())
        self.assertEqual(result, 42)
        self.assertLess(time.monotonic() - start, 30)

    def test_propagates_main_coroutine_exception(self):
        """主协程抛错时照常上抛，收尾不吞异常。"""

        async def stubborn():
            while True:
                try:
                    await asyncio.sleep(3600)
                except asyncio.CancelledError:
                    continue

        async def coro():
            asyncio.create_task(stubborn())
            raise RuntimeError('boom')

        with self.assertRaises(RuntimeError):
            automation_tasks._run_with_bounded_teardown(coro())

    def test_kill_local_browser_parses_port_from_cdp_url(self):
        """CDP 兜底杀进程按 URL 端口匹配 pkill；无端口时不执行。"""
        with mock.patch('subprocess.run') as run_mock:
            automation_tasks._kill_local_browser_by_cdp(
                'ws://127.0.0.1:58249/devtools/browser/abc')
            run_mock.assert_called_once()
            self.assertIn('remote-debugging-port=58249', run_mock.call_args[0][0])
        with mock.patch('subprocess.run') as run2:
            automation_tasks._kill_local_browser_by_cdp('http://127.0.0.1')
            run2.assert_not_called()


class ExportSessionStorageTests(TestCase):
    """CDP 兜底导出必须包含 sessionStorage：uap-ui 类系统的鉴权 token 存在
    sessionStorage，playwright storage_state() 不含它，缺了会导致用例重新登录。"""

    def _fake_cdp(self, storage_state_hang=False, evaluate_hang=False):
        """构造 connect_over_cdp 返回的假浏览器：storage_state / evaluate 可无限挂起。"""

        async def hang(*args, **kwargs):
            await asyncio.sleep(3600)

        async def eval_ok(script):
            return json.dumps({'tokenType': 'bearer', 'isLdap': '0'})

        page = mock.MagicMock()
        page.url = 'http://192.168.177.51:9998/web/uap-ui/index.html#/homePage'
        page.evaluate = hang if evaluate_hang else eval_ok

        async def storage_state():
            if storage_state_hang:
                await hang()
            return {'cookies': [{'name': 'JSESSIONID'}], 'origins': []}

        ctx = mock.MagicMock()
        ctx.storage_state = storage_state
        ctx.pages = [page]
        browser = mock.MagicMock()
        browser.contexts = [ctx]
        browser.close = mock.AsyncMock()

        async def fake_connect(url, timeout=None):
            return browser

        async def fake_start():
            pw = mock.MagicMock()
            pw.chromium.connect_over_cdp = fake_connect
            pw.stop = mock.AsyncMock()
            return pw

        return mock.patch('playwright.async_api.async_playwright',
                          lambda: mock.MagicMock(start=fake_start))

    def test_export_includes_session_storage(self):
        """storage_state 的 origins 并入逐页收集的 sessionStorage。"""

        async def fake_evaluate(script):
            return json.dumps({'tokenType': 'bearer', 'isLdap': '0'})

        page = mock.MagicMock()
        page.url = 'http://192.168.177.51:9998/web/uap-ui/index.html#/homePage'
        page.evaluate = mock.AsyncMock(side_effect=fake_evaluate)

        async def run():
            with mock.patch('playwright.async_api.async_playwright') as mock_pw_cls:
                pw = mock.MagicMock()
                browser = mock.MagicMock()
                ctx = mock.MagicMock()
                ctx.storage_state = mock.AsyncMock(
                    return_value={'cookies': [{'name': 'JSESSIONID'}], 'origins': []})
                ctx.pages = [page]
                browser.contexts = [ctx]
                browser.close = mock.AsyncMock()
                pw.chromium.connect_over_cdp = mock.AsyncMock(return_value=browser)
                pw.stop = mock.AsyncMock()
                mock_pw_cls.return_value.start = mock.AsyncMock(return_value=pw)
                return await automation_tasks.export_state_via_cdp('http://127.0.0.1:9999')

        state = asyncio.run(run())

        self.assertIsNotNone(state)
        origin = next(o for o in state['origins'] if o['origin'] == 'http://192.168.177.51:9998')
        items = {i['name']: i['value'] for i in origin['sessionStorage']}
        self.assertEqual(items, {'tokenType': 'bearer', 'isLdap': '0'})

    def test_hanging_evaluate_is_skipped_not_deadlock(self):
        """登录页刚跳转主页时 CDP evaluate 可能永不返回（线上实测卡死）；
        evaluate 挂起必须超时跳过，而不是卡住整个登录会话。"""
        async def run():
            with self._fake_cdp(evaluate_hang=True):
                return await asyncio.wait_for(
                    automation_tasks.export_state_via_cdp(
                        'http://127.0.0.1:9999', step_timeout=2),
                    timeout=10)

        state = asyncio.run(run())
        self.assertIsNotNone(state)
        self.assertEqual(state['cookies'], [{'name': 'JSESSIONID'}])

    def test_hanging_storage_state_raises_quickly(self):
        """storage_state 挂起时按 step_timeout 快速抛错走兜底，不卡会话。"""
        async def run():
            with self._fake_cdp(storage_state_hang=True):
                return await asyncio.wait_for(
                    automation_tasks.export_state_via_cdp(
                        'http://127.0.0.1:9999', step_timeout=2),
                    timeout=10)

        start = time.monotonic()
        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(run())
        self.assertLess(time.monotonic() - start, 8)


class SharedLoginBrowserTests(TestCase):
    """登录浏览器复用：登录成功后用例执行 CDP attach 同一浏览器，
    绕开 storage_state 无法还原 sessionStorage 的限制。"""

    def setUp(self):
        self.user = User.objects.create_user('share-user', password='x')
        self.project = Project.objects.create(name='共享项目', owner=self.user)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='环境S', base_url='https://x.com',
            login_url='https://x.com/login', username='admin', password='pw')
        self.case = AutomationCase.objects.create(project=self.project, title='用例S', steps=[])
        self.session = AutomationExecutionSession.objects.create(
            project=self.project, environment=self.env)
        self.execution = AutomationExecution.objects.create(
            case=self.case, session=self.session, environment=self.env)

    @staticmethod
    def _login_detail(cdp='ws://127.0.0.1:61323/devtools/browser/abc'):
        return {'result_detail': [], 'success_trace': [],
                'cdp_url': cdp, 'browser_session': None}

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_cases_attach_login_browser_without_storage_state(self, mock_task):
        """登录返回 cdp_url 时，用例执行连接同一浏览器且不再注入 storage_state。"""
        mock_task.side_effect = [
            (True, '登录成功', {'cookies': []}, self._login_detail()),
            (True, 'ok', None, {'result_detail': [], 'success_trace': [],
                                'cdp_url': None, 'browser_session': None}),
        ]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        case_call = mock_task.call_args_list[1]
        self.assertEqual(case_call.kwargs.get('cdp_url'),
                         'ws://127.0.0.1:61323/devtools/browser/abc')
        self.assertIsNone(case_call.kwargs.get('storage_state'))

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_remote_env_login_browser_not_killed(self, mock_task):
        """环境配置 cdp_url（用户自己的浏览器）时，登录会话绝不 kill。"""
        self.env.cdp_url = 'http://127.0.0.1:9222'
        self.env.save()

        class FakeSession:
            def __init__(self):
                self.killed = False

            async def kill(self):
                self.killed = True

        fake_session = FakeSession()
        mock_task.side_effect = [
            (True, '登录成功', None, {'result_detail': [], 'success_trace': [],
                                      'cdp_url': self.env.cdp_url,
                                      'browser_session': fake_session}),
            (True, 'ok', None, {'result_detail': [], 'success_trace': [],
                                'cdp_url': None, 'browser_session': None}),
        ]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        self.assertFalse(fake_session.killed)

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_local_login_browser_killed_at_session_end(self, mock_task):
        """本地登录浏览器在会话收尾时被 kill，避免残留进程。"""
        class FakeSession:
            def __init__(self):
                self.killed = False

            async def kill(self):
                self.killed = True

        fake_session = FakeSession()
        mock_task.side_effect = [
            (True, '登录成功', {'cookies': []},
             {'result_detail': [], 'success_trace': [],
              'cdp_url': 'ws://127.0.0.1:61323/devtools/browser/abc',
              'browser_session': fake_session}),
            (True, 'ok', None, {'result_detail': [], 'success_trace': [],
                                'cdp_url': None, 'browser_session': None}),
        ]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        self.assertTrue(fake_session.killed)

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_export_none_but_shared_browser_still_runs(self, mock_task):
        """storage_state 导出失败但有可复用共享浏览器时，不误判登录失败。"""
        mock_task.side_effect = [
            (True, '登录成功', None, self._login_detail()),
            (True, 'ok', None, {'result_detail': [], 'success_trace': [],
                                'cdp_url': None, 'browser_session': None}),
        ]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.login_status, 'success')
        self.assertEqual(self.session.status, 'done')
