# -*- coding: utf-8 -*-
"""ZentaoService 单元测试：mock requests，不发起真实网络请求

覆盖重构后的同步实现（httpx/async → requests/同步，参考禅道连接实现方式）。
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.requirement_analysis.services import ZentaoService


def _cfg(url='https://zentao.example.com'):
    return SimpleNamespace(
        zentao_url=url,
        zentao_account='admin',
        zentao_password='secret123',
    )


def _resp(status_code=201, payload=None, text=''):
    payload = payload if payload is not None else {}
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload,
        text=text,
    )


class ZentaoGetTokenTests(SimpleTestCase):

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_returns_token_on_201(self, mock_post):
        mock_post.return_value = _resp(201, {'token': 'abc123'})
        token = ZentaoService._get_token(_cfg())
        self.assertEqual(token, 'abc123')

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_posts_token_url_with_account_password(self, mock_post):
        mock_post.return_value = _resp(201, {'token': 'abc123'})
        ZentaoService._get_token(_cfg())
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://zentao.example.com/api.php/v1/tokens')
        self.assertEqual(
            kwargs['json'],
            {'account': 'admin', 'password': 'secret123'},
        )
        self.assertEqual(kwargs['headers'], {'Accept': 'application/json'})
        self.assertFalse(kwargs['verify'])
        self.assertEqual(kwargs['timeout'], 10)

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_raises_when_token_field_missing(self, mock_post):
        mock_post.return_value = _resp(201, {'foo': 'bar'})
        with self.assertRaisesRegex(Exception, '返回数据中无token字段'):
            ZentaoService._get_token(_cfg())

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_raises_on_http_error(self, mock_post):
        mock_post.return_value = _resp(401, text='Unauthorized')
        with self.assertRaisesRegex(Exception, 'HTTP 401'):
            ZentaoService._get_token(_cfg())

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_raises_on_timeout(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout()
        with self.assertRaisesRegex(Exception, '连接禅道超时'):
            ZentaoService._get_token(_cfg())

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_raises_on_connect_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError()
        with self.assertRaisesRegex(Exception, '无法连接到禅道服务器'):
            ZentaoService._get_token(_cfg())

    @mock.patch('apps.requirement_analysis.services.requests.post')
    def test_raises_clear_message_on_ssl_error(self, mock_post):
        # SSLError 是 ConnectionError 的子类，必须先于 ConnectionError 捕获
        import requests
        mock_post.side_effect = requests.exceptions.SSLError('UNEXPECTED_EOF_WHILE_READING')
        with self.assertRaisesRegex(Exception, 'HTTPS 连接被中断'):
            ZentaoService._get_token(_cfg())


class ZentaoCallApiTests(SimpleTestCase):

    def _patch_token(self):
        return mock.patch.object(
            ZentaoService, '_get_token', return_value='token-xyz'
        )

    @mock.patch('apps.requirement_analysis.services.requests.get')
    def test_get_returns_data_with_token_header(self, mock_get):
        with self._patch_token():
            mock_get.return_value = _resp(200, {'products': [{'id': 1}]})
            data = ZentaoService._call_api(_cfg(), '/api.php/v1/products')
        self.assertEqual(data, {'products': [{'id': 1}]})
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], 'https://zentao.example.com/api.php/v1/products')
        self.assertEqual(kwargs['headers'], {'Token': 'token-xyz'})

    @mock.patch('apps.requirement_analysis.services.requests.get')
    def test_raises_when_api_returns_error_field(self, mock_get):
        with self._patch_token():
            mock_get.return_value = _resp(200, {'error': 'not allowed'})
            with self.assertRaisesRegex(Exception, '禅道API返回错误: not allowed'):
                ZentaoService._call_api(_cfg(), '/api.php/v1/products')

    @mock.patch('apps.requirement_analysis.services.requests.get')
    def test_raises_clear_message_on_ssl_error(self, mock_get):
        import requests
        with self._patch_token():
            mock_get.side_effect = requests.exceptions.SSLError('EOF occurred')
            with self.assertRaisesRegex(Exception, 'HTTPS 连接被中断'):
                ZentaoService._call_api(_cfg(), '/api.php/v1/products')

    @mock.patch('apps.requirement_analysis.services.requests.get')
    def test_trailing_slash_in_url_is_normalized(self, mock_get):
        with self._patch_token():
            mock_get.return_value = _resp(200, {})
            ZentaoService._call_api(_cfg('https://zentao.example.com/'), '/api.php/v1/products')
        args, _ = mock_get.call_args
        self.assertEqual(args[0], 'https://zentao.example.com/api.php/v1/products')


class ZentaoPublicMethodsTests(SimpleTestCase):

    def test_get_products_returns_list(self):
        with mock.patch.object(
            ZentaoService, '_call_api', return_value={'products': [{'id': 1}]}
        ) as m:
            result = ZentaoService.get_products(_cfg())
        m.assert_called_once_with(_cfg(), '/api.php/v1/products?page=1&limit=100000')
        self.assertEqual(result, [{'id': 1}])

    def test_test_connection_success_masks_token(self):
        with mock.patch.object(ZentaoService, '_get_token', return_value='abcdefghijkl'):
            result = ZentaoService.test_connection(_cfg())
        self.assertTrue(result['success'])
        self.assertEqual(result['token'], 'abcdefgh...')
        self.assertEqual(result['message'], '连接成功')

    def test_test_connection_failure_reports_message(self):
        with mock.patch.object(
            ZentaoService, '_get_token', side_effect=Exception('无法连接到禅道服务器')
        ):
            result = ZentaoService.test_connection(_cfg())
        self.assertFalse(result['success'])
        self.assertIn('无法连接到禅道服务器', result['message'])
