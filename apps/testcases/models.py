from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.projects.models import Project
from apps.versions.models import Version

class TestCase(models.Model):
    """测试用例模型"""
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('critical', '紧急'),
    ]
    
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '激活'),
        ('deprecated', '废弃'),
    ]
    
    TYPE_CHOICES = [
        ('functional', '功能测试'),
        ('integration', '集成测试'),
        ('api', 'API测试'),
        ('ui', 'UI测试'),
        ('performance', '性能测试'),
        ('security', '安全测试'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='testcases')
    versions = models.ManyToManyField(Version, blank=True, related_name='testcases', verbose_name='关联版本')
    title = models.CharField(max_length=500, verbose_name='用例标题')
    description = models.TextField(blank=True, verbose_name='用例描述')
    preconditions = models.TextField(blank=True, verbose_name='前置条件')
    steps = models.TextField(blank=True, verbose_name='操作步骤')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    test_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='functional', verbose_name='测试类型')
    tags = models.JSONField(default=list, verbose_name='标签')
    requirement = models.ForeignKey(
        'requirement_analysis.Requirement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='testcases', verbose_name='关联需求'
    )
    source_generation_task = models.ForeignKey(
        'requirement_analysis.TestCaseGenerationTask', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adopted_cases', verbose_name='来源生成任务'
    )
    zentao_case_id = models.CharField(
        max_length=50, null=True, blank=True, unique=True, verbose_name='禅道用例ID'
    )
    product_id = models.IntegerField(null=True, blank=True, verbose_name='禅道产品ID')
    module_id = models.IntegerField(null=True, blank=True, verbose_name='禅道模块ID')
    story_id = models.IntegerField(null=True, blank=True, verbose_name='禅道需求ID')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_testcases', verbose_name='作者')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_testcases', verbose_name='指派人')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    def __str__(self):
        return self.title
    
    class Meta:
        db_table = 'testcases'
        verbose_name = '测试用例'
        verbose_name_plural = '测试用例'
        ordering = ['-created_at']

class TestCaseStep(models.Model):
    """测试用例步骤"""
    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='step_details')
    step_number = models.PositiveIntegerField(verbose_name='步骤序号')
    action = models.TextField(verbose_name='操作')
    expected = models.TextField(verbose_name='预期结果')
    
    class Meta:
        db_table = 'testcase_steps'
        unique_together = ['testcase', 'step_number']
        ordering = ['step_number']
        verbose_name = '测试用例步骤'
        verbose_name_plural = '测试用例步骤'

class TestCaseAttachment(models.Model):
    """测试用例附件"""
    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='attachments')
    name = models.CharField(max_length=255, verbose_name='附件名称')
    file = models.FileField(upload_to='testcase_attachments/', verbose_name='文件')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='上传者')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='上传时间')
    
    class Meta:
        db_table = 'testcase_attachments'
        verbose_name = '测试用例附件'
        verbose_name_plural = '测试用例附件'

class TestCaseComment(models.Model):
    """测试用例评论"""
    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='评论者')
    content = models.TextField(verbose_name='评论内容')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='评论时间')

    class Meta:
        db_table = 'testcase_comments'
        verbose_name = '测试用例评论'
        verbose_name_plural = '测试用例评论'
        ordering = ['-created_at']


class ZentaoSyncTask(models.Model):
    """禅道用例导入/导出后台任务（避免大批量同步请求撞前端超时）"""

    TASK_TYPE_CHOICES = [
        ('export', '导出到禅道'),
        ('import', '从禅道导入'),
    ]
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '进行中'),
        ('succeeded', '已完成'),
        ('failed', '失败'),
    ]

    task_id = models.CharField(max_length=32, unique=True, verbose_name='任务ID')
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, verbose_name='任务类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.IntegerField(default=0, verbose_name='进度百分比')
    result = models.JSONField(null=True, blank=True, verbose_name='结果')
    input_params = models.JSONField(null=True, blank=True, verbose_name='入参')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='zentao_sync_tasks',
        verbose_name='创建者'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'zentao_sync_tasks'
        verbose_name = '禅道同步任务'
        verbose_name_plural = '禅道同步任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_task_type_display()}-{self.task_id}"


class TestCaseImportRecord(models.Model):
    """测试用例 Excel 导入记录"""

    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('importing', '导入中'),
        ('completed', '已完成'),
        ('partial_success', '部分成功'),
        ('failed', '失败'),
    ]

    import_no = models.CharField(max_length=50, unique=True, verbose_name='导入编号')
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='testcase_import_records',
        verbose_name='关联项目'
    )
    import_file = models.FileField(upload_to='testcase_imports/', verbose_name='导入文件')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.IntegerField(default=0, verbose_name='进度')
    total_rows = models.IntegerField(default=0, verbose_name='总行数')
    success_count = models.IntegerField(default=0, verbose_name='成功数')
    failed_count = models.IntegerField(default=0, verbose_name='失败数')
    skip_count = models.IntegerField(default=0, verbose_name='跳过数')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    failure_details = models.JSONField(default=list, blank=True, verbose_name='失败明细')
    failure_report_file = models.FileField(
        upload_to='testcase_import_failures/',
        blank=True,
        null=True,
        verbose_name='失败明细文件'
    )
    template_version = models.CharField(max_length=20, default='v1', verbose_name='模板版本')
    celery_task_id = models.CharField(max_length=100, blank=True, verbose_name='Celery任务ID')
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='testcase_import_records',
        verbose_name='创建者'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'testcase_import_records'
        verbose_name = '测试用例导入记录'
        verbose_name_plural = '测试用例导入记录'
        ordering = ['-created_at']

    def __str__(self):
        return self.import_no


class TestCaseVersion(models.Model):
    """测试用例版本历史（内容变更快照，只增不改；与发布版本 TestCase.versions 无关）"""

    SOURCE_CHOICES = [
        ('created', '创建'),
        ('manual_edit', '手动编辑'),
        ('ai_modified', 'AI修改'),
        ('ai_supplemented', 'AI补充新增'),
        ('zentao_sync', '禅道同步'),
        ('restore', '回退'),
    ]

    testcase = models.ForeignKey(
        TestCase, on_delete=models.CASCADE,
        related_name='version_history', verbose_name='测试用例'
    )
    version = models.PositiveIntegerField(verbose_name='版本号')
    title = models.CharField(max_length=500, verbose_name='用例标题')
    description = models.TextField(blank=True, verbose_name='用例描述')
    preconditions = models.TextField(blank=True, verbose_name='前置条件')
    steps = models.TextField(blank=True, verbose_name='操作步骤')
    priority = models.CharField(max_length=20, blank=True, default='medium', verbose_name='优先级')
    test_type = models.CharField(max_length=20, blank=True, default='functional', verbose_name='测试类型')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='created', verbose_name='变更来源')
    note = models.CharField(max_length=500, blank=True, default='', verbose_name='版本说明')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='操作人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'testcase_versions'
        verbose_name = '用例版本'
        verbose_name_plural = '用例版本'
        ordering = ['version']
        unique_together = ['testcase', 'version']

    def __str__(self):
        return f"{self.testcase_id} v{self.version} ({self.source})"


class TestCaseAiTask(models.Model):
    """用例 AI 修改/补充后台任务（复用禅道同步任务的后台执行+轮询模式）"""

    MODE_CHOICES = [
        ('modify', 'AI修改'),
        ('supplement', 'AI补充'),
    ]
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('running', '进行中'),
        ('succeeded', '已完成'),
        ('failed', '失败'),
    ]

    task_id = models.CharField(max_length=32, unique=True, verbose_name='任务ID')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, verbose_name='任务类型')
    note = models.TextField(blank=True, default='', verbose_name='修改/补充意见')
    # supplement 模式：需求上下文（预填 Requirement.spec，发起时可编辑覆盖）
    requirement_text = models.TextField(blank=True, default='', verbose_name='需求上下文')
    requirement = models.ForeignKey(
        'requirement_analysis.Requirement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ai_tasks', verbose_name='关联需求'
    )
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='case_ai_tasks', verbose_name='关联项目'
    )
    case_ids = models.JSONField(default=list, blank=True, verbose_name='目标用例ID列表')
    created_cases = models.JSONField(default=list, blank=True, verbose_name='新建用例ID列表')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='case_ai_tasks', verbose_name='创建者')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'testcase_ai_tasks'
        verbose_name = '用例AI任务'
        verbose_name_plural = '用例AI任务'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_id} ({self.mode} {self.status})"
