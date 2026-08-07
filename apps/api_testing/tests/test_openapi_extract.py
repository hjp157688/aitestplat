# apps/api_testing/tests/test_openapi_extract.py
"""EndpointExtractor / SecurityExtractor 单元测试：Swagger 2.0 兼容性"""
from django.test import SimpleTestCase

from apps.api_testing.openapi.endpoints import EndpointExtractor
from apps.api_testing.openapi.security import SecurityExtractor
from apps.api_testing.openapi.example_generator import generate_example


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

    def test_body_param_x_example_preferred(self):
        """Swagger 2.0 in:body 参数带 x-example 时，优先导入示例内容而非按 schema 生成"""
        spec = dict(SWAGGER2_BASE, paths={
            '/login': {
                'post': {
                    'operationId': 'login',
                    'consumes': ['application/json'],
                    'parameters': [
                        {'name': 'body', 'in': 'body', 'required': True,
                         'schema': {'type': 'object', 'properties': {'username': {'type': 'string'}}},
                         'x-example': {'username': 'admin', 'password': 'p@ss'}},
                    ],
                    'responses': {'200': {'description': 'ok'}},
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['request_body']['example'],
                         {'username': 'admin', 'password': 'p@ss'})

    def test_body_param_examples_map_media_type(self):
        spec = dict(SWAGGER2_BASE, paths={
            '/pet': {
                'post': {
                    'operationId': 'createPet',
                    'consumes': ['application/json'],
                    'parameters': [
                        {'name': 'body', 'in': 'body', 'required': True,
                         'schema': {'type': 'object'},
                         'examples': {'application/json': {'name': 'dog'}}},
                    ],
                    'responses': {'200': {'description': 'ok'}},
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['request_body']['example'], {'name': 'dog'})

    def test_openapi3_content_examples_named_object(self):
        """OpenAPI 3 requestBody content 的命名 examples 应解包出 value 作为示例"""
        spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test', 'version': '1.0'},
            'paths': {
                '/pets': {
                    'post': {
                        'operationId': 'createPet',
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {'type': 'object'},
                                    'examples': {
                                        'Dog': {'summary': '狗', 'value': {'name': 'wangcai'}},
                                    },
                                },
                            },
                        },
                        'responses': {'200': {'description': 'ok'}},
                    },
                },
            },
        }
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['request_body']['example'], {'name': 'wangcai'})

    def test_query_param_carries_example_carriers(self):
        """普通参数应透传 x-example / default / enum，供转换阶段填充示例值"""
        spec = dict(SWAGGER2_BASE, paths={
            '/search': {
                'get': {
                    'operationId': 'search',
                    'parameters': [
                        {'name': 'kw', 'in': 'query', 'type': 'string', 'x-example': '测试'},
                        {'name': 'sort', 'in': 'query', 'type': 'string',
                         'default': 'desc', 'enum': ['asc', 'desc']},
                    ],
                    'responses': {'200': {'description': 'ok'}},
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)
        by_name = {p['name']: p for p in endpoint['parameters']}
        self.assertEqual(by_name['kw']['x-example'], '测试')
        self.assertEqual(by_name['sort']['default'], 'desc')
        self.assertEqual(by_name['sort']['enum'], ['asc', 'desc'])
        self.assertIsNone(by_name['kw']['default'])

    def test_swagger2_response_examples_extracted(self):
        """Swagger 2.0 response 级 examples（媒体类型映射）应提取为响应示例"""
        body = {'account': 'admin', 'code': 0}
        spec = dict(SWAGGER2_BASE, paths={
            '/login': {
                'post': {
                    'operationId': 'login',
                    'responses': {
                        '200': {'description': 'ok', 'schema': {'type': 'object'},
                                'examples': {'application/json': body}},
                        '404': {'description': 'not found'},
                    },
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)
        self.assertIn('200', endpoint['response_examples'])
        self.assertEqual(endpoint['response_examples']['200'], body)
        self.assertNotIn('404', endpoint['response_examples'])

    def test_openapi3_content_example_extracted(self):
        spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test', 'version': '1.0'},
            'paths': {
                '/pets': {
                    'get': {
                        'operationId': 'listPets',
                        'responses': {
                            '200': {'description': 'ok',
                                    'content': {'application/json': {
                                        'schema': {'type': 'array', 'items': {'type': 'string'}},
                                        'example': ['dog', 'cat'],
                                    }}},
                        },
                    },
                },
            },
        }
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['response_examples']['200'], ['dog', 'cat'])

    def test_openapi3_named_examples_unwrapped(self):
        spec = {
            'openapi': '3.0.0',
            'info': {'title': 'Test', 'version': '1.0'},
            'paths': {
                '/pets': {
                    'get': {
                        'operationId': 'listPets',
                        'responses': {
                            '200': {'description': 'ok',
                                    'content': {'application/json': {
                                        'examples': {'One': {'summary': 's', 'value': {'n': 1}}},
                                    }}},
                        },
                    },
                },
            },
        }
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['response_examples']['200'], {'n': 1})

    def test_response_example_falls_back_to_schema_generation(self):
        """无自带示例时按响应 schema 生成示例"""
        spec = dict(SWAGGER2_BASE, paths={
            '/x': {
                'get': {
                    'operationId': 'x',
                    'responses': {
                        '200': {'description': 'ok',
                                'schema': {'type': 'object',
                                           'properties': {'id': {'type': 'integer'}}}},
                    },
                },
            },
        })
        (endpoint,) = self.extractor.extract(spec)
        self.assertEqual(endpoint['response_examples']['200'], {'id': 1})


class GenerateExampleFallbackTests(SimpleTestCase):
    """文档没给示例时，string 字段应留空而不是填 'string' 占位文本"""

    def test_string_without_hint_is_empty(self):
        self.assertEqual(generate_example({'type': 'string'}), '')

    def test_object_string_properties_empty(self):
        self.assertEqual(
            generate_example({'type': 'object', 'properties': {
                'username': {'type': 'string'},
                'age': {'type': 'integer'},
            }}),
            {'username': '', 'age': 1})

    def test_array_of_strings_without_hint(self):
        self.assertEqual(generate_example({'type': 'array', 'items': {'type': 'string'}}), [''])

    def test_unknown_format_is_empty(self):
        self.assertEqual(generate_example({'type': 'string', 'format': 'nosuch'}), '')


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
