from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.projects.models import Project
import json
import re
import httpx
import asyncio
from typing import Dict, Any, List, AsyncIterator
import logging

from apps.ai.client import AIClient
from apps.ai import observability
from apps.ai.providers import MODEL_CHOICES as providers_MODEL_CHOICES

logger = logging.getLogger(__name__)

# 测试用例编号格式：可选前缀(字母/中文) + 可选分隔符 + 数字，如 LOGIN_001 / TC-003 / IMMSG001 / 001
_CASE_ID_PATTERN = re.compile(r'^([A-Za-z一-鿿]*)([-_]*)(\d+)$')


class RequirementDocument(models.Model):
    """需求文档模型"""
    DOCUMENT_TYPE_CHOICES = [
        ('pdf', 'PDF文档'),
        ('docx', 'Word文档'),
        ('txt', '文本文档'),
        ('md', 'Markdown文档'),
    ]

    STATUS_CHOICES = [
        ('uploaded', '已上传'),
        ('analyzing', '分析中'),
        ('analyzed', '分析完成'),
        ('failed', '分析失败'),
    ]

    title = models.CharField(max_length=200, verbose_name='文档标题')
    file = models.FileField(upload_to='requirement_docs/%Y/%m/', verbose_name='文档文件')
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPE_CHOICES, verbose_name='文档类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded', verbose_name='状态')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents',
                                    verbose_name='上传者')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='requirement_documents',
                                verbose_name='关联项目', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    file_size = models.PositiveIntegerField(verbose_name='文件大小(bytes)', null=True, blank=True)
    extracted_text = models.TextField(verbose_name='提取的文本内容', blank=True)

    class Meta:
        db_table = 'requirement_documents'
        verbose_name = '需求文档'
        verbose_name_plural = '需求文档'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class RequirementAnalysis(models.Model):
    """需求分析记录"""
    document = models.OneToOneField(RequirementDocument, on_delete=models.CASCADE, related_name='analysis',
                                    verbose_name='关联文档')
    analysis_report = models.TextField(verbose_name='分析报告', blank=True)
    requirements_count = models.PositiveIntegerField(verbose_name='需求数量', default=0)
    analysis_time = models.FloatField(verbose_name='分析耗时(秒)', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'requirement_analyses'
        verbose_name = '需求分析'
        verbose_name_plural = '需求分析'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.document.title} - 分析报告"


class GeneratedTestCase(models.Model):
    """生成的测试用例模型"""
    PRIORITY_CHOICES = [
        ('P0', '最高优先级'),
        ('P1', '高优先级'),
        ('P2', '中优先级'),
        ('P3', '低优先级'),
    ]

    STATUS_CHOICES = [
        ('generated', '已生成'),
        ('reviewing', '评审中'),
        ('reviewed', '已评审'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('adopted', '已采纳'),
        ('discarded', '已弃用'),
    ]

    requirement = models.ForeignKey('Requirement', on_delete=models.CASCADE, related_name='test_cases',
                                    verbose_name='关联需求')
    case_id = models.CharField(max_length=50, verbose_name='用例编号')
    title = models.CharField(max_length=300, verbose_name='用例标题')
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, verbose_name='优先级')
    precondition = models.TextField(verbose_name='前置条件')
    test_steps = models.TextField(verbose_name='测试步骤')
    expected_result = models.TextField(verbose_name='预期结果')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generated', verbose_name='状态')
    generated_by_ai = models.CharField(max_length=50, verbose_name='生成AI模型', default='AI-A')
    reviewed_by_ai = models.CharField(max_length=50, verbose_name='评审AI模型', null=True, blank=True)
    review_comments = models.TextField(verbose_name='评审意见', blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'generated_test_cases'
        verbose_name = '生成的测试用例'
        verbose_name_plural = '生成的测试用例'
        ordering = ['-created_at']
        unique_together = ['requirement', 'case_id']

    def __str__(self):
        return f"{self.case_id} - {self.title[:50]}"


class AnalysisTask(models.Model):
    """分析任务模型"""
    TASK_TYPE_CHOICES = [
        ('requirement_analysis', '需求分析'),
        ('testcase_generation', '测试用例生成'),
        ('testcase_review', '测试用例评审'),
    ]

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]

    task_id = models.CharField(max_length=100, unique=True, verbose_name='任务ID')
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES, verbose_name='任务类型')
    document = models.ForeignKey(RequirementDocument, on_delete=models.CASCADE, related_name='tasks',
                                 verbose_name='关联文档')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.PositiveIntegerField(default=0, verbose_name='进度百分比')
    result = models.JSONField(verbose_name='任务结果', null=True, blank=True)
    error_message = models.TextField(verbose_name='错误信息', blank=True)
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'analysis_tasks'
        verbose_name = '分析任务'
        verbose_name_plural = '分析任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_id} - {self.get_task_type_display()}"


class AIModelConfig(models.Model):
    """AI模型配置模型（全平台唯一配置表，提供商枚举收敛于 apps.ai.providers）"""

    # 提供商枚举唯一来源：apps.ai.providers（合并自 api_testing.AIServiceConfig 的 openai/azure/anthropic 等）
    MODEL_CHOICES = providers_MODEL_CHOICES

    ROLE_CHOICES = [
        ('writer', '测试用例编写专家'),
        ('reviewer', '测试评审专家'),
        ('browser_use_text', 'Browser Use - 文本模式'),
        ('embedding', '嵌入模型'),
        ('tokenizer', '分词模型'),
        ('api_testcase_generator', '接口测试用例生成'),
        # 合并自 api_testing.AIServiceConfig 的旧角色（保数据完整，无运行时消费方，UI 不展示）
        ('doc_extractor', 'API文档提取'),
        ('naming', '参数命名规范化'),
        ('mock_data', '模拟数据生成'),
        ('description', '参数描述补全'),
    ]

    SCOPE_CHOICES = [
        ('global', '全局'),
        ('user', '用户'),
    ]

    name = models.CharField(max_length=200, verbose_name='配置名称')
    model_type = models.CharField(max_length=20, choices=MODEL_CHOICES, verbose_name='模型类型')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, verbose_name='角色')
    api_key = models.CharField(max_length=500, verbose_name='API Key', blank=True, null=True)
    base_url = models.CharField(max_length=500, verbose_name='API Base URL')
    model_name = models.CharField(max_length=200, verbose_name='模型名称')
    max_tokens = models.IntegerField(default=4096, verbose_name='最大Token数')
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    top_p = models.FloatField(default=0.9, verbose_name='Top P参数')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    scope = models.CharField(
        max_length=10, choices=SCOPE_CHOICES, default='global', verbose_name='作用域',
        help_text='global=全局配置；user=用户私有配置（合并自 api_testing.AIServiceConfig）',
    )
    provider_extra = models.JSONField(default=dict, blank=True, verbose_name='提供商扩展参数',
                                      help_text='如 Azure OpenAI 的 api_version 等')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_model_config'
        verbose_name = 'AI模型配置'
        verbose_name_plural = 'AI模型配置'
        # 移除 unique_together 约束，允许同一个 role 有多个配置
        # 在应用层面通过代码控制：每个 role 只能有一个 is_active=True 的配置

    def __str__(self):
        return f"{self.get_model_type_display()} - {self.get_role_display()}"

    @classmethod
    def get_active_config(cls, model_type: str, role: str):
        """获取活跃的配置。

        model_type 传 None 表示任意提供商（修正旧实现 model_type=None
        被译为 `IS NULL` 永远匹配不到的 bug），统一走 apps.ai.ConfigResolver。
        """
        from apps.ai.resolver import ConfigResolver
        return ConfigResolver.active(role=role, model_type=model_type)


class PromptConfig(models.Model):
    """提示词配置模型（v2：全类型注册 + 版本化，种子来源见 apps.ai.prompt_seeds）"""
    PROMPT_CHOICES = [
        ('writer', '用例编写提示词'),
        ('reviewer', '用例评审提示词'),
        ('requirement_parse', '需求解析提示词'),
        ('api_testcase_generator', '接口测试用例生成'),
        ('knowledge_structure', '知识库-结构分析'),
        ('knowledge_section', '知识库-章节提取'),
        ('knowledge_rerank', '知识库-相关性重排'),
        ('browser_use_task', 'Browser Use-执行任务'),
        ('browser_use_breakdown', 'Browser Use-任务拆分'),
    ]

    name = models.CharField(max_length=100, verbose_name='配置名称')
    prompt_type = models.CharField(max_length=30, choices=PROMPT_CHOICES, verbose_name='提示词类型')
    content = models.TextField(verbose_name='提示词内容')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    version_note = models.CharField(max_length=200, blank=True, default='', verbose_name='版本说明')
    seed_hash = models.CharField(max_length=64, blank=True, default='', verbose_name='种子内容指纹')
    is_seeded = models.BooleanField(default=False, verbose_name='是否来自种子')
    # 种子行（系统数据）无属主；用户自建的提示词由 serializer 写入 created_by
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'prompt_config'
        verbose_name = '提示词配置'
        verbose_name_plural = '提示词配置'
        ordering = ['prompt_type', '-version']

    def __str__(self):
        return f"{self.get_prompt_type_display()} - {self.name} (v{self.version})"

    @classmethod
    def get_active_config(cls, prompt_type: str):
        """获取活跃的提示词配置（统一走 apps.ai.prompt_registry，最新版本优先）"""
        from apps.ai.prompt_registry import get_prompt
        return get_prompt(prompt_type)


class GenerationConfig(models.Model):
    """生成行为配置模型"""
    OUTPUT_MODE_CHOICES = [
        ('stream', '实时流式输出'),
        ('complete', '完整输出'),
    ]

    name = models.CharField(max_length=100, verbose_name='配置名称', default='默认生成配置')
    default_output_mode = models.CharField(
        max_length=10,
        choices=OUTPUT_MODE_CHOICES,
        default='stream',
        verbose_name='默认输出模式',
        help_text='测试用例生成的默认输出方式'
    )

    # 扩展配置字段
    enable_auto_review = models.BooleanField(
        default=True,
        verbose_name='启用AI评审和改进',
        help_text='生成完成后自动进行AI评审，并根据评审意见改进测试用例'
    )
    review_timeout = models.IntegerField(
        default=120,
        verbose_name='评审和改进超时时间（秒）',
        help_text='AI评审和改进的最大等待时间（总时长）'
    )

    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'generation_config'
        verbose_name = '生成行为配置'
        verbose_name_plural = '生成行为配置'

    def __str__(self):
        return self.name

    @classmethod
    def get_active_config(cls):
        """获取活跃的生成配置"""
        return cls.objects.filter(is_active=True).first()


class TestCaseGenerationTask(models.Model):
    """测试用例生成任务模型"""
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('generating', '生成中'),
        ('reviewing', '评审中'),
        ('revising', '改进中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]

    OUTPUT_MODE_CHOICES = [
        ('stream', '实时流式输出'),
        ('complete', '完整输出'),
    ]

    task_id = models.CharField(max_length=50, unique=True, verbose_name='任务ID')
    title = models.CharField(max_length=200, verbose_name='任务标题')
    requirement_text = models.TextField(verbose_name='需求描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.IntegerField(default=0, verbose_name='进度百分比')

    # 流式输出配置
    output_mode = models.CharField(
        max_length=10,
        choices=OUTPUT_MODE_CHOICES,
        default='stream',
        verbose_name='输出模式'
    )

    GRANULARITY_CHOICES = [
        ('coarse', '粗粒度'),
        ('medium', '中粒度'),
        ('fine', '细粒度'),
    ]

    case_type = models.TextField(blank=True, default='', verbose_name='用例类型补充指令')
    granularity = models.CharField(
        max_length=10, choices=GRANULARITY_CHOICES, default='medium', verbose_name='颗粒度'
    )

    # 流式缓冲区和状态跟踪
    stream_buffer = models.TextField(blank=True, verbose_name='流式输出缓冲区')
    stream_position = models.IntegerField(default=0, verbose_name='流式输出位置')
    last_stream_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最后流式更新时间'
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generation_tasks',
        verbose_name='关联项目'
    )
    requirement = models.ForeignKey(
        'Requirement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generation_tasks',
        verbose_name='关联需求'
    )

    # 配置参数
    writer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True,
        related_name='writer_tasks', verbose_name='编写模型配置'
    )
    reviewer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True,
        related_name='reviewer_tasks', verbose_name='评审模型配置'
    )
    writer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True,
        related_name='writer_tasks', verbose_name='编写提示词配置'
    )
    reviewer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True,
        related_name='reviewer_tasks', verbose_name='评审提示词配置'
    )

    # 生成结果
    generated_test_cases = models.TextField(blank=True, verbose_name='生成的测试用例')
    review_feedback = models.TextField(blank=True, verbose_name='评审反馈')
    final_test_cases = models.TextField(blank=True, verbose_name='最终测试用例')

    # 元数据
    generation_log = models.TextField(blank=True, verbose_name='生成日志')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    is_saved_to_records = models.BooleanField(default=False, verbose_name='是否已保存到记录')
    saved_at = models.DateTimeField(null=True, blank=True, verbose_name='保存到记录时间')

    class Meta:
        db_table = 'testcase_generation_task'
        verbose_name = '测试用例生成任务'
        verbose_name_plural = '测试用例生成任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class ZentaoConfig(models.Model):
    """禅道连接配置"""
    name = models.CharField(max_length=100, default='默认配置', verbose_name='配置名称')
    zentao_url = models.CharField(max_length=500, verbose_name='禅道地址')
    zentao_account = models.CharField(max_length=100, verbose_name='登录账号')
    zentao_password = models.CharField(max_length=255, verbose_name='登录密码')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'zentao_configs'
        verbose_name = '禅道配置'
        verbose_name_plural = '禅道配置'

    def __str__(self):
        return f"{self.name} - {self.zentao_url}"

    @classmethod
    def get_active_config(cls):
        """获取活跃的禅道配置"""
        return cls.objects.filter(is_active=True).first()


class Requirement(models.Model):
    """需求管理模型"""
    SOURCE_TYPE_CHOICES = [
        ('zentao', '禅道同步'),
        ('manual', '手动创建'),
        ('ai_import', 'AI导入'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='requirements',
        verbose_name='关联项目'
    )
    zentao_id = models.IntegerField(
        null=True, blank=True, unique=True, verbose_name='禅道需求ID'
    )
    product_id = models.IntegerField(null=True, blank=True, verbose_name='禅道产品ID')
    product_name = models.CharField(
        max_length=200, blank=True, default='', verbose_name='产品名称'
    )
    title = models.CharField(max_length=500, verbose_name='需求标题')
    spec = models.TextField(blank=True, default='', verbose_name='需求描述')
    category = models.CharField(
        max_length=50, blank=True, default='', verbose_name='分类'
    )
    priority = models.IntegerField(
        null=True, blank=True, verbose_name='优先级(1-5)'
    )
    stage = models.CharField(
        max_length=50, blank=True, default='', verbose_name='阶段'
    )
    status = models.CharField(
        max_length=50, blank=True, default='draft', verbose_name='状态'
    )
    source_type = models.CharField(
        max_length=20, choices=SOURCE_TYPE_CHOICES, default='manual',
        verbose_name='来源类型'
    )
    source_note = models.CharField(
        max_length=500, blank=True, default='', verbose_name='来源备注'
    )
    estimate = models.IntegerField(
        null=True, blank=True, verbose_name='预计工时(小时)'
    )
    module_id = models.IntegerField(null=True, blank=True, verbose_name='模块ID')
    assigned_to = models.CharField(
        max_length=100, blank=True, default='', verbose_name='指派人'
    )
    raw_data = models.JSONField(
        null=True, blank=True, verbose_name='原始数据(禅道)'
    )
    synced_at = models.DateTimeField(
        null=True, blank=True, verbose_name='同步时间'
    )

    # AI 分析来源独有（吸收自 BusinessRequirement）
    requirement_id = models.CharField(
        max_length=50, blank=True, default='', verbose_name='需求编号(AI生成)'
    )
    requirement_level = models.CharField(
        max_length=10, blank=True, default='', verbose_name='需求级别'
    )
    acceptance_criteria = models.TextField(blank=True, default='', verbose_name='验收标准')
    analysis = models.ForeignKey(
        'RequirementAnalysis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='unified_requirements', verbose_name='关联文档分析'
    )
    module_name = models.CharField(
        max_length=100, blank=True, default='', verbose_name='模块名称(AI来源文本)'
    )
    parent_requirement = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        verbose_name='父级需求'
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_requirements', verbose_name='创建者'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'requirements'
        verbose_name = '需求'
        verbose_name_plural = '需求'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_source_type_display()}"


def create_requirement_from_br_data(analysis, req_data):
    """从旧 BusinessRequirement 格式的 req_data 字典创建 Requirement。

    字段映射：
        requirement_name -> title
        description -> spec
        requirement_type -> category
        module -> module_name
        estimated_hours -> estimate
        requirement_id, requirement_level, acceptance_criteria, parent_requirement -> 同名
        reviewer -> 丢弃（Requirement 无对应字段）
    """
    project = analysis.document.project
    if not project:
        from apps.projects.models import Project as _Project
        from apps.users.models import User as _User
        owner, _ = _User.objects.get_or_create(
            username='ai_default', defaults={'is_active': False},
        )
        project, _ = _Project.objects.get_or_create(
            name='AI分析需求默认项目',
            defaults={'description': 'AI分析自动创建的需求', 'owner': owner},
        )
    return Requirement.objects.create(
        project=project,
        source_type='ai_import',
        analysis=analysis,
        title=req_data.get('requirement_name', '') or req_data.get('requirement_id', ''),
        spec=req_data.get('description', '') or '',
        category=req_data.get('requirement_type', '') or '',
        module_name=req_data.get('module', '') or '',
        requirement_id=req_data.get('requirement_id', '') or '',
        requirement_level=req_data.get('requirement_level', '') or '',
        acceptance_criteria=req_data.get('acceptance_criteria', '') or '',
        estimate=req_data.get('estimated_hours'),
        parent_requirement=req_data.get('parent_requirement'),
    )


class KnowledgeDocument(models.Model):
    """知识文档模型"""
    KNOWLEDGE_LEVEL_CHOICES = [
        ('global', '全局知识'),
        ('project', '项目知识'),
    ]

    STATUS_CHOICES = [
        ('uploaded', '已上传'),
        ('processing', '处理中'),
        ('ready', '就绪'),
        ('failed', '失败'),
    ]

    name = models.CharField(max_length=200, verbose_name='文档名称')
    file = models.FileField(upload_to='knowledge_docs/%Y/%m/', verbose_name='文档文件')
    file_type = models.CharField(max_length=10, verbose_name='文件类型')
    knowledge_level = models.CharField(
        max_length=20, choices=KNOWLEDGE_LEVEL_CHOICES, default='global', verbose_name='知识级别'
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE,
        related_name='knowledge_documents', verbose_name='关联项目'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='uploaded', verbose_name='状态'
    )
    raw_text = models.TextField(blank=True, verbose_name='解析后的文本内容')
    chunk_count = models.IntegerField(default=0, verbose_name='分块数量')
    entry_count = models.IntegerField(default=0, verbose_name='提取的条目数')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    is_extracting = models.BooleanField(default=False, verbose_name='是否提取中')
    extract_progress = models.IntegerField(default=0, verbose_name='提取进度(0-100)')
    extract_message = models.CharField(max_length=200, blank=True, default='', verbose_name='提取状态信息')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    ragflow_dataset_id = models.CharField(max_length=64, blank=True)
    ragflow_document_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'knowledge_documents'
        verbose_name = '知识文档'
        verbose_name_plural = '知识文档'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"


class KnowledgeEntry(models.Model):
    """知识条目模型（手动创建或LLM自动提取）"""
    CATEGORY_CHOICES = [
        ('module', '功能模块'),
        ('data_model', '数据模型'),
        ('interface', '接口规范'),
        ('business_rule', '业务规则'),
        ('naming', '命名约定'),
        ('constraint', '约束条件'),
        ('other', '其他'),
    ]

    SOURCE_CHOICES = [
        ('manual', '手动创建'),
        ('llm_extract', 'LLM提取'),
    ]

    name = models.CharField(max_length=200, verbose_name='条目名称')
    content = models.TextField(verbose_name='条目内容')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name='分类'
    )
    knowledge_level = models.CharField(
        max_length=20, choices=KnowledgeDocument.KNOWLEDGE_LEVEL_CHOICES,
        default='global', verbose_name='知识级别'
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE,
        related_name='knowledge_entries', verbose_name='关联项目'
    )
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='manual', verbose_name='来源'
    )
    source_document = models.ForeignKey(
        KnowledgeDocument, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='entries', verbose_name='来源文档'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    ragflow_dataset_id = models.CharField(max_length=64, blank=True)
    ragflow_document_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'knowledge_entries'
        verbose_name = '知识条目'
        verbose_name_plural = '知识条目'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_category_display()}"


class AIModelService:
    """AI模型服务类"""

    @staticmethod
    def get_openai_compatible_headers(api_key: str) -> Dict[str, str]:
        """构建 OpenAI 兼容接口请求头，同时兼容部分厂商的 api-key 认证。"""
        return {
            'Authorization': f'Bearer {api_key}',
            'api-key': api_key,
            'Content-Type': 'application/json'
        }

    @staticmethod
    def build_openai_compatible_url(base_url: str, endpoint: str) -> str:
        """根据用户输入的 base_url 构建 OpenAI 兼容接口地址。"""
        normalized_base_url = base_url.rstrip('/')

        if normalized_base_url.endswith(endpoint):
            return normalized_base_url

        for known_endpoint in ('/chat/completions', '/models'):
            if normalized_base_url.endswith(known_endpoint):
                normalized_base_url = normalized_base_url[:-len(known_endpoint)]
                break

        import re
        version_match = re.search(r'/v(\d+)/?$', normalized_base_url)
        if version_match:
            return f"{normalized_base_url}{endpoint}"

        return f"{normalized_base_url}/v1{endpoint}"

    @staticmethod
    async def call_openai_compatible_api(
            config: AIModelConfig,
            messages: List[Dict[str, str]],
            max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        调用OpenAI兼容格式的API

        Args:
            config: AI模型配置
            messages: 消息列表
            max_tokens: 可选的最大token数，如果不指定则使用config.max_tokens

        Returns:
            API响应字典
        """
        # 统一走 apps.ai.AIClient（鉴权/URL/可观测均收敛于此）
        return await AIClient.chat(config, messages, max_tokens=max_tokens)

    @staticmethod
    async def list_available_models(config: AIModelConfig) -> List[str]:
        """获取当前配置下可用的模型列表。"""
        return await AIClient.list_models(config)

    @staticmethod
    async def call_deepseek_api(config: AIModelConfig, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用DeepSeek API (兼容OpenAI格式)"""
        return await AIModelService.call_openai_compatible_api(config, messages)

    @staticmethod
    async def call_qwen_api(config: AIModelConfig, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用千问API (兼容OpenAI格式)"""
        return await AIModelService.call_openai_compatible_api(config, messages)

    @staticmethod
    async def generate_embeddings(
            config: AIModelConfig,
            texts: List[str]
    ) -> List[List[float]]:
        """
        调用 OpenAI 兼容的 embedding API 生成向量

        Args:
            config: AI模型配置（role=embedding 或任意兼容 embedding API 的模型）
            texts: 待向量化的文本列表

        Returns:
            embedding 向量列表
        """
        return await AIClient.embeddings(config, texts)

    @staticmethod
    async def call_openai_compatible_api_stream(
            config: AIModelConfig,
            messages: List[Dict[str, str]],
            callback=None,
            max_tokens: int = None
    ) -> AsyncIterator[str]:
        """
        流式调用OpenAI兼容格式的API，支持自动续写（统一走 apps.ai.AIClient）。
        """
        async for chunk in AIClient.chat_stream(config, messages, callback=callback, max_tokens=max_tokens):
            yield chunk

    @staticmethod
    def _build_knowledge_section(selected_knowledge: list = None) -> str:
        """
        构建业务知识 prompt 片段

        Args:
            selected_knowledge: 用户选择的业务知识列表

        Returns:
            格式化的业务知识 prompt 字符串
        """
        if not selected_knowledge:
            return ""

        items = []
        for k in selected_knowledge:
            name = k.get('name', '知识点')
            content = k.get('content', '')
            if content:
                items.append(f"### {name}\n{content}")

        if not items:
            return ""

        return (
            "【业务知识 - 请严格参考以下知识设计测试用例】\n"
            "以下是该项目的业务背景知识，请确保生成的测试用例符合这些知识中描述的规范、约束和业务规则：\n\n"
            + "\n\n".join(items)
            + "\n\n"
        )

    @staticmethod
    async def generate_test_cases(task: TestCaseGenerationTask, selected_knowledge: list = None) -> str:
        """生成测试用例"""
        writer_prompt = task.writer_prompt_config.content

        # 构建业务知识部分
        knowledge_section = AIModelService._build_knowledge_section(selected_knowledge)

        # 构建用户提示（fine 保留既有详细指令；coarse/medium 精简偏好；输出顺序/特殊字符指令不变）
        user_message = AIModelService._build_writer_user_message(
            task.requirement_text, knowledge_section, task.case_type, task.granularity)

        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": user_message}
        ]

        # 所有支持的模型都使用兼容OpenAI的接口
        # 使用配置的max_tokens，不硬编码限制
        response = await AIModelService.call_openai_compatible_api(
            task.writer_model_config,
            messages
            # 不再硬编码max_tokens，使用配置文件中的值（如32000）
        )

        return response['choices'][0]['message']['content']

    @staticmethod
    async def review_test_cases(task: TestCaseGenerationTask, test_cases: str) -> str:
        """评审测试用例"""
        try:
            reviewer_prompt = task.reviewer_prompt_config.content

            # 增强的评审指令
            user_message = (
                f"请对以下生成的测试用例进行严格的专家级评审。\n\n"
                f"【评审重点】\n"
                f"1. **覆盖率漏洞**：请仔细比对用例集是否覆盖了常见的异常场景（如断网、超时、数据冲突）和边界条件。\n"
                f"2. **逻辑严密性**：检查预期结果是否具体、可验证（例如'提示错误'是不够的，需说明具体错误码或文案）。\n"
                f"3. **冗余检查**：指出是否有重复或无效的用例。\n\n"
                f"【待评审用例】\n{test_cases}\n\n"
                f"【输出格式要求】\n"
                f"请输出一份包含评分、问题列表和改进建议的详细评审报告。"
                f"**重要**：输出格式要求紧凑，不要在段落之间添加多余的空行，每个问题点之间用单空行分隔即可，用例展示仍为markdown形式。"
            )

            messages = [
                {"role": "system", "content": reviewer_prompt},
                {"role": "user", "content": user_message}
            ]

            # 所有支持的模型都使用兼容OpenAI的接口
            response = await AIModelService.call_openai_compatible_api(task.reviewer_model_config, messages)

            return response['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"评审测试用例时出错: {e}")
            # 返回一个默认的评审结果
            return f"评审过程中出现错误: {str(e)}\n\n建议：测试用例结构完整，可以使用。"

    @staticmethod
    def _build_preferences_block(case_type: str = '', granularity: str = 'medium') -> str:
        """按颗粒度与用户补充指令生成【生成偏好】指令块（纯函数，可单测）"""
        lines = []
        g = (granularity or 'medium').lower()
        if g == 'coarse':
            lines.append('【颗粒度：粗】场景级拆分：优先关键功能与主路径，同类验证点可合并为一条用例，数量精简。')
        elif g == 'fine':
            lines.append('【颗粒度：细】逐验证点拆分：禁止将多个验证点合并进一条用例，每条只验证一个点，应写尽写。')
        else:
            lines.append('【颗粒度：中】正常、异常与边界场景兼顾，同类验证点可适度合并。')
        if case_type and case_type.strip():
            lines.append(f'【用户补充要求】{case_type.strip()}')
        return '\n'.join(lines)

    @staticmethod
    def _build_writer_user_message(
            requirement_text: str,
            knowledge_section: str,
            case_type: str = '',
            granularity: str = 'medium') -> str:
        """构建测试用例生成阶段的用户消息（纯函数，可单测）。

        granularity=fine 时保留既有详细指令（数量原则/深度遍历/拒绝合并/场景扩展库）；
        coarse/medium 使用精简的颗粒度偏好行。均保留输出顺序与特殊字符指令，并追加用户补充要求。
        """
        g = (granularity or 'medium').lower()
        if g == 'fine':
            instructions = (
                f"1. **数量原则**：请根据需求内容的实际复杂度，自动决定生成用例的数量。务必覆盖所有功能点、异常场景和边界条件，不设数量上限，应写尽写。\n"
                f"2. **深度遍历策略**：\n"
                f"   - 请按文档结构逐章节分析，不要遗漏末尾的功能点。\n"
                f"   - 对每个功能点，必须设计：1个正常场景 + 2-3个异常/边界场景。\n"
                f"3. **拒绝合并**：严禁将多个验证点合并在一条用例中。例如'验证输入框'应拆分为'输入为空'、'输入超长'、'输入特殊字符'等独立用例。\n"
                f"4. **场景扩展库**：\n"
                f"   - 数据完整性（必填项、默认值、数据类型）\n"
                f"   - 业务逻辑约束（状态流转、权限控制、重复操作）\n"
                f"   - 外部接口异常（超时、断网、返回错误）\n"
                f"   - UI交互体验（提示文案、跳转逻辑、防误触）\n"
            )
            if case_type and case_type.strip():
                instructions += f"【用户补充要求】{case_type.strip()}\n"
        else:
            instructions = AIModelService._build_preferences_block(case_type, granularity)

        return (
            f"{knowledge_section}"
            f"请深入分析以下需求文档，并设计高覆盖率的测试用例。\n\n"
            f"【生成指令】\n{instructions.rstrip()}\n"
            f"5. **⚠️ 输出顺序要求（必须严格执行）**：\n"
            f"   - **必须按用例编号从小到大的顺序输出**（如：001, 002, 003...或LOGIN_001, LOGIN_002, LOGIN_003...）\n"
            f"   - **绝对不能跳号、重复或乱序输出**\n"
            f"   - **编号必须连续，中间不能有遗漏**\n"
            f"   - **所有用例必须一次性完整输出，不能中断**\n"
            rf"6. **⚠️ 特殊字符处理（关键）**：\n"
            rf"   - **禁止任何 Markdown 标记**：不得使用加粗 `**`/`*`、标题 `#`、代码块围栏、HTML 标签或 `<br>`。\n"
            rf"   - **不得输出 Markdown 表格**；JSON 字符串值中的管道符 '|' 可原样书写，无需转义或实体替换。\n"
            rf"   - 多步骤请拆成 `steps` 数组的多个元素（每个元素 `{{\"desc\":...,\"expect\":...}}`），不要用 `<br>` 或序号拼接。\n\n"
            f"【需求文档内容】\n{requirement_text}"
        )

    @staticmethod
    async def generate_test_cases_stream(
            task: TestCaseGenerationTask,
            callback=None,
            selected_knowledge: list = None
    ) -> str:
        """
        流式生成测试用例

        Args:
            task: 生成任务对象
            callback: 可选的回调函数，每收到一个chunk就调用，用于实时保存到数据库
            selected_knowledge: 用户选择的业务知识列表

        Returns:
            str: 完整的测试用例内容
        """
        writer_prompt = task.writer_prompt_config.content

        # 构建业务知识部分
        knowledge_section = AIModelService._build_knowledge_section(selected_knowledge)

        # 构建用户提示（fine 保留既有详细指令；输出顺序/特殊字符指令不变）
        user_message = AIModelService._build_writer_user_message(
            task.requirement_text, knowledge_section, task.case_type, task.granularity)

        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": user_message}
        ]

        # 流式调用API，确保正确关闭生成器
        # 使用配置的max_tokens，不硬编码限制
        generator = AIModelService.call_openai_compatible_api_stream(
            task.writer_model_config,
            messages,
            callback=callback
            # 不再硬编码max_tokens，使用配置文件中的值（如32000）
        )

        full_content = ""
        chunk_count = 0
        try:
            async for chunk in generator:
                full_content += chunk
                chunk_count += 1
        except Exception as e:
            logger.error(f"流式生成测试用例时出错: {e}")
            raise
        finally:
            # 确保生成器被正确关闭
            try:
                await generator.aclose()
            except Exception as close_error:
                logger.warning(f"关闭generator时出错: {close_error}")

        logger.info(f"流式生成完成: 总chunk数={chunk_count}, 总字符数={len(full_content)}")

        # 统计生成的用例数量
        case_count = full_content.count('TC-') + full_content.count('TEST-') + full_content.count('测试用例')
        logger.info(f"生成用例统计: 约检测到{case_count}个用例编号标记")

        return full_content

    @staticmethod
    async def review_test_cases_stream(
            task: TestCaseGenerationTask,
            test_cases: str,
            callback=None
    ) -> str:
        """
        流式评审测试用例

        Args:
            task: 生成任务对象
            test_cases: 待评审的测试用例
            callback: 可选的回调函数，每收到一个chunk就调用

        Returns:
            str: 完整的评审反馈
        """
        reviewer_prompt = task.reviewer_prompt_config.content

        # 增强的评审指令
        user_message = (
            f"请对以下生成的测试用例进行严格的专家级评审。\n\n"
            f"【评审重点】\n"
            f"1. **覆盖率漏洞**：请仔细比对用例集是否覆盖了常见的异常场景（如断网、超时、数据冲突）和边界条件。\n"
            f"2. **逻辑严密性**：检查预期结果是否具体、可验证（例如'提示错误'是不够的，需说明具体错误码或文案）。\n"
            f"3. **冗余检查**：指出是否有重复或无效的用例。\n\n"
            f"【待评审用例】\n{test_cases}\n\n"
            f"【输出格式要求】\n"
            f"请输出一份包含评分、问题列表和改进建议的详细评审报告。"
            f"**重要**：输出格式要求紧凑，不要在段落之间添加多余的空行，每个问题点之间用单空行分隔即可，用例展示仍为markdown形式。"
        )

        messages = [
            {"role": "system", "content": reviewer_prompt},
            {"role": "user", "content": user_message}
        ]

        # 流式调用API，确保正确关闭生成器
        generator = AIModelService.call_openai_compatible_api_stream(
            task.reviewer_model_config,
            messages,
            callback=callback
        )

        full_content = ""
        chunk_count = 0
        try:
            async for chunk in generator:
                full_content += chunk
                chunk_count += 1
        except Exception as e:
            logger.error(f"流式评审测试用例时出错: {e}")
            return f"评审过程中出现错误: {str(e)}\n\n建议：测试用例结构完整，可以使用。"
        finally:
            # 确保生成器被正确关闭
            try:
                await generator.aclose()
            except Exception as close_error:
                logger.warning(f"关闭generator时出错: {close_error}")

        logger.info(f"流式评审完成: 总chunk数={chunk_count}, 总字符数={len(full_content)}")
        return full_content

    @staticmethod
    def _build_revise_user_message(
            original_test_cases: str,
            review_feedback: str,
            prefs: str = '') -> str:
        """构建评审后改进阶段的用户消息（纯函数，可单测）。

        与 writer 的 JSONL 输出约定保持一致：禁止 Markdown（加粗/表格/<br>），
        steps 必须是 [{desc, expect}] 数组。
        """
        return (
            f"请根据以下专家评审意见，改进和完善测试用例。\n\n"
            f"{prefs}\n\n"
            f"【原始测试用例】\n{original_test_cases}\n\n"
            f"【评审意见】\n{review_feedback}\n\n"
            f"【改进要求】\n"
            f"1. 严格根据评审意见指出的问题进行修改\n"
            f"2. 补充缺失的测试场景\n"
            f"3. 修正不合理的预期结果\n"
            f"4. 删除冗余的测试用例\n"
            f"5. 保持测试用例的格式规范\n"
            f"6. **⚠️ 输出格式（必须严格执行）**：与【原始测试用例】保持同一 **JSONL** 结构——"
            f"每行一个独立可解析的 JSON 对象，行内不要换行；字段：case_id/title/precondition/steps/priority/test_type/module；"
            f"其中 `steps` 必须为 `[{{\"desc\":\"步骤描述\",\"expect\":\"该步骤预期结果\"}}]` 数组。\n"
            f"7. **⚠️ 禁止 Markdown**：不得使用 Markdown 加粗（`**`/`*`）、标题（`#`）、代码块围栏、"
            f"HTML 标签或 `<br>`；不得输出 Markdown 表格。`desc`/`expect` 均为纯文本，多步请拆成多个数组元素。\n"
            f"8. **⚠️ 输出顺序要求（必须严格执行）**：按编号从小到大输出，绝对不跳号、重复或乱序，"
            f"编号连续，所有用例一次性完整输出。\n"
            f"9. **必须输出完整**：请输出所有改进后的测试用例，不因篇幅省略任何一条。\n"
            f"10. **测试用例编号规则**：新增用例按原编号规则继续编号（如原最后一个为 TC-003，新增应为 TC-004），"
            f"不得使用'新增'、'用例1'等作为编号。\n\n"
            f"请直接输出改进后的完整测试用例，不要包含任何说明性文字。"
        )

    @staticmethod
    async def revise_test_cases_based_on_review(
            task: TestCaseGenerationTask,
            original_test_cases: str,
            review_feedback: str,
            callback=None
    ) -> str:
        """
        根据评审意见改进测试用例

        Args:
            task: 生成任务对象
            original_test_cases: 原始生成的测试用例
            review_feedback: AI评审意见
            callback: 可选的回调函数，每收到一个chunk就调用

        Returns:
            str: 改进后的测试用例
        """
        writer_prompt = task.writer_prompt_config.content

        prefs = AIModelService._build_preferences_block(task.case_type, task.granularity)

        # 构建改进指令（JSONL 输出约定，禁止任何 Markdown 标记）
        user_message = AIModelService._build_revise_user_message(
            original_test_cases, review_feedback, prefs)

        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": user_message}
        ]

        # 流式调用API，确保正确关闭生成器
        # 使用配置的max_tokens，不硬编码限制
        generator = AIModelService.call_openai_compatible_api_stream(
            task.writer_model_config,
            messages,
            callback=callback
            # 不再硬编码max_tokens，使用配置文件中的值（如32000）
        )

        full_content = ""
        chunk_count = 0
        try:
            async for chunk in generator:
                full_content += chunk
                chunk_count += 1
        except Exception as e:
            logger.error(f"根据评审意见改进测试用例时出错: {e}")
            # 改进失败时返回原始用例
            return original_test_cases
        finally:
            # 确保生成器被正确关闭
            try:
                await generator.aclose()
            except Exception as close_error:
                logger.warning(f"关闭generator时出错: {close_error}")

        logger.info(f"流式改进完成: 总chunk数={chunk_count}, 总字符数={len(full_content)}")

        # 统计改进后的用例数量
        case_count = full_content.count('TC-') + full_content.count('**TC-') + full_content.count('测试用例')
        logger.info(f"改进用例统计: 约检测到{case_count}个用例编号标记")

        return full_content

    @staticmethod
    def sort_test_cases_by_id(test_cases_content: str) -> str:
        """
        按照测试用例编号（case_id 数字部分）对 JSONL 测试用例排序。

        Args:
            test_cases_content: 测试用例内容（JSONL 字符串）

        Returns:
            str: 排序后的测试用例内容
        """
        if not test_cases_content:
            return test_cases_content

        lines = [ln for ln in test_cases_content.split('\n') if ln.strip()]
        if len(lines) < 2:
            return test_cases_content

        # 逐行解析为 (原始行, 用例对象|None)
        entries = []
        for line in lines:
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                obj = None
            entries.append((line, obj))

        # 非 JSONL（没有一行是可解析且含 case_id 的对象）直接原样返回
        if not any(isinstance(obj, dict) and 'case_id' in obj for _, obj in entries):
            logger.info("未检测到 JSONL 测试用例编号，保持原顺序")
            return test_cases_content

        def sort_key(entry):
            line, obj = entry
            if not (isinstance(obj, dict) and isinstance(obj.get('case_id'), str)):
                return (2, 0)  # 不可解析/无编号 → 排到末尾，保持原有相对顺序
            m = _CASE_ID_PATTERN.match(obj['case_id'].strip())
            if not m:
                return (2, 0)
            return (1, int(m.group(3)))

        # Python 排序稳定：同编号/兜底行保持原始相对顺序，不丢任何行
        entries.sort(key=sort_key)
        logger.info(f"成功对{len(entries)}个测试用例按编号排序")
        return '\n'.join(line for line, _ in entries)

    @staticmethod
    def fix_incomplete_last_case(test_cases_content: str) -> str:
        """
        检测并移除 JSONL 末尾不完整的用例行（截断/无法解析的行）。

        Args:
            test_cases_content: 测试用例内容（JSONL 字符串）

        Returns:
            str: 修复后的测试用例内容
        """
        if not test_cases_content:
            return test_cases_content

        lines = test_cases_content.split('\n')

        # 从末尾向前：跳过空行，丢弃截断或无法解析成用例对象的行
        end = len(lines)
        while end > 0:
            line = lines[end - 1].strip()
            if not line:
                end -= 1
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                obj = None
            if isinstance(obj, dict) and ('case_id' in obj or 'title' in obj):
                break  # 最后是完整用例，无需处理
            logger.warning(f"检测到末尾不完整用例行，已移除: {line[:60]}")
            end -= 1

        if end == len(lines):
            return test_cases_content
        logger.info(f"已删除不完整的末尾内容，保留了{end}行")
        return '\n'.join(lines[:end])

    @staticmethod
    def renumber_test_cases(test_cases_content: str) -> str:
        """
        按顺序重新编号 JSONL 测试用例，使编号连续。

        保留每行的前缀与分隔符（如 LOGIN_ / TC- / IMMSG），位数与原有编号一致；
        多前缀（如混合 LOGIN_* 与 REGISTER_*）各自独立连续编号；无数字编号的行保持不变。

        Args:
            test_cases_content: 测试用例内容（JSONL 字符串）

        Returns:
            str: 重新编号后的测试用例内容
        """
        if not test_cases_content:
            return test_cases_content

        entries = []
        for line in test_cases_content.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                obj = None
            entries.append(obj)

        if not any(isinstance(obj, dict) and 'case_id' in obj for obj in entries):
            logger.warning("未检测到 JSONL 测试用例，无法重新编号")
            return test_cases_content

        counters = {}  # 按 前缀+分隔符 分别计数，避免不同模块编号互相干扰
        out_lines = []
        for obj in entries:
            if not isinstance(obj, dict):
                # 丢弃非对象 JSON 行（如裸 null/数字/字符串），避免污染最终用例，
                # 否则保存/解析用例时会对 None 调用 .get() 而崩溃。
                logger.warning(
                    f"renumber_test_cases: 丢弃非对象 JSON 行: "
                    f"{json.dumps(obj, ensure_ascii=False)[:60]!r}")
                continue
            case_id = obj.get('case_id')
            m = _CASE_ID_PATTERN.match(str(case_id).strip()) if isinstance(case_id, str) else None
            if m:
                key = m.group(1) + m.group(2)
                counters[key] = counters.get(key, 0) + 1
                width = max(len(m.group(3)), 1)
                obj['case_id'] = f"{m.group(1)}{m.group(2)}{str(counters[key]).zfill(width)}"
            out_lines.append(json.dumps(obj, ensure_ascii=False))

        logger.info(f"重新编号完成: 共{sum(counters.values())}条测试用例")
        return '\n'.join(out_lines)


class RagflowConfig(models.Model):
    """RAGFlow 连接与检索配置(单例行)"""
    base_url = models.CharField(max_length=255, default="http://127.0.0.1:9380")
    api_key = models.CharField(max_length=255, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    rerank_id = models.CharField(max_length=255, blank=True)
    chunk_method = models.CharField(max_length=64, default="naive")
    graphrag_enabled = models.BooleanField(default=False)
    graphrag_method = models.CharField(max_length=16, default="light")
    score_scale = models.FloatField(default=10)
    embedding_models_json = models.TextField(default="{}", help_text="RAGFlow dataset_id → embedding_model 快照")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ragflow_configs"

    @staticmethod
    def get_solo():
        cfg, _ = RagflowConfig.objects.get_or_create(pk=1)
        return cfg


class RagflowBinding(models.Model):
    """项目 ⇄ RAGFlow dataset 绑定(多对多;null=全局默认)"""
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.CASCADE, related_name="ragflow_bindings")
    dataset_id = models.CharField(max_length=64)
    dataset_name = models.CharField(max_length=255, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)  # 拉取快照
    is_write_target = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)  # 项目级引擎开关
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ragflow_bindings"
        constraints = [models.UniqueConstraint(fields=["project", "dataset_id"], name="uniq_project_dataset")]

    def __str__(self):
        return f"{self.dataset_name}({self.dataset_id})"
