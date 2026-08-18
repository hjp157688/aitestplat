"""禅道用例导入导出端点测试（mock ZentaoService）

导入/导出已改为后台任务：POST 只创建任务并返回 task_id，实际工作在
_run_zentao_task 里执行。运行期逻辑通过直接同步调用 runner 测试，避免线程竞态。
"""
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.testcases.views import _run_zentao_task

User = get_user_model()


class BaseZentaoTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('zuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)


class ZentaoExportViewTests(BaseZentaoTestCase):

    @mock.patch('apps.testcases.views._start_zentao_thread')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_creates_task_and_returns_task_id(self, mock_cfg, mock_start):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        p = Project.objects.create(name='p', owner=self.user)
        tc = TestCase.objects.create(
            project=p, author=self.user, title='t', steps='[]', priority='medium',
        )

        resp = self.client.post(
            '/api/testcases/zentao-export/',
            {'case_ids': [tc.id], 'product_id': 7},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        task = ZentaoSyncTask.objects.get(task_id=body['task_id'])
        self.assertEqual(task.task_type, 'export')
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.input_params['case_ids'], [tc.id])
        mock_start.assert_called_once_with(task)

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_requires_case_ids(self, mock_cfg):
        resp = self.client.post('/api/testcases/zentao-export/', {'case_ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_requires_config(self, mock_cfg):
        from apps.testcases.models import TestCase
        from apps.projects.models import Project
        mock_cfg.return_value = None
        p = Project.objects.create(name='p', owner=self.user)
        tc = TestCase.objects.create(project=p, author=self.user, title='t', steps='[]', priority='medium')
        resp = self.client.post(
            '/api/testcases/zentao-export/', {'case_ids': [tc.id]}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('配置中心', resp.json()['error'])

    @mock.patch('apps.testcases.views.ZentaoService.create_testcase')
    @mock.patch('apps.testcases.views.ZentaoService.update_testcase')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_runner_creates_and_updates(self, mock_cfg, mock_update, mock_create):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        mock_create.return_value = {'id': 'case_100'}
        mock_update.return_value = {'id': 'case_200'}
        p = Project.objects.create(name='p', owner=self.user)
        new_case = TestCase.objects.create(
            project=p, author=self.user, title='new',
            steps='[]', priority='medium',
        )
        existing_case = TestCase.objects.create(
            project=p, author=self.user, title='ex',
            steps='[]', priority='medium', zentao_case_id='case_200',
        )
        task = ZentaoSyncTask.objects.create(
            task_id='e00000000000000000000000000000', task_type='export',
            input_params={'case_ids': [new_case.id, existing_case.id], 'product_id': 7},
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.result['success_count'], 2)
        self.assertEqual(task.result['failed_count'], 0)
        mock_create.assert_called_once()
        mock_update.assert_called_once()
        new_case.refresh_from_db()
        self.assertEqual(new_case.zentao_case_id, 'case_100')
        self.assertEqual(new_case.product_id, 7)

    @mock.patch('apps.testcases.views.ZentaoService.create_testcase')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_runner_reports_partial_failures(self, mock_cfg, mock_create):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.projects.models import Project
        from apps.requirement_analysis.models import Requirement
        mock_cfg.return_value = mock.MagicMock()
        mock_create.return_value = {'id': 'case_300'}
        p = Project.objects.create(name='p', owner=self.user)
        # 带关联需求的用例：p_id 取需求的禅道产品，走 create
        req = Requirement.objects.create(
            project=p, source_type='zentao', title='R', zentao_id=55, product_id=7,
        )
        ok_case = TestCase.objects.create(
            project=p, author=self.user, title='ok', steps='[]', priority='medium',
            requirement=req,
        )
        # 无关联需求且未传产品：手动路径 p_id 为空 -> 失败
        no_product_case = TestCase.objects.create(
            project=p, author=self.user, title='np', steps='[]', priority='medium',
        )
        task = ZentaoSyncTask.objects.create(
            task_id='e10000000000000000000000000000', task_type='export',
            input_params={'case_ids': [no_product_case.id, ok_case.id]},
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.result['success_count'], 1)
        self.assertEqual(task.result['failed_count'], 1)
        self.assertEqual(task.result['failures'][0]['title'], 'np')
        self.assertIn('未指定禅道产品', task.result['failures'][0]['error'])

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_runner_raises_without_config(self, mock_cfg):
        from apps.testcases.models import ZentaoSyncTask
        mock_cfg.return_value = None
        task = ZentaoSyncTask.objects.create(
            task_id='e20000000000000000000000000000', task_type='export',
            input_params={'case_ids': []},
        )
        with self.assertRaisesRegex(Exception, '配置中心'):
            _run_zentao_task(task)


class ZentaoTaskDetailViewTests(BaseZentaoTestCase):

    @mock.patch('apps.testcases.views._start_zentao_thread')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_task_detail_returns_progress_and_result(self, mock_cfg, mock_start):
        from apps.testcases.models import ZentaoSyncTask
        mock_cfg.return_value = mock.MagicMock()
        resp = self.client.post(
            '/api/testcases/zentao-export/', {'case_ids': [999999]}, format='json'
        )
        task_id = resp.json()['task_id']
        task = ZentaoSyncTask.objects.get(task_id=task_id)
        task.status = 'succeeded'
        task.progress = 100
        task.result = {'success_count': 3, 'failed_count': 1, 'failures': [{'case_id': 1, 'title': 'x', 'error': 'e'}]}
        task.save()

        resp = self.client.get(f'/api/testcases/zentao-task/{task_id}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['status'], 'succeeded')
        self.assertEqual(body['progress'], 100)
        self.assertEqual(body['result']['success_count'], 3)

    def test_task_detail_404(self):
        resp = self.client.get('/api/testcases/zentao-task/doesnotexist/')
        self.assertEqual(resp.status_code, 404)


class ZentaoImportViewTests(BaseZentaoTestCase):

    @mock.patch('apps.testcases.views._start_zentao_thread')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_creates_task_and_returns_task_id(self, mock_cfg, mock_start):
        from apps.testcases.models import ZentaoSyncTask
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        p = Project.objects.create(name='p', owner=self.user)
        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'product', 'scope_id': 7, 'story_ids': [55], 'project_id': p.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        task = ZentaoSyncTask.objects.get(task_id=body['task_id'])
        self.assertEqual(task.task_type, 'import')
        self.assertEqual(task.input_params['story_ids'], [55])
        mock_start.assert_called_once_with(task)

    @mock.patch('apps.testcases.views.ZentaoService.get_testcase_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_testcases')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_runner_creates_cases_and_requirement(self, mock_cfg, mock_cases, mock_detail, mock_tc_detail):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        mock_detail.return_value = {
            'id': 55, 'product': 7, 'module': 8,
            'title': '需求X', 'spec': '描述',
        }
        mock_cases.return_value = [{
            'id': 'case_300', 'title': 'c1', 'precondition': '',
            'steps': [], 'type': 'feature', 'pri': 2,
        }]
        mock_tc_detail.return_value = {
            'id': 'case_300', 'title': 'c1', 'precondition': '',
            'steps': [{'desc': 's', 'expect': 'e'}], 'type': 'feature', 'pri': 2,
        }

        p = Project.objects.create(name='p', owner=self.user)
        task = ZentaoSyncTask.objects.create(
            task_id='i00000000000000000000000000000', task_type='import',
            created_by=self.user,
            input_params={'scope_type': 'product', 'scope_id': 7, 'story_ids': [55], 'project_id': p.id},
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.result['created'], 1)
        self.assertEqual(task.result['updated'], 0)

        tc = TestCase.objects.get(zentao_case_id='case_300')
        self.assertEqual(tc.title, 'c1')
        self.assertIsNotNone(tc.requirement_id)
        self.assertEqual(tc.requirement.zentao_id, 55)
        self.assertEqual(tc.story_id, 55)
        import json
        imported_steps = json.loads(tc.steps)
        self.assertEqual(imported_steps, [{'desc': 's', 'expect': 'e'}])

    @mock.patch('apps.testcases.views.ZentaoService.get_testcase_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_testcases')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_runner_updates_existing(self, mock_cfg, mock_cases, mock_detail, mock_tc_detail):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.projects.models import Project
        from apps.requirement_analysis.models import Requirement
        mock_cfg.return_value = mock.MagicMock()
        mock_detail.return_value = {
            'id': 55, 'product': 7, 'module': 8, 'title': 'X', 'spec': '',
        }
        mock_cases.return_value = [{
            'id': 'case_300', 'title': 'c1-updated', 'precondition': '',
            'steps': [], 'type': 'feature', 'pri': 2,
        }]
        mock_tc_detail.return_value = {
            'id': 'case_300', 'title': 'c1-updated', 'precondition': '',
            'steps': [], 'type': 'feature', 'pri': 2,
        }
        p = Project.objects.create(name='p', owner=self.user)
        req = Requirement.objects.create(
            project=p, source_type='zentao', title='X', zentao_id=55,
        )
        TestCase.objects.create(
            project=p, author=self.user, title='old', steps='[]',
            priority='medium', zentao_case_id='case_300', requirement=req,
        )
        task = ZentaoSyncTask.objects.create(
            task_id='i10000000000000000000000000000', task_type='import',
            created_by=self.user,
            input_params={'scope_type': 'product', 'scope_id': 7, 'story_ids': [55], 'project_id': p.id},
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.result['updated'], 1)
        self.assertEqual(task.result['created'], 0)
        self.assertEqual(TestCase.objects.get(zentao_case_id='case_300').title, 'c1-updated')

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_requires_args(self, mock_cfg):
        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'product', 'scope_id': 7, 'story_ids': [], 'project_id': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
