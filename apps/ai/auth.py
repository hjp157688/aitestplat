# -*- coding: utf-8 -*-
"""
统一鉴权与 URL 构建。

提供 build_headers / build_url，按提供商注册表（apps.ai.providers）的
auth 风格为每个提供商生成正确的请求头与请求地址。
"""
import re
from typing import Dict

from .providers import get_provider

DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
}


def build_headers(provider: str, api_key: str, api_version: str = None) -> Dict[str, str]:
    """按提供商鉴权风格构建请求头。

    Args:
        provider: 提供商 key（见 providers.PROVIDERS）
        api_key: 密钥
        api_version: 可选，Azure OpenAI 的 api-version（同时拼在 URL 上）
    """
    headers = dict(DEFAULT_HEADERS)
    style = get_provider(provider)['auth']

    if not api_key:
        return headers

    if style == 'api_key':
        # 通义千问 DashScope compatible-mode：仅 api-key 头
        headers['api-key'] = api_key
    elif style == 'anthropic':
        # Anthropic 原生风格（仅用于 test_connection 等探测场景，消息体仍是 OpenAI 兼容格式）
        headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
    elif style == 'azure':
        # Azure OpenAI：api-key 头 + URL 上的 api-version 查询参数
        headers['api-key'] = api_key
    else:
        # bearer（默认）：绝大多数 OpenAI 兼容提供商
        headers['Authorization'] = f'Bearer {api_key}'

    return headers


def build_url(base_url: str, endpoint: str, provider: str = 'other',
              api_version: str = None) -> str:
    """根据用户输入的 base_url 构建 OpenAI 兼容接口地址。

    移植自 apps/requirement_analysis/models.py 的 build_openai_compatible_url，
    处理 /v1、/v4 版本归一化；Azure OpenAI 追加 api-version 查询参数。
    """
    normalized_base_url = (base_url or '').rstrip('/')

    if normalized_base_url.endswith(endpoint):
        url = normalized_base_url
        if provider == 'azure_openai' and api_version:
            sep = '&' if '?' in url else '?'
            url = f'{url}{sep}api-version={api_version}'
        return url

    for known_endpoint in ('/chat/completions', '/models'):
        if normalized_base_url.endswith(known_endpoint):
            normalized_base_url = normalized_base_url[:-len(known_endpoint)]
            break

    if re.search(r'/v(\d+)/?$', normalized_base_url):
        url = f"{normalized_base_url}{endpoint}"
    else:
        url = f"{normalized_base_url}/v1{endpoint}"

    if provider == 'azure_openai' and api_version:
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}api-version={api_version}'

    return url
