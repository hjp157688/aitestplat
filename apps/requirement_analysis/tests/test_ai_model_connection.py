# -*- coding: utf-8 -*-
"""AI 模型连接测试按角色分流测试

verify: tokenizer/embedding 角色走 /embeddings 测试，其余角色走 /chat/completions
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase


def _cfg(role):
    return SimpleNamespace(role=role, base_url='https://api.example.com/v1', model_name='model-x')


class AiModelConnectionTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.requirement_analysis.views import _test_ai_model_connection
        cls.helper = staticmethod(_test_ai_model_connection)

    def test_tokenizer_role_uses_embeddings_endpoint(self):
        from apps.requirement_analysis.models import AIModelService
        with mock.patch.object(
            AIModelService, 'generate_embeddings', return_value=[[0.1, 0.2, 0.3]]
        ) as m:
            result = self.helper(_cfg('tokenizer'))
        m.assert_called_once()
        m.assert_called_once_with(_cfg('tokenizer'), ['连接测试'])
        self.assertTrue(result['success'])
        self.assertIn('向量维度: 3', result['response'])

    def test_embedding_role_uses_embeddings_endpoint(self):
        from apps.requirement_analysis.models import AIModelService
        with mock.patch.object(
            AIModelService, 'generate_embeddings', return_value=[[0.1] * 5]
        ) as m:
            result = self.helper(_cfg('embedding'))
        m.assert_called_once()
        self.assertTrue(result['success'])
        self.assertIn('向量维度: 5', result['response'])

    def test_writer_role_uses_chat_endpoint(self):
        from apps.requirement_analysis.models import AIModelService
        resp = {'choices': [{'message': {'content': '连接成功'}}]}
        with mock.patch.object(
            AIModelService, 'call_openai_compatible_api', return_value=resp
        ) as m:
            result = self.helper(_cfg('writer'))
        m.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['response'], '连接成功')

    def test_embedding_error_reports_failure(self):
        from apps.requirement_analysis.models import AIModelService
        with mock.patch.object(
            AIModelService, 'generate_embeddings', side_effect=Exception('404 Not Found')
        ):
            result = self.helper(_cfg('tokenizer'))
        self.assertFalse(result['success'])
        self.assertIn('404 Not Found', result['message'])
