import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='输入需求文本创建测试用例生成任务，立即返回 task_id。'
                      '随后用 get_generation_task 轮询进度与用例，用 adopt_generated_testcases 采纳进平台。')
async def generate_testcases_from_text(
    title: str,
    requirement_text: str,
    project_id: int | None = None,
    case_type: str = '',
    granularity: str = 'medium',
    output_mode: str | None = None,
) -> str:
    try:
        return json.dumps(
            await asyncio.to_thread(
                service.generate_testcases_from_text,
                title, requirement_text, project_id=project_id, case_type=case_type,
                granularity=granularity, output_mode=output_mode),
            ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='按 task_id 查询测试用例生成任务：status/progress 与已解析用例摘要；include_full=true 时附 final_test_cases 原文。')
async def get_generation_task(task_id: str, include_full: bool = False) -> str:
    try:
        return json.dumps(await asyncio.to_thread(
            service.get_generation_task, task_id, include_full=include_full), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='把已完成生成任务的最终用例（可 case_indices 指定部分，默认全量）采纳进平台正式用例库。幂等：已采纳会返回 already_saved。')
async def adopt_generated_testcases(
    task_id: str,
    project_id: int | None = None,
    case_indices: list[int] | None = None,
) -> str:
    try:
        return json.dumps(
            await asyncio.to_thread(
                service.adopt_generated_testcases, task_id, project_id=project_id,
                case_indices=case_indices),
            ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)
