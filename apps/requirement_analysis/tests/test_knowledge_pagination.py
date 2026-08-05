# -*- coding: utf-8 -*-
"""知识文档 / 条目分页接口测试

verify: 知识库列表接口支持 ?page_size / ?page 参数（KnowledgePagination），
修复前端分页控件与实际每页条数不一致的问题
"""
from django.contrib.auth import get_user_model
from django.test import TestCase


class KnowledgePaginationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from apps.requirement_analysis.models import KnowledgeDocument, KnowledgeEntry
        User = get_user_model()
        cls.user = User.objects.create_user(username='bk_page_user', password='x')
        for i in range(25):
            KnowledgeEntry.objects.create(
                name=f'条目{i}', content=f'内容{i}', category='other', created_by=cls.user,
            )
        for i in range(5):
            KnowledgeDocument.objects.create(
                name=f'文档{i}', file=f'd{i}.txt', file_type='txt', created_by=cls.user,
            )

    def _client(self):
        from django.test import Client
        c = Client()
        c.force_login(self.user)
        return c

    def test_entries_page_size_honored(self):
        resp = self._client().get('/api/requirement-analysis/knowledge-entries/', {'page_size': 10})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 25)
        self.assertEqual(len(body['results']), 10)

    def test_entries_page_param(self):
        resp = self._client().get(
            '/api/requirement-analysis/knowledge-entries/',
            {'page': 3, 'page_size': 10},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 25)
        self.assertEqual(len(body['results']), 5)  # 25 - 20

    def test_documents_page_size_honored(self):
        resp = self._client().get(
            '/api/requirement-analysis/knowledge-documents/',
            {'page': 1, 'page_size': 5},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['count'], 5)
        self.assertEqual(len(body['results']), 5)
