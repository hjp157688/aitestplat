# -*- coding: utf-8 -*-
"""apps.ai 网关——纯函数与 DB 行为测试（auth / resolver / observability / prompt registry）。"""

import asyncio
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai import auth, observability, resolver
from apps.ai.models import AiCallRecord, AiModelPricing
from apps.ai.prompt_registry import content_hash, get_prompt, get_prompt_content
from apps.requirement_analysis.models import AIModelConfig, PromptConfig

User = get_user_model()


class AuthHeadersTest(TestCase):
    def test_bearer_provider(self):
        headers = auth.build_headers('deepseek', 'k1')
        self.assertEqual(headers['Authorization'], 'Bearer k1')
        self.assertNotIn('api-key', headers)

    def test_api_key_provider_qwen(self):
        headers = auth.build_headers('qwen', 'k1')
        self.assertEqual(headers['api-key'], 'k1')
        self.assertNotIn('Authorization', headers)

    def test_azure_provider(self):
        headers = auth.build_headers('azure_openai', 'k1')
        self.assertEqual(headers['api-key'], 'k1')
        self.assertNotIn('Authorization', headers)

    def test_anthropic_provider(self):
        headers = auth.build_headers('anthropic', 'k1')
        self.assertEqual(headers['x-api-key'], 'k1')
        self.assertEqual(headers['anthropic-version'], '2023-06-01')

    def test_url_version_normalization(self):
        self.assertEqual(
            auth.build_url('https://api.deepseek.com', '/chat/completions', 'deepseek'),
            'https://api.deepseek.com/v1/chat/completions')
        self.assertEqual(
            auth.build_url('https://api.deepseek.com/v1', '/chat/completions', 'deepseek'),
            'https://api.deepseek.com/v1/chat/completions')
        self.assertEqual(
            auth.build_url('https://open.bigmodel.cn/api/paas/v4', '/chat/completions', 'zhipu'),
            'https://open.bigmodel.cn/api/paas/v4/chat/completions')
        self.assertEqual(
            auth.build_url('https://x/openai/v1/chat/completions', '/chat/completions', 'deepseek'),
            'https://x/openai/v1/chat/completions')

    def test_azure_url_appends_api_version(self):
        url = auth.build_url('https://my-azure.openai.azure.com/openai/v1', '/chat/completions',
                             'azure_openai', '2024-02-15-preview')
        self.assertTrue(url.endswith('?api-version=2024-02-15-preview'))
        url2 = auth.build_url('https://my-azure.openai.azure.com/openai/v1', '/chat/completions',
                              'azure_openai', None)
        self.assertNotIn('api-version', url2)


class ResolverTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='x')
        self.other = User.objects.create_user(username='bob', password='x')

    def _config(self, **kw):
        defaults = dict(
            name='cfg', model_type='deepseek', role='writer', api_key='k',
            base_url='https://api.deepseek.com', model_name='deepseek-chat',
            is_active=True, created_by=self.user,
        )
        defaults.update(kw)
        return AIModelConfig.objects.create(**defaults)

    def test_role_only_lookup_ignores_model_type(self):
        """回归：model_type=None 必须匹配任意提供商（旧实现 IS NULL 永远不匹配）。"""
        self._config(role='writer', model_type='qwen')
        cfg = resolver.ConfigResolver.active(role='writer', model_type=None)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.model_type, 'qwen')

    def test_ignores_inactive(self):
        self._config(role='writer', is_active=False)
        self.assertIsNone(resolver.ConfigResolver.active(role='writer'))

    def test_model_type_filter(self):
        self._config(role='writer', model_type='deepseek')
        self._config(role='writer', model_type='qwen')
        cfg = resolver.ConfigResolver.active(role='writer', model_type='qwen')
        self.assertEqual(cfg.model_type, 'qwen')

    def test_priority_fallback(self):
        # tokenizer 未配置 -> embedding -> writer 兜底
        self._config(role='writer')
        cfg = resolver.ConfigResolver.active_by_priority(
            resolver.ConfigResolver.EMBEDDING_ROLE_PRIORITY)
        self.assertEqual(cfg.role, 'writer')

    def test_user_scope(self):
        self._config(role='writer', created_by=self.user)
        self._config(role='writer', created_by=self.other)
        cfg = resolver.ConfigResolver.active(role='writer', user=self.user, scope='user')
        self.assertEqual(cfg.created_by, self.user)

    def test_get_active_config_none_model_type_fixed(self):
        """AIModelConfig.get_active_config(None, role) 现在能正确匹配。"""
        self._config(role='writer', model_type='zhipu')
        cfg = AIModelConfig.get_active_config(model_type=None, role='writer')
        self.assertIsNotNone(cfg)


class ObservabilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='carol', password='x')

    def test_emit_success_creates_record(self):
        observability.emit('deepseek', 'deepseek-chat', 'writer', 'success',
                           latency_ms=12, prompt_tokens=10, completion_tokens=5,
                           config_id=1, created_by_id=self.user.id)
        rec = AiCallRecord.objects.get(config_id=1)
        self.assertEqual(rec.status, 'success')
        self.assertEqual(rec.total_tokens, 15)
        self.assertEqual(rec.scenario, 'general')

    def test_emit_failure_creates_failed_record(self):
        observability.emit('qwen', 'qwen-plus', 'api_testcase_generator', 'failed',
                           error_message='timeout', latency_ms=3000)
        rec = AiCallRecord.objects.get(status='failed')
        self.assertEqual(rec.provider, 'qwen')
        self.assertIn('timeout', rec.error_message)

    def test_scenario_contextvar(self):
        token = observability.set_scenario('writer')
        try:
            observability.emit('deepseek', 'm', 'writer', 'success', latency_ms=1)
        finally:
            observability.reset_scenario(token)
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.scenario, 'writer')

    def test_estimate_cost_with_pricing(self):
        AiModelPricing.objects.create(provider='deepseek', model_keyword='',
                                      input_per_million=0.14, output_per_million=0.28)
        cost = observability.estimate_cost('deepseek', 'deepseek-chat', 1_000_000, 1_000_000)
        self.assertAlmostEqual(cost, 0.42, places=6)


class PromptRegistryTest(TestCase):
    """注：迁移 0011 已把 9 类种子写入 prompt_config，此处用自定义类型避免与种子数据耦合。"""
    CTEST = 'ctest_placeholder'

    def setUp(self):
        self.user = User.objects.create_user(username='dave', password='x')
        PromptConfig.objects.filter(prompt_type=self.CTEST).delete()

    def tearDown(self):
        PromptConfig.objects.filter(prompt_type=self.CTEST).delete()

    def test_fallback_when_unseeded(self):
        content = get_prompt_content('no_such_prompt_xyz', default='DEFAULT-probe {content}',
                                     content='hello')
        self.assertEqual(content, 'DEFAULT-probe hello')

    def test_active_row_used(self):
        PromptConfig.objects.create(prompt_type=self.CTEST, name='v1', content='OLD',
                                    is_active=True, created_by=self.user)
        self.assertEqual(get_prompt_content(self.CTEST, default='fallback'), 'OLD')

    def test_latest_version_selected(self):
        # 尚无 version 字段时（Phase C 前），默认取最新创建的行
        PromptConfig.objects.create(prompt_type=self.CTEST, name='a', content='A',
                                    is_active=True, created_by=self.user)
        PromptConfig.objects.create(prompt_type=self.CTEST, name='b', content='B',
                                    is_active=True, created_by=self.user)
        self.assertEqual(get_prompt_content(self.CTEST), 'B')

    def test_seeded_writer_available(self):
        """迁移 0011 后 writer 应有真实种子行。"""
        row = get_prompt('writer')
        self.assertIsNotNone(row)
        self.assertTrue(row.is_seeded)
        self.assertIn('测试用例', row.content)

    def test_seed_all_idempotent(self):
        """内容未变化时重复 seed 不新增行。"""
        from apps.ai import prompt_seeds
        before = PromptConfig.objects.count()
        prompt_seeds.seed_all(force=False)
        after = PromptConfig.objects.count()
        self.assertEqual(before, after)

    def test_content_hash(self):
        self.assertEqual(content_hash('abc'), content_hash('abc'))
        self.assertNotEqual(content_hash('abc'), content_hash('abd'))
