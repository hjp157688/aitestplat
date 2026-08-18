from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

INSTRUCTIONS = (
    'AITestPlat 测试平台 MCP 接口。'
    '长操作遵循 run → result 模式：先调用 xxx_run 拿到 task_id/execution_id，'
    '再轮询对应 result/读取工具取最终结果（不要盲目重试 run）。'
    '错误响应统一为 {"error": "..."}。'
)

# 自托管平台：远程 agent 通过任意 host/IP 连接，关闭 DNS 重绑定保护，
# 由 auth.py 的 Bearer 校验兜底。
mcp = FastMCP(
    'aitestplat',
    instructions=INSTRUCTIONS,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
