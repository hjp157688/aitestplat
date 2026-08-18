# -*- coding: utf-8 -*-
"""删除已合并的 api_testing.AIServiceConfig / ApiPromptConfig（表 api_ai_service_configs / api_prompt_configs）。"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0007_merge_ai_service_configs'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ApiPromptConfig',
        ),
        migrations.DeleteModel(
            name='AIServiceConfig',
        ),
    ]
