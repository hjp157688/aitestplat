import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='为选中的已有 API 请求(request_ids)启动 AI 用例变体生成，立即返回 task_id（单次最多 20 个）。')
async def generate_api_testcases(
    request_ids: list[int],
    environment_id: int | None = None,
    ai_config_id: int | None = None,
) -> str:
    try:
        return json.dumps(await asyncio.to_thread(
            service.generate_api_testcases,
            request_ids, environment_id=environment_id, ai_config_id=ai_config_id),
            ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='按 task_id 查询 API 生成任务进度与结果。')
async def get_api_generation_task(task_id: str) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.get_api_generation_task, task_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='把已完成生成任务中选中的 cases（每个需含 request_id 等字段）保存为平台 ApiRequest 记录；可指定 suite_name/collection_id/project_id。')
async def save_api_testcases(
    task_id: str,
    cases: list[dict],
    project_id: int | None = None,
    collection_id: int | None = None,
    suite_name: str | None = None,
) -> str:
    try:
        return json.dumps(await asyncio.to_thread(
            service.save_api_testcases,
            task_id, cases, project_id=project_id, collection_id=collection_id,
            suite_name=suite_name), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)
