"""BrowserProfile 注入 storage_state 的测试（不真正启动浏览器）。"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase

import apps.ui_automation.ai_base as ai_base_module
from apps.ui_automation.ai_base import BaseBrowserAgent


def _bare_agent(storage_state=None):
    """绕过 __init__ 的模型配置校验，仅测 profile 构造。"""
    agent = BaseBrowserAgent.__new__(BaseBrowserAgent)
    agent.storage_state = storage_state
    agent.enable_gif = False
    agent.case_name = 'test'
    return agent


class _FakeController:
    """替代 browser_use.Controller：action 仅作装饰器，注册动作原样返回。"""

    def action(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


def _make_bare_agent_for_run_task():
    """构造可通过 run_task 前置逻辑的裸 agent（mock 掉 LLM 校验与僵尸进程清理）。"""
    agent = BaseBrowserAgent.__new__(BaseBrowserAgent)
    agent.storage_state = None
    agent.enable_gif = False
    agent.case_name = 'test'
    agent.execution_mode = 'text'
    agent.model_name = 'gpt-x'
    agent.llm = None
    agent._ai_provider = 'other'
    agent._ai_config_id = None

    async def _no_verify():
        return None

    agent._verify_execution_llm = _no_verify
    agent._cleanup_zombie_chrome = lambda: None
    return agent


class StorageStateProfileTests(TestCase):
    def test_profile_includes_storage_state_when_given(self):
        agent = _bare_agent({'cookies': [], 'origins': []})
        profile = agent._create_browser_profile()
        # browser-use 0.10.1 只认文件路径：dict 会被 StorageStateWatchdog 的
        # os.path.exists 静默跳过，登录态从不注入 → 用例被迫重新登录。
        # dict 必须落成临时 JSON 文件后传路径。
        state = profile.storage_state
        self.assertIsInstance(state, str)
        self.assertTrue(os.path.exists(state))
        with open(state, encoding='utf-8') as f:
            self.assertEqual(json.load(f), {'cookies': [], 'origins': []})

    def test_profile_without_storage_state_unchanged(self):
        agent = _bare_agent(None)
        profile = agent._create_browser_profile()
        self.assertIsNone(profile.storage_state)

    def test_profile_storage_state_path_passthrough(self):
        """已是文件路径的 storage_state 原样透传，不重复落盘。"""
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'cookies': [{'name': 'sid'}]}, f)
        try:
            agent = _bare_agent(path)
            profile = agent._create_browser_profile()
            self.assertEqual(profile.storage_state, path)
        finally:
            os.unlink(path)

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


class ExportStorageStateAdaptationTests(TestCase):
    """适配 browser-use 0.10.1 BrowserSession 的真实导出方法与返回类型。"""

    def test_export_prefers_export_storage_state_method(self):
        # browser-use 0.10.1 BrowserSession 的真实方法名是 export_storage_state（返回 dict）
        agent = _bare_agent(None)

        class FakeSession:
            async def export_storage_state(self):
                return {'cookies': [{'name': 'sid'}], 'origins': []}

        agent.browser_session = FakeSession()
        self.assertEqual(
            asyncio.run(agent.export_storage_state()),
            {'cookies': [{'name': 'sid'}], 'origins': []}
        )

    def test_export_json_string_state_is_parsed(self):
        agent = _bare_agent(None)

        class FakeSession:
            async def export_storage_state(self):
                return '{"cookies": [{"name": "sid"}]}'

        agent.browser_session = FakeSession()
        self.assertEqual(asyncio.run(agent.export_storage_state()), {'cookies': [{'name': 'sid'}]})

    def test_export_session_without_exporter_returns_none(self):
        agent = _bare_agent(None)
        agent.browser_session = object()
        self.assertIsNone(asyncio.run(agent.export_storage_state()))


class RunTaskSessionHandoffTests(TestCase):
    """回归：run_task 内创建的 browser-use Agent 持有真正的 BrowserSession，
    必须交接给 self.browser_session，否则 export_storage_state 永远返回 None。
    通过 mock Agent/Controller 验证交接，不启动真实浏览器。"""

    def test_run_task_hands_browser_session_to_self(self):
        class FakeSession:
            async def export_storage_state(self):
                return {'cookies': [{'name': 'sid'}], 'origins': []}

        created_sessions = []

        class FakeAgent:
            def __init__(self, **kwargs):
                self.browser_session = FakeSession()
                self.history = SimpleNamespace(steps=[])
                created_sessions.append(self.browser_session)

            async def run(self, max_steps=None, on_step_end=None):
                return self.history

        agent = _make_bare_agent_for_run_task()

        self.assertIsNone(getattr(agent, 'browser_session', None))
        with mock.patch.object(ai_base_module, 'Agent', FakeAgent), \
                mock.patch.object(ai_base_module, 'Controller', _FakeController):
            asyncio.run(agent.run_task('做点什么'))

        # 交接成功：self.browser_session 指向 run_task 内创建的会话，且可导出登录态
        self.assertIsInstance(agent.browser_session, FakeSession)
        self.assertIs(agent.browser_session, created_sessions[0])
        self.assertEqual(
            asyncio.run(agent.export_storage_state()),
            {'cookies': [{'name': 'sid'}], 'origins': []}
        )

    def test_run_task_resets_stale_session_before_start(self):
        agent = _make_bare_agent_for_run_task()

        class FakeSession:
            async def export_storage_state(self):
                return {'cookies': []}

        stale = FakeSession()
        agent.browser_session = stale

        class FailAgent:
            def __init__(self, **kwargs):
                raise RuntimeError('Agent construction failed')

        with mock.patch.object(ai_base_module, 'Agent', FailAgent), \
                mock.patch.object(ai_base_module, 'Controller', _FakeController):
            with self.assertRaises(RuntimeError):
                asyncio.run(agent.run_task('做点什么'))

        # 异常路径：旧会话已重置，不会误读上一次执行的登录态
        self.assertIsNone(agent.browser_session)


class RunTaskScreenshotSkipTests(TestCase):
    """环境级截图开关：enable_screenshot=False 时，run_task 创建的 Agent
    打上 _skip_step_screenshot 标记（经模块级补丁跳过逐页截图）。"""

    def test_skip_flag_set_when_screenshot_disabled(self):
        from apps.ui_automation import ai_base as ai_base_module

        class FakeAgent:
            def __init__(self, **kwargs):
                self.browser_session = None
                self.history = SimpleNamespace(steps=[])
                self.flags = []

            async def run(self, max_steps=None, on_step_end=None):
                return self.history

        created = []

        class CapturingAgent(FakeAgent):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.kwargs = kwargs
                created.append(self)

        agent = _make_bare_agent_for_run_task()
        agent.enable_screenshot = False
        with mock.patch.object(ai_base_module, 'Agent', CapturingAgent), \
                mock.patch.object(ai_base_module, 'Controller', _FakeController):
            asyncio.run(agent.run_task('做点什么'))
        self.assertEqual(len(created), 1)
        self.assertTrue(created[0]._skip_step_screenshot)
        # 截图关闭时 GIF 一并停用
        self.assertFalse(created[0].kwargs.get('generate_gif'))


class CdpSetCookiesPatchTests(TestCase):
    """browser-use 0.10.1 的 _cdp_set_cookies 在无 focus target（浏览器刚启动、
    还没有标签页，watchdog 此时加载登录态）时静默 return，登录态被丢弃。
    ai_base 补丁后应改用 root CDP client 设置 cookie，与 focus 无关。"""

    def _fake_session(self, focus=None):
        calls = []

        async def set_cookies(params=None, session_id=None):
            calls.append(params)

        root = SimpleNamespace(send=SimpleNamespace(
            Storage=SimpleNamespace(setCookies=set_cookies)))
        return SimpleNamespace(agent_focus_target_id=focus, cdp_client=root), calls

    def test_set_cookies_without_focus_still_applies(self):
        from browser_use.browser.session import BrowserSession
        session, calls = self._fake_session(focus=None)
        cookies = [{'name': 'JSESSIONID', 'value': 'x', 'domain': '192.168.177.51'}]
        asyncio.run(BrowserSession._cdp_set_cookies(session, cookies))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['cookies'], cookies)

    def test_set_cookies_empty_noop(self):
        from browser_use.browser.session import BrowserSession
        session, calls = self._fake_session(focus=None)
        asyncio.run(BrowserSession._cdp_set_cookies(session, []))
        self.assertEqual(calls, [])
