# -*- coding: utf-8 -*-
"""AI 调用可观测模型：落库每次 AI 调用的元数据（成功/失败、耗时、token、成本）。"""

from django.db import models
from django.conf import settings


class AiCallRecord(models.Model):
    """AI 调用记录（一次实际发给模型提供商的请求）。"""

    STATUS_CHOICES = [
        ('success', '成功'),
        ('failed', '失败'),
    ]

    provider = models.CharField(max_length=30, blank=True, default='', verbose_name='提供商')
    model_name = models.CharField(max_length=200, blank=True, default='', verbose_name='模型')
    role = models.CharField(max_length=30, blank=True, default='', verbose_name='角色')
    scenario = models.CharField(max_length=50, blank=True, default='',
                                verbose_name='场景',
                                help_text='如 writer / review / requirement_parse / max_tokens / test_connection / browser_use_task 等')
    config_id = models.IntegerField(null=True, blank=True, verbose_name='配置ID')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='success', verbose_name='状态')
    latency_ms = models.IntegerField(null=True, blank=True, verbose_name='耗时(毫秒)')
    prompt_tokens = models.IntegerField(null=True, blank=True, verbose_name='输入Token')
    completion_tokens = models.IntegerField(null=True, blank=True, verbose_name='输出Token')
    total_tokens = models.IntegerField(null=True, blank=True, verbose_name='总Token')
    cost_estimate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True,
                                        verbose_name='预估成本')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='触发用户',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ai_call_records'
        verbose_name = 'AI调用记录'
        verbose_name_plural = 'AI调用记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['role', 'status']),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.provider}/{self.model_name} {self.status}"


class AiModelPricing(models.Model):
    """模型单价（每百万 token，美元）。model_keyword 对 model_name 做子串匹配，'' 为兜底。"""

    provider = models.CharField(max_length=30, verbose_name='提供商')
    model_keyword = models.CharField(max_length=100, default='', verbose_name='模型关键字')
    input_per_million = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='输入单价/百万')
    output_per_million = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='输出单价/百万')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_model_pricing'
        verbose_name = '模型单价'
        verbose_name_plural = '模型单价'
        unique_together = ('provider', 'model_keyword')

    def __str__(self):
        return f"{self.provider}/{self.model_keyword or '*'}"


def get_price_infos():
    """按提供商分组返回价格行，供成本估算使用（稀疏表，无行则成本为 None）。"""
    return list(AiModelPricing.objects.all())
