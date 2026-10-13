"""用例版本快照信号：任何创建路径（API/导入/禅道/AI补充）都自动产生 v1"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TestCase, TestCaseVersion
from .services import snapshot_case_version


@receiver(post_save, sender=TestCase)
def snapshot_initial_version(sender, instance, created, **kwargs):
    """创建用例时自动落 v1 快照。

    调用方可通过临时属性覆盖来源信息：
    instance._snapshot_source / _snapshot_note / _snapshot_user
    （AI 补充创建用例时用 ai_supplemented 标记首版）
    """
    if not created:
        return
    if TestCaseVersion.objects.filter(testcase=instance).exists():
        return
    snapshot_case_version(
        instance,
        source=getattr(instance, '_snapshot_source', None) or 'created',
        note=getattr(instance, '_snapshot_note', '') or '',
        created_by=getattr(instance, '_snapshot_user', None),
    )
