# -*- coding: utf-8 -*-
"""EmbeddingService 分词模型配置优先级测试

verify: get_embedding_config 优先返回 tokenizer，其次 embedding，最后 writer
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase


def _make_config(role, active=True, **kwargs):
    from apps.requirement_analysis.models import AIModelConfig
    User = get_user_model()
    user, _ = User.objects.get_or_create(username='test_embed_user')
    defaults = {
        'name': f'{role}-config',
        'model_type': 'other',
        'role': role,
        'api_key': 'sk-test',
        'base_url': 'https://api.example.com/v1',
        'model_name': f'{role}-model',
        'is_active': active,
        'created_by': user,
    }
    defaults.update(kwargs)
    return AIModelConfig.objects.create(**defaults)


class EmbeddingConfigPriorityTests(TestCase):

    def setUp(self):
        from apps.requirement_analysis.embedding_service import EmbeddingService
        self.service = EmbeddingService()

    def test_prioritizes_tokenizer_over_embedding_and_writer(self):
        from apps.requirement_analysis.models import AIModelConfig
        _make_config('writer')
        _make_config('embedding', name='embed-config')
        tokenizer = _make_config('tokenizer', name='tok-config')

        config = self.service.get_embedding_config(refresh=True)
        self.assertIsNotNone(config)
        self.assertEqual(config.id, tokenizer.id)
        self.assertEqual(config.role, 'tokenizer')

    def test_falls_back_to_embedding_when_no_tokenizer(self):
        from apps.requirement_analysis.models import AIModelConfig
        writer = _make_config('writer', name='writer-config')
        embedding = _make_config('embedding', name='embed-config')

        config = self.service.get_embedding_config(refresh=True)
        self.assertEqual(config.id, embedding.id)
        self.assertEqual(config.role, 'embedding')

    def test_falls_back_to_writer_as_last_resort(self):
        from apps.requirement_analysis.models import AIModelConfig
        writer = _make_config('writer', name='writer-config')

        config = self.service.get_embedding_config(refresh=True)
        self.assertEqual(config.id, writer.id)
        self.assertEqual(config.role, 'writer')

    def test_ignores_inactive_tokenizer(self):
        from apps.requirement_analysis.models import AIModelConfig
        _make_config('tokenizer', active=False)
        embedding = _make_config('embedding', name='embed-config')

        config = self.service.get_embedding_config(refresh=True)
        self.assertEqual(config.id, embedding.id)

    def test_none_when_nothing_configured(self):
        config = self.service.get_embedding_config(refresh=True)
        self.assertIsNone(config)

    def test_fresh_query_when_nothing_configured(self):
        # 未配置任何模型时返回 None，且 None 不被缓存（后续新建配置无需手动刷新）
        self.assertIsNone(self.service.get_embedding_config())
        self.assertIsNone(self.service.get_embedding_config())

        _make_config('tokenizer')
        self.assertIsNotNone(self.service.get_embedding_config(), "未配置时应每次重新查询")

    def test_clear_cache(self):
        _make_config('tokenizer')
        self.assertIsNotNone(self.service.get_embedding_config())
        from apps.requirement_analysis.models import AIModelConfig
        AIModelConfig.objects.update(is_active=False)
        self.service.clear_cache()
        self.assertIsNone(self.service.get_embedding_config())

    def test_langchain_adapter_delegates_to_embed(self):
        from apps.requirement_analysis.models import AIModelConfig
        _make_config('tokenizer')
        model = self.service.get_langchain_embedding_model()
        self.assertIsNotNone(model)
        with mock.patch.object(self.service, 'embed', return_value=[[0.1, 0.2]]) as m:
            self.assertEqual(model.embed_documents(['doc']), [[0.1, 0.2]])
        m.assert_called_once_with(['doc'])
        with mock.patch.object(self.service, 'embed_single', return_value=[0.3, 0.4]) as m2:
            self.assertEqual(model.embed_query('q'), [0.3, 0.4])
        m2.assert_called_once_with('q')

    def test_langchain_adapter_none_when_unconfigured(self):
        model = self.service.get_langchain_embedding_model()
        self.assertIsNone(model)
