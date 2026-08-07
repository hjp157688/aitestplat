# -*- coding: utf-8 -*-
"""执行链路集成测试：mock 网络层，验证 execute 视图
- 裸相对 URL + 环境 base_url → 实际发送到拼接后的完整地址
- x-www-form-urlencoded 列表 body → 以 data dict（urlencoded）发送而非 json
- 无 scheme 且无 base_url → 返回 400 且带清晰中文错误
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.api_testing.models import ApiCollection, ApiProject, ApiRequest, Environment


class FakeResponse:
    status_code = 200
    text = '{}'
    headers = {'content-type': 'application/json'}

    def json(self):
        return {}


class ExecuteFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='exec', password='x12345')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = ApiProject.objects.create(
            name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        col = ApiCollection.objects.create(name='C', project=self.project)
        self.req = ApiRequest.objects.create(
            name='登录', method='POST', url='/uap-change-service/oauth/token', collection=col,
            body={'type': 'x-www-form-urlencoded', 'data': [
                {'key': 'userName', 'value': 'admin', 'enabled': True},
                {'key': 'password', 'value': 'UZfp==', 'enabled': True},
            ]},
            created_by=self.user,
        )
        self.env = Environment.objects.create(
            name='env1', scope='LOCAL', project=self.project, is_active=True,
            variables={'base_url': 'https://192.168.1.10:9993'}, created_by=self.user,
        )

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_bare_url_prepends_base_and_urlencoded_sent_as_data(self, mock_request):
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        call_kwargs = mock_request.call_args.kwargs
        self.assertEqual(call_kwargs['url'], 'https://192.168.1.10:9993/uap-change-service/oauth/token')
        self.assertEqual(call_kwargs['data'], {'userName': 'admin', 'password': 'UZfp=='})
        self.assertNotIn('json', call_kwargs)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_absolute_url_untouched(self, mock_request):
        self.req.url = 'https://api.example.com/v1/oauth/token'
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'], 'https://api.example.com/v1/oauth/token')

    @patch('apps.api_testing.views.requests.request')
    def test_no_scheme_without_base_returns_clear_error(self, mock_request):
        self.env.variables = {}
        self.env.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        mock_request.assert_not_called()
        msg = str(resp.data.get('error_message', ''))
        self.assertIn('base_url', msg)
        self.assertIn('协议', msg)

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_auth_spec_header_injected_when_not_overridden(self, mock_request):
        """auth_spec 配置的认证头在执行时补进请求头（接口显式同名头优先）"""
        self.req.auth_spec = {'header_name': 'Authorization', 'header_value': 'Bearer {{token}}'}
        self.req.variables = {'token': 'abc123'}
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        headers = mock_request.call_args.kwargs['headers']
        self.assertEqual(headers.get('Authorization'), 'Bearer abc123')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_auth_spec_does_not_override_explicit_header(self, mock_request):
        self.req.auth_spec = {'header_name': 'Authorization', 'header_value': 'Bearer {{token}}'}
        self.req.variables = {'token': 'abc123'}
        self.req.headers = [{'key': 'Authorization', 'value': 'Bearer explicit', 'enabled': True}]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        headers = mock_request.call_args.kwargs['headers']
        self.assertEqual(headers.get('Authorization'), 'Bearer explicit')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_payload_variables_preferred_over_db(self, mock_request):
        """前端本次发送的 variables 优先于 DB 旧值（改完直接发送也生效）"""
        self.req.variables = {'login_user': 'db_user'}
        self.req.body = {'type': 'x-www-form-urlencoded', 'data': [
            {'key': 'userName', 'value': '{{login_user}}', 'enabled': True},
        ]}
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id,
             'variables': {'login_user': 'live_user'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(mock_request.call_args.kwargs['data'], {'userName': 'live_user'})

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_json_body_content_type_corrected(self, mock_request):
        """JSON body 即使带了遗留的 urlencoded Content-Type 头，也按 application/json 发出"""
        self.req.body = {'type': 'json', 'data': {'username': 'admin'}}
        self.req.headers = [
            {'key': 'Content-Type', 'value': 'application/x-www-form-urlencoded', 'enabled': True}]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs['headers'].get('Content-Type'), 'application/json')
        self.assertEqual(kwargs['json'], {'username': 'admin'})

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_path_params_substituted_in_url(self, mock_request):
        """path_params 行数组应替换 URL 里的 {name} 模板"""
        self.req.url = '{{base_url}}/users/{id}/orders?x=1'
        self.req.params = []
        self.req.path_params = [
            {'key': 'id', 'value': '42', 'enabled': True, 'required': True},
        ]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        url = mock_request.call_args.kwargs['url']
        self.assertEqual(url, 'https://192.168.1.10:9993/users/42/orders?x=1')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_path_params_from_payload_preferred(self, mock_request):
        """前端本次发送的 path_params 优先于 DB 值"""
        self.req.url = '{{base_url}}/users/{id}'
        self.req.params = []
        self.req.path_params = [{'key': 'id', 'value': 'db', 'enabled': True}]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id,
             'path_params': [{'key': 'id', 'value': 'live', 'enabled': True}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'],
            'https://192.168.1.10:9993/users/live')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_empty_path_value_keeps_placeholder(self, mock_request):
        """空值的路径参数不替换，保留 {name} 模板避免生成畸形 URL"""
        self.req.url = '{{base_url}}/users/{id}'
        self.req.params = []
        self.req.path_params = [{'key': 'id', 'value': '', 'enabled': True}]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            mock_request.call_args.kwargs['url'],
            'https://192.168.1.10:9993/users/{id}')

    @patch('apps.api_testing.views.requests.request', return_value=FakeResponse())
    def test_list_params_normalized_and_disabled_skipped(self, mock_request):
        """DB 里 params 存行数组时：仅启用且有 key 的行进 query 参数"""
        self.req.params = [
            {'key': 'a', 'value': '1', 'enabled': True},
            {'key': 'b', 'value': '2', 'enabled': False},
        ]
        self.req.save()
        resp = self.client.post(
            f'/api/api-testing/requests/{self.req.id}/execute/',
            {'environment_id': self.env.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(mock_request.call_args.kwargs['params'], {'a': '1'})
