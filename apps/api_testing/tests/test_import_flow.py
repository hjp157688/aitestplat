# apps/api_testing/tests/test_import_flow.py
"""OpenAPI 导入全流程集成测试：解析真实文件 → 导入 Collection"""
import os

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.api_testing.models import ApiCollection, ApiProject, ApiRequest
from apps.api_testing.services import OpenAPIParser

MEDIA_FILE = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', 'media',
    'api_docs', '2026', '08', '默认模块.swagger_4pBxUWE.json',
)
MEDIA_FILE = os.path.abspath(MEDIA_FILE)


class ImportFlowTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='openapi_tester', password='x12345')
        self.project = ApiProject.objects.create(
            name='P', owner=self.user, project_type='HTTP', status='NOT_STARTED')
        self.collection = ApiCollection.objects.create(
            name='Imported', project=self.project, order=1)

    def test_parse_and_import_real_swagger2_file(self):
        """真实 Swagger 2.0 文件应能解析并导入，保留请求体与响应 schema"""
        self.assertTrue(os.path.exists(MEDIA_FILE), MEDIA_FILE)

        result = OpenAPIParser.parse(MEDIA_FILE)
        self.assertGreater(result['endpoint_count'], 0)
        self.assertEqual(result['spec_version'], 'swagger_2.0')

        count = OpenAPIParser.import_to_collection(
            result['endpoints'][:3], self.collection.id, self.user,
            base_url='https://api.example.com',
        )
        self.assertEqual(count, 3)

        requests = list(ApiRequest.objects.filter(collection=self.collection).order_by('order'))
        self.assertEqual(len(requests), 3)
        # 导入的数据应带请求体 / 响应 schema / 认证头
        self.assertTrue(any(
            r.body.get('type') in ('json', 'x-www-form-urlencoded', 'form-data')
            for r in requests
        ) or any(r.request_schema for r in requests))
        # 表单类请求体（form-data / x-www-form-urlencoded）的 data 必须是行数组，
        # 而不是 {key: value} 字典——只有行数组前端才能正确展示、生成代码、执行
        for r in requests:
            if r.body.get('type') in ('x-www-form-urlencoded', 'form-data'):
                data = r.body.get('data')
                self.assertIsInstance(data, list)
                for row in data:
                    self.assertIn('key', row)
                    self.assertIn('value', row)
        self.assertTrue(any(r.response_schemas for r in requests))
        # URL 使用 base_url 模板（统一 snake_case，与环境变量 key 一致）
        self.assertTrue(all(r.url.startswith('{{base_url}}') for r in requests))

    def test_import_preserves_doc_example_content(self):
        """真实文档里参数自带的示例内容（x-example 等）应导入为参数值，而非空占位符"""
        result = OpenAPIParser.parse(MEDIA_FILE)

        # 找到第一个带示例内容 query 参数的端点
        target = None
        for ep in result['endpoints']:
            if any(p.get('in') == 'query' and p.get('x-example') is not None
                   for p in ep.get('parameters') or []):
                target = ep
                break
        self.assertIsNotNone(target, '真实文档应存在带 x-example 的 query 参数')

        count = OpenAPIParser.import_to_collection(
            [target], self.collection.id, self.user,
            base_url='https://api.example.com',
        )
        self.assertEqual(count, 1)
        request = ApiRequest.objects.get(collection=self.collection)

        target_param = next(p for p in target['parameters']
                            if p.get('in') == 'query' and p.get('x-example') is not None)
        imported = {p['key']: p['value'] for p in request.params or []}
        # 文档自带的示例内容应导入为参数值，而非空占位符
        self.assertTrue(str(target_param['x-example']) != '')
        self.assertEqual(imported.get(target_param['name']), str(target_param['x-example']))

    def test_import_persists_path_params_and_response_examples(self):
        """path_params（in:path 参数行）与 response_examples（按状态码的响应示例）应落库"""
        result = OpenAPIParser.parse(MEDIA_FILE)

        target = next(
            (ep for ep in result['endpoints']
             if any(p.get('in') == 'path' for p in ep.get('parameters') or [])
             or bool(ep.get('response_examples'))),
            None)
        self.assertIsNotNone(target, '真实文档应存在带 path 参数 / 响应示例的端点')

        count = OpenAPIParser.import_to_collection(
            [target], self.collection.id, self.user,
            base_url='https://api.example.com',
        )
        self.assertEqual(count, 1)
        request = ApiRequest.objects.get(collection=self.collection)

        # path 参数：URL 保留模板 {name}，同时有可编辑的行
        has_path = any(p.get('in') == 'path' for p in target.get('parameters') or [])
        if has_path:
            self.assertIn('{', request.url)
            self.assertTrue(request.path_params)
        # 响应示例：按状态码存到 response_examples
        if target.get('response_examples'):
            self.assertTrue(request.response_examples)
            for status, example in target['response_examples'].items():
                self.assertEqual(request.response_examples.get(status), example)
