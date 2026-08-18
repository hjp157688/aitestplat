import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='列出数据工厂全部随机数据/编码/加密/JSON 等工具的 tool_name 与 tool_category')
async def list_data_factory_tools() -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.list_data_factory_tools), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='同步执行数据工厂工具并立即返回生成结果。入参 input_data 为工具专用字段字典（如造随机手机号可传空 {}）。')
async def generate_test_data(tool_name: str, tool_category: str, input_data: dict | None = None) -> str:
    try:
        return json.dumps(
            await asyncio.to_thread(service.generate_test_data, tool_name, tool_category, input_data),
            ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)
