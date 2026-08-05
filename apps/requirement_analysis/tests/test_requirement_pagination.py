# -*- coding: utf-8 -*-
"""需求管理分页接口测试

verify: 需求管理列表接口支持 ?page_size / ?page 参数（RequirementPagination），
修复前端分页控件里“每页条数”选择无效、页数与实际条数不一致的问题。

注意：本仓库 pytest 直接跑在共享 dev 库上（TestCae 事务回滚隔离），
因此断言不依赖绝对 count，只用相对关系证明分页参数被采纳。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase


class RequirementPaginationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from apps.projects.models import Project
        from apps.requirement_analysis.models import Requirement
        User = get_user_model()
        user = User.objects.create_user(username='req_page_user', password='x')
        project = Project.objects.create(name='需求分页测试项目', owner=user)
        # 创建的数据显著多于任何请求的 page_size，保证各页都是满页
        Requirement.objects.bulk_create([
            Requirement(title=f'需求{i}', spec=f'规格{i}', project=project, created_by=user)
            for i in range(40)
        ])

    def _get(self, params):
        from django.test import Client
        User = get_user_model()
        client = Client()
        client.force_login(User.objects.get(username='req_page_user'))
        return client.get('/api/requirement-analysis/requirements-manage/', params)

    def test_page_size_honored(self):
        """page_size 被后端采纳：请求 3 条/页返回 3 条，5 条/页返回 5 条"""
        resp3 = self._get({'page_size': 3})
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(len(resp3.json()['results']), 3)

        resp5 = self._get({'page_size': 5})
        self.assertEqual(resp5.status_code, 200)
        self.assertEqual(len(resp5.json()['results']), 5)

    def test_page_param(self):
        """page 参数生效：不同页返回不同数据，next 链接携带 page/page_size"""
        body1 = self._get({'page': 1, 'page_size': 3}).json()
        body2 = self._get({'page': 2, 'page_size': 3}).json()

        ids1 = {r['id'] for r in body1['results']}
        ids2 = {r['id'] for r in body2['results']}
        self.assertTrue(ids1)
        self.assertTrue(ids2)
        self.assertTrue(ids1.isdisjoint(ids2), '第2页数据不应与第1页重叠')

        self.assertIn('page=2', body1['next'])
        self.assertIn('page_size=3', body1['next'])
