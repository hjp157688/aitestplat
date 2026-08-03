from rest_framework import serializers
from .models import (
    RequirementDocument, RequirementAnalysis, BusinessRequirement,
    GeneratedTestCase, AnalysisTask, AIModelConfig, PromptConfig, TestCaseGenerationTask,
    GenerationConfig, ZentaoConfig, Requirement, KnowledgeDocument, KnowledgeEntry
)


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


class BusinessRequirementSerializer(serializers.ModelSerializer):
    requirement_type_display = serializers.CharField(source='get_requirement_type_display', read_only=True)
    requirement_level_display = serializers.CharField(source='get_requirement_level_display', read_only=True)
    parent_requirement_name = serializers.CharField(source='parent_requirement.requirement_name', read_only=True)
    
    class Meta:
        model = BusinessRequirement
        fields = ['id', 'requirement_id', 'requirement_name', 'requirement_type', 
                 'requirement_type_display', 'parent_requirement', 'parent_requirement_name',
                 'module', 'requirement_level', 'requirement_level_display', 'reviewer', 
                 'estimated_hours', 'description', 'acceptance_criteria', 'created_at', 'updated_at']


class RequirementAnalysisSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    document_id = serializers.IntegerField(source='document.id', read_only=True)
    requirements = BusinessRequirementSerializer(many=True, read_only=True)
    
    class Meta:
        model = RequirementAnalysis
        fields = ['id', 'document_id', 'document_title', 'analysis_report', 
                 'requirements_count', 'analysis_time', 'created_at', 'updated_at', 'requirements']


class GeneratedTestCaseSerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requirement_name = serializers.CharField(source='requirement.requirement_name', read_only=True)
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
    """AI模型配置序列化器"""
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    api_key_masked = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AIModelConfig
        fields = ['id', 'name', 'model_type', 'model_type_display', 'role', 'role_display',
                 'api_key', 'api_key_masked', 'base_url', 'model_name', 'max_tokens', 'temperature', 'top_p', 
                 'is_active', 'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name']
        extra_kwargs = {
            'api_key': {'write_only': True}  # API Key只用于写入，不在响应中返回
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
    """提示词配置序列化器"""
    prompt_type_display = serializers.CharField(source='get_prompt_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = PromptConfig
        fields = ['id', 'name', 'prompt_type', 'prompt_type_display', 'content', 'is_active',
                 'created_by', 'created_by_name', 'created_at', 'updated_at']
        read_only_fields = ['created_by', 'created_by_name']

    def validate(self, attrs):
        prompt_type = attrs.get('prompt_type')
        if prompt_type is None and self.instance:
            prompt_type = self.instance.prompt_type

        if prompt_type:
            queryset = PromptConfig.objects.filter(prompt_type=prompt_type)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                prompt_display = dict(PromptConfig.PROMPT_CHOICES).get(prompt_type, prompt_type)
                raise serializers.ValidationError({
                    'prompt_type': f'{prompt_display}已存在，请勿重复添加'
                })

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


class TestCaseGenerationTaskSerializer(serializers.ModelSerializer):
    """测试用例生成任务序列化器"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    writer_model_name = serializers.CharField(source='writer_model_config.name', read_only=True)
    reviewer_model_name = serializers.CharField(source='reviewer_model_config.name', read_only=True)
    writer_prompt_name = serializers.CharField(source='writer_prompt_config.name', read_only=True)
    reviewer_prompt_name = serializers.CharField(source='reviewer_prompt_config.name', read_only=True)
    
    class Meta:
        model = TestCaseGenerationTask
        fields = ['id', 'task_id', 'title', 'requirement_text', 'status', 'status_display',
                 'progress', 'project', 'project_name', 'writer_model_config', 'writer_model_name', 
                 'reviewer_model_config', 'reviewer_model_name', 'writer_prompt_config', 'writer_prompt_name',
                 'reviewer_prompt_config', 'reviewer_prompt_name', 'generated_test_cases',
                 'review_feedback', 'final_test_cases', 'generation_log', 'error_message',
                 'created_by', 'created_by_name', 'created_at', 'updated_at', 'completed_at']
        read_only_fields = ['task_id', 'status', 'progress', 'generated_test_cases', 
                          'review_feedback', 'final_test_cases', 'generation_log', 
                          'error_message', 'created_by', 'completed_at']
    
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


class ZentaoSyncRequestSerializer(serializers.Serializer):
    """禅道同步请求"""
    project_id = serializers.IntegerField(help_text="目标项目ID")
    product_id = serializers.IntegerField(help_text="禅道产品ID")
    product_name = serializers.CharField(default='', help_text="产品名称")
    story_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="要同步的需求ID列表"
    )


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    """知识文档序列化器"""
    knowledge_level_display = serializers.CharField(source='get_knowledge_level_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            'id', 'name', 'file', 'file_url', 'file_type', 'knowledge_level',
            'knowledge_level_display', 'project', 'project_name', 'status',
            'status_display', 'raw_text', 'chunk_count', 'entry_count',
            'error_message', 'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'file_type', 'status', 'raw_text', 'chunk_count', 'entry_count',
            'error_message', 'created_by', 'created_at', 'updated_at',
        ]

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


class KnowledgeDocumentUploadSerializer(serializers.ModelSerializer):
    """知识文档上传序列化器"""
    class Meta:
        model = KnowledgeDocument
        fields = ['id', 'name', 'file', 'knowledge_level', 'project']

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                default_user = User.objects.first()
            validated_data['created_by'] = default_user

        # 自动检测文件类型
        file_name = validated_data.get('file').name.lower()
        if file_name.endswith('.pdf'):
            validated_data['file_type'] = 'pdf'
        elif file_name.endswith('.docx') or file_name.endswith('.doc'):
            validated_data['file_type'] = 'docx'
        elif file_name.endswith('.md'):
            validated_data['file_type'] = 'md'
        elif file_name.endswith('.xlsx') or file_name.endswith('.xls'):
            validated_data['file_type'] = 'xlsx'
        else:
            validated_data['file_type'] = 'txt'

        return super().create(validated_data)


class KnowledgeEntrySerializer(serializers.ModelSerializer):
    """知识条目序列化器"""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    knowledge_level_display = serializers.CharField(source='get_knowledge_level_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    source_document_name = serializers.CharField(source='source_document.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = KnowledgeEntry
        fields = [
            'id', 'name', 'content', 'category', 'category_display',
            'knowledge_level', 'knowledge_level_display', 'project', 'project_name',
            'source', 'source_display', 'source_document', 'source_document_name',
            'is_active', 'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
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


class KnowledgeRetrieveRequestSerializer(serializers.Serializer):
    """知识检索请求序列化器"""
    requirement_text = serializers.CharField(help_text="需求描述文本")
    project_id = serializers.IntegerField(required=False, allow_null=True, help_text="项目ID")
    top_k = serializers.IntegerField(default=10, help_text="返回数量")
