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
