# -*- coding: utf-8 -*-
"""AI 网关后台管理（只读审计）。"""

from django.contrib import admin
from django.db.models import Count, Q

from .models import AiCallRecord, AiModelPricing


@admin.register(AiCallRecord)
class AiCallRecordAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'provider', 'model_name', 'role', 'scenario', 'status',
                    'latency_ms', 'total_tokens', 'cost_estimate']
    list_filter = ['provider', 'role', 'scenario', 'status']
    search_fields = ['model_name', 'provider', 'role', 'scenario', 'error_message']
    readonly_fields = [f.name for f in AiCallRecord._meta.fields if f.name != 'id']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['delete_selected']

    def has_add_permission(self, request):
        return False


@admin.register(AiModelPricing)
class AiModelPricingAdmin(admin.ModelAdmin):
    list_display = ['provider', 'model_keyword', 'input_per_million', 'output_per_million', 'updated_at']
    list_filter = ['provider']
    search_fields = ['provider', 'model_keyword']
