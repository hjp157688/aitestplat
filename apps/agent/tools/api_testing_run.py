import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='列出 API 测试套件（可按 project_id 过滤）')
async def list_api_test_suites(project_id: int | None = None) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.list_api_test_suites, project_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='列出 API 请求（可按 project_id / collection_id 过滤），用于拿到 request_id')
async def list_api_requests(project_id: int | None = None, collection_id: int | None = None) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.list_api_requests, project_id, collection_id),
                          ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='同步执行单个 API 请求并返回结果（状态码/耗时/断言）。')
async def run_api_request(request_id: int) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.run_api_request, request_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='同步执行整个 API 测试套件，返回执行记录（含 id，可用 get_api_execution 查明细）。')
async def run_api_test_suite(suite_id: int) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.run_api_test_suite, suite_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='按 execution_id 查 API 测试执行结果（每请求状态码/断言/日志）。')
async def get_api_execution(execution_id: int) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.get_api_execution, execution_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)
