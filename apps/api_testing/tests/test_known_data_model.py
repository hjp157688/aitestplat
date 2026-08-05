from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.api_testing.models import ApiKnownData, ApiProject, ApiRequest, ApiCollection


class ApiKnownDataModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='kd', password='x12345')
        self.project = ApiProject.objects.create(
            name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')

    def test_apirequest_variables_field(self):
        req = ApiRequest.objects.create(name='R', method='GET', url='http://x', created_by=self.user)
        self.assertEqual(req.variables, {})
        req.variables = {'login_username': 'zhangsan'}
        req.save()
        req.refresh_from_db()
        self.assertEqual(req.variables['login_username'], 'zhangsan')

    def test_apiknowndata_crud(self):
        from django.db import IntegrityError  # noqa
        kd = ApiKnownData.objects.create(
            project=self.project, name='login_username', value='zhangsan',
            description='测试账号', created_by=self.user)
        self.assertEqual(ApiKnownData.objects.filter(project=self.project).count(), 1)
        self.assertEqual(kd.name, 'login_username')