# -*- coding: utf-8 -*-
"""项目⇄RAGFlow dataset 绑定计算与 embedding 一致性校验测试

覆盖(RAGFlow 知识库引擎迁移 Task 4)：
- project_dataset_name / global_dataset_name 命名约定
- dataset_ids_for: global + enabled 绑定合并;无绑定/全部禁用回退自动库
- write_target_dataset: is_write_target 命中;无命中回退自动库
- validate_binding_embedding: 绑定集内 embedding 不一致上报;一致/空返回空表
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.projects.models import Project
from apps.requirement_analysis import ragflow_bindings as rb
from apps.requirement_analysis.models import RagflowBinding


class BindingsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u1", password="x")
        self.p = Project.objects.create(name="P", owner=self.user)

    def test_unbound_project_falls_back_to_auto(self):
        self.assertEqual(
            rb.dataset_ids_for(self.p.id),
            ["aitestplat_global", "aitestplat_proj_%s" % self.p.id],
        )
        self.assertEqual(
            rb.write_target_dataset(self.p.id),
            "aitestplat_proj_%s" % self.p.id,
        )

    def test_bound_merges_global_and_selected(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="existing_ds", dataset_name="共享库", embedding_model="m1")
        self.assertEqual(rb.dataset_ids_for(self.p.id), ["aitestplat_global", "existing_ds"])

    def test_embedding_mismatch_reported(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="d1", embedding_model="m1")
        RagflowBinding.objects.create(project=self.p, dataset_id="d2", embedding_model="m2")
        errs = rb.validate_binding_embedding(self.p.id, global_embedding="m1")
        self.assertTrue(any("d2" in e for e in errs))


class DatasetIdsForTest(TestCase):
    """合并语义与回退语义的真实断言"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u2", password="x")
        self.p = Project.objects.create(name="P", owner=self.user)
        self.auto = "aitestplat_proj_%s" % self.p.id

    def test_no_bindings_returns_global_plus_auto(self):
        self.assertEqual(rb.dataset_ids_for(self.p.id), ["aitestplat_global", self.auto])
        self.assertEqual(rb.global_dataset_name(), "aitestplat_global")
        self.assertEqual(rb.project_dataset_name(self.p.id), self.auto)

    def test_multiple_bindings_all_merged_after_global(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="b1", dataset_name="库1")
        RagflowBinding.objects.create(project=self.p, dataset_id="b2", dataset_name="库2")
        self.assertEqual(
            rb.dataset_ids_for(self.p.id), ["aitestplat_global", "b1", "b2"])

    def test_disabled_binding_excluded_and_fallback_to_auto(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="off_ds", dataset_name="停用库", enabled=False)
        # 唯一绑定已禁用 → 视为未绑定,回退自动库
        self.assertEqual(rb.dataset_ids_for(self.p.id), ["aitestplat_global", self.auto])

    def test_disabled_and_enabled_mixed_keeps_only_enabled(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="off_ds", dataset_name="停用库", enabled=False)
        RagflowBinding.objects.create(
            project=self.p, dataset_id="on_ds", dataset_name="启用库", enabled=True)
        self.assertEqual(rb.dataset_ids_for(self.p.id), ["aitestplat_global", "on_ds"])


class WriteTargetDatasetTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u3", password="x")
        self.p = Project.objects.create(name="P", owner=self.user)
        self.auto = "aitestplat_proj_%s" % self.p.id

    def test_none_is_write_target_falls_back_to_auto(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="read_ds", dataset_name="只读库", is_write_target=False)
        RagflowBinding.objects.create(
            project=self.p, dataset_id="read_ds2", dataset_name="只读库2", is_write_target=False)
        self.assertEqual(rb.write_target_dataset(self.p.id), self.auto)

    def test_picks_the_is_write_target_binding(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="read_ds", dataset_name="只读库", is_write_target=False)
        RagflowBinding.objects.create(
            project=self.p, dataset_id="write_ds", dataset_name="写入库", is_write_target=True)
        self.assertEqual(rb.write_target_dataset(self.p.id), "write_ds")

    def test_disabled_write_target_ignored(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="write_ds", dataset_name="写入库",
            is_write_target=True, enabled=False)
        self.assertEqual(rb.write_target_dataset(self.p.id), self.auto)


class ValidateBindingEmbeddingTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u4", password="x")
        self.p = Project.objects.create(name="P", owner=self.user)

    def test_no_bindings_returns_empty(self):
        self.assertEqual(rb.validate_binding_embedding(self.p.id), [])

    def test_all_same_model_returns_empty(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="d1", embedding_model="m1")
        RagflowBinding.objects.create(project=self.p, dataset_id="d2", embedding_model="m1")
        self.assertEqual(rb.validate_binding_embedding(self.p.id, global_embedding="m1"), [])

    def test_mismatch_lists_each_divergent_dataset(self):
        RagflowBinding.objects.create(
            project=self.p, dataset_id="d1", dataset_name="库A", embedding_model="m1")
        RagflowBinding.objects.create(
            project=self.p, dataset_id="d2", dataset_name="库B", embedding_model="m2")
        RagflowBinding.objects.create(
            project=self.p, dataset_id="d3", dataset_name="库C", embedding_model="m3")
        errs = rb.validate_binding_embedding(self.p.id)
        # 以首条(m1)为基准,库B/库C 应被上报,库A 不应出现
        self.assertCountEqual(errs, ["库B:m2", "库C:m3"])

    def test_mismatch_uses_dataset_id_when_name_blank(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="d1", embedding_model="m1")
        RagflowBinding.objects.create(project=self.p, dataset_id="d2", embedding_model="m2")
        errs = rb.validate_binding_embedding(self.p.id)
        self.assertIn("d2:m2", errs)

    def test_bound_embedding_missing_model_is_ignored(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="d1", embedding_model="m1")
        RagflowBinding.objects.create(project=self.p, dataset_id="d2", embedding_model="")
        self.assertEqual(rb.validate_binding_embedding(self.p.id), [])

    def test_disabled_binding_not_part_of_consistency_check(self):
        RagflowBinding.objects.create(project=self.p, dataset_id="d1", embedding_model="m1")
        RagflowBinding.objects.create(
            project=self.p, dataset_id="d2", embedding_model="m2", enabled=False)
        self.assertEqual(rb.validate_binding_embedding(self.p.id), [])
