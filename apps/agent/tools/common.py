import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='列出平台上的所有项目（id/name/description/status）')
async def list_projects() -> str:
    try:
        # 工具被 FastMCP 在事件循环上直接调用（mcp 1.25 对 sync fn 是同步执行），
        # Django ORM 不能在事件循环线程运行，须经 asyncio.to_thread 委托到工作线程。
        return json.dumps(await asyncio.to_thread(service.list_projects), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 统一返回结构化错误
        return json.dumps({'error': str(e)}, ensure_ascii=False)
