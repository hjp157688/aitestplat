from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.api_testing import services
from apps.api_testing.models import ApiProject, ApiRequest, ApiCollection
from apps.api_testing.services import ApiTestCaseGenerator


class SaveVariablesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='sv', password='x12345')
        self.project = ApiProject.objects.create(name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        col = ApiCollection.objects.create(name='C', project=self.project)
        self.req = ApiRequest.objects.create(name='登录', method='POST', url='http://x/api/login',
                                             body={'type': 'json', 'data': {'username': '{{login_username}}'}},
                                             collection=col, created_by=self.user)
        services._generation_tasks.clear()
        self.task_id = 'APITASK_SV'
        services._generation_tasks[self.task_id] = {
            'status': 'completed',
            'result': {},
            'known_data': {
                'environment': {'token': 't1'},
                'known_data': [{'name': 'login_username', 'value': 'zhangsan'}],
                'history': [],
            },
        }

    def test_save_backfills_case_variables_and_reports_pending(self):
        cases = [{
            'request_id': self.req.id,
            'name': '登录-正向',
            'params_override': {},
            'body_override': {'username': '{{login_username}}', 'password': '{{login_password}}', 'code': '{{code}}'},
            'assertions': [{'type': 'status_code', 'operator': 'equals', 'expected': 200}],
        }]
        res = ApiTestCaseGenerator.save_generated_cases(self.task_id, cases, self.user, project_id=self.project.id)
        new_req = ApiRequest.objects.get(parent_request_id=self.req.id)
        self.assertEqual(new_req.variables['login_username'], 'zhangsan')
        self.assertNotIn('login_password', new_req.variables)      # 无已知值不写入
        self.assertEqual(res['pending_variables'], ['code', 'login_password'])
        # 只回填"被引用且已知"的键：本用例引用 login_username/login_password/code，
        # 已知池含 login_username、token（token 未被引用）→ 写入 1 个
        self.assertEqual(res['variables_count'], 1)