# -*- coding: utf-8 -*-
"""
统一模型配置解析器。

收敛全平台「哪个模型配置用来调用」的决策逻辑：
- active(role, model_type=None, ...) ：model_type=None 表示任意提供商（修复旧
  get_active_config(model_type=None, ...) 永远匹配不到的 bug）
- active_by_priority(roles, ...)     ：按角色优先序（embedding: tokenizer→embedding→writer）
- 支持 scope='user' + user= 的用户级配置（合并自 api_testing.AIServiceConfig 的用户隔离语义）
"""
from typing import Optional, Sequence

PROVIDER_ANY = None


class ConfigResolver:
    """AI 模型配置解析器（全部为静态方法）。"""

    # embedding 配置的默认优先序（与旧 embedding_service 一致）
    EMBEDDING_ROLE_PRIORITY = ('tokenizer', 'embedding', 'writer')

    @staticmethod
    def active(role: str, model_type: Optional[str] = None,
               user=None, scope: str = 'global'):
        """获取指定角色的活跃配置。

        Args:
            role: 角色（writer / reviewer / browser_use_text ...）
            model_type: None 表示任意提供商；否则按提供商过滤
            user: 传 user 时优先其本人名下配置（scope='user'）
            scope: 'global' 全局配置 / 'user' 用户配置
        """
        from apps.requirement_analysis.models import AIModelConfig

        queryset = AIModelConfig.objects.filter(role=role, is_active=True)
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        if scope and scope != 'global' and user is not None:
            queryset = queryset.filter(created_by=user)
        return queryset.order_by('-updated_at').first()

    @staticmethod
    def active_by_priority(roles: Sequence[str], user=None) -> Optional[object]:
        """按角色优先序逐个解析，返回第一个命中的活跃配置（如 embedding 的回退链）。"""
        if not roles:
            return None
        for role in roles:
            config = ConfigResolver.active(role, user=user)
            if config:
                return config
        return None
