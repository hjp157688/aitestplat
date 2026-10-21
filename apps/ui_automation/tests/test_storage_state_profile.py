"""BrowserProfile 注入 storage_state 的测试（不真正启动浏览器）。"""
import asyncio
from unittest import mock

from django.test import TestCase

from apps.ui_automation.ai_base import BaseBrowserAgent


def _bare_agent(storage_state=None):
    """绕过 __init__ 的模型配置校验，仅测 profile 构造。"""
    agent = BaseBrowserAgent.__new__(BaseBrowserAgent)
    agent.storage_state = storage_state
    agent.enable_gif = False
    agent.case_name = 'test'
    return agent


class StorageStateProfileTests(TestCase):
    def test_profile_includes_storage_state_when_given(self):
        agent = _bare_agent({'cookies': [], 'origins': []})
        profile = agent._create_browser_profile()
        self.assertEqual(profile.storage_state, {'cookies': [], 'origins': []})

    def test_profile_without_storage_state_unchanged(self):
        agent = _bare_agent(None)
        profile = agent._create_browser_profile()
        self.assertIsNone(profile.storage_state)

    def test_export_storage_state_from_session(self):
        agent = _bare_agent(None)

        class FakeSession:
            async def get_storage_state(self):
                return {'cookies': [{'name': 'sid'}]}

        agent.browser_session = FakeSession()
        state = asyncio.run(agent.export_storage_state())
        self.assertEqual(state, {'cookies': [{'name': 'sid'}]})

    def test_export_storage_state_missing_session_returns_none(self):
        agent = _bare_agent(None)
        self.assertIsNone(asyncio.run(agent.export_storage_state()))
