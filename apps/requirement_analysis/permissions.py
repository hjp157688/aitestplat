# -*- coding: utf-8 -*-
"""项目隔离加固：知识库/需求资源的项目访问校验

- is_admin(user)：superuser 或 staff 视为管理员。
- assert_project_access(user, project_id)：project_id 为空（全局资源）直接放行；
  否则要求 user 为管理员、项目 owner 或项目成员（ProjectMember），否则抛
  rest_framework.exceptions.PermissionDenied。
"""
from rest_framework.exceptions import PermissionDenied

from apps.projects.models import Project, ProjectMember


def is_admin(user):
    return bool(user and (user.is_superuser or user.is_staff))


def assert_project_access(user, project_id=None):
    """校验 user 对 project_id 的访问权；无权限抛 PermissionDenied。

    project_id 为 None 表示全局资源（如 global 知识库数据），放行。
    """
    if project_id is None:
        return
    # 管理员跨项目放行
    if is_admin(user):
        return
    # 匿名/伪造用户直接拒绝（防御：供 service 层等无 DRF 鉴权保护处调用）
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("无权访问该项目")
    try:
        proj = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise PermissionDenied("项目不存在或无权限")
    if proj.owner_id == user.id:
        return
    if ProjectMember.objects.filter(project=proj, user=user).exists():
        return
    raise PermissionDenied("无权访问该项目")
