import json
from unittest import mock
from django.test import TestCase
from apps.agent import service
from apps.agent.service_identity import get_service_user
from apps.ui_automation.models import AIExecutionRecord, UiProject


# 注意：本模块直接测 service 层（同步、主线程），因为
#  1) run_adhoc 需 mock threading.Thread.start 阻止真实 AI 线程启动；
#  2) 一旦 mock 了 Thread.start，asyncio.to_thread 依赖的
#     ThreadPoolExecutor 就无法孵化工作线程（asyncio.to_thread 会死锁），
#     因此不能经由异步工具的路径来测；
#  3) 工具异步封装（async def → asyncio.to_thread）由
#     test_integration_smoke 在真实事件循环上覆盖。
class UiAdhocTests(TestCase):
    def setUp(self):
        self.user = get_service_user()
        self.project = UiProject.objects.create(
            name='UI-Proj', owner=self.user, base_url='https://example.com')

    @mock.patch('threading.Thread.start')
    def test_run_adhoc(self, thread_start):
        out = service.run_ui_automation_adhoc('去登录页验证登录', project_id=self.project.id)
        self.assertNotIn('error', out)
        self.assertIn('execution_id', out)
        thread_start.assert_called_once()

    def test_run_adhoc_requires_description(self):
        with self.assertRaises(ValueError):
            service.run_ui_automation_adhoc('')

    def test_get_execution(self):
        rec = AIExecutionRecord.objects.create(
            project=self.project, case_name='Adhoc Task', task_description='x',
            execution_mode='text', status='running', executed_by=self.user)
        out = service.get_ui_execution(rec.id)
        self.assertEqual(out['status'], 'running')

    def test_stop_execution(self):
        from apps.ui_automation.views import STOP_SIGNALS
        rec = AIExecutionRecord.objects.create(
            project=self.project, case_name='Adhoc Task', task_description='x',
            execution_mode='text', status='running', executed_by=self.user)
        STOP_SIGNALS[rec.id] = False
        try:
            out = service.stop_ui_execution(rec.id)
            self.assertNotIn('error', out)
            self.assertTrue(STOP_SIGNALS.get(rec.id, False))
        finally:
            STOP_SIGNALS.pop(rec.id, None)
