"""禅道用例「直接搜索」导入测试（mock ZentaoService 网络层）

覆盖两块：
1. 搜索代理端点 /api/requirement-analysis/zentao/testcases/search/
   （真实走 ZentaoService.search_testcases，只 mock 禅道 REST 数据源）
2. 导入端点 /api/testcases/zentao-import/ 的 case_ids 模式与
   _run_zentao_import_by_cases 运行期逻辑（同步调用，避免线程竞态）
"""
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.testcases.views import _run_zentao_task

User = get_user_model()

# 模拟禅道 /products/{id}/testcases 列表返回（字段与禅道 REST v1 对齐）
ZENTAO_CASES = [
    {'id': 'case_101', 'title': '登录功能验证', 'story': 55, 'pri': 1, 'type': 'feature'},
    {'id': 'case_102', 'title': '注销流程测试', 'story': 0, 'pri': 3, 'type': 'feature'},
    {'id': 'case_103', 'title': '下单冒烟', 'story': None, 'pri': 2, 'type': 'functional'},
]


def _make_detail(case_id, title='登录功能验证', story=0, steps=None):
    return {
        'id': int(str(case_id).split('_')[-1]),
        'title': title,
        'precondition': '已登录',
        'steps': steps if steps is not None else [{'desc': '打开首页', 'expect': '正常'}],
        'pri': 1,
        'type': 'feature',
        'product': 7,
        'module': 3,
        'story': story,
    }


class ZentaoSearchEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('zsearch', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @mock.patch('apps.requirement_analysis.views.ZentaoService.get_products')
    @mock.patch('apps.requirement_analysis.views.ZentaoService.get_product_testcases')
    @mock.patch('apps.requirement_analysis.views.ZentaoConfig.get_active_config')
    def test_search_filters_by_keyword_and_passes_story(self, mock_cfg, mock_cases, mock_products):
        mock_cfg.return_value = mock.MagicMock()
        mock_products.return_value = [{'id': 7, 'name': '演示产品'}]
        mock_cases.return_value = ZENTAO_CASES

        resp = self.client.get('/api/requirement-analysis/zentao/testcases/search/?keyword=测试')
        self.assertEqual(resp.status_code, 200)
        cases = resp.json()['cases']
        # '测试' 命中 case_102 标题（case_101/103 不含）
        self.assertEqual([c['id'] for c in cases], ['case_102'])
        self.assertEqual(cases[0]['product_id'], 7)
        self.assertEqual(cases[0]['product_name'], '演示产品')
        # story 字段透传（0 / None 原样返回）
        self.assertIn('story', cases[0])

    @mock.patch('apps.requirement_analysis.views.ZentaoService.get_products')
    @mock.patch('apps.requirement_analysis.views.ZentaoService.get_product_testcases')
    @mock.patch('apps.requirement_analysis.views.ZentaoConfig.get_active_config')
    def test_search_matches_case_id_case_insensitive(self, mock_cfg, mock_cases, mock_products):
        mock_cfg.return_value = mock.MagicMock()
        mock_products.return_value = [{'id': 7, 'name': '演示产品'}]
        mock_cases.return_value = ZENTAO_CASES

        resp = self.client.get('/api/requirement-analysis/zentao/testcases/search/?keyword=CASE_103')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([c['id'] for c in resp.json()['cases']], ['case_103'])

    @mock.patch('apps.requirement_analysis.views.ZentaoService.get_product_testcases')
    @mock.patch('apps.requirement_analysis.views.ZentaoConfig.get_active_config')
    def test_search_scoped_to_product(self, mock_cfg, mock_cases):
        mock_cfg.return_value = mock.MagicMock()
        mock_cases.return_value = ZENTAO_CASES

        resp = self.client.get(
            '/api/requirement-analysis/zentao/testcases/search/?keyword=登录&product_id=7'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([c['id'] for c in resp.json()['cases']], ['case_101'])
        # 指定产品时不应遍历全部产品
        mock_cases.assert_called_once()

    @mock.patch('apps.requirement_analysis.views.ZentaoConfig.get_active_config')
    def test_search_requires_keyword(self, mock_cfg):
        mock_cfg.return_value = mock.MagicMock()
        resp = self.client.get('/api/requirement-analysis/zentao/testcases/search/')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.requirement_analysis.views.ZentaoConfig.get_active_config')
    def test_search_requires_config(self, mock_cfg):
        mock_cfg.return_value = None
        resp = self.client.get('/api/requirement-analysis/zentao/testcases/search/?keyword=x')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('配置中心', resp.json()['error'])


class ZentaoSearchImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('zimport', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        from apps.projects.models import Project
        self.project = Project.objects.create(name='p', owner=self.user)

    @mock.patch('apps.testcases.views._start_zentao_thread')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_by_case_ids_creates_task(self, mock_cfg, mock_start):
        from apps.testcases.models import ZentaoSyncTask
        mock_cfg.return_value = mock.MagicMock()

        resp = self.client.post(
            '/api/testcases/zentao-import/',
            {'scope_type': 'search', 'case_ids': ['case_101', 'case_102'],
             'project_id': self.project.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        task = ZentaoSyncTask.objects.get(task_id=body['task_id'])
        self.assertEqual(task.task_type, 'import')
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.input_params['case_ids'], ['case_101', 'case_102'])
        self.assertEqual(task.input_params['project_id'], self.project.id)
        mock_start.assert_called_once_with(task)

    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_requires_case_ids_or_story_ids(self, mock_cfg):
        mock_cfg.return_value = mock.MagicMock()
        resp = self.client.post(
            '/api/testcases/zentao-import/', {'project_id': self.project.id}, format='json'
        )
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_testcase_detail')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_runner_with_and_without_story(self, mock_cfg, mock_detail, mock_story):
        from apps.testcases.models import TestCase, ZentaoSyncTask
        from apps.requirement_analysis.models import Requirement

        mock_cfg.return_value = mock.MagicMock()
        # case_101 有 story -> 自动建 Requirement；case_102 无 story -> requirement 留空
        mock_detail.side_effect = lambda config, cid: (
            _make_detail('case_101', story=55) if str(cid) == 'case_101'
            else _make_detail('case_102', title='注销流程测试', story=0)
        )
        mock_story.return_value = {
            'id': 55, 'product': 7, 'module': 3,
            'title': '登录需求', 'spec': 'xx', 'status': 'active',
        }
        task = ZentaoSyncTask.objects.create(
            task_id='s00000000000000000000000000000', task_type='import',
            input_params={'scope_type': 'search', 'case_ids': ['case_101', 'case_102'],
                          'project_id': self.project.id},
            created_by=self.user,
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.status, 'succeeded')
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.result['created'], 2)
        self.assertEqual(task.result['failed'], 0)

        with_story = TestCase.objects.get(zentao_case_id='case_101')
        no_story = TestCase.objects.get(zentao_case_id='case_102')

        # 有 story：自动创建 Requirement 并关联
        self.assertIsNotNone(with_story.requirement)
        req = with_story.requirement
        self.assertEqual(req.zentao_id, 55)
        self.assertEqual(req.source_type, 'zentao')
        self.assertEqual(req.title, '登录需求')
        self.assertEqual(with_story.story_id, 55)
        self.assertEqual(with_story.product_id, 7)
        self.assertEqual(with_story.title, '登录功能验证')
        self.assertEqual(with_story.priority, 'critical')

        # 无 story：requirement 留空，其余字段照常
        self.assertIsNone(no_story.requirement)
        self.assertIsNone(no_story.story_id)
        self.assertEqual(no_story.title, '注销流程测试')
        self.assertEqual(no_story.product_id, 7)
        self.assertEqual(no_story.project_id, self.project.id)

        # Requirement 表只建了一条
        self.assertEqual(Requirement.objects.count(), 1)

    @mock.patch('apps.testcases.views.ZentaoService.get_story_detail')
    @mock.patch('apps.testcases.views.ZentaoService.get_testcase_detail')
    @mock.patch('apps.testcases.views.ZentaoConfig.get_active_config')
    def test_import_runner_dedupes_by_zentao_case_id(self, mock_cfg, mock_detail, mock_story):
        from apps.testcases.models import TestCase, ZentaoSyncTask

        mock_cfg.return_value = mock.MagicMock()
        mock_detail.side_effect = lambda config, cid: _make_detail(str(cid), story=0)
        existing = TestCase.objects.create(
            project=self.project, author=self.user, title='old',
            steps='[]', priority='low', zentao_case_id='case_101',
        )
        task = ZentaoSyncTask.objects.create(
            task_id='d00000000000000000000000000000', task_type='import',
            input_params={'scope_type': 'search', 'case_ids': ['case_101'],
                          'project_id': self.project.id},
        )

        _run_zentao_task(task)

        task.refresh_from_db()
        self.assertEqual(task.result['updated'], 1)
        self.assertEqual(task.result['created'], 0)
        existing.refresh_from_db()
        self.assertEqual(existing.title, '登录功能验证')
        self.assertEqual(TestCase.objects.count(), 1)
