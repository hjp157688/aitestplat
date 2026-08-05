# -*- coding: utf-8 -*-
"""AI 网关视图：AI 调用记录（只读 + 统计）。"""

from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AiCallRecord
from .serializers import AiCallRecordSerializer


class AiCallRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """AI 调用记录（成功/失败、耗时、token、成本），只读。"""

    queryset = AiCallRecord.objects.all()
    serializer_class = AiCallRecordSerializer
    filterset_fields = ['provider', 'role', 'scenario', 'status', 'config_id']
    ordering_fields = ['created_at', 'latency_ms', 'total_tokens']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """聚合统计：总数 / 成功率 / 平均耗时 / 今日调用数。"""
        qs = self.filter_queryset(self.get_queryset())
        aggregate = qs.aggregate(
            total=Count('id'),
            failed=Count('id', filter=Q(status='failed')),
            avg_latency=Avg('latency_ms'),
            total_tokens=Count('id'),
        )
        total = aggregate['total'] or 0
        failed = aggregate['failed'] or 0
        try:
            today_count = qs.filter(created_at__date=timezone.localdate()).count()
        except Exception:
            today_count = 0
        return Response({
            'total': total,
            'success': total - failed,
            'failed': failed,
            'success_rate': round((total - failed) / total, 4) if total else 1.0,
            'avg_latency_ms': round(aggregate['avg_latency'], 1) if aggregate['avg_latency'] else None,
            'today_count': today_count,
        })
