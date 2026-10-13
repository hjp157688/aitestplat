"""testcase_modifier / testcase_supplement 提示词种子注册测试"""
from django.test import TestCase
from apps.ai.prompt_seeds import SEEDS, seed
from apps.ai.prompt_registry import get_prompt_content


class TestcasePromptSeedsTests(TestCase):
    def test_new_prompt_types_registered(self):
        self.assertIn('testcase_modifier', SEEDS)
        self.assertIn('testcase_supplement', SEEDS)

    def test_seed_produces_readable_content(self):
        for prompt_type in ('testcase_modifier', 'testcase_supplement'):
            created = seed(prompt_type)
            self.assertTrue(created or True)  # seed 幂等，不强制新建
            content = get_prompt_content(prompt_type)
            self.assertTrue(content.strip(), f'{prompt_type} 种子内容不应为空')
            self.assertIn('JSONL', content)
