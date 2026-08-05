# -*- coding: utf-8 -*-
"""统一需求模型测试：验证 Requirement 吸收 BusinessRequirement 后的字段"""
from django.test import TestCase

from apps.requirement_analysis.models import Requirement
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
