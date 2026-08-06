# -*- coding: utf-8 -*-
"""执行/导入正确性修复的单元测试：
- RequestConverter._build_body 保留 raw body（text/plain 等）
- RequestConverter 导入 URL 用 {{base_url}} 占位
- utils.normalize_base_url 自动补 base / 去占位符 / 无 base 报中文错误
- utils.request_body_kwargs 按 body_type 正确组装发送参数（urlencoded/form-data/raw/json）
"""
from django.test import SimpleTestCase
from unittest.mock import patch

from apps.api_testing.openapi.converter import RequestConverter
from apps.api_testing import utils


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

    def test_raw_string_to_data(self):
        self.assertEqual(utils.request_body_kwargs('raw', '<xml/>'), {'data': '<xml/>'})

    def test_json_dict_to_json(self):
        self.assertEqual(utils.request_body_kwargs('json', {'a': 1}), {'json': {'a': 1}})
