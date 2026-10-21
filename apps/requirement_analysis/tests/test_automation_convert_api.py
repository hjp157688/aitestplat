"""batch-convert / retry-convert API 测试（mock 异步任务入口，不真调 AI）。"""
import json
from unittest import mock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import (
    AutomationCase,
    GeneratedTestCase,
    Requirement,
    TestCaseGenerationTask,
)

User = get_user_model()
CONVERT_URL = '/api/requirement-analysis/automation-cases/batch-convert/'


class BatchConvertApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('conv-user', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name='转化项目', owner=self.user)
        self.requirement = Requirement.objects.create(
            project=self.project, title='需求A', created_by=self.user)
        self.gen1 = GeneratedTestCase.objects.create(
            requirement=self.requirement, case_id='TC-001', title='登录成功',
            priority='P1', precondition='', test_steps='1. 打开登录页', expected_result='成功')
        self.gen2 = GeneratedTestCase.objects.create(
            requirement=self.requirement, case_id='TC-002', title='登录失败',
            priority='P2', precondition='', test_steps='1. 输错密码', expected_result='提示错误')

    @mock.patch('apps.requirement_analysis.automation_tasks.start_conversion_tasks')
    def test_convert_from_generated_ids_idempotent(self, mock_start):
        resp = self.client.post(
            CONVERT_URL,
            {'source_type': 'generated', 'ids': [self.gen1.id, self.gen2.id]}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['created_count'], 2)
        mock_start.assert_called_once()

        # 重复转化：幂等跳过，不新增
        resp2 = self.client.post(
            CONVERT_URL,
            {'source_type': 'generated', 'ids': [self.gen1.id, self.gen2.id]}, format='json')
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp2.json()['created_count'], 0)
        self.assertEqual(resp2.json()['skipped_count'], 2)
        self.assertEqual(AutomationCase.objects.count(), 2)
        case = AutomationCase.objects.get(source_generated_case=self.gen1)
        self.assertEqual(case.project, self.project)
        self.assertEqual(case.requirement, self.requirement)
        self.assertEqual(case.convert_status, 'processing')

    @mock.patch('apps.requirement_analysis.automation_tasks.start_conversion_tasks')
    def test_convert_from_manual_testcase_ids(self, mock_start):
        from apps.testcases.models import TestCase as ManualTestCase
        manual = ManualTestCase.objects.create(
            project=self.project, author=self.user, title='新增用户',
            preconditions='管理员已登录', steps='1. 进入用户管理')
        resp = self.client.post(CONVERT_URL, {'source_type': 'testcase', 'ids': [manual.id]}, format='json')
        self.assertEqual(resp.status_code, 201)
        case = AutomationCase.objects.get(source_test_case=manual)
        self.assertEqual(case.project, self.project)
        self.assertEqual(case.title, '新增用户')

    @mock.patch('apps.requirement_analysis.automation_tasks.start_conversion_tasks')
    def test_convert_inline_from_task(self, mock_start):
        task = TestCaseGenerationTask.objects.create(
            task_id='T-conv-inline-1', title='搜索任务',
            requirement_text='搜索需求', project=self.project, created_by=self.user,
            requirement=self.requirement, status='completed')
        resp = self.client.post(
            CONVERT_URL,
            {'source_type': 'generated', 'task_id': task.task_id
             if hasattr(task, 'task_id') else task.pk,
             'cases': [{'title': '搜索商品', 'precondition': '有商品数据',
                        'steps': '1. 输入关键词', 'expected_result': '出现结果列表'}]},
            format='json')
        self.assertEqual(resp.status_code, 201)
        case = AutomationCase.objects.get(title='搜索商品')
        self.assertEqual(case.project, self.project)
        self.assertEqual(case.requirement.title, '需求A')  # _ensure_task_requirement 复用任务需求
        self.assertEqual(case.source_type, 'inline')

    def test_convert_rejects_bad_params(self):
        resp = self.client.post(CONVERT_URL, {'source_type': 'bad', 'ids': [1]}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(CONVERT_URL, {'source_type': 'testcase', 'ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.requirement_analysis.automation_tasks.start_conversion_tasks')
    def test_retry_convert(self, mock_start):
        case = AutomationCase.objects.create(
            project=self.project, title='失败用例', convert_status='failed', convert_error='旧错误')
        resp = self.client.post(
            f'/api/requirement-analysis/automation-cases/{case.id}/retry-convert/', format='json')
        self.assertEqual(resp.status_code, 200)
        case.refresh_from_db()
        self.assertEqual(case.convert_status, 'processing')
        self.assertEqual(case.convert_error, '')
        mock_start.assert_called_once()

    def test_run_conversion_without_writer_marks_failed(self):
        from apps.requirement_analysis import automation_tasks
        case = AutomationCase.objects.create(project=self.project, title='无模型用例')
        with mock.patch.object(automation_tasks.ConfigResolver, 'active', return_value=None):
            automation_tasks.run_conversion(case.pk)
        case.refresh_from_db()
        self.assertEqual(case.convert_status, 'failed')
        self.assertIn('writer', case.convert_error)

    @mock.patch('apps.requirement_analysis.automation_tasks.start_conversion_tasks')
    def test_inline_convert_preserves_steps(self, mock_start):
        task = TestCaseGenerationTask.objects.create(
            task_id='T-conv-inline-2', title='步骤任务', requirement_text='步骤需求',
            project=self.project, created_by=self.user, requirement=self.requirement,
            status='completed')
        resp = self.client.post(
            CONVERT_URL,
            {'source_type': 'generated', 'task_id': task.task_id,
             'cases': [{'title': '下单流程', 'precondition': '购物车有商品',
                        'steps': '1. 点击结算\n2. 确认支付', 'expected_result': '订单创建成功'}]},
            format='json')
        self.assertEqual(resp.status_code, 201)
        case = AutomationCase.objects.get(title='下单流程')
        # 转化前：steps 草稿保留原始步骤与预期文本
        self.assertEqual(case.steps, [{'index': 1, 'action': '1. 点击结算\n2. 确认支付',
                                       'verify': '订单创建成功'}])

        from apps.requirement_analysis import automation_tasks
        with mock.patch.object(automation_tasks.ConfigResolver, 'active', return_value=object()), \
                mock.patch('apps.requirement_analysis.automation_tasks.AIClient.chat_sync') as mock_chat:
            mock_chat.return_value = {'choices': [{'message': {
                'content': '[{"index": 1, "action": "点击结算按钮", "verify": "跳转支付页"}]'}}]}
            automation_tasks.run_conversion(case.pk)
        case.refresh_from_db()
        self.assertEqual(case.convert_status, 'done')
        messages = mock_chat.call_args[0][1]
        user_message = messages[-1]['content']
        self.assertIn('1. 点击结算\n2. 确认支付', user_message)
        self.assertIn('预期结果：订单创建成功', user_message)

    def test_inline_conversion_includes_env_variables_and_expected(self):
        from apps.requirement_analysis import automation_tasks
        from apps.requirement_analysis.models import AutomationEnvironment
        AutomationEnvironment.objects.create(
            project=self.project, name='联调环境', variables=[{'key': 'product', 'value': '手机'}])
        case = AutomationCase.objects.create(
            project=self.project, requirement=self.requirement, title='内联步骤用例',
            precondition='有商品', steps=[{'index': 1, 'action': '搜索商品', 'verify': '出现结果'}])
        with mock.patch.object(automation_tasks.ConfigResolver, 'active', return_value=object()), \
                mock.patch('apps.requirement_analysis.automation_tasks.AIClient.chat_sync') as mock_chat:
            mock_chat.return_value = {'choices': [{'message': {
                'content': '[{"index": 1, "action": "搜索商品", "verify": "出现结果"}]'}}]}
            automation_tasks.run_conversion(case.pk)
        messages = mock_chat.call_args[0][1]
        user_message = messages[-1]['content']
        self.assertIn('预期结果：出现结果', user_message)
        self.assertIn('product', user_message)
        case.refresh_from_db()
        self.assertEqual(case.convert_status, 'done')


class AutomationEnvironmentApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('env-user', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name='环境项目', owner=self.user)

    def test_env_crud_and_password_write_only(self):
        resp = self.client.post(
            '/api/requirement-analysis/automation-environments/',
            {'project': self.project.id, 'name': '测试环境', 'base_url': 'https://a.com',
             'login_url': 'https://a.com/login', 'username': 'admin', 'password': 'secret',
             'variables': [{'key': 'product', 'value': '手机', 'description': ''}]},
            format='json')
        self.assertEqual(resp.status_code, 201)
        env_id = resp.json()['id']
        # 列表不回显明文密码
        resp_list = self.client.get(
            '/api/requirement-analysis/automation-environments/',
            {'project': self.project.id})
        items = resp_list.json()['results'] if isinstance(resp_list.json(), dict) else resp_list.json()
        target = next(e for e in items if e['id'] == env_id)
        self.assertNotIn('secret', resp_list.content.decode())
        self.assertTrue(target['has_password'])
        # 更新：不传 password 不清空
        resp_patch = self.client.patch(
            f'/api/requirement-analysis/automation-environments/{env_id}/',
            {'name': '测试环境2'}, format='json')
        self.assertEqual(resp_patch.status_code, 200)
        from apps.requirement_analysis.models import AutomationEnvironment
        self.assertEqual(AutomationEnvironment.objects.get(pk=env_id).password, 'secret')
