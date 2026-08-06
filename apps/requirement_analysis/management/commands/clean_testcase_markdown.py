# -*- coding: utf-8 -*-
"""清理 AI 生成测试用例中的 Markdown/HTML 残留。

背景：旧版 writer 提示词按 Markdown 表格输出，且评审改进步骤会加粗，导致入库的
测试用例如下：
- title 两侧带 `**`（如 `**验证登录**`）
- steps 为单个元素，desc 内嵌 `<br>` 和序号，expect 为空

本命令就地清洗这些残留（幂等，可重复执行）：去 **、<br>→换行、把步骤文本
拆成多步 [{desc, expect}]（旧表格的整体预期挂到末步）。

只处理命中特征的记录（title 含 ** 或 steps 含 <br>/**），人工编辑的规范用例不受影响。

用法：
    python manage.py clean_testcase_markdown            # 真实清洗并保存
    python manage.py clean_testcase_markdown --dry-run  # 只统计不写库
"""
import json
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('apps.requirement_analysis')


class Command(BaseCommand):
    help = '清理 AI 生成测试用例中的 Markdown 残留（**、<br>、预期为空）'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='只统计待清洗记录，不写库')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        from apps.testcases.models import TestCase
        from apps.requirement_analysis.text_cleaner import clean_text, normalize_steps

        # 命中特征：标题带 ** 或 步骤带 <br>/**
        candidates = (
            TestCase.objects.filter(title__contains='**')
            | TestCase.objects.filter(steps__contains='<br')
            | TestCase.objects.filter(steps__contains='**')
        ).distinct().order_by('id')

        changed_count = 0
        for case in candidates:
            new_title = clean_text(case.title) if case.title else ''
            new_pre = clean_text(case.preconditions) if case.preconditions else ''

            new_steps = None
            if case.steps:
                try:
                    raw = json.loads(case.steps)
                except (json.JSONDecodeError, ValueError):
                    raw = case.steps  # 纯文本步骤块
                new_steps = normalize_steps(raw)

            changed = (
                new_title != case.title
                or new_pre != case.preconditions
                or (new_steps is not None
                    and json.dumps(new_steps, ensure_ascii=False) != case.steps)
            )
            if not changed:
                continue

            changed_count += 1
            if dry_run:
                self.stdout.write(f'  [dry-run] #{case.id} {new_title[:40]!r}')
                continue

            case.title = new_title
            case.preconditions = new_pre
            if new_steps is not None:
                case.steps = json.dumps(new_steps, ensure_ascii=False)
            case.save(update_fields=['title', 'preconditions', 'steps'])

        action = '待清洗' if dry_run else '已清洗'
        self.stdout.write(self.style.SUCCESS(f'共 {changed_count} 条记录{action}。'))
        return
