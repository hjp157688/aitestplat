# -*- coding: utf-8 -*-
"""AI 网关序列化器。"""

from rest_framework import serializers

from .models import AiCallRecord


class AiCallRecordSerializer(serializers.ModelSerializer):
    """只读的 AI 调用记录。"""

    provider_display = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AiCallRecord
        fields = [
            'id', 'provider', 'provider_display', 'model_name', 'role', 'scenario',
            'status', 'status_display', 'latency_ms', 'prompt_tokens', 'completion_tokens',
            'total_tokens', 'cost_estimate', 'error_message', 'config_id', 'created_at',
        ]
        read_only_fields = fields

    def get_provider_display(self, obj):
        from .providers import provider_display_name
        return provider_display_name(obj.provider)
