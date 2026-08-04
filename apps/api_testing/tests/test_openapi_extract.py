# apps/api_testing/tests/test_openapi_extract.py
"""EndpointExtractor / SecurityExtractor 单元测试：Swagger 2.0 兼容性"""
from django.test import SimpleTestCase

from apps.api_testing.openapi.endpoints import EndpointExtractor
from apps.api_testing.openapi.security import SecurityExtractor


SWAGGER2_BASE = {
    'swagger': '2.0',
    'info': {'title': 'Test', 'version': '1.0'},
    'securityDefinitions': {
        'basic': {'type': 'basic'},
    },
    'security': [{'basic': []}],
}


class EndpointExtractorSwagger2Tests(SimpleTestCase):

    def setUp(self):
        self.extractor = EndpointExtractor()

    def test_body_parameter_becomes_request_body(self):
        """Swagger 2.0 的 in:body 参数应转为 request_body"""
        spec = dict(SWAGGER2_BASE, paths={
            '/pet': {
                'post': {
                    'operationId': 'createPet',
                    'consumes': ['application/json'],
                    'parameters': [
                        {'name': 'body', 'in': 'body', 'required': True,
                         'schema': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
                         'description': '宠物对象'},
                    ],
                    'responses': {'200': {'description': 'ok'}},
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)

        self.assertEqual(endpoint['parameters'], [])  # body 参数不进入普通 parameters
        self.assertIsNotNone(endpoint['request_body'])
        rb = endpoint['request_body']
        self.assertEqual(rb['content_type'], 'application/json')
        self.assertEqual(rb['required'], True)
        self.assertEqual(rb['description'], '宠物对象')
        self.assertEqual(rb['schema']['properties']['name']['type'], 'string')
        self.assertIsInstance(rb['example'], dict)

    def test_formdata_parameters_become_form_body(self):
        """Swagger 2.0 的 formData 参数应转为 form-data request_body"""
        spec = dict(SWAGGER2_BASE, paths={
            '/login': {
                'post': {
                    'operationId': 'loginUser',
                    'consumes': ['application/x-www-form-urlencoded'],
                    'parameters': [
                        {'name': 'username', 'in': 'formData', 'required': True, 'type': 'string'},
                        {'name': 'password', 'in': 'formData', 'required': True, 'type': 'string'},
                    ],
                    'responses': {'200': {'description': 'ok'}},
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)

        self.assertIsNotNone(endpoint['request_body'])
        rb = endpoint['request_body']
        self.assertIn('form', rb['content_type'])
        self.assertEqual(rb['required'], True)
        self.assertEqual(rb['schema']['type'], 'object')
        self.assertIn('username', rb['schema']['properties'])
        self.assertIn('password', rb['schema']['properties'])
        # formData 参数不应重复出现在普通 parameters 中
        self.assertFalse(any(p['in'] == 'formData' for p in (endpoint['parameters'] or [])))

    def test_response_schema_is_extracted(self):
        """Swagger 2.0 响应直接挂在 schema 字段，应被提取"""
        schema = {'type': 'object', 'properties': {'id': {'type': 'integer'}}}
        spec = dict(SWAGGER2_BASE, paths={
            '/pet/{petId}': {
                'get': {
                    'operationId': 'getPet',
                    'parameters': [
                        {'name': 'petId', 'in': 'path', 'required': True, 'type': 'integer'},
                    ],
                    'responses': {
                        '200': {'description': 'ok', 'schema': schema},
                        '404': {'description': 'not found'},
                    },
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)

        self.assertIn('200', endpoint['response_schemas'])
        self.assertEqual(endpoint['response_schemas']['200']['properties']['id']['type'], 'integer')
        self.assertNotIn('404', endpoint['response_schemas'])


class EndpointExtractorOpenAPI3Tests(SimpleTestCase):
    """确保 OpenAPI 3.x 原有路径不被 Swagger 2.0 支持破坏"""

    def setUp(self):
        self.extractor = EndpointExtractor()

    def test_openapi3_request_body_and_response(self):
        spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test', 'version': '1.0'},
            'paths': {
                '/pets': {
                    'post': {
                        'operationId': 'createPet',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {'type': 'object',
                                               'properties': {'name': {'type': 'string'}}},
                                },
                            },
                        },
                        'responses': {
                            '200': {'description': 'ok',
                                    'content': {'application/json': {
                                        'schema': {'type': 'object'}}}},
                        },
                    },
                },
            },
            'components': {
                'securitySchemes': {
                    'BearerAuth': {'type': 'http', 'scheme': 'bearer'},
                },
            },
        }
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['request_body']['content_type'], 'application/json')
        self.assertIn('200', endpoint['response_schemas'])


class SecurityExtractorSwagger2Tests(SimpleTestCase):

    def setUp(self):
        self.extractor = SecurityExtractor()

    def test_security_definitions_supported(self):
        """Swagger 2.0 的 securityDefinitions 应生成全局认证头"""
        spec = dict(SWAGGER2_BASE, paths={
            '/pet': {'get': {'operationId': 'listPets',
                             'responses': {'200': {'description': 'ok'}}}},
        })
        result = self.extractor.extract(spec)

        self.assertTrue(result['global'])
        header = result['global'][0]
        self.assertEqual(header['key'], 'Authorization')
        self.assertIn('Basic', header['value'])

    def test_no_security_definitions_returns_empty(self):
        spec = {'openapi': '3.0.0',
                'paths': {'/pets': {'get': {'responses': {'200': {'description': 'ok'}}}}}}
        result = self.extractor.extract(spec)
        self.assertEqual(result, {'global': [], 'by_operation_id': {}})
