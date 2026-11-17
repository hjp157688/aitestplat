"""automation_case_converter 提示词种子测试。"""
from django.test import TestCase

from apps.ai.prompt_registry import get_prompt_content_raw
from apps.ai.prompt_seeds import PROMPT_SEEDS_TYPES, seed


class AutomationConverterSeedTests(TestCase):
    def test_type_registered_and_seeded(self):
        self.assertIn('automation_case_converter', PROMPT_SEEDS_TYPES)
        # 数据迁移 0011 会按 PROMPT_SEEDS_TYPES 预播种（测试库建库时已含该类型），
        # 先清掉既有行以验证 seed() 的新建路径
        from apps.requirement_analysis.models import PromptConfig
        PromptConfig.objects.filter(prompt_type='automation_case_converter').delete()
        self.assertTrue(seed('automation_case_converter'))

    def test_seed_idempotent_and_content(self):
        seed('automation_case_converter')
        self.assertFalse(seed('automation_case_converter'))  # 指纹未变，跳过
        content = get_prompt_content_raw('automation_case_converter')
        self.assertIn('browser-use', content)
        self.assertIn('{{base_url}}', content)   # 占位符约定必须原样保留
        self.assertIn('"action"', content)
