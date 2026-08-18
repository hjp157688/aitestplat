from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class AgentAppTests(SimpleTestCase):
    def test_app_installed(self):
        self.assertIsNotNone(apps.get_app_config('agent'))

    def test_mcp_settings_present(self):
        self.assertTrue(hasattr(settings, 'MCP_SERVER_TOKEN'))
        self.assertEqual(settings.MCP_SERVICE_USER, 'mcp_agent')
        self.assertEqual(settings.MCP_HOST, '0.0.0.0')
        self.assertEqual(settings.MCP_PORT, 8765)
