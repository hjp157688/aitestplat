# -*- coding: utf-8 -*-
"""
提供商注册表 —— 全平台 AI 提供商枚举的唯一来源。

每个提供商声明：
- name: 展示名称（中/英，与前端 i18n 对应）
- default_base_url: 默认 API Base URL（空表示需用户填写，如 Azure）
- auth: 鉴权风格（bearer / api_key / azure / anthropic）
- model_hint: 建议的默认模型名（空表示不预填）

鉴权风格说明：
- bearer      -> Authorization: Bearer <key>
- api_key     -> api-key: <key>（通义千问 DashScope compatible-mode）
- azure       -> api-key: <key> + ?api-version=xxx（API版本走 provider_extra.api_version）
- anthropic   -> x-api-key: <key> + anthropic-version: 2023-06-01（原生风格）
"""
from typing import Dict, Any

PROVIDERS: Dict[str, Dict[str, Any]] = {
    'deepseek': {
        'name': 'DeepSeek',
        'default_base_url': 'https://api.deepseek.com',
        'auth': 'bearer',
        'model_hint': 'deepseek-chat',
    },
    'qwen': {
        'name': '通义千问',
        'default_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'auth': 'api_key',
        'model_hint': 'qwen-plus',
    },
    'siliconflow': {
        'name': '硅基流动',
        'default_base_url': 'https://api.siliconflow.cn/v1',
        'auth': 'bearer',
        'model_hint': 'Qwen/Qwen2.5-7B-Instruct',
    },
    'zhipu': {
        'name': '智谱',
        'default_base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'auth': 'bearer',
        'model_hint': 'glm-4-plus',
    },
    'xiaomi': {
        'name': '小米',
        'default_base_url': 'https://api.xiaomimimo.com/v1',
        'auth': 'bearer',
        'model_hint': '',
    },
    'xiaomi_coding_plan': {
        'name': '小米coding plan',
        'default_base_url': 'https://token-plan-cn.xiaomimimo.com/v1',
        'auth': 'bearer',
        'model_hint': '',
    },
    'openai': {
        'name': 'OpenAI',
        'default_base_url': 'https://api.openai.com/v1',
        'auth': 'bearer',
        'model_hint': 'gpt-4o-mini',
    },
    'azure_openai': {
        'name': 'Azure OpenAI',
        'default_base_url': '',
        'auth': 'azure',
        'model_hint': '',
    },
    'anthropic': {
        'name': 'Anthropic',
        'default_base_url': 'https://api.anthropic.com/v1',
        'auth': 'anthropic',
        'model_hint': 'claude-sonnet-4-20250514',
    },
    'google_gemini': {
        'name': 'Google Gemini',
        'default_base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'auth': 'bearer',
        'model_hint': '',
    },
    'other': {
        'name': '其他',
        'default_base_url': '',
        'auth': 'bearer',
        'model_hint': '',
    },
}

# 顺序即下拉框顺序（放到元组里作为模型 choices 使用）
MODEL_CHOICES = [(key, info['name']) for key, info in PROVIDERS.items()]


def get_provider(provider: str) -> Dict[str, Any]:
    """按 key 取提供商信息；未知提供商回退到 'other'。"""
    return PROVIDERS.get(provider or '', PROVIDERS['other'])


def provider_display_name(provider: str) -> str:
    """展示名称，未知回退原值。"""
    return get_provider(provider)['name']
