"""接口管理树节点批量操作后端测试"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.api_testing.models import (
    ApiProject, ApiCollection, ApiRequest,
    TestSuite, TestSuiteRequest, OperationLog,
)


class GenerateCapTests(TestCase):
    """generate-testcases 批量上限防御"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cap', password='x12345')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_too_many_requests_rejected(self):
        with patch(
            'apps.api_testing.services.ApiTestCaseGenerator.generate',
            return_value='task-1',
        ):
            resp = self.client.post(
                '/api/api-testing/requests/generate-testcases/',
                {'request_ids': list(range(1, 22))}, format='json',
            )
        self.assertEqual(resp.status_code, 400)

    def test_empty_list_rejected(self):
        resp = self.client.post(
            '/api/api-testing/requests/generate-testcases/',
            {'request_ids': []}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_within_limit_forwards_to_generator(self):
        with patch(
            'apps.api_testing.services.ApiTestCaseGenerator.generate',
            return_value='task-1',
        ) as mock_gen:
            resp = self.client.post(
                '/api/api-testing/requests/generate-testcases/',
                {'request_ids': [1, 2, 3]}, format='json',
            )
        self.assertEqual(resp.status_code, 201)
        mock_gen.assert_called_once()


class BatchDeleteBase(TestCase):
    """通用 setUp：用户/项目/集合/请求"""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='bop', password='x12345')
        self.other = User.objects.create_user(username='other', password='x12345')
        self.project = ApiProject.objects.create(
            name='P', owner=self.user, project_type='HTTP', status='NOT_STARTED')
        self.other_project = ApiProject.objects.create(
            name='Other', owner=self.other, project_type='HTTP', status='NOT_STARTED')

        self.collection = ApiCollection.objects.create(
            name='C', project=self.project, order=1)
        self.sub_collection = ApiCollection.objects.create(
            name='Sub', project=self.project, parent=self.collection, order=1)

        self.request_a = ApiRequest.objects.create(
            collection=self.collection, name='A', method='GET', url='/a',
            created_by=self.user)
        self.request_b = ApiRequest.objects.create(
            collection=self.sub_collection, name='B', method='POST', url='/b',
            created_by=self.user)
        # 生成用例（父请求的子节点）
        self.case_a = ApiRequest.objects.create(
            collection=self.collection, parent_request=self.request_a,
            name='A-case', method='GET', url='/a', created_by=self.user)
        # 他人项目下的请求（本用户无权）
        self.other_request = ApiRequest.objects.create(
            collection=None, name='OtherReq', method='GET', url='/other',
            created_by=self.other)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _batch_delete(self, **kwargs):
        return self.client.post(
            '/api/api-testing/requests/batch-delete/', kwargs, format='json')


class BatchDeleteTests(BatchDeleteBase):

    def test_mixed_delete_counts_and_cascade(self):
        resp = self._batch_delete(
            collection_ids=[self.collection.id],
            request_ids=[self.request_b.id],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['deleted_collections'], 1)
        self.assertEqual(data['deleted_requests'], 1)
        # 级联：父集合 + 子集合 + 其中请求 + 生成用例全部消失
        self.assertFalse(ApiCollection.objects.filter(id=self.collection.id).exists())
        self.assertFalse(ApiCollection.objects.filter(id=self.sub_collection.id).exists())
        self.assertFalse(ApiRequest.objects.filter(id=self.request_a.id).exists())
        self.assertFalse(ApiRequest.objects.filter(id=self.case_a.id).exists())
        self.assertFalse(ApiRequest.objects.filter(id=self.request_b.id).exists())

    def test_delete_request_cascades_generated_cases(self):
        resp = self._batch_delete(request_ids=[self.request_a.id])
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApiRequest.objects.filter(id=self.case_a.id).exists())
        self.assertTrue(ApiRequest.objects.filter(id=self.request_b.id).exists())

    def test_unauthorized_requests_excluded(self):
        resp = self._batch_delete(request_ids=[self.other_request.id])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['deleted_requests'], 0)
        self.assertEqual(data['rejected_requests'], 1)
        self.assertTrue(ApiRequest.objects.filter(id=self.other_request.id).exists())

    def test_requests_under_deleted_collection_deduped(self):
        resp = self._batch_delete(
            collection_ids=[self.collection.id],
            request_ids=[self.request_a.id],
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['deleted_requests'], 0)
        self.assertFalse(ApiRequest.objects.filter(id=self.request_a.id).exists())

    def test_empty_body_rejected(self):
        resp = self._batch_delete()
        self.assertEqual(resp.status_code, 400)

    def test_deleted_logs_written_only_for_permitted(self):
        self._batch_delete(
            collection_ids=[self.collection.id],
            request_ids=[self.other_request.id],
        )
        self.assertEqual(
            OperationLog.objects.filter(
                resource_type='collection', resource_id=self.collection.id,
                operation_type='delete').count(), 1)
        self.assertEqual(
            OperationLog.objects.filter(
                resource_type='request', resource_id=self.other_request.id,
                operation_type='delete').count(), 0)


class CreateSuiteFromRequestsTests(BatchDeleteBase):
    """create-from-requests + add-requests 归属校验"""

    def test_create_suite_links_requests_in_order_and_dedup(self):
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {
                'project_id': self.project.id,
                'name': 'LoginSuite',
                'request_ids': [self.request_b.id, self.request_a.id, self.request_a.id],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data['added_count'], 2)
        suite = TestSuite.objects.get(id=data['id'])
        self.assertEqual(suite.name, 'LoginSuite')
        self.assertEqual(suite.created_by, self.user)
        links = list(TestSuiteRequest.objects.filter(
            test_suite=suite).order_by('order'))
        self.assertEqual([l.request_id for l in links],
                         [self.request_b.id, self.request_a.id])

    def test_requests_from_other_project_excluded(self):
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {
                'project_id': self.project.id,
                'name': 'X',
                'request_ids': [self.other_request.id],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['added_count'], 0)
        self.assertEqual(TestSuite.objects.filter(name='X').count(), 1)

    def test_missing_name_400(self):
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {'project_id': self.project.id, 'request_ids': [self.request_a.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_foreign_environment_400(self):
        from apps.api_testing.models import Environment
        foreign_env = Environment.objects.create(
            scope='GLOBAL', name='ForeignEnv', project=None,
            created_by=self.other)
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {
                'project_id': self.project.id,
                'name': 'Y',
                'environment_id': foreign_env.id,
                'request_ids': [self.request_a.id],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_add_requests_rejects_foreign_requests(self):
        suite = TestSuite.objects.create(
            name='S', project=self.project, created_by=self.user)
        resp = self.client.post(
            f'/api/api-testing/test-suites/{suite.id}/add-requests/',
            {'request_ids': [self.other_request.id, self.request_a.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['added_count'], 1)
        self.assertEqual(data['rejected_count'], 1)
        self.assertTrue(
            TestSuiteRequest.objects.filter(
                test_suite=suite, request=self.request_a).exists())
        self.assertFalse(
            TestSuiteRequest.objects.filter(
                test_suite=suite, request=self.other_request).exists())

    def test_create_suite_writes_operation_log(self):
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {'project_id': self.project.id, 'name': 'LogSuite',
             'request_ids': [self.request_a.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        suite = TestSuite.objects.get(id=resp.json()['id'])
        self.assertEqual(
            OperationLog.objects.filter(
                resource_type='suite', resource_id=suite.id,
                operation_type='create').count(), 1)
