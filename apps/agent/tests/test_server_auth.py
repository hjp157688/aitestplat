import json
from unittest import IsolatedAsyncioTestCase
from django.core.management import CommandError, load_command_class
from django.test import TestCase, override_settings
from apps.agent.server import build_server

EXPECTED_TOOLS = [
    'list_projects', 'list_data_factory_tools', 'generate_test_data',
    'generate_testcases_from_text', 'get_generation_task', 'adopt_generated_testcases',
    'generate_api_testcases', 'get_api_generation_task', 'save_api_testcases',
    'list_api_test_suites', 'list_api_requests', 'run_api_request', 'run_api_test_suite',
    'get_api_execution',
    'run_ui_automation_adhoc', 'get_ui_execution', 'stop_ui_execution',
]


class ServerTests(TestCase):
    def test_build_server_registers_all_tools(self):
        mcp = build_server()
        names = [t.name for t in mcp._tool_manager.list_tools()]
        for tool in EXPECTED_TOOLS:
            self.assertIn(tool, names)


class CommandTests(TestCase):
    @override_settings(MCP_SERVER_TOKEN=None)
    def test_http_requires_token(self):
        cmd = load_command_class('apps.agent', 'mcp_server')
        with self.assertRaises(CommandError):
            cmd.handle(transport='http', host=None, port=None)


class AuthTests(IsolatedAsyncioTestCase):
    @staticmethod
    def _make_app(token, inner_counts):
        from apps.agent.auth import wrap_auth

        async def inner(scope, receive, send):
            inner_counts['called'] += 1
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})
        return wrap_auth(inner, token)

    async def test_rejects_missing_bearer(self):
        counts = {'called': 0}
        app = self._make_app('sekret', counts)
        sent = []
        async def send(msg):
            sent.append(msg)
        await app({'type': 'http', 'headers': [(b'authorization', b'Bearer wrong')]}, None, send)
        self.assertEqual(sent[0]['status'], 401)
        self.assertEqual(counts['called'], 0)

    async def test_allows_valid_bearer(self):
        counts = {'called': 0}
        app = self._make_app('sekret', counts)
        sent = []
        async def send(msg):
            sent.append(msg)
        await app({'type': 'http', 'headers': [(b'authorization', b'Bearer sekret')]}, None, send)
        self.assertEqual(sent[0]['status'], 200)
        self.assertEqual(counts['called'], 1)
