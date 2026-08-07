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

    def test_save_normalizes_generated_assertions(self):
        """保存生成用例时统一断言 schema：path→json_path、补 name/operator，编辑器可正常展示"""
        cases = [{
            'request_id': self.req.id,
            'name': '登录-查id',
            'body_override': {'username': '{{login_username}}'},
            'assertions': [
                {'type': 'status_code', 'operator': 'equals', 'expected': 200},
                {'type': 'json_path', 'operator': 'exists', 'path': '$.id'},
            ],
        }]
        ApiTestCaseGenerator.save_generated_cases(
            self.task_id, cases, self.user, project_id=self.project.id, suite_name='登录套件')

        new_req = ApiRequest.objects.get(parent_request_id=self.req.id)
        stored = {a['type']: a for a in new_req.assertions}
        # json_path 断言字段名归一到 json_path，name/operator 补齐
        self.assertEqual(stored['json_path'], {
            'type': 'json_path', 'operator': 'exists', 'json_path': '$.id', 'name': 'JSON $.id 存在',
        })
        self.assertEqual(stored['status_code']['name'], '状态码等于200')

        # 套件关联的断言同样归一化
        from apps.api_testing.models import TestSuiteRequest, TestSuite
        suite = TestSuite.objects.get(name='登录套件')
        suite_assertions = TestSuiteRequest.objects.get(test_suite=suite).assertions
        suite_stored = {a['type']: a for a in suite_assertions}
        self.assertEqual(suite_stored['status_code']['name'], '状态码等于200')