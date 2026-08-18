import asyncio
import json
from datetime import timedelta
from unittest import mock
from django.test import TransactionTestCase
from django.utils import timezone
import requests
from apps.agent.tools.api_testing_run import (
    list_api_test_suites, list_api_requests, run_api_request,
    run_api_test_suite, get_api_execution)
from apps.agent.service_identity import get_service_user
from apps.api_testing.models import (
    ApiProject, ApiCollection, ApiRequest, TestSuite, TestSuiteRequest, TestExecution)


def _fake_response():
    r = requests.Response()
    r.status_code = 200
    r._content = b'{"id": 1}'
    r.headers['content-type'] = 'application/json'
    r.url = 'http://example.com/user/1'
    r.elapsed = timedelta(milliseconds=12)
    return r


# 工具函数已异步化（asyncio.to_thread 在工作线程执行 Django ORM），
# 工作线程用独立连接只能看到已提交数据，故用 TransactionTestCase。
class ApiRunTests(TransactionTestCase):
    def setUp(self):
        self.user = get_service_user()
        self.proj = ApiProject.objects.create(name='API-Proj', owner=self.user)
        self.col = ApiCollection.objects.create(name='Coll', project=self.proj)
        self.req = ApiRequest.objects.create(
            name='GetUser', method='GET', url='http://example.com/user/1',
            collection=self.col, request_type='HTTP', created_by=self.user)

    def test_list_filters(self):
        suites = json.loads(asyncio.run(list_api_test_suites(project_id=self.proj.id)))
        reqs = json.loads(asyncio.run(list_api_requests(project_id=self.proj.id)))
        self.assertIsInstance(reqs, list)
        self.assertEqual(len(reqs), 1)

    @mock.patch('apps.api_testing.views.requests.request', return_value=_fake_response())
    def test_run_api_request(self, mock_request):
        out = json.loads(asyncio.run(run_api_request(self.req.id)))
        self.assertNotIn('error', out)
        self.assertEqual(out.get('status_code'), 200)
        mock_request.assert_called_once()

    @mock.patch('apps.api_testing.views.requests.request', return_value=_fake_response())
    def test_run_api_test_suite(self, mock_request):
        suite = TestSuite.objects.create(name='Smoke', project=self.proj, created_by=self.user)
        TestSuiteRequest.objects.create(test_suite=suite, request=self.req, order=0, assertions=[])
        out = json.loads(asyncio.run(run_api_test_suite(suite.id)))
        self.assertNotIn('error', out)
        self.assertIn('id', out)

    def test_get_api_execution(self):
        suite = TestSuite.objects.create(name='Smoke', project=self.proj, created_by=self.user)
        ex = TestExecution.objects.create(
            test_suite=suite, status='COMPLETED', start_time=timezone.now(),
            executed_by=self.user, total_requests=1, passed_requests=1,
            failed_requests=0, results=[])
        out = json.loads(asyncio.run(get_api_execution(ex.id)))
        self.assertEqual(out['status'], 'COMPLETED')
        self.assertIn('results', out)

    def test_run_api_request_not_found(self):
        out = json.loads(asyncio.run(run_api_request(999999)))
        self.assertIn('error', out)
