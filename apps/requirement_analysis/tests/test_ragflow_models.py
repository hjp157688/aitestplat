# -*- coding: utf-8 -*-
"""RAGFlow 配置/绑定模型 + 知识库 snapshot 字段测试

覆盖（知识库引擎迁移第一步）：
- RagflowConfig.get_solo() 单例语义与默认值
- RagflowBinding 按 (project, dataset_id) 唯一约束；跨项目/全局 null 不冲突
- KnowledgeDocument / KnowledgeEntry 新增 ragflow_dataset_id / ragflow_document_id 快照字段
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from apps.projects.models import Project
from apps.requirement_analysis.constants import ENTRY_DOC_PREFIX, SCORE_SCALE_DEFAULT
from apps.requirement_analysis.models import (
    KnowledgeDocument,
    KnowledgeEntry,
    RagflowBinding,
    RagflowConfig,
)


class RagflowConfigTest(TestCase):
    def test_get_solo_creates_singleton(self):
        cfg = RagflowConfig.get_solo()
        self.assertEqual(cfg, RagflowConfig.get_solo())
        self.assertEqual(cfg.pk, 1)
        self.assertEqual(cfg.embedding_model, "")
        self.assertEqual(cfg.base_url, "http://127.0.0.1:9380")
        self.assertEqual(cfg.chunk_method, "naive")
        self.assertFalse(cfg.graphrag_enabled)
        self.assertEqual(cfg.score_scale, SCORE_SCALE_DEFAULT)

    def test_get_solo_is_persistent(self):
        RagflowConfig.get_solo().save()
        # 重建后（模拟同库另一进程）仍只有一条，主键固定为 1
        self.assertEqual(RagflowConfig.objects.count(), 1)


class RagflowBindingTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ragflowowner', password='x12345')
        self.project = Project.objects.create(name='P', owner=self.user)

    def test_binding_unique_per_project(self):
        RagflowBinding.objects.create(project=self.project, dataset_id="a", dataset_name="A")
        with self.assertRaises(IntegrityError):
            RagflowBinding.objects.create(
                project=self.project, dataset_id="a", dataset_name="A2")

    def test_same_dataset_allowed_across_projects_and_global(self):
        """唯一约束是 (project, dataset_id)：不同项目、以及 project=null 的全局默认行不冲突"""
        other = Project.objects.create(name='P2', owner=self.user)
        RagflowBinding.objects.create(project=self.project, dataset_id="a", dataset_name="A")
        # 同一 dataset 不同项目：允许
        RagflowBinding.objects.create(project=other, dataset_id="a", dataset_name="A-other")
        # 同一 dataset 全局默认（project=null）：允许
        RagflowBinding.objects.create(project=None, dataset_id="a", dataset_name="global")
        self.assertEqual(RagflowBinding.objects.filter(dataset_id="a").count(), 3)

    def test_binding_defaults(self):
        b = RagflowBinding.objects.create(project=self.project, dataset_id="a", dataset_name="A")
        self.assertTrue(b.is_write_target)
        self.assertTrue(b.enabled)
        self.assertEqual(b.embedding_model, "")
        self.assertEqual(str(b), "A(a)")


class KnowledgeRagflowSnapshotFieldsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ragflowowner', password='x12345')
        self.project = Project.objects.create(name='P', owner=self.user)

    def test_document_ragflow_snapshot_fields_roundtrip(self):
        doc = KnowledgeDocument.objects.create(
            name='d', file='knowledge_docs/t.txt', file_type='txt',
            project=self.project, created_by=self.user,
            ragflow_dataset_id='ds-1', ragflow_document_id='doc-1')
        refreshed = KnowledgeDocument.objects.get(pk=doc.pk)
        self.assertEqual(refreshed.ragflow_dataset_id, 'ds-1')
        self.assertEqual(refreshed.ragflow_document_id, 'doc-1')

    def test_entry_ragflow_snapshot_fields_roundtrip(self):
        entry = KnowledgeEntry.objects.create(
            name='e', content='x', created_by=self.user,
            ragflow_dataset_id='ds-entry', ragflow_document_id='doc-entry')
        refreshed = KnowledgeEntry.objects.get(pk=entry.pk)
        self.assertEqual(refreshed.ragflow_dataset_id, 'ds-entry')
        self.assertEqual(refreshed.ragflow_document_id, 'doc-entry')

    def test_snapshot_fields_default_blank(self):
        doc = KnowledgeDocument.objects.create(
            name='d', file='knowledge_docs/t.txt', file_type='txt',
            project=self.project, created_by=self.user)
        self.assertEqual(doc.ragflow_dataset_id, "")
        self.assertEqual(doc.ragflow_document_id, "")


class ConstantsTest(TestCase):
    def test_entry_doc_prefix(self):
        self.assertEqual(ENTRY_DOC_PREFIX, "kb_entry_")

    def test_score_scale_default(self):
        self.assertEqual(SCORE_SCALE_DEFAULT, 10)
