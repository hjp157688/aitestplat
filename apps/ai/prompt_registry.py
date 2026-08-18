# -*- coding: utf-8 -*-
"""
统一 Prompt 注册表读取层。

- get_prompt(type)          : 取某类型当前活跃的 PromptConfig（按 version 降序取最新）
- get_prompt_content(type, default=) : 取内容；未 seed（表里没有该类型）时回退代码默认值

提示词内容的**管理与编辑**走数据库（PromptConfig v2），种子来源见 prompt_seeds.py。
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger('apps.ai.prompt_registry')


def get_prompt(prompt_type: str):
    """取指定类型当前活跃的 PromptConfig 行（最新版本优先）。未配置返回 None。"""
    from apps.requirement_analysis.models import PromptConfig

    queryset = PromptConfig.objects.filter(prompt_type=prompt_type, is_active=True)
    if 'version' in {f.name for f in PromptConfig._meta.get_fields()}:
        # 最新版本优先，同版本时取最新创建（-pk 保证 MySQL 排序稳定）
        return queryset.order_by('-version', '-pk').first()
    return queryset.order_by('-pk').first()


def get_prompt_content(prompt_type: str, default: str = '', **fmt) -> str:
    """取类型提示词内容；未 seed 时回退 `default`（代码内默认）。支持 .format 关键字。

    Args:
        prompt_type: PromptConfig.prompt_type
        default: 代码默认内容（新增类型未入库/未 seed 时的兜底，避免 404）
        **fmt: 可选，用 str.format 填充占位符（如 {content}）
    """
    row = get_prompt(prompt_type)
    content = row.content if (row and row.content) else default
    if fmt:
        try:
            content = content.format(**fmt)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(f'prompt {prompt_type} 格式化失败（占位符缺失或错误）: {e!r}')
    return content


def get_prompt_content_raw(prompt_type: str, default: str = '') -> str:
    """取类型提示词内容（不做 .format 格式化）。

    用于含裸 JSON 花括号（如 PARSE_PROMPT）的提示词，调用方自行 .replace() 占位。
    """
    row = get_prompt(prompt_type)
    return row.content if (row and row.content) else default


def _get_prompt_content_reconnect(prompt_type: str, default: str = '', **fmt) -> str:
    """读提示词；长驻线程连接被 MySQL 静默断开时关闭重连后重试一次再抛。

    `OperationalError (0, '')`（errno=0 空错误包）＝ MySQL 已静默断开连接，
    常见于 daphne 单线程执行器里长期复用的缓存连接（wait_timeout 过期、被 kill）。
    """
    from django.db import connection
    from django.db.utils import OperationalError

    try:
        return get_prompt_content(prompt_type, default, **fmt)
    except OperationalError:
        # 仅在不在事务内时关闭本线程连接，强制下次查询重连；否则原样抛出
        if not connection.in_atomic_block:
            logger.warning(f'prompt {prompt_type} 读取遇连接断开，关闭重连后重试')
            connection.close()
            return get_prompt_content(prompt_type, default, **fmt)
        raise


async def get_prompt_content_async(prompt_type: str, default: str = '', **fmt) -> str:
    """异步取类型提示词内容（供 asyncio 上下文的消费者，如知识库提取器/检索器）。"""
    from asgiref.sync import sync_to_async

    return await sync_to_async(_get_prompt_content_reconnect)(prompt_type, default, **fmt)


def content_hash(content: str) -> str:
    """计算提示词内容指纹，用于判定种子内容是否变化。"""
    return hashlib.sha256((content or '').encode('utf-8')).hexdigest()
