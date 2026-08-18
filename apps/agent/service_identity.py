from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


def get_service_user():
    """幂等获取/创建 MCP 服务账号。进程内直连业务即以此身份执行。"""
    username = getattr(settings, 'MCP_SERVICE_USER', 'mcp_agent')
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'is_active': True, 'is_staff': False, 'is_superuser': False},
    )
    return user


def resolve_project(project_id=None):
    """project_id 存在则校验并返回 Project；None 返回 None；不存在抛 ValueError。"""
    if project_id is None:
        return None
    from apps.projects.models import Project
    try:
        return Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise ValueError(f'项目不存在: {project_id}')
