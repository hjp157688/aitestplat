# -*- coding: utf-8 -*-
"""知识文档 / 条目批量删除接口测试

verify: batch_delete 接收 ids，删除模型并清理 ChromaDB
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase


class _FakeVectorStore:
    def __init__(self):
        self.removed_entries = []
        self.removed_docs = []

    def remove_entry(self, entry_id):
        self.removed_entries.append(entry_id)

    def remove_by_document(self, project_id, document_id):
        self.removed_docs.append(document_id)


class KnowledgeBatchDeleteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from apps.requirement_analysis.models import KnowledgeDocument, KnowledgeEntry
        User = get_user_model()
        cls.user = User.objects.create_user(username='bk_batch_user', password='x')
        cls.doc1 = KnowledgeDocument.objects.create(
            name='文档1', file='x.txt', file_type='txt', created_by=cls.user,
        )
        cls.doc2 = KnowledgeDocument.objects.create(
            name='文档2', file='y.txt', file_type='txt', created_by=cls.user,
        )
        cls.entry1 = KnowledgeEntry.objects.create(
            name='条目1', content='内容1', category='module', created_by=cls.user,
        )
        cls.entry2 = KnowledgeEntry.objects.create(
            name='条目2', content='内容2', category='other', created_by=cls.user,
        )

    def _client(self):
        from django.test import Client
        c = Client()
        c.force_login(self.user)
        return c

    def test_batch_delete_documents_cleans_chromadb(self):
        from apps.requirement_analysis.models import KnowledgeDocument
        import apps.requirement_analysis.vector_store as vs_mod

        fake = _FakeVectorStore()
        c = self._client()
        with mock.patch.object(vs_mod, 'vector_store', fake):
            resp = c.post(
                '/api/requirement-analysis/knowledge-documents/batch_delete/',
                {'ids': [self.doc1.id, self.doc2.id]},
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['deleted'], 2)
        self.assertEqual(set(fake.removed_docs), {self.doc1.id, self.doc2.id})
        self.assertFalse(KnowledgeDocument.objects.filter(id__in=[self.doc1.id, self.doc2.id]).exists())

    def test_batch_delete_entries_cleans_chromadb(self):
        from apps.requirement_analysis.models import KnowledgeEntry
        import apps.requirement_analysis.vector_store as vs_mod

        fake = _FakeVectorStore()
        c = self._client()
        with mock.patch.object(vs_mod, 'vector_store', fake):
            resp = c.post(
                '/api/requirement-analysis/knowledge-entries/batch_delete/',
                {'ids': [self.entry1.id, self.entry2.id]},
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['deleted'], 2)
        self.assertEqual(set(fake.removed_entries), {self.entry1.id, self.entry2.id})
        self.assertFalse(KnowledgeEntry.objects.filter(id__in=[self.entry1.id, self.entry2.id]).exists())

    def test_batch_delete_without_ids_returns_400(self):
        c = self._client()
        resp = c.post(
            '/api/requirement-analysis/knowledge-documents/batch_delete/',
            {},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
