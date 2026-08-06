# -*- coding: utf-8 -*-
"""数据迁移：把 api_testing.AIServiceConfig / ApiPromptConfig 行并入
requirement_analysis.AIModelConfig / PromptConfig（单表合一）。

- service_type -> model_type 映射（azure -> azure_openai）
- 用户私有配置以 scope='user' + created_by 保留隔离语义
- 合并后原表由 0008 删除
"""
from django.db import migrations

SERVICE_TYPE_MAP = {
    'openai': 'openai',
    'azure': 'azure_openai',
    'anthropic': 'anthropic',
    'deepseek': 'deepseek',
    'qwen': 'qwen',
    'siliconflow': 'siliconflow',
    'other': 'other',
}


def merge_forwards(apps, schema_editor):
    AIServiceConfig = apps.get_model('api_testing', 'AIServiceConfig')
    AIModelConfig = apps.get_model('requirement_analysis', 'AIModelConfig')
    ApiPromptConfig = apps.get_model('api_testing', 'ApiPromptConfig')
    PromptConfig = apps.get_model('requirement_analysis', 'PromptConfig')
    User = apps.get_model('users', 'User')

    backup_created_by = None
    superuser = User.objects.filter(is_superuser=True).first()
    if superuser:
        backup_created_by = superuser.id

    for row in AIServiceConfig.objects.all().order_by('id'):
        AIModelConfig.objects.create(
            name=row.name,
            model_type=SERVICE_TYPE_MAP.get(row.service_type, 'other'),
            role=row.role,
            api_key=row.api_key,
            base_url=(row.base_url or '') or '',
            model_name=row.model_name,
            max_tokens=row.max_tokens,
            temperature=row.temperature,
            top_p=0.9,
            is_active=row.is_active,
            scope='user',
            created_by_id=row.created_by_id or backup_created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    for row in ApiPromptConfig.objects.all().order_by('id'):
        PromptConfig.objects.create(
            name=row.name,
            prompt_type='api_testcase_generator',
            content=row.content,
            is_active=row.is_active,
            created_by_id=row.created_by_id or backup_created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        # 依赖 requirement_analysis 0010：既需要 0009 的 scope/provider_extra/加宽列，
        # 也需要 0010 把 prompt_config.prompt_type 加宽到 30（api_testcase_generator 为 22 字符）
        ('requirement_analysis',
         '0010_alter_promptconfig_options_promptconfig_is_seeded_and_more'),
        ('api_testing', '0006_apirequest_auth_spec_apirequest_deprecated_and_more'),
    ]

    operations = [
        migrations.RunPython(merge_forwards, migrations.RunPython.noop),
    ]
