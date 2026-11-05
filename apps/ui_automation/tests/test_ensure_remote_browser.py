"""_ensure_remote_browser：cdp_url 未监听时自动拉起本机调试 Chrome 的兜底测试（不真正启动浏览器）。"""
import asyncio
from unittest import mock

from django.test import TestCase

from apps.ui_automation.ai_base import BaseBrowserAgent
from .test_storage_state_profile import _bare_agent


class EnsureRemoteBrowserTests(TestCase):
    def _agent(self, cdp_url):
        agent = _bare_agent()
        agent.cdp_url = cdp_url
        return agent

    def test_no_cdp_url_is_noop(self):
        """未设置 cdp_url：不探测、不启动。"""
        agent = self._agent(None)
        with mock.patch.object(BaseBrowserAgent, '_probe_cdp') as probe, \
             mock.patch('subprocess.Popen') as popen:
            asyncio.run(agent._ensure_remote_browser())
        probe.assert_not_called()
        popen.assert_not_called()

    def test_cdp_already_listening_is_noop(self):
        """CDP 已就绪：直接返回，不启动 Chrome。"""
        agent = self._agent('http://127.0.0.1:9222')

        async def _up(host, port):
            return True

        with mock.patch.object(BaseBrowserAgent, '_probe_cdp', side_effect=_up) as probe, \
             mock.patch('subprocess.Popen') as popen:
            asyncio.run(agent._ensure_remote_browser())
        self.assertEqual(probe.await_count, 1)
        popen.assert_not_called()

    def test_local_unreachable_launches_chrome_and_waits_ready(self):
        """本机端口未监听：启动调试 Chrome 并轮询到就绪。"""
        agent = self._agent('http://127.0.0.1:9222')
        calls = {'probe': 0}

        async def _probe(host, port):
            calls['probe'] += 1
            return calls['probe'] > 1  # 第一次未就绪，之后就绪

        agent._find_chrome_executable = lambda: '/fake/chrome'
        with mock.patch.object(BaseBrowserAgent, '_probe_cdp', side_effect=_probe), \
             mock.patch('subprocess.Popen') as popen, \
             mock.patch('asyncio.sleep', new=_zero_sleep):
            asyncio.run(agent._ensure_remote_browser())
        popen.assert_called_once()
        args = popen.call_args.args[0]
        self.assertIn('--remote-debugging-port=9222', args)
        self.assertTrue(any(a.startswith('--user-data-dir=') for a in args))

    def test_remote_unreachable_raises_instead_of_launch(self):
        """远端地址不可达：直接报错，绝不尝试在服务器上拉起浏览器。"""
        agent = self._agent('http://10.0.0.8:9222')

        async def _down(host, port):
            return False

        with mock.patch.object(BaseBrowserAgent, '_probe_cdp', side_effect=_down), \
             mock.patch('subprocess.Popen') as popen:
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(agent._ensure_remote_browser())
        popen.assert_not_called()
        self.assertIn('隧道', str(ctx.exception))

    def test_launch_timeout_raises(self):
        """拉起后 15 秒仍未就绪：报错退出。"""
        agent = self._agent('http://127.0.0.1:9222')

        async def _down(host, port):
            return False

        agent._find_chrome_executable = lambda: '/fake/chrome'
        with mock.patch.object(BaseBrowserAgent, '_probe_cdp', side_effect=_down), \
             mock.patch('subprocess.Popen'), \
             mock.patch('asyncio.sleep', new=_zero_sleep):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(agent._ensure_remote_browser())
        self.assertIn('未就绪', str(ctx.exception))


async def _zero_sleep(_delay):
    """测试中跳过真实等待。"""
    return None
