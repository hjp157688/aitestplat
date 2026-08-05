# -*- coding: utf-8 -*-
"""配置合并映射测试：SERVICE_TYPE_MAP 必须覆盖旧 AIServiceConfig 全部服务类型，且落在统一提供商枚举内。"""

import importlib

from django.test import SimpleTestCase

from apps.ai.providers import PROVIDERS

m = importlib.import_module('apps.api_testing.migrations.0007_merge_ai_service_configs')


class ConfigMergeMappingTest(SimpleTestCase):

    def test_map_covers_all_old_choices(self):
        # 旧 AIServiceConfig.SERVICE_TYPE_CHOICES 的全部 key
        old_choices = ['openai', 'azure', 'anthropic', 'deepseek', 'qwen', 'siliconflow', 'other']
        for old in old_choices:
            self.assertIn(old, m.SERVICE_TYPE_MAP, f'SERVICE_TYPE_MAP 缺少 {old}')

    def test_map_lands_in_unified_providers(self):
        for old, new in m.SERVICE_TYPE_MAP.items():
            self.assertIn(new, PROVIDERS, f'{old} -> {new} 不在统一提供商注册表')

    def test_azure_maps_to_azure_openai(self):
        self.assertEqual(m.SERVICE_TYPE_MAP['azure'], 'azure_openai')
