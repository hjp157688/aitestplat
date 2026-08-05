# -*- coding: utf-8 -*-
"""把全部提示词种子 upsert 进 PromptConfig。

用法：
    python manage.py seed_prompts                    # 全部类型，内容变化才新建版本
    python manage.py seed_prompts --type writer      # 仅某类型
    python manage.py seed_prompts --force            # 强制重建新版本
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.ai import prompt_seeds


class Command(BaseCommand):
    help = '把 Prompt 种子（docs/*.md + 内联默认）upsert 进 PromptConfig'

    def add_arguments(self, parser):
        parser.add_argument('--type', dest='prompt_type', default=None,
                            help='只种子指定类型')
        parser.add_argument('--force', action='store_true', default=False,
                            help='即使内容未变化也重建新版本')

    def handle(self, *args, **options):
        prompt_type = options.get('prompt_type')
        force = options.get('force')

        # 种子归属人：第一个超管（无则 None）
        created_by = get_user_model().objects.filter(is_superuser=True).first()

        try:
            if prompt_type:
                if prompt_type not in prompt_seeds.PROMPT_SEEDS_TYPES:
                    raise CommandError(f'未知提示词类型: {prompt_type}（可选：{", ".join(prompt_seeds.PROMPT_SEEDS_TYPES)}）')
                results = {prompt_type: prompt_seeds.seed(prompt_type, created_by=created_by, force=force)}
            else:
                results = prompt_seeds.seed_all(created_by=created_by, force=force)
        except Exception as e:
            raise CommandError(f'种子化失败: {e!r}')

        for t, changed in results.items():
            if changed:
                self.stdout.write(self.style.SUCCESS(f'  [{t}] 已新建新版本（激活）'))
            else:
                self.stdout.write(f'  [{t}] 种子未变化，跳过')

        self.stdout.write(self.style.SUCCESS('提示词种子处理完成'))
