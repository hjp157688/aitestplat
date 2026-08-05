import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.api_testing.known_data import (
    collect_known_data, build_known_data_prompt, flatten_pool,
)
from apps.api_testing.models import (
    ApiKnownData, ApiProject, ApiRequest, ApiCollection, Environment, RequestHistory,
)


def _mk_user():
    return get_user_model().objects.create_user(username='kd_user', password='x12345')


class CollectKnownDataTests(TestCase):
    def setUp(self):
        self.user = _mk_user()
        self.project = ApiProject.objects.create(name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        self.env = Environment.objects.create(
            name='dev', scope='LOCAL', project=self.project, is_active=True,
            variables={'base_url': 'http://localhost:8000', 'token': 'abc123'},
            created_by=self.user,
        )
        ApiKnownData.objects.create(project=self.project, name='login_username', value='zhangsan', created_by=self.user)
        col = ApiCollection.objects.create(name='C', project=self.project)
        req = ApiRequest.objects.create(name='登录', method='POST', url='http://localhost:8000/api/login', collection=col, created_by=self.user)
        RequestHistory.objects.create(
            request=req, environment=self.env,
            request_data={'params': {}, 'body': {'type': 'json', 'data': {'username': 'zhangsan'}}},
            response_data={'json': {'code': 0, 'data': {'token': 'hist_token', 'user_id': 12}, 'msg': 'ok'}},
            status_code=200, executed_by=self.user,
        )

    def test_collect_known_data_includes_three_sources(self):
        data = collect_known_data(self.project.id, self.env.id)
        self.assertEqual(data['environment']['token'], 'abc123')
        self.assertEqual(data['known_data'][0]['name'], 'login_username')
        self.assertEqual(data['known_data'][0]['value'], 'zhangsan')
        # history：请求字段（username）与响应字段（token）都提炼出来
        self.assertEqual(len(data['history']), 1)
        fields = data['history'][0]['fields']
        self.assertIn('token', fields)
        self.assertEqual(fields['token'], 'hist_token')

    def test_history_only_recent_success(self):
        old = timezone.now() - timedelta(days=60)
        req = ApiRequest.objects.get(name='登录')
        RequestHistory.objects.create(
            request=req, environment=self.env, request_data={}, response_data={'json': {'k': 1}},
            status_code=500, executed_at=old, executed_by=self.user,
        )
        data = collect_known_data(self.project.id, self.env.id)
        self.assertEqual(len(data['history']), 1)  # 旧的 500 记录被排除

    def test_build_known_data_prompt_and_flatten(self):
        data = collect_known_data(self.project.id, self.env.id)
        text = build_known_data_prompt(data)
        self.assertIn('base_url', text)
        self.assertIn('login_username', text)
        pool = flatten_pool(data)
        self.assertEqual(pool['base_url'], 'http://localhost:8000')
        self.assertEqual(pool['login_username'], 'zhangsan')
        self.assertEqual(pool['token'], 'hist_token')