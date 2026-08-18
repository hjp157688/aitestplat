import asyncio
import json
from apps.agent import service
from apps.agent.mcp_instance import mcp


@mcp.tool(description='用自然语言驱动 UI 浏览器自动化（复用平台 run_adhoc）。立即返回 execution_id，'
                      '用 get_ui_execution 轮询结果，用 stop_ui_execution 停止。')
async def run_ui_automation_adhoc(
    task_description: str,
    project_id: int | None = None,
    execution_mode: str = 'text',
    enable_gif: bool = True,
) -> str:
    try:
        return json.dumps(await asyncio.to_thread(
            service.run_ui_automation_adhoc,
            task_description, project_id=project_id, execution_mode=execution_mode,
            enable_gif=enable_gif), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='按 execution_id 查 UI 自动化执行状态与结果（含截图/GIF 引用）；include_full=true 附完整日志。')
async def get_ui_execution(execution_id: int, include_full: bool = False) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.get_ui_execution, execution_id, include_full=include_full),
                          ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)


@mcp.tool(description='向正在运行的 UI 自动化任务发送停止信号。')
async def stop_ui_execution(execution_id: int) -> str:
    try:
        return json.dumps(await asyncio.to_thread(service.stop_ui_execution, execution_id), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        return json.dumps({'error': str(e)}, ensure_ascii=False)
