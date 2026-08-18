import json
from unittest import IsolatedAsyncioTestCase

from mcp.shared.memory import create_connected_server_and_client_session

from apps.agent.server import build_server


class McpIntegrationSmokeTests(IsolatedAsyncioTestCase):
    """真实事件循环上的 MCP 全链路冒烟（守卫 C1 回归）。

    既有单测都直接调用工具函数，从未让 FastMCP 在 asyncio 事件循环里
    触发工具调用。本测试通过内存流连接真实 server，走 client → FastMCP →
    asyncio.to_thread → Django ORM 的完整路径，任何在该路径上直接执行
    ORM（SynchronousOnlyOperation）都会在此失败。
    """

    async def test_list_projects_over_live_loop(self):
        server = build_server()
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool('list_projects', {})
            self.assertFalse(result.isError, f'tool call marked as error: {result}')
            # FastMCP 对 str 返回包装为 TextContent；内容应为合法 JSON 列表而非 {"error": ...}
            joined = ''.join(
                (c.text if hasattr(c, 'text') else c.get('text', ''))
                for c in result.content
            )
            data = json.loads(joined)
            self.assertIsInstance(data, list)
            self.assertNotIn('error', data)
