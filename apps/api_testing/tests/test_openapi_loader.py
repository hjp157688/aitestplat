# apps/api_testing/tests/test_openapi_loader.py
"""SpecLoader 单元测试：验证递归 schema 与非法字段的宽松解析行为"""
import json
import os
import tempfile

from django.test import SimpleTestCase

from apps.api_testing.openapi import SpecLoader


def _write_json(dir_path, name, obj):
    path = os.path.join(dir_path, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)
    return path


class SpecLoaderTests(SimpleTestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self.loader = SpecLoader()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _openapi3_spec(self, schemas):
        return {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0'},
            'paths': {
                '/cats': {
                    'get': {
                        'responses': {
                            '200': {
                                'description': 'ok',
                                'content': {
                                    'application/json': {
                                        'schema': {'$ref': '#/components/schemas/Category'},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            'components': {'schemas': schemas},
        }

    def test_recursive_schema_does_not_raise(self):
        """递归 schema（Category 含 children 自引用）不应导致解析失败"""
        spec = self._openapi3_spec({
            'Category': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'children': {
                        'type': 'array',
                        'items': {'$ref': '#/components/schemas/Category'},
                    },
                },
            },
        })
        path = _write_json(self.tmpdir, 'recursive.json', spec)

        result = self.loader.load(path)

        schema = result['paths']['/cats']['get']['responses']['200']['content']['application/json']['schema']
        self.assertEqual(schema['type'], 'object')
        self.assertIn('properties', schema)

    def test_lenient_with_minor_invalid_field(self):
        """Swagger 2.0 中 type:'' 等轻微非法字段不应导致解析失败（宽松模式）"""
        spec = {
            'swagger': '2.0',
            'info': {'title': 'Test API', 'version': '1.0'},
            'host': 'example.com',
            'basePath': '/',
            'schemes': ['https'],
            'paths': {
                '/login': {
                    'post': {
                        'parameters': [
                            {'name': 'idCard', 'in': 'formData', 'required': True,
                             'type': '', 'description': '身份证号'},
                        ],
                        'responses': {'200': {'description': 'ok'}},
                    },
                },
            },
        }
        path = _write_json(self.tmpdir, 'swagger2_invalid.json', spec)

        result = self.loader.load(path)

        self.assertEqual(result['swagger'], '2.0')
        self.assertIn('/login', result['paths'])

    def test_unparseable_file_raises_value_error(self):
        """完全无法解析的文件应抛出 ValueError（供上层展示错误信息）"""
        path = os.path.join(self.tmpdir, 'garbage.json')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('this is not json {{{{')

        with self.assertRaises(ValueError):
            self.loader.load(path)
