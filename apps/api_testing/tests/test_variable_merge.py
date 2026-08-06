from django.test import SimpleTestCase
from apps.api_testing.utils import merge_variables


class MergeVariablesTests(SimpleTestCase):
    def test_case_overrides_env(self):
        merged = merge_variables({'token': 'env_token', 'u': 'a'}, {'token': 'case_token'})
        self.assertEqual(merged['token'], 'case_token')
        self.assertEqual(merged['u'], 'a')

    def test_empty_case_keeps_env(self):
        self.assertEqual(merge_variables({'a': '1'}, None), {'a': '1'})
        self.assertEqual(merge_variables({'a': '1'}, {}), {'a': '1'})