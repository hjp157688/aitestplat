from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.api_testing import services
from apps.api_testing.models import ApiProject, ApiRequest, ApiCollection, Environment
from apps.api_testing.services import ApiTestCaseGenerator


class _Snoop:
    """记录 _run_generation 收到的实参，避免真实线程/AI 调用。"""
    received = None


class GenerationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='gf', password='x12345')
        self.project = ApiProject.objects.create(name='P', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        col = ApiCollection.objects.create(name='C', project=self.project)
        self.req = ApiRequest.objects.create(name='登录', method='POST', url='http://x/api/login', collection=col, created_by=self.user)
        self.env = Environment.objects.create(name='dev', scope='LOCAL', project=self.project, is_active=True,
                                              variables={'token': 't1'}, created_by=self.user)
        services._generation_tasks.clear()

    @patch.object(ApiTestCaseGenerator, '_call_ai', return_value={'test_cases': {}})
    @patch.object(ApiTestCaseGenerator, '_run_generation')
    def test_generate_passes_environment_id(self, mock_run, mock_ai):
        ApiTestCaseGenerator.generate([self.req.id], None, self.user, environment_id=self.env.id)
        # _run_generation 调用为位置参数 (task_id, request_ids, config_id, user, environment_id)
        _, args, _ = mock_run.mock_calls[0]
        self.assertEqual(args[4], self.env.id)

    @patch.object(ApiTestCaseGenerator, '_call_ai', return_value={'test_cases': {}})
    @patch.object(ApiTestCaseGenerator, '_run_generation')
    def test_serializer_accepts_environment_id(self, mock_run, mock_ai):
        from apps.api_testing.serializers import TestCaseGenerationRequestSerializer
        s = TestCaseGenerationRequestSerializer(data={'request_ids': [self.req.id], 'ai_config_id': None, 'environment_id': self.env.id})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['environment_id'], self.env.id)


class GenerationTaskKnownDataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='gf2', password='x12345')
        self.project = ApiProject.objects.create(name='P2', owner=self.user, project_type='HTTP', status='IN_PROGRESS')
        col = ApiCollection.objects.create(name='C', project=self.project)
        self.req = ApiRequest.objects.create(name='登录', method='POST', url='http://x/api/login', collection=col, created_by=self.user)
        self.env = Environment.objects.create(name='dev', scope='LOCAL', project=self.project, is_active=True,
                                              variables={'token': 't1'}, created_by=self.user)
        services._generation_tasks.clear()

        # 创建一个激活的 api_testcase_generator 配置，避免 _run_generation 在 config_id=None 时
        # 调用 ConfigResolver.active 查库失败
        from apps.requirement_analysis.models import AIModelConfig
        self.ai_config = AIModelConfig.objects.create(
            name='test-gen-config',
            model_type='deepseek',
            role='api_testcase_generator',
            api_key='sk-test',
            base_url='https://api.deepseek.com',
            model_name='deepseek-chat',
            is_active=True,
            scope='global',
            created_by=self.user,
        )

    @patch.object(ApiTestCaseGenerator, '_call_ai',
                  return_value={'test_cases': {'1': [{'name': '正向'}]}})
    def test_run_generation_stores_known_data_and_passes_to_prompt(self, mock_ai):
        from unittest.mock import patch as _p
        # 直接调用 _run_generation 需要预先初始化任务状态（generate() 会做这一步）
        services._generation_tasks['APITASK_T'] = {
            'status': 'pending', 'progress': 0, 'result': None, 'error': None, 'known_data': None,
        }
        with _p.object(ApiTestCaseGenerator, 'build_prompt',
                       return_value=('sys', 'user')) as mock_bp:
            ApiTestCaseGenerator._run_generation('APITASK_T', [self.req.id], None, self.user, environment_id=self.env.id)
        # build_prompt 收到 known_data
        args, kwargs = mock_bp.call_args
        self.assertIsNotNone(kwargs.get('known_data'))
        self.assertEqual(kwargs['known_data']['environment']['token'], 't1')
        task = services._generation_tasks['APITASK_T']
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['known_data']['environment']['token'], 't1')

    @patch.object(ApiTestCaseGenerator, '_call_ai',
                  return_value={'test_cases': {'1': [{'name': '正向'}]}})
    def test_run_generation_sends_example_and_schema_to_prompt(self, mock_ai):
        """生成用例时，响应 schema/示例、路径参数示例都应随请求数据发给 AI"""
        self.req.path_params = [{'key': 'id', 'value': '42', 'enabled': True, 'required': True}]
        self.req.params = [{'key': 'kw', 'value': '示例词', 'enabled': True}]
        self.req.response_schemas = {'200': {'type': 'object', 'properties': {'code': {'type': 'integer'}}}}
        self.req.response_examples = {'200': {'code': 0, 'msg': '成功'}}
        self.req.save()

        services._generation_tasks['APITASK_T'] = {
            'status': 'pending', 'progress': 0, 'result': None, 'error': None, 'known_data': None,
        }
        with patch.object(ApiTestCaseGenerator, 'build_prompt',
                          return_value=('sys', 'user')) as mock_bp:
            ApiTestCaseGenerator._run_generation('APITASK_T', [self.req.id], None, self.user, environment_id=self.env.id)

        args, _ = mock_bp.call_args
        rd = args[0][0]
        self.assertEqual(rd['path_params'][0]['value'], '42')
        self.assertEqual(rd['params'][0]['value'], '示例词')
        self.assertEqual(rd['response_examples'], {'200': {'code': 0, 'msg': '成功'}})
        self.assertEqual(rd['response_schemas']['200']['properties']['code']['type'], 'integer')