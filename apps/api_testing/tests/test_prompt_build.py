from unittest.mock import patch

from django.test import SimpleTestCase
from apps.api_testing.services import ApiTestCaseGenerator


class BuildPromptTests(SimpleTestCase):
    @patch('apps.ai.prompt_registry.get_prompt_content_raw', return_value='fake system prompt')
    def test_known_data_embedded_in_user_message(self, _mock):
        requests_data = [{'id': 1, 'name': '登录', 'method': 'POST', 'url': '/api/login',
                          'headers': {}, 'params': {}, 'body': {}, 'description': ''}]
        known_data = {
            'environment': {'base_url': 'http://x'},
            'known_data': [{'name': 'login_username', 'value': 'zhangsan'}],
            'history': [],
        }
        _, user_msg = ApiTestCaseGenerator.build_prompt(requests_data, known_data)
        self.assertIn('login_username', user_msg)
        self.assertIn('zhangsan', user_msg)

    @patch('apps.ai.prompt_registry.get_prompt_content_raw', return_value='fake system prompt')
    def test_known_data_empty_when_none(self, _mock):
        _, user_msg = ApiTestCaseGenerator.build_prompt([{'id': 1}])
        self.assertNotIn('项目已知数据', user_msg)