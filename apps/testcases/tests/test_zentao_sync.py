"""禅道用例导入导出端点测试（mock ZentaoService）"""
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class BaseZentaoTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('zuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)


class ZentaoExportViewTests(BaseZentaoTestCase):
    @mock.patch('apps.testcases.views.ZentaoService.create_testcase')
    @mock.patch('apps.testcases.views.ZentaoService.update_testcase')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_export_creates_and_updates(self, mock_cfg, mock_update, mock_create):
        from apps.testcases.models import TestCase
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        mock_create.return_value = {'id': 100}
        mock_update.return_value = {'id': 200}
        p = Project.objects.create(name='p', owner=self.user)
        new_case = TestCase.objects.create(
            project=p, author=self.user, title='new',
            steps='[]', priority='medium',
        )
        existing_case = TestCase.objects.create(
            project=p, author=self.user, title='ex',
            steps='[]', priority='medium', zentao_case_id=200,
        )

        resp = self.client.post(
            '/api/testcases/zentao-export/',
            {'case_ids': [new_case.id, existing_case.id], 'product_id': 7},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['success_count'], 2)
        self.assertEqual(body['failed_count'], 0)
        mock_create.assert_called_once()
        mock_update.assert_called_once()
        new_case.refresh_from_db()
        self.assertEqual(new_case.zentao_case_id, 100)
        self.assertEqual(new_case.product_id, 7)

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


class ZentaoImportViewTests(BaseZentaoTestCase):
    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_testcases')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_creates_cases_and_requirement(self, mock_cfg, mock_cases, mock_detail):
        from apps.testcases.models import TestCase
        from apps.projects.models import Project
        mock_cfg.return_value = mock.MagicMock()
        mock_detail.return_value = {
            'id': 55, 'product': 7, 'module': 8,
            'title': '需求X', 'spec': '描述',
        }
        mock_cases.return_value = [{
            'id': 300, 'title': 'c1', 'precondition': '',
            'steps': [{'desc': 's', 'expect': 'e'}], 'type': 'feature', 'pri': 2,
        }]

        p = Project.objects.create(name='p', owner=self.user)
        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'product', 'scope_id': 7, 'story_ids': [55], 'project_id': p.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['created'], 1)
        self.assertEqual(body['updated'], 0)

        tc = TestCase.objects.get(zentao_case_id=300)
        self.assertEqual(tc.title, 'c1')
        self.assertIsNotNone(tc.requirement_id)
        self.assertEqual(tc.requirement.zentao_id, 55)
        self.assertEqual(tc.story_id, 55)

    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_story_testcases')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_updates_existing(self, mock_cfg, mock_cases, mock_detail):
        from apps.testcases.models import TestCase
        from apps.projects.models import Project
        from apps.requirement_analysis.models import Requirement
        mock_cfg.return_value = mock.MagicMock()
        mock_detail.return_value = {
            'id': 55, 'product': 7, 'module': 8, 'title': 'X', 'spec': '',
        }
        mock_cases.return_value = [{
            'id': 300, 'title': 'c1-updated', 'precondition': '',
            'steps': [], 'type': 'feature', 'pri': 2,
        }]
        p = Project.objects.create(name='p', owner=self.user)
        req = Requirement.objects.create(
            project=p, source_type='zentao', title='X', zentao_id=55,
        )
        TestCase.objects.create(
            project=p, author=self.user, title='old', steps='[]',
            priority='medium', zentao_case_id=300, requirement=req,
        )

        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'product', 'scope_id': 7, 'story_ids': [55], 'project_id': p.id},
            format='json',
        )
        body = resp.json()
        self.assertEqual(body['updated'], 1)
        self.assertEqual(body['created'], 0)
        self.assertEqual(TestCase.objects.get(zentao_case_id=300).title, 'c1-updated')

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_requires_args(self, mock_cfg):
        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'product', 'scope_id': 7, 'story_ids': [], 'project_id': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
