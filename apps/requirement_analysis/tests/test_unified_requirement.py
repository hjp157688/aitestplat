# -*- coding: utf-8 -*-
"""统一需求模型测试：验证 Requirement 吸收 BusinessRequirement 后的字段"""
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.requirement_analysis.models import (
    Requirement, RequirementDocument, RequirementAnalysis,
    BusinessRequirement,
)
from apps.projects.models import Project
from apps.users.models import User


class UnifiedRequirementModelTests(TestCase):
    @staticmethod
    def _make_project(name):
        """Project.owner 为非空外键，创建测试项目需同时创建 owner 用户"""
        owner = User.objects.create(username=f'tester_{name}')
        return Project.objects.create(name=name, owner=owner)

    def test_ai_source_fields_exist(self):
        r = Requirement(
            project=self._make_project('t'),
            source_type='ai_import',
            title='登录需求',
            requirement_id='REQ-001',
            requirement_level='high',
            acceptance_criteria='能登录',
            module_name='登录模块',
            spec='描述',
        )
        # 字段存在性已由上方的构造函数不再抛 TypeError 证明；
        # 不调用 full_clean()，因 Requirement.created_by 为必填(blank=False)，
        # 而本测试仅关心吸收字段，未创建创建者用户。
        r.save()
        self.assertEqual(r.requirement_id, 'REQ-001')
        self.assertEqual(r.module_name, '登录模块')

    def test_zentao_source_fields_still_exist(self):
        r = Requirement(
            project=self._make_project('t2'),
            source_type='zentao',
            title='禅道需求',
            zentao_id=100,
            product_id=1,
            module_id=2,
        )
        r.save()
        self.assertEqual(r.zentao_id, 100)
        self.assertEqual(r.module_id, 2)


class BusinessRequirementMigrationTests(TestCase):
    """测试 BusinessRequirement -> Requirement 数据迁移"""

    def setUp(self):
        self.user = User.objects.create(username='migration_tester')

    def _make_requirement_document(self):
        """RequirementDocument 需要 file 和 uploaded_by 必填字段"""
        fake_file = SimpleUploadedFile(
            'test.txt', b'test content', content_type='text/plain'
        )
        return RequirementDocument.objects.create(
            title='d',
            document_type='txt',
            file=fake_file,
            uploaded_by=self.user,
        )

    def test_migrate_preserves_fields(self):
        doc = self._make_requirement_document()
        analysis = RequirementAnalysis.objects.create(
            document=doc, analysis_report='', requirements_count=1
        )
        br = BusinessRequirement.objects.create(
            analysis=analysis, requirement_id='REQ-001',
            requirement_name='登录', requirement_type='functional',
            module='登录模块', requirement_level='high',
            description='描述', acceptance_criteria='能登录',
        )
        # 执行迁移（在测试中调用 RunPython 的正向函数）
        from django.apps import apps as django_apps
        from apps.requirement_analysis.migrations._0012_helpers import migrate_business_requirements
        migrate_business_requirements(django_apps, None)

        r = Requirement.objects.filter(requirement_id='REQ-001', source_type='ai_import').first()
        self.assertIsNotNone(r)
        self.assertEqual(r.title, '登录')
        self.assertEqual(r.spec, '描述')
        self.assertEqual(r.module_name, '登录模块')
        self.assertEqual(r.requirement_level, 'high')
        self.assertEqual(r.acceptance_criteria, '能登录')
        self.assertEqual(r.analysis_id, analysis.id)
        self.assertEqual(r.category, 'functional')
        self.assertEqual(r.source_type, 'ai_import')

    def test_migrate_parent_requirement(self):
        doc = self._make_requirement_document()
        analysis = RequirementAnalysis.objects.create(
            document=doc, analysis_report='', requirements_count=2
        )
        parent = BusinessRequirement.objects.create(
            analysis=analysis, requirement_id='REQ-PARENT',
            requirement_name='父需求', requirement_type='functional',
            module='公共模块', requirement_level='high',
            description='父需求描述', acceptance_criteria='父验收',
        )
        child = BusinessRequirement.objects.create(
            analysis=analysis, requirement_id='REQ-CHILD',
            requirement_name='子需求', requirement_type='functional',
            module='公共模块', requirement_level='medium',
            description='子需求描述', acceptance_criteria='子验收',
            parent_requirement=parent,
        )
        from django.apps import apps as django_apps
        from apps.requirement_analysis.migrations._0012_helpers import migrate_business_requirements
        migrate_business_requirements(django_apps, None)

        migrated_parent = Requirement.objects.get(requirement_id='REQ-PARENT', source_type='ai_import')
        migrated_child = Requirement.objects.get(requirement_id='REQ-CHILD', source_type='ai_import')
        self.assertEqual(migrated_child.parent_requirement_id, migrated_parent.id)

    def test_migrate_empty_br_table(self):
        from django.apps import apps as django_apps
        from apps.requirement_analysis.migrations._0012_helpers import migrate_business_requirements
        migrate_business_requirements(django_apps, None)

        count = Requirement.objects.filter(source_type='ai_import').count()
        self.assertEqual(count, 0)
