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
        self.assertTrue(any(r.response_schemas for r in requests))
        # URL 使用 base_url 模板（统一 snake_case，与环境变量 key 一致）
        self.assertTrue(all(r.url.startswith('{{base_url}}') for r in requests))
