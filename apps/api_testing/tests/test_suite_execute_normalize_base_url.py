# -*- coding: utf-8 -*-
"""自动化测试页 → 套件执行链路回归测试

覆盖 TestSuiteViewSet.execute（前端「自动化测试」页 run 套件走的正是这条链路）：
- 裸相对 URL（/oauth2/oauth/token，无 scheme）→ 自动拼接环境 base_url 再发送
- 绝对 URL 原样发送
- body 按类型正确编码：urlencoded→data、form-data→files、raw→data、json→json

修复前该视图同时漏了 normalize_base_url（裸 URL 抛 requests InvalidURL）和
非 json body 的发送（form/urlencoded/raw 全被丢弃）。
"""
from unittest.mock import patch

import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.api_testing.models import (
    ApiCollection, ApiProject, ApiRequest, Environment, TestSuite, TestSuiteRequest)


class FakeResponse:
    def __init__(self, text='{}', status_code=200):
        self.status_code = status_code
        self.text = text
        self.headers = {'content-type': 'application/json'}

    def json(self):
        return json.loads(self.text)


class SuiteExecuteBase(TestCase):
    """共享夹具：项目 / 集合 / 环境(base_url) / 空套件"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='suiteowner', password='x12345')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = ApiProject.objects.create(
            name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        self.col = ApiCollection.objects.create(name='C', project=self.project)
        self.env = Environment.objects.create(
            name='env1', scope='LOCAL', project=self.project, is_active=True,
            variables={'base_url': 'https://oauth.example.com:8443'}, created_by=self.user)

    def make_suite(self, url, body=None):
        if body is None:
            body = {'type': 'none', 'data': None}
        self.req = ApiRequest.objects.create(
            name='req', method='POST', url=url, collection=self.col,
            body=body, created_by=self.user)
        self.suite = TestSuite.objects.create(
            name='Smoke', project=self.project, environment=self.env, created_by=self.user)
        TestSuiteRequest.objects.create(
            test_suite=self.suite, request=self.req, order=1, assertions=[])
        return self.suite


class SuiteExecuteNormalizeBaseUrlTests(SuiteExecuteBase):
    def setUp(self):
        super().setUp()

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_bare_url_prepends_environment_base_url(self, mock_request):
        suite = self.make_suite('/oauth2/oauth/token',
                                body={'type': 'x-www-form-urlencoded', 'data': [
                                    {'key': 'grant_type', 'value': 'password', 'enabled': True},
                                ]})
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(mock_request.call_count, 1)
        self.assertEqual(
            mock_request.call_args.kwargs['url'],
            'https://oauth.example.com:8443/oauth2/oauth/token')
        self.assertEqual(resp.data['failed_requests'], 0)
        self.assertEqual(resp.data['passed_requests'], 1)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_absolute_url_untouched(self, mock_request):
        suite = self.make_suite('https://api.example.com/v1/oauth/token')
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'], 'https://api.example.com/v1/oauth/token')


class SuiteExecuteBodyEncodingTests(SuiteExecuteBase):
    def setUp(self):
        super().setUp()
        self.headers = {
            'Authorization': 'Bearer {{token}}',
        }

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_urlencoded_body_sent_as_data_not_json(self, mock_request):
        suite = self.make_suite('/oauth2/oauth/token', body={'type': 'x-www-form-urlencoded', 'data': [
            {'key': 'grant_type', 'value': 'password', 'enabled': True},
            {'key': 'userName', 'value': 'admin', 'enabled': True},
            {'key': 'disabled_key', 'value': 'x', 'enabled': False},
        ]})
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs['data'], {'grant_type': 'password', 'userName': 'admin'})
        self.assertNotIn('json', call_kwargs)
        self.assertEqual(resp.data['passed_requests'], 1)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_form_data_sent_as_files(self, mock_request):
        suite = self.make_suite('/upload', body={'type': 'form-data', 'data': [
            {'key': 'file', 'value': 'hello', 'enabled': True},
        ]})
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        call_kwargs = mock_request.call_args.kwargs
        self.assertIn('files', call_kwargs)
        self.assertEqual(call_kwargs['files']['file'][1], 'hello')
        self.assertNotIn('json', call_kwargs)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_raw_body_sent_as_data(self, mock_request):
        suite = self.make_suite('/raw', body={'type': 'raw', 'data': '{"a": 1}'})
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(mock_request.call_args.kwargs['data'], '{"a": 1}')
        self.assertNotIn('json', mock_request.call_args.kwargs)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_json_body_still_sent_as_json(self, mock_request):
        suite = self.make_suite('/json', body={'type': 'json', 'data': {'a': '{{case_var}}'}})
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs['json'], {'a': '{{case_var}}'})
        self.assertNotIn('data', call_kwargs)


class SuiteBatchWithTestcaseTests(SuiteExecuteBase):
    """接口管理批量「创建套件 / 加入已有套件」时，AI 生成的测试用例
    （parent_request 非空的 ApiRequest）也要能作为套件步骤加入。

    后端本就按 ApiRequest.id 收（collection__project 校验），用例 id 直接可过；
    此用例锁定该假设，防止将来后端收紧校验把 testcase 挡在门外。
    """

    def _child_testcase(self):
        """给 self.req 生成一条子测试用例（模拟 AI 生成落库形态）"""
        return ApiRequest.objects.create(
            name=f'{self.req.name} - 正向用例',
            method=self.req.method, url=self.req.url, collection=self.col,
            parent_request=self.req, body=self.req.body,
            assertions=[], created_by=self.user)

    def test_create_from_requests_accepts_testcase_id(self):
        self.make_suite('/oauth2/oauth/token', body={'type': 'json', 'data': {'a': 1}})
        testcase = self._child_testcase()
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {'project_id': self.project.id, 'name': '套件X',
             'request_ids': [self.req.id, testcase.id]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['added_count'], 2)
        suite = TestSuite.objects.get(id=resp.data['id'])
        step_ids = list(suite.testsuiterequest_set.values_list('request_id', flat=True))
        self.assertIn(testcase.id, step_ids)

    def test_add_requests_accepts_testcase_id(self):
        suite = self.make_suite('/oauth2/oauth/token', body={'type': 'json', 'data': {'a': 1}})
        testcase = self._child_testcase()
        resp = self.client.post(
            f'/api/api-testing/test-suites/{suite.id}/add-requests/',
            {'request_ids': [testcase.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['rejected_count'], 0)
        step_ids = list(suite.testsuiterequest_set.values_list('request_id', flat=True))
        self.assertIn(testcase.id, step_ids)


class SuiteImportKeepsAssertionsTests(SuiteExecuteBase):
    """导入套件时保留请求自带的断言。

    否则 AI 生成的测试用例（parent_request 非空、自带断言）导入套件后，
    步骤级断言被硬编码成 [] 丢掉：步骤列表显示 0 条断言、编辑无从下手。
    期望：建步骤时把 request.assertions 复制为步骤级断言。
    """

    ASSERTIONS = [
        {'type': 'json_path', 'json_path': '$.id', 'expected': 1,
         'operator': 'equals', 'name': 'id 等于 1'},
        {'type': 'status_code', 'expected': 200, 'operator': 'equals',
         'name': '状态码为 200'},
    ]

    def test_create_from_requests_copies_request_assertions(self):
        self.make_suite('/user/1', body={'type': 'json', 'data': {}})
        self.req.assertions = self.ASSERTIONS
        self.req.save()
        resp = self.client.post(
            '/api/api-testing/test-suites/create-from-requests/',
            {'project_id': self.project.id, 'name': '套件X',
             'request_ids': [self.req.id]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        step = TestSuite.objects.get(id=resp.data['id']).testsuiterequest_set.first()
        self.assertEqual(step.assertions, self.ASSERTIONS)

    def test_add_requests_copies_request_assertions(self):
        self.make_suite('/user/1', body={'type': 'json', 'data': {}})
        self.req.assertions = self.ASSERTIONS
        self.req.save()
        req2 = ApiRequest.objects.create(
            name='另一条', method='GET', url='http://example.com/x',
            collection=self.col, assertions=self.ASSERTIONS, created_by=self.user)
        resp = self.client.post(
            f'/api/api-testing/test-suites/{self.suite.id}/add-requests/',
            {'request_ids': [req2.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        step = TestSuiteRequest.objects.get(test_suite=self.suite, request=req2)
        self.assertEqual(step.assertions, self.ASSERTIONS)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_execute_result_has_assertions_and_response_body(self, mock_request):
        self.make_suite('/user/1', body={'type': 'json', 'data': {}})
        self.req.assertions = self.ASSERTIONS
        self.req.save()
        resp = self.client.post(f'/api/api-testing/test-suites/{self.suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertEqual(row['response_body'], '{}')
        self.assertEqual(len(row['assertions_results']), 2)
        self.assertEqual(row['assertions_results'][1]['name'], '状态码为 200')
        self.assertIn('passed', row['assertions_results'][1])


class SchedulerExecuteAlignTests(SuiteExecuteBase):
    """scheduler 定时套件执行（utils.execute_test_suite）与 UI 套件执行对齐：
    每条结果也要带断言明细 + 响应体预览，否则定时任务跑出来的执行记录
    在「执行历史→结果」里看不到详细执行过程。"""

    @patch('requests.request', return_value=FakeResponse())
    def test_execute_test_suite_records_response_body_and_assertions(self, mock_request):
        from apps.api_testing.utils import execute_test_suite
        suite = self.make_suite('/user/1', body={'type': 'json', 'data': {}})
        self.req.assertions = [{'type': 'status_code', 'expected': 200,
                                'operator': 'equals', 'name': '状态码'}]
        self.req.save()
        out = execute_test_suite(suite, self.env, self.user)
        self.assertTrue(out['success'], out)
        row = out['results'][0]
        self.assertEqual(row['response_body'], '{}')
        self.assertEqual(len(row['assertions_results']), 1)
        self.assertEqual(row['assertions_results'][0]['name'], '状态码')
        self.assertIn('passed', row['assertions_results'][0])

    @patch('requests.request', return_value=FakeResponse('{"id": 1}'))
    def test_execute_test_suite_includes_request_and_response_content(self, mock_request):
        from apps.api_testing.utils import execute_test_suite
        suite = self.make_suite('/user/1', body={'type': 'json', 'data': {'a': 1}})
        self.req.headers = [{'key': 'X-Test', 'value': 'hello', 'enabled': True}]
        self.req.save()
        out = execute_test_suite(suite, self.env, self.user)
        self.assertTrue(out['success'], out)
        row = out['results'][0]
        self.assertIn('X-Test', row['request_headers'])
        self.assertIn('hello', row['request_headers'])
        self.assertIn('"a": 1', row['request_body'])
        self.assertIn('content-type', row['response_headers'])
        self.assertEqual(row['url'], 'https://oauth.example.com:8443/user/1')


class ExecutionRequestResponseDetailTests(SuiteExecuteBase):
    """执行记录要能回溯「请求内容 + 响应头」，否则执行历史里只看得见状态码/耗时/响应体，
    看不到实际发出去的请求头/参数/请求体。"""

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse('{"id": 1}'))
    def test_execute_result_includes_request_and_response_content(self, mock_request):
        suite = self.make_suite('/user/1', body={'type': 'json', 'data': {'a': 1}})
        self.req.headers = [{'key': 'X-Test', 'value': 'hello', 'enabled': True}]
        self.req.save()
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertEqual(row['url'], 'https://oauth.example.com:8443/user/1')
        self.assertIn('X-Test', row['request_headers'])
        self.assertIn('hello', row['request_headers'])
        self.assertIn('"a": 1', row['request_body'])
        self.assertIn('content-type', row['response_headers'])

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse('{"id": 1}'))
    def test_execute_get_result_includes_params(self, mock_request):
        suite = self.make_suite('/user/1', body={'type': 'none', 'data': None})
        self.req.method = 'GET'
        self.req.params = [{'key': 'page', 'value': '2', 'enabled': True}]
        self.req.save()
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertIn('page', row['request_params'])
        self.assertIn('"2"', row['request_params'])
    """步骤级断言按完整 schema 执行（编辑器/导入覆盖生效）。

    修复前步骤级断言只认 status_code，编辑器里加的 json_path 等其它类型
    在套件执行时被静默忽略 → 编辑断言形同虚设、断言明细也没有这些条目。
    """

    STEP_JSON_ASSERTION = [
        {'type': 'json_path', 'json_path': '$.id', 'expected': 1,
         'operator': 'equals', 'name': 'id=1'},
    ]

    def _suite_with_step(self, assertions, request_assertions=None):
        suite = self.make_suite('/user/1', body={'type': 'json', 'data': {}})
        self.req.assertions = request_assertions or []
        self.req.save()
        step = TestSuiteRequest.objects.get(test_suite=suite, request=self.req)
        step.assertions = assertions
        step.save()
        return suite

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse('{"id": 1}'))
    def test_step_json_path_assertion_evaluated_and_passes(self, mock_request):
        suite = self._suite_with_step(self.STEP_JSON_ASSERTION)
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertTrue(row['passed'])
        self.assertEqual(len(row['assertions_results']), 1)
        self.assertEqual(row['assertions_results'][0]['name'], 'id=1')
        self.assertEqual(resp.data['failed_requests'], 0)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse('{"id": 2}'))
    def test_step_json_path_assertion_fails_when_mismatch(self, mock_request):
        suite = self._suite_with_step(self.STEP_JSON_ASSERTION)
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertFalse(row['passed'])
        self.assertEqual(resp.data['failed_requests'], 1)
        self.assertEqual(len(row['assertions_results']), 1)
        self.assertFalse(row['assertions_results'][0]['passed'])

    def test_step_status_code_legacy_value_key_still_works(self):
        # 旧数据 status_code 用 value 而非 expected，步骤级执行需兼容
        suite = self._suite_with_step([
            {'type': 'status_code', 'value': 200, 'name': '状态码'}])
        with patch('apps.api_testing.views.requests.request',
                   return_value=FakeResponse('{"id": 1}')):
            resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['results'][0]['passed'])

    @patch('requests.request', return_value=FakeResponse('{"id": 1}'))
    def test_scheduler_also_honors_step_json_path_assertion(self, mock_request):
        from apps.api_testing.utils import execute_test_suite
        suite = self._suite_with_step(self.STEP_JSON_ASSERTION)
        out = execute_test_suite(suite, self.env, self.user)
        self.assertTrue(out['success'], out)
        row = out['results'][0]
        self.assertTrue(row['passed'])
        self.assertEqual(len(row['assertions_results']), 1)


class SuiteExecuteCaseVariablesTests(SuiteExecuteBase):
    """套件执行要用上用例级变量（request.variables），并优先于环境变量。

    修复前 TestSuiteViewSet.execute 只合并环境变量，AI 生成的测试用例
    （parent_request 子请求自带 variables）导入套件后，执行时用例变量形同虚设，
    仍然用环境的局部变量 → 与接口管理里单请求执行的行为不一致。
    """

    def _env_and_request(self):
        self.env.variables = {'base_url': 'https://oauth.example.com:8443', 'token': 'ENV_TOKEN'}
        self.env.save()
        suite = self.make_suite('/user/{{token}}', body={'type': 'none', 'data': None})
        self.req.variables = {'token': 'CASE_TOKEN'}
        self.req.save()
        return suite

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_suite_execute_uses_case_variables_over_env(self, mock_request):
        suite = self._env_and_request()
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'],
            'https://oauth.example.com:8443/user/CASE_TOKEN')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_suite_execute_falls_back_to_env_when_no_case_var(self, mock_request):
        suite = self._env_and_request()
        self.req.variables = {}
        self.req.save()
        resp = self.client.post(f'/api/api-testing/test-suites/{suite.id}/execute/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'],
            'https://oauth.example.com:8443/user/ENV_TOKEN')


