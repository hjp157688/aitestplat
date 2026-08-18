from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('启动 AITestPlat MCP server（FastMCP 进程内直连业务）。'
            '--transport stdio：本机 agent 直连；--transport http：远程 agent 连接（需 MCP_SERVER_TOKEN）。')

    def add_arguments(self, parser):
        parser.add_argument('--transport', choices=['stdio', 'http'], default='stdio')
        parser.add_argument('--host', default=None)
        parser.add_argument('--port', type=int, default=None)

    def handle(self, *args, **options):
        from django.conf import settings
        from apps.agent.server import build_server
        from apps.agent.service_identity import get_service_user

        transport = options['transport']
        if transport == 'http' and not getattr(settings, 'MCP_SERVER_TOKEN', None):
            raise CommandError('http transport 需要设置 MCP_SERVER_TOKEN（写入 .env）')

        get_service_user()  # 幂等创建服务账号（MCP_SERVICE_USER，默认 mcp_agent）
        mcp = build_server()

        if transport == 'stdio':
            # stdio 通道全被解析为 JSON-RPC，任何 stdout 输出都会污染协议，必须走 stderr
            self.stderr.write(self.style.SUCCESS('MCP stdio server 启动（等待客户端...）'))
            mcp.run(transport='stdio')
            return

        import uvicorn
        from apps.agent.auth import wrap_auth
        host = options['host'] or getattr(settings, 'MCP_HOST', '0.0.0.0')
        port = options['port'] or getattr(settings, 'MCP_PORT', 8765)
        app = wrap_auth(mcp.streamable_http_app(), settings.MCP_SERVER_TOKEN)
        self.stderr.write(self.style.SUCCESS(f'MCP http server: http://{host}:{port}/mcp'))
        uvicorn.run(app, host=host, port=int(port), log_level='info')
