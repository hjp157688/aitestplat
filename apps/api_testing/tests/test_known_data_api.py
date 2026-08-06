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