from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.api_testing.models import ApiProject, ApiKnownData


class KnownDataApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='kdapi', password='x12345')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = ApiProject.objects.create(name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')

    def test_create_and_list(self):
        resp = self.client.post('/api/api-testing/api-known-data/', {
            'project': self.project.id, 'name': 'login_username', 'value': 'zhangsan', 'description': '测试账号',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp = self.client.get(f'/api/api-testing/api-known-data/?project={self.project.id}')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'login_username')

    def test_update(self):
        kd = ApiKnownData.objects.create(project=self.project, name='n', value='v', created_by=self.user)
        resp = self.client.patch(f'/api/api-testing/api-known-data/{kd.id}/', {'value': 'v2'}, format='json')
        self.assertEqual(resp.status_code, 200)
        kd.refresh_from_db()
        self.assertEqual(kd.value, 'v2')


class KnownDataApiSecurityTests(TestCase):
    """跨项目权限隔离：用户 B 不能访问用户 A 项目的已知测试数据"""

    def setUp(self):
        self.user_a = get_user_model().objects.create_user(username='kda', password='x12345')
        self.user_b = get_user_model().objects.create_user(username='kdb', password='x12345')
        self.project_a = ApiProject.objects.create(name='PA', owner=self.user_a, project_type='HTTP', status='IN_PROGRESS')
        self.project_b = ApiProject.objects.create(name='PB', owner=self.user_b, project_type='HTTP', status='IN_PROGRESS')
        self.kd_a = ApiKnownData.objects.create(project=self.project_a, name='secret', value='s3cret', created_by=self.user_a)
        self.kd_b = ApiKnownData.objects.create(project=self.project_b, name='public', value='hello', created_by=self.user_b)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def test_user_b_list_with_project_a_param_returns_empty(self):
        """用户B 按 project=A 过滤 → 0 条（不应看到A的数据）"""
        client_b = self._client(self.user_b)
        resp = client_b.get(f'/api/api-testing/api-known-data/?project={self.project_a.id}')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 0)

    def test_user_b_list_without_project_sees_only_own_records(self):
        """用户B 不带 project 过滤 → 只看到B的记录，看不到A的"""
        client_b = self._client(self.user_b)
        resp = client_b.get('/api/api-testing/api-known-data/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'public')
        self.assertEqual(rows[0]['project'], self.project_b.id)

    def test_user_b_cannot_create_into_project_a(self):
        """用户B POST 带 A 的 project id → 400（project 不在可选范围内）"""
        client_b = self._client(self.user_b)
        resp = client_b.post('/api/api-testing/api-known-data/', {
            'project': self.project_a.id, 'name': 'hack', 'value': 'bad',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_user_b_cannot_patch_project_a_record(self):
        """用户B PATCH A 的记录 → 404"""
        client_b = self._client(self.user_b)
        resp = client_b.patch(f'/api/api-testing/api-known-data/{self.kd_a.id}/', {'value': 'hacked'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_delete_project_a_record(self):
        """用户B DELETE A 的记录 → 404"""
        client_b = self._client(self.user_b)
        resp = client_b.delete(f'/api/api-testing/api-known-data/{self.kd_a.id}/')
        self.assertEqual(resp.status_code, 404)