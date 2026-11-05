from rest_framework import serializers
from .models import (
    RequirementDocument, RequirementAnalysis,
    GeneratedTestCase, AnalysisTask, AIModelConfig, PromptConfig, TestCaseGenerationTask,
    GenerationConfig, ZentaoConfig, Requirement, WeKnoraConfig, WeKnoraProjectBinding,
    AutomationCase, AutomationEnvironment,
    AutomationExecution, AutomationExecutionSession
)
from apps.projects.models import Project


class RequirementDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = RequirementDocument
        fields = ['id', 'title', 'file', 'file_url', 'document_type', 'document_type_display',
                 'status', 'status_display', 'uploaded_by', 'uploaded_by_name', 'project',
                 'project_name', 'created_at', 'updated_at', 'file_size', 'extracted_text']
        read_only_fields = ['uploaded_by', 'file_size', 'extracted_text']

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class RequirementSerializer(serializers.ModelSerializer):
    """需求管理序列化器"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = Requirement
        fields = [
            'id', 'project', 'project_name', 'zentao_id', 'product_id',
            'product_name', 'title', 'spec', 'category', 'priority',
            'stage', 'status', 'source_type', 'source_type_display',
            'source_note', 'estimate', 'module_id', 'assigned_to',
            'raw_data', 'synced_at', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'synced_at', 'raw_data']

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        return super().create(validated_data)


class RequirementListSerializer(serializers.ModelSerializer):
    """需求列表序列化器（简化版）"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = Requirement
        fields = [
            'id', 'project', 'project_name', 'zentao_id', 'product_id',
            'product_name', 'title', 'priority', 'status', 'source_type',
            'source_type_display', 'category', 'estimate', 'module_id',
            'assigned_to', 'synced_at', 'created_at', 'updated_at'
        ]

class RequirementAnalysisSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    document_id = serializers.IntegerField(source='document.id', read_only=True)
    requirements = RequirementSerializer(many=True, read_only=True, source='unified_requirements')

    class Meta:
        model = RequirementAnalysis
        fields = ['id', 'document_id', 'document_title', 'analysis_report',
                 'requirements_count', 'analysis_time', 'created_at', 'updated_at', 'requirements']


class GeneratedTestCaseSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requirement_name = serializers.CharField(source='requirement.title', read_only=True)
    requirement_id_display = serializers.CharField(source='requirement.requirement_id', read_only=True)

    class Meta:
        model = GeneratedTestCase
        fields = ['id', 'case_id', 'title', 'priority', 'priority_display', 'precondition',
                 'test_steps', 'expected_result', 'status', 'status_display', 'generated_by_ai',
                 'reviewed_by_ai', 'review_comments', 'requirement', 'requirement_name',
                 'requirement_id_display', 'created_at', 'updated_at']


class AnalysisTaskSerializer(serializers.ModelSerializer):
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    document_title = serializers.CharField(source='document.title', read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = AnalysisTask
        fields = ['id', 'task_id', 'task_type', 'task_type_display', 'document', 'document_title',
                 'status', 'status_display', 'progress', 'result', 'error_message',
                 'started_at', 'completed_at', 'created_at', 'duration']
        read_only_fields = ['task_id', 'result', 'error_message', 'started_at', 'completed_at']

    def get_duration(self, obj):
        if obj.started_at and obj.completed_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None


class DocumentUploadSerializer(serializers.ModelSerializer):
    """文档上传专用序列化器"""
    class Meta:
        model = RequirementDocument
        fields = ['id', 'title', 'file', 'project']

    def create(self, validated_data):
        # 自动设置上传者（如果用户已登录）
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['uploaded_by'] = user
        else:
            # 如果是匿名用户，使用第一个超级用户作为默认用户
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['uploaded_by'] = default_user

        # 根据文件扩展名设置文档类型
        file = validated_data['file']
        if file.name.lower().endswith('.pdf'):
            validated_data['document_type'] = 'pdf'
        elif file.name.lower().endswith(('.doc', '.docx')):
            validated_data['document_type'] = 'docx'
        elif file.name.lower().endswith('.txt'):
            validated_data['document_type'] = 'txt'
        elif file.name.lower().endswith('.md'):
            validated_data['document_type'] = 'md'

        # 设置文件大小
        validated_data['file_size'] = file.size

        return super().create(validated_data)


class TestCaseGenerationRequestSerializer(serializers.Serializer):
    """测试用例生成请求序列化器"""
    requirement_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="需求ID列表"
    )
    test_level = serializers.ChoiceField(
        choices=[('unit', '单元测试'), ('integration', '集成测试'), ('system', '系统测试'), ('acceptance', '验收测试')],
        default='system',
        help_text="测试级别"
    )
    test_priority = serializers.ChoiceField(
        choices=[('P0', '最高优先级'), ('P1', '高优先级'), ('P2', '中优先级'), ('P3', '低优先级')],
        default='P1',
        help_text="测试优先级"
    )
    test_case_count = serializers.IntegerField(
        min_value=1,
        max_value=200,
        default=50,
        help_text="生成测试用例数量"
    )


class TestCaseReviewRequestSerializer(serializers.Serializer):
    """测试用例评审请求序列化器"""
    test_case_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="测试用例ID列表"
    )
    review_criteria = serializers.CharField(
        max_length=500,
        default="检查测试用例的完整性、准确性和可执行性",
        help_text="评审标准"
    )


class AIModelConfigSerializer(serializers.ModelSerializer):
    """AI模型配置序列化器（全平台统一配置表）"""
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    api_key_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AIModelConfig
        fields = ['id', 'name', 'model_type', 'model_type_display', 'role', 'role_display',
                  'api_key', 'api_key_masked', 'base_url', 'model_name', 'max_tokens', 'temperature', 'top_p',
                  'is_active', 'scope', 'provider_extra',
                  'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name']
        extra_kwargs = {
            'api_key': {'write_only': True},  # API Key只用于写入，不在响应中返回
            'provider_extra': {'required': False},
        }

    def get_api_key_masked(self, obj):
        """返回掩码版本的API Key"""
        if obj.api_key:
            # 显示前3个字符和后4个字符，中间用*替代
            if len(obj.api_key) > 7:
                return f"{obj.api_key[:3]}{'*' * (len(obj.api_key) - 7)}{obj.api_key[-4:]}"
            else:
                return '*' * len(obj.api_key)
        return ''

    def validate(self, attrs):
        """同一 (role, scope) 只能有一个活跃配置（应用层单 active 约束）。"""
        role = attrs.get('role') or (self.instance.role if self.instance else None)
        scope = attrs.get('scope') or (self.instance.scope if self.instance else 'global')
        is_active = attrs.get('is_active', self.instance.is_active if self.instance else True)

        if role and is_active:
            queryset = AIModelConfig.objects.filter(role=role, scope=scope, is_active=True)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    f'已存在活跃的 "{role}" 配置（作用域 {scope}），请先停用旧的配置再启用新的')

        # azure_openai 建议带 api-version，但允许为空（由用户决定）
        return attrs

    def create(self, validated_data):
        # 自动设置创建者
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            # 如果是匿名用户，使用第一个超级用户作为默认用户
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user

        return super().create(validated_data)


class PromptConfigSerializer(serializers.ModelSerializer):
    """提示词配置序列化器（v2：版本化，同一类型允许多版本，惟一一活跃）"""
    prompt_type_display = serializers.CharField(source='get_prompt_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = PromptConfig
        fields = ['id', 'name', 'prompt_type', 'prompt_type_display', 'content', 'is_active',
                  'version', 'version_note', 'is_seeded', 'seed_hash',
                  'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name', 'is_seeded', 'seed_hash']

    def validate(self, attrs):
        is_active = attrs.get('is_active', self.instance.is_active if self.instance else True)
        if is_active:
            prompt_type = attrs.get('prompt_type') or (self.instance.prompt_type if self.instance else None)
            if prompt_type:
                queryset = PromptConfig.objects.filter(prompt_type=prompt_type, is_active=True)
                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)
                if queryset.exists():
                    display = dict(PromptConfig.PROMPT_CHOICES).get(prompt_type, prompt_type)
                    raise serializers.ValidationError({
                        'is_active': f'{display} 已有活跃版本，请先停用旧的再启用新的'
                    })
        return attrs

    def create(self, validated_data):
        # 同一类型自动推进版本号
        prompt_type = validated_data.get('prompt_type')
        if prompt_type:
            latest = PromptConfig.objects.filter(prompt_type=prompt_type).order_by('-version').first()
            validated_data['version'] = (latest.version or 1) + 1 if latest else 1
            validated_data['version_note'] = validated_data.get('version_note') or f'v{validated_data["version"]}'
        # 自动设置创建者
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user

        return super().create(validated_data)


class TestCaseGenerationTaskSerializer(serializers.ModelSerializer):
    """测试用例生成任务序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    writer_model_name = serializers.CharField(source='writer_model_config.name', read_only=True)
    reviewer_model_name = serializers.CharField(source='reviewer_model_config.name', read_only=True)
    writer_prompt_name = serializers.CharField(source='writer_prompt_config.name', read_only=True)
    reviewer_prompt_name = serializers.CharField(source='reviewer_prompt_config.name', read_only=True)
    granularity_display = serializers.CharField(source='get_granularity_display', read_only=True)
    adopted_count = serializers.SerializerMethodField()
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseGenerationTask
        fields = ['id', 'task_id', 'title', 'requirement_text', 'status', 'status_display',
                 'progress', 'output_mode', 'project', 'project_name', 'requirement',
                 'writer_model_config', 'writer_model_name',
                 'reviewer_model_config', 'reviewer_model_name', 'writer_prompt_config', 'writer_prompt_name',
                 'reviewer_prompt_config', 'reviewer_prompt_name', 'generated_test_cases',
                 'review_feedback', 'final_test_cases', 'generation_log', 'error_message',
                 'weknora_answer', 'weknora_references', 'weknora_steps',
                 'created_by', 'created_by_name', 'created_at', 'updated_at', 'completed_at',
                 'case_type', 'granularity', 'granularity_display', 'adopted_count', 'case_count']
        read_only_fields = ['task_id', 'status', 'progress', 'generated_test_cases',
                          'review_feedback', 'final_test_cases', 'generation_log',
                          'error_message', 'weknora_answer', 'weknora_references', 'weknora_steps',
                          'created_by', 'completed_at']

    def get_adopted_count(self, obj):
        """该任务已采纳入库的用例数（测试用例通过 source_generation_task 回链）"""
        return obj.adopted_cases.count()

    def get_case_count(self, obj):
        """final_test_cases 实际用例条数（后端权威解析，前端不再自行计数）"""
        if not obj.final_test_cases:
            return 0
        # 函数内导入避免 serializers→views 循环依赖
        from apps.requirement_analysis.views import TestCaseGenerationTaskViewSet
        try:
            return len(TestCaseGenerationTaskViewSet()._parse_test_cases_content(obj.final_test_cases))
        except Exception:
            return 0

    def create(self, validated_data):
        # 自动设置创建者和任务ID
        import uuid
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user

        validated_data['task_id'] = f"TASK_{uuid.uuid4().hex[:8].upper()}"

        return super().create(validated_data)


class TestCaseGenerationRequestSerializer(serializers.Serializer):
    """新的测试用例生成请求序列化器"""
    title = serializers.CharField(max_length=200, help_text="任务标题")
    requirement_text = serializers.CharField(help_text="需求描述")
    use_writer_model = serializers.BooleanField(default=True, help_text="是否使用编写模型")
    use_reviewer_model = serializers.BooleanField(default=True, help_text="是否使用评审模型")
    selected_knowledge = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="用户选择的业务知识列表"
    )
    case_type = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default='',
        help_text='用例类型补充指令（自由文本）')
    granularity = serializers.ChoiceField(
        choices=['coarse', 'medium', 'fine'], required=False, default='medium',
        help_text='颗粒度')


class GenerationConfigSerializer(serializers.ModelSerializer):
    """生成行为配置序列化器"""
    default_output_mode_display = serializers.CharField(source='get_default_output_mode_display', read_only=True)

    class Meta:
        model = GenerationConfig
        fields = [
            'id', 'name', 'default_output_mode', 'default_output_mode_display',
            'enable_auto_review', 'review_timeout',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._deactivate_others(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._deactivate_others(instance)
        return instance

    def _deactivate_others(self, instance):
        """激活互斥：is_active=True 时禁用其他配置，保证同一时刻最多一个启用（与 enable action 行为一致）"""
        if instance.is_active:
            GenerationConfig.objects.exclude(pk=instance.pk).update(is_active=False)


class ZentaoConfigSerializer(serializers.ModelSerializer):
    """禅道配置序列化器"""
    password_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ZentaoConfig
        fields = [
            'id', 'name', 'zentao_url', 'zentao_account',
            'zentao_password', 'password_masked', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'zentao_password': {'write_only': True}
        }

    def get_password_masked(self, obj):
        """返回掩码版本的密码"""
        if obj.zentao_password:
            if len(obj.zentao_password) > 7:
                return f"{obj.zentao_password[:3]}{'*' * (len(obj.zentao_password) - 7)}{obj.zentao_password[-4:]}"
            else:
                return '*' * len(obj.zentao_password)
        return ''


class AIRequirementParseRequestSerializer(serializers.Serializer):
    """AI解析需求请求"""
    project_id = serializers.IntegerField(help_text="项目ID")
    content = serializers.CharField(help_text="需求文档文本内容")


class AIRequirementImportRequestSerializer(serializers.Serializer):
    """AI导入需求请求"""
    project_id = serializers.IntegerField(help_text="项目ID")
    requirements = serializers.ListField(
        child=serializers.DictField(),
        help_text="AI解析出的需求项列表"
    )


class RequirementGenerateTestCasesRequestSerializer(serializers.Serializer):
    """从需求管理批量AI生成测试用例请求"""
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="选中的需求ID列表"
    )
    output_mode = serializers.ChoiceField(
        choices=['stream', 'complete'], required=False, default=None,
        help_text='输出模式（默认使用生成行为配置）')
    case_type = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default='',
        help_text='用例类型补充指令（自由文本）')
    granularity = serializers.ChoiceField(
        choices=['coarse', 'medium', 'fine'], required=False, default='medium',
        help_text='颗粒度')
    use_reviewer_model = serializers.BooleanField(
        default=True, required=False, help_text='是否使用评审模型')
    selected_knowledge = serializers.DictField(
        required=False,
        default=dict,
        help_text="按需求ID分组的业务知识列表，如 {<requirement_id>: [{id, type, name, content}]}。"
                  "每条需求只使用其对应 ID 的知识作为生成上下文。"
    )


class ZentaoSyncRequestSerializer(serializers.Serializer):
    """禅道同步请求"""
    project_id = serializers.IntegerField(help_text="目标项目ID")
    product_id = serializers.IntegerField(help_text="禅道产品ID")
    product_name = serializers.CharField(default='', help_text="产品名称")
    story_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="要同步的需求ID列表"
    )


class WeKnoraConfigSerializer(serializers.ModelSerializer):
    """WeKnora 连接配置序列化器(单例行)"""
    class Meta:
        model = WeKnoraConfig
        fields = [
            'id', 'base_url', 'api_key', 'timeout', 'default_agent_id',
            'default_agent_name', 'knowledge_base_ids', 'enabled',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True, 'required': False},
            'knowledge_base_ids': {'required': False},
            'default_agent_name': {'required': False},
        }


class WeKnoraProjectBindingSerializer(serializers.ModelSerializer):
    """项目 ⇄ WeKnora 智能体绑定序列化器"""
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = WeKnoraProjectBinding
        fields = [
            'id', 'project', 'project_name', 'agent_id', 'agent_name',
            'knowledge_base_ids', 'enabled', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'agent_name': {'required': False},
            'knowledge_base_ids': {'required': False},
        }

# ============ 自动化用例（转化与执行） ============


class AutomationEnvironmentSerializer(serializers.ModelSerializer):
    """环境序列化：password 只写不读，回显 has_password 布尔。"""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = AutomationEnvironment
        fields = ['id', 'project', 'name', 'base_url', 'login_url', 'username', 'password',
                  'has_password', 'variables', 'is_active', 'description',
                  'enable_screenshot', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_has_password(self, obj):
        return bool(obj.password)

    def validate_variables(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('variables 必须是数组')
        for item in value:
            if not isinstance(item, dict) or not str(item.get('key', '')).strip():
                raise serializers.ValidationError('每个变量必须包含非空 key')
        return value

    def update(self, instance, validated_data):
        # 未传 password 字段时保持原值，避免编辑其他字段把密码清空
        if 'password' not in validated_data:
            validated_data['password'] = instance.password
        return super().update(instance, validated_data)


class AutomationCaseSerializer(serializers.ModelSerializer):
    source_type = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', read_only=True)
    requirement_title = serializers.CharField(source='requirement.title', read_only=True)
    last_execution = serializers.SerializerMethodField()

    class Meta:
        model = AutomationCase
        fields = ['id', 'project', 'project_name', 'requirement', 'requirement_title',
                  'source_generated_case', 'source_test_case', 'source_type', 'title',
                  'precondition', 'steps', 'convert_status', 'convert_error',
                  'last_failure_summary', 'success_trace',
                  'created_at', 'updated_at', 'last_execution']
        read_only_fields = ['project', 'requirement', 'source_generated_case', 'source_test_case',
                            'convert_status', 'convert_error', 'last_failure_summary',
                            'success_trace', 'created_at', 'updated_at']

    def get_source_type(self, obj):
        return obj.source_type

    def get_last_execution(self, obj):
        execution = obj.automation_executions.order_by('-id').first()
        if not execution:
            return None
        return {'id': execution.id, 'status': execution.status,
                'finished_at': execution.finished_at}

    def validate_steps(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('steps 必须是数组')
        normalized = []
        for index, step in enumerate(value, start=1):
            step = step or {}
            action = str(step.get('action', '')).strip()
            if not action:
                continue
            normalized.append({
                'index': index,
                'action': action,
                'verify': str(step.get('verify', '')).strip(),
            })
        return normalized


class AutomationExecutionSerializer(serializers.ModelSerializer):
    case_title = serializers.CharField(source='case.title', read_only=True)
    environment_name = serializers.CharField(source='environment.name', read_only=True)

    class Meta:
        model = AutomationExecution
        fields = ['id', 'case', 'case_title', 'session', 'environment', 'environment_name',
                  'status', 'result_detail', 'log', 'error', 'started_at', 'finished_at']


class AutomationExecutionSessionSerializer(serializers.ModelSerializer):
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    executions = serializers.SerializerMethodField()

    class Meta:
        model = AutomationExecutionSession
        fields = ['id', 'project', 'environment', 'environment_name', 'status', 'login_status',
                  'error', 'executions', 'started_at', 'finished_at']

    def get_executions(self, obj):
        return [
            {'id': e.id, 'case_id': e.case_id, 'case_title': e.case.title,
             'status': e.status, 'error': e.error}
            for e in obj.executions.select_related('case').order_by('id')
        ]
