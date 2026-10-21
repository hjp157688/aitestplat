"""执行编排与会话/记录 API 测试（mock BrowserAgent 层）。"""
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
        mock_task.return_value = (True, 'step log', None)
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        self.assertEqual(self.session.login_status, 'not_required')
        executions = list(self.session.executions.order_by('id'))
        self.assertEqual([e.status for e in executions], ['success', 'success'])
        self.assertEqual(executions[0].log, 'step log')

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_one_case_failure_does_not_block_others(self, mock_task):
        mock_task.side_effect = [(False, 'boom', None), (True, 'ok', None)]
        automation_tasks.run_session(self.session.pk)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'done')
        statuses = [e.status for e in self.session.executions.order_by('id')]
        self.assertEqual(statuses, ['failed', 'success'])

    @mock.patch.object(automation_tasks, 'run_browser_task')
    def test_login_failure_fails_whole_session(self, mock_task):
        self.env.login_url = 'https://x.com/login'
        self.env.save()
        mock_task.return_value = (False, '登录页打不开', None)
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
        mock_task.side_effect = [
            (True, '登录成功', {'cookies': [{'name': 'sid'}]}),
            (True, 'ok', None),
            (True, 'ok', None),
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
        mock_task.return_value = (False, '提交了密码 s3cretPw! 但登录失败', None)
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

    def __init__(self, state=None, leak=''):
        self._state = state
        self._leak = leak

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

    @mock.patch('apps.ui_automation.ai_agent.BrowserAgent')
    def test_login_state_export_none_fails_whole_session(self, mock_agent_cls):
        """登录任务成功但 storage_state 导出为 None → 整批失败，不裸跑。"""
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
        ok, log, exported = automation_tasks.run_browser_task('任务', case_name='单测', keep_alive=True)
        self.assertTrue(ok)
        self.assertEqual(exported, state)
        mock_agent_cls.assert_called_once_with(case_name='单测', storage_state=None, keep_alive=True)

        # 普通用例执行（keep_alive=False）：会话随 agent 结束被 reset，不导出
        mock_agent_cls.return_value = _FakeAgent(state=state)
        ok2, _log, exported2 = automation_tasks.run_browser_task('任务', case_name='单测')
        self.assertTrue(ok2)
        self.assertIsNone(exported2)
