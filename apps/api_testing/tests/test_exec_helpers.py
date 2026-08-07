# -*- coding: utf-8 -*-
"""执行/导入正确性修复的单元测试：
- RequestConverter._build_body 保留 raw body（text/plain 等）
- RequestConverter 导入 URL 用 {{base_url}} 占位
- utils.normalize_base_url 自动补 base / 去占位符 / 无 base 报中文错误
- utils.request_body_kwargs 按 body_type 正确组装发送参数（urlencoded/form-data/raw/json）
- utils.execute_assertions 支持 operator + path 别名（AI 生成断言语义可执行）
- utils.normalize_assertions 统一断言 schema
"""
import json
from django.test import SimpleTestCase
from unittest.mock import patch

from apps.api_testing.openapi.converter import RequestConverter
from apps.api_testing import utils
from apps.core.variable_resolver import VariableResolver
from requests.structures import CaseInsensitiveDict


class ConverterBodyUrlTests(SimpleTestCase):
    def setUp(self):
        self.converter = RequestConverter()

    def test_raw_content_type_body_preserved(self):
        body = self.converter._build_body({
            'content_type': 'text/plain',
            'example': 'hello world',
        })
        self.assertEqual(body['type'], 'raw')
        self.assertEqual(body['data'], 'hello world')

    def test_xml_raw_example_preserved(self):
        body = self.converter._build_body({
            'content_type': 'application/xml',
            'example': '<a>1</a>',
        })
        self.assertEqual(body['type'], 'raw')
        self.assertEqual(body['data'], '<a>1</a>')

    def test_none_when_no_request_body(self):
        self.assertEqual(self.converter._build_body(None), {'type': 'none', 'data': {}})

    def test_json_still_json(self):
        body = self.converter._build_body({
            'content_type': 'application/json',
            'example': {'a': 1},
        })
        self.assertEqual(body['type'], 'json')
        self.assertEqual(body['data'], {'a': 1})

    def test_url_uses_snake_base_url_placeholder(self):
        data = self.converter.convert(
            {'name': 'x', 'method': 'POST', 'path': '/api/login'}, [], base_url='https://h')
        self.assertTrue(data['url'].startswith('{{base_url}}/api/login'), data['url'])

    def test_url_bare_when_no_base(self):
        data = self.converter.convert(
            {'name': 'x', 'method': 'POST', 'path': '/api/login'}, [], base_url='')
        self.assertEqual(data['url'], '/api/login')


class ParamExampleResolutionTests(SimpleTestCase):
    """_param_example 应按示例载体优先级导入文档自带的示例内容，而不是空占位符"""

    def setUp(self):
        self.converter = RequestConverter()

    def test_yapi_x_example_used(self):
        """YApi 等导出的 x-example 应作为参数值导入（真实文件的常见形态）"""
        val = self.converter._param_example(
            {'name': 'X-API-Key', 'in': 'header', 'type': 'string',
             'x-example': 'uap_api_secret_key_2026'})
        self.assertEqual(val, 'uap_api_secret_key_2026')

    def test_openapi3_example_used(self):
        val = self.converter._param_example(
            {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer'}, 'example': 20})
        self.assertEqual(val, '20')

    def test_examples_map_media_type(self):
        val = self.converter._param_example(
            {'name': 'lat', 'in': 'query',
             'examples': {'application/json': 31.23}})
        self.assertEqual(val, '31.23')

    def test_examples_named_object_unwrapped(self):
        val = self.converter._param_example(
            {'name': 'q', 'in': 'query',
             'examples': {'One': {'summary': '示例', 'value': 'hello'}}})
        self.assertEqual(val, 'hello')

    def test_swagger2_param_default_used(self):
        """Swagger 2.0 的 default 直接挂在参数上，应被采用"""
        val = self.converter._param_example(
            {'name': 'pageSize', 'in': 'query', 'type': 'integer', 'default': 20})
        self.assertEqual(val, '20')

    def test_swagger2_param_enum_first_used(self):
        val = self.converter._param_example(
            {'name': 'sort', 'in': 'query', 'type': 'string', 'enum': ['asc', 'desc']})
        self.assertEqual(val, 'asc')

    def test_schema_default_used(self):
        val = self.converter._param_example(
            {'name': 'p', 'in': 'query', 'schema': {'type': 'string', 'default': 'x'}})
        self.assertEqual(val, 'x')

    def test_schema_format_example(self):
        val = self.converter._param_example(
            {'name': 'd', 'in': 'query', 'schema': {'type': 'string', 'format': 'date'}})
        self.assertEqual(val, '2024-01-01')

    def test_string_without_hint_empty(self):
        """无任何示例提示的 string 参数保持留空，不引入 'string' 占位符"""
        self.assertEqual(self.converter._param_example(
            {'name': 'q', 'in': 'query', 'type': 'string'}), '')

    def test_integer_type_fallback(self):
        self.assertEqual(self.converter._param_example(
            {'name': 'n', 'in': 'query', 'type': 'integer'}), '0')

    def test_number_x_example_as_string(self):
        val = self.converter._param_example(
            {'name': 'X-Timestamp', 'in': 'header', 'type': 'number', 'x-example': 1675000000})
        self.assertEqual(val, '1675000000')

    def test_boolean_lowercased(self):
        val = self.converter._param_example(
            {'name': 'isAll', 'in': 'query', 'type': 'boolean', 'x-example': True})
        self.assertEqual(val, 'true')

    def test_convert_populates_query_and_header_from_x_example(self):
        """端到端：convert 后 query/header 参数值来自文档示例内容"""
        data = self.converter.convert(
            {
                'name': '登录', 'method': 'POST', 'path': '/login',
                'parameters': [
                    {'name': 'username', 'in': 'query', 'type': 'string',
                     'x-example': 'admin', 'required': True},
                    {'name': 'loginType', 'in': 'query', 'type': 'integer',
                     'x-example': 1, 'required': True},
                    {'name': 'X-API-Key', 'in': 'header', 'type': 'string',
                     'x-example': 'secret', 'required': True},
                ],
            },
            [], base_url='https://h',
        )
        params = {p['key']: p['value'] for p in data['params']}
        self.assertEqual(params['username'], 'admin')
        self.assertEqual(params['loginType'], '1')
        headers = {h['key']: h['value'] for h in data['headers']}
        self.assertEqual(headers['X-API-Key'], 'secret')


class ConverterParamRowTests(SimpleTestCase):
    """转换器应输出 path_params，并给 query/header 行补 param_type/required"""

    def setUp(self):
        self.converter = RequestConverter()

    def test_path_param_converted_with_example(self):
        data = self.converter.convert({
            'name': 'GetPet', 'method': 'GET', 'path': '/pet/{petId}',
            'parameters': [
                {'name': 'petId', 'in': 'path', 'required': True, 'type': 'integer',
                 'x-example': 7},
                {'name': 'qw', 'in': 'query', 'type': 'string', 'x-example': 'dog'},
                {'name': 'X-Key', 'in': 'header', 'type': 'string', 'x-example': 'k'},
            ],
        }, [], base_url='https://h')
        # URL 保留路径模板，参数进 path_params
        self.assertEqual(data['url'], '{{base_url}}/pet/{petId}')
        pp = {p['key']: p for p in data['path_params']}
        self.assertEqual(pp['petId']['value'], '7')
        self.assertTrue(pp['petId']['required'])
        self.assertTrue(pp['petId']['enabled'])
        self.assertEqual(pp['petId']['param_type'], 'integer')
        # query/header 行带 param_type/required
        qp = {p['key']: p for p in data['params']}
        self.assertEqual(qp['qw']['param_type'], 'string')
        self.assertEqual(qp['qw']['value'], 'dog')
        hd = {h['key']: h for h in data['headers']}
        self.assertEqual(hd['X-Key']['param_type'], 'string')
        self.assertEqual(hd['X-Key']['value'], 'k')

    def test_convert_emits_response_examples(self):
        data = self.converter.convert({
            'name': 'x', 'method': 'GET', 'path': '/a',
            'response_examples': {'200': {'code': 0}},
        }, [], base_url='')
        self.assertEqual(data['response_examples'], {'200': {'code': 0}})
        self.assertEqual(data['path_params'], [])

    def test_emits_empty_path_params_when_none(self):
        data = self.converter.convert(
            {'name': 'x', 'method': 'GET', 'path': '/a'}, [], base_url='')
        self.assertEqual(data['path_params'], [])


class ReplacePathParamsTests(SimpleTestCase):
    """_replace_path_params 应安全替换单花括号模板，不破坏 {{var}}"""

    def test_basic_substitution(self):
        url = utils._replace_path_params(
            '{{base_url}}/users/{id}', [{'key': 'id', 'value': '42', 'enabled': True}],
            {}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/42')

    def test_does_not_clobber_double_brace_variable(self):
        # {id} 在 {{id}} 里不应被替换（负向后视）
        url = utils._replace_path_params(
            '{{base_url}}/users/{{id}}', [{'key': 'id', 'value': '42', 'enabled': True}],
            {}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/{{id}}')

    def test_disabled_or_empty_row_keeps_placeholder(self):
        url = utils._replace_path_params(
            '{{base_url}}/users/{id}',
            [{'key': 'id', 'value': '42', 'enabled': False},
             {'key': 'x', 'value': '', 'enabled': True}],
            {}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/{id}')

    def test_value_with_variable_and_function_resolved(self):
        url = utils._replace_path_params(
            '{{base_url}}/users/{id}',
            [{'key': 'id', 'value': '{{uid}}', 'enabled': True}],
            {'uid': '999'}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/999')

    def test_dict_form_path_params(self):
        url = utils._replace_path_params(
            '{{base_url}}/users/{id}', {'id': '7'}, {}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/7')

    def test_missing_row_keeps_template(self):
        url = utils._replace_path_params(
            '{{base_url}}/users/{id}', [{'key': 'other', 'value': '1', 'enabled': True}],
            {}, VariableResolver())
        self.assertEqual(url, '{{base_url}}/users/{id}')


class NormalizeBaseUrlTests(SimpleTestCase):
    def test_prepends_base_to_bare_path(self):
        self.assertEqual(
            utils.normalize_base_url('/api/login', {'base_url': 'https://h'}),
            'https://h/api/login')

    def test_prepends_base_case_insensitive_key(self):
        self.assertEqual(
            utils.normalize_base_url('/api/login', {'BaseURL': 'https://h'}),
            'https://h/api/login')

    def test_strips_remaining_camel_placeholder(self):
        # 老数据可能存了 {{baseUrl}}；_replace_variables 不替换，normalize 需剥掉并补 base
        self.assertEqual(
            utils.normalize_base_url('{{baseUrl}}/api/login', {'base_url': 'https://h'}),
            'https://h/api/login')

    def test_absolute_url_untouched(self):
        self.assertEqual(
            utils.normalize_base_url('https://x/api/login', {'base_url': 'https://h'}),
            'https://x/api/login')

    def test_raises_clear_error_when_no_base(self):
        with self.assertRaises(Exception) as ctx:
            utils.normalize_base_url('/api/login', {})
        self.assertIn('base_url', str(ctx.exception))
        self.assertIn('协议', str(ctx.exception))

    def test_nested_current_value_base(self):
        # 环境变量支持 {currentValue, initialValue} 结构，取 currentValue
        self.assertEqual(
            utils.normalize_base_url('/oauth2/oauth/token', {
                'base_url': {'currentValue': 'http://10.0.0.1:9998',
                             'initialValue': 'http://10.0.0.1:9998'},
            }),
            'http://10.0.0.1:9998/oauth2/oauth/token')

    def test_nested_fallback_to_initial_value(self):
        self.assertEqual(
            utils.normalize_base_url('/api/login', {
                'base_url': {'currentValue': '', 'initialValue': 'https://old-h'},
            }),
            'https://old-h/api/login')


class RequestBodyKwargsTests(SimpleTestCase):
    def test_urlencoded_list_to_data_dict(self):
        kwargs = utils.request_body_kwargs('x-www-form-urlencoded', [
            {'key': 'userName', 'value': 'admin', 'enabled': True},
            {'key': 'password', 'value': 'pwd', 'enabled': True},
            {'key': 'skipme', 'value': 'x', 'enabled': False},
        ])
        self.assertEqual(kwargs, {'data': {'userName': 'admin', 'password': 'pwd'}})

    def test_form_data_list_to_files(self):
        kwargs = utils.request_body_kwargs('form-data', [
            {'key': 'username', 'value': 'john', 'enabled': True},
        ])
        self.assertIn('files', kwargs)
        self.assertEqual(kwargs['files']['username'][1], 'john')

    def test_urlencoded_dict_input_compat(self):
        """兼容历史导入的 {key: value} 字典格式 → 与行数组等价的 data dict"""
        kwargs = utils.request_body_kwargs('x-www-form-urlencoded', {
            'userName': 'admin', 'password': 'pwd',
        })
        self.assertEqual(kwargs, {'data': {'userName': 'admin', 'password': 'pwd'}})

    def test_form_data_dict_input_compat(self):
        kwargs = utils.request_body_kwargs('form-data', {'username': 'john'})
        self.assertIn('files', kwargs)
        self.assertEqual(kwargs['files']['username'][1], 'john')

    def test_raw_string_to_data(self):
        self.assertEqual(utils.request_body_kwargs('raw', '<xml/>'), {'data': '<xml/>'})

    def test_json_dict_to_json(self):
        self.assertEqual(utils.request_body_kwargs('json', {'a': 1}), {'json': {'a': 1}})


class _FakeResponse:
    """复刻 requests.Response 行为（headers 大小写不敏感）。"""

    def __init__(self, status_code=200, text='', headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = CaseInsensitiveDict(headers or {})


class ExecuteAssertionsTests(SimpleTestCase):
    """execute_assertions：JSONPath 断言支持 operator / path 别名，AI 生成断言语义可执行"""

    def _json_response(self, payload):
        return _FakeResponse(status_code=200, text=json.dumps(payload),
                             headers={'Content-Type': 'application/json'})

    def test_status_code_equals_default(self):
        res = self._json_response({})
        result = utils.execute_assertions(res, [{'type': 'status_code', 'expected': 200}])
        self.assertTrue(result[0]['passed'])

    def test_status_code_not_equals_operator(self):
        res = self._json_response({})
        result = utils.execute_assertions(res, [{'type': 'status_code', 'operator': 'not_equals', 'expected': 404}])
        self.assertTrue(result[0]['passed'])

    def test_json_path_equals(self):
        res = self._json_response({'id': 5, 'name': 'Buddy'})
        result = utils.execute_assertions(res, [{'type': 'json_path', 'json_path': '$.id', 'expected': 5}])
        self.assertTrue(result[0]['passed'])
        self.assertEqual(result[0]['actual'], 5)

    def test_json_path_path_alias(self):
        # AI 生成的旧格式：path 而非 json_path 也应可执行
        res = self._json_response({'name': 'Buddy'})
        result = utils.execute_assertions(res, [{'type': 'json_path', 'path': '$.name', 'expected': 'Buddy'}])
        self.assertTrue(result[0]['passed'])

    def test_json_path_not_equals(self):
        res = self._json_response({'code': 200})
        result = utils.execute_assertions(
            res, [{'type': 'json_path', 'operator': 'not_equals', 'path': '$.code', 'expected': 500}])
        self.assertTrue(result[0]['passed'])

    def test_json_path_exists_and_not_exists(self):
        res = self._json_response({'data': {'id': 1}})
        exists = utils.execute_assertions(res, [{'type': 'json_path', 'operator': 'exists', 'path': '$.data.id'}])
        self.assertTrue(exists[0]['passed'])
        not_exists = utils.execute_assertions(
            res, [{'type': 'json_path', 'operator': 'not_exists', 'path': '$.data.missing'}])
        self.assertTrue(not_exists[0]['passed'])

    def test_json_path_greater_than(self):
        res = self._json_response({'count': 42})
        result = utils.execute_assertions(
            res, [{'type': 'json_path', 'operator': 'greater_than', 'path': '$.count', 'expected': 40}])
        self.assertTrue(result[0]['passed'])

    def test_json_path_contains(self):
        res = self._json_response({'msg': 'hello world'})
        result = utils.execute_assertions(
            res, [{'type': 'json_path', 'operator': 'contains', 'path': '$.msg', 'expected': 'world'}])
        self.assertTrue(result[0]['passed'])

    def test_json_path_missing_value_fails(self):
        res = self._json_response({'a': 1})
        result = utils.execute_assertions(res, [{'type': 'json_path', 'path': '$.b', 'expected': 1}])
        self.assertFalse(result[0]['passed'])

    def test_header_expected_value(self):
        res = _FakeResponse(headers={'X-Token': 'abc'})
        result = utils.execute_assertions(
            res, [{'type': 'header', 'header_name': 'X-Token', 'expected_value': 'abc'}])
        self.assertTrue(result[0]['passed'])

    def test_header_expected_fallback(self):
        res = _FakeResponse(headers={'X-Token': 'abc'})
        result = utils.execute_assertions(res, [{'type': 'header', 'header_name': 'X-Token', 'expected': 'abc'}])
        self.assertTrue(result[0]['passed'])

    def test_contains_text(self):
        res = _FakeResponse(text='hello world')
        result = utils.execute_assertions(res, [{'type': 'contains', 'expected': 'world'}])
        self.assertTrue(result[0]['passed'])

    def test_response_time_operator_supported(self):
        res = _FakeResponse()
        result = utils.execute_assertions(
            res, [{'type': 'response_time', 'operator': 'less_than', 'expected': 1000, 'actual_time': 500}])
        self.assertTrue(result[0]['passed'])


class NormalizeAssertionsTests(SimpleTestCase):
    """normalize_assertions：path→json_path、补 name/operator，幂等"""

    def test_path_to_json_path(self):
        out = utils.normalize_assertions([{'type': 'json_path', 'operator': 'equals', 'path': '$.id', 'expected': 1}])
        self.assertEqual(out[0]['json_path'], '$.id')
        self.assertNotIn('path', out[0])

    def test_operator_default_and_name_filled(self):
        out = utils.normalize_assertions([{'type': 'json_path', 'path': '$.id', 'expected': 1}])
        self.assertEqual(out[0]['operator'], 'equals')
        self.assertTrue(out[0]['name'])

    def test_generated_name_for_status_code(self):
        out = utils.normalize_assertions([{'type': 'status_code', 'operator': 'equals', 'expected': 200}])
        self.assertEqual(out[0]['name'], '状态码等于200')

    def test_generated_name_for_json_path_exists(self):
        out = utils.normalize_assertions([{'type': 'json_path', 'operator': 'exists', 'path': '$.id'}])
        self.assertEqual(out[0]['name'], 'JSON $.id 存在')

    def test_idempotent(self):
        once = utils.normalize_assertions([{'type': 'json_path', 'operator': 'exists', 'path': '$.id'}])
        twice = utils.normalize_assertions(once)
        self.assertEqual(once, twice)

    def test_skips_non_dict(self):
        out = utils.normalize_assertions([None, 'x', {'type': 'status_code', 'expected': 200}])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['type'], 'status_code')

    def test_unknown_operator_reset_to_equals(self):
        out = utils.normalize_assertions([{'type': 'json_path', 'operator': 'weird', 'path': '$.a'}])
        self.assertEqual(out[0]['operator'], 'equals')

    def test_header_path_mapped_to_header_name(self):
        out = utils.normalize_assertions(
            [{'type': 'header', 'path': 'X-Token', 'expected_value': 'abc'}])
        self.assertEqual(out[0]['header_name'], 'X-Token')
        self.assertNotIn('path', out[0])
