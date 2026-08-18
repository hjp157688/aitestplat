# -*- coding: utf-8 -*-
"""数据迁移：把已存在的 writer/reviewer PromptConfig 行标记为种子，
并为全部 9 类提示词补建种子（含旧接口用例提示词 ApiPromptConfig 并入的 api_testcase_generator）。
"""
import hashlib

from django.db import migrations

from apps.ai import prompt_seeds


def seed_defaults(apps, schema_editor):
    PromptConfig = apps.get_model('requirement_analysis', 'PromptConfig')
    User = apps.get_model('users', 'User')

    created_by_id = None
    su = User.objects.filter(is_superuser=True).first()
    if su:
        created_by_id = su.id

    for prompt_type in prompt_seeds.PROMPT_SEEDS_TYPES:
        content = prompt_seeds.content_for(prompt_type)
        if not content:
            continue
        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        seed_name = prompt_seeds.SEEDS[prompt_type]['name']

        active = PromptConfig.objects.filter(
            prompt_type=prompt_type, is_active=True,
        ).order_by('-version', '-id').first()

        if active and active.seed_hash == digest:
            # 指纹一致：仅补种子标记
            if not active.is_seeded:
                active.is_seeded = True
                active.version = active.version or 1
                active.save(update_fields=['is_seeded', 'version'])
            continue

        # 无活跃行 / 指纹不一致 → 新建版本并激活
        latest = PromptConfig.objects.filter(prompt_type=prompt_type) \
            .order_by('-version', '-id').first()
        version = (latest.version or 1) + 1 if latest else 1

        row = PromptConfig.objects.create(
            name=seed_name,
            prompt_type=prompt_type,
            content=content,
            is_active=True,
            version=version,
            version_note=f'种子 v{version}',
            seed_hash=digest,
            is_seeded=True,
            created_by_id=created_by_id,
        )
        PromptConfig.objects.filter(prompt_type=prompt_type).exclude(id=row.id).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        # schema 变更先行（version/is_seeded/seed_hash 列）
        ('requirement_analysis',
         '0010_alter_promptconfig_options_promptconfig_is_seeded_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
