def build_server():
    """导入 tools 包（注册全部 @mcp.tool），返回 FastMCP 实例。"""
    from apps.agent import tools  # noqa: F401
    from apps.agent.mcp_instance import mcp
    return mcp
