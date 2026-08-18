# -*- coding: utf-8 -*-
"""项目隔离加固：assert_project_access / is_admin + 知识库视图 403 注入测试

覆盖（知识库引擎迁移 Task 5）：
- assert_project_access：成员/owner 放行、外人拒绝、superuser/staff 放行、
  project_id=None 放行、项目不存在拒绝、匿名用户拒绝
- is_admin：superuser/staff 为 True，普通用户为 False
- 视图注入 403（每个接入点一条）：
  KnowledgeRetrieveViewSet.search / KnowledgeDocumentViewSet.batch_delete /
  update_chunk / process / extract / perform_destroy 与 global 写需管理员、
  KnowledgeEntryViewSet create / update / destroy
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.projects.models import Project, ProjectMember
from apps.requirement_analysis.models import KnowledgeDocument, KnowledgeEntry
from apps.requirement_analysis.permissions import assert_project_access, is_admin

KB_DOC = "knowledge_docs/t.txt"


def make_client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


class AssertProjectAccessTest(TestCase):
    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_user(username="o", password="x")
        self.member = U.objects.create_user(username="m", password="x")
        self.outsider = U.objects.create_user(username="s", password="x")
        self.staff = U.objects.create_user(username="st", password="x", is_staff=True)
        self.superuser = U.objects.create_superuser(username="su", password="x")
        self.p = Project.objects.create(name="P", owner=self.owner)
        ProjectMember.objects.create(project=self.p, user=self.member)

    def test_member_allowed(self):
        assert_project_access(self.member, self.p.id)  # 不抛

    def test_owner_allowed(self):
        assert_project_access(self.owner, self.p.id)  # 不抛

    def test_outsider_denied(self):
        with self.assertRaises(PermissionDenied):
            assert_project_access(self.outsider, self.p.id)

    def test_superuser_allowed(self):
        assert_project_access(self.superuser, self.p.id)  # 不抛

    def test_staff_allowed(self):
        assert_project_access(self.staff, self.p.id)  # 不抛

    def test_project_none_allowed(self):
        assert_project_access(self.outsider, None)  # 不抛

    def test_project_missing_denied(self):
        with self.assertRaises(PermissionDenied):
            assert_project_access(self.owner, 999999)

    def test_anonymous_denied(self):
        from django.contrib.auth.models import AnonymousUser

        with self.assertRaises(PermissionDenied):
            assert_project_access(AnonymousUser(), self.p.id)


class IsAdminTest(TestCase):
    def setUp(self):
        U = get_user_model()
        self.u = U.objects.create_user(username="u", password="x")
        self.staff = U.objects.create_user(username="st", password="x", is_staff=True)
        self.superuser = U.objects.create_superuser(username="su", password="x")

    def test_regular_user_not_admin(self):
        self.assertFalse(is_admin(self.u))

    def test_staff_is_admin(self):
        self.assertTrue(is_admin(self.staff))

    def test_superuser_is_admin(self):
        self.assertTrue(is_admin(self.superuser))

    def test_none_not_admin(self):
        self.assertFalse(is_admin(None))


class KnowledgeRetrieveSearchAccessTest(TestCase):
    """KnowledgeRetrieveViewSet.search：project_id 非空时校验"""

    URL = "/api/requirement-analysis/knowledge/search/"

    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_user(username="o", password="x")
        self.member = U.objects.create_user(username="m", password="x")
        self.outsider = U.objects.create_user(username="s", password="x")
        self.p = Project.objects.create(name="P", owner=self.owner)
        ProjectMember.objects.create(project=self.p, user=self.member)

    def test_search_outsider_project_denied(self):
        resp = make_client(self.outsider).post(
            self.URL, {"requirement_text": "hello", "project_id": self.p.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_search_member_allowed(self):
        resp = make_client(self.member).post(
            self.URL, {"requirement_text": "hello", "project_id": self.p.id},
            format="json",
        )
        self.assertNotEqual(resp.status_code, 403)


class KnowledgeDocumentViewAccessTest(TestCase):
    """KnowledgeDocumentViewSet 写操作：非空 project 校验 + global 写需管理员"""

    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_user(username="o", password="x")
        self.member = U.objects.create_user(username="m", password="x")
        self.outsider = U.objects.create_user(username="s", password="x")
        self.admin = U.objects.create_superuser(username="a", password="x")
        self.p = Project.objects.create(name="P", owner=self.owner)
        ProjectMember.objects.create(project=self.p, user=self.member)
        self.doc = KnowledgeDocument.objects.create(
            name="d", file=KB_DOC, file_type="txt",
            project=self.p, created_by=self.owner,
        )
        self.gdoc = KnowledgeDocument.objects.create(
            name="g", file=KB_DOC, file_type="txt",
            project=None, knowledge_level="global", created_by=self.admin,
        )

    def test_batch_delete_outsider_denied(self):
        resp = make_client(self.outsider).post(
            "/api/requirement-analysis/knowledge-documents/batch_delete/",
            {"ids": [self.doc.id]}, format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(KnowledgeDocument.objects.filter(pk=self.doc.pk).exists())

    def test_batch_delete_global_non_admin_denied(self):
        resp = make_client(self.member).post(
            "/api/requirement-analysis/knowledge-documents/batch_delete/",
            {"ids": [self.gdoc.id]}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_batch_delete_global_admin_allowed(self):
        resp = make_client(self.admin).post(
            "/api/requirement-analysis/knowledge-documents/batch_delete/",
            {"ids": [self.gdoc.id]}, format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_update_chunk_outsider_denied(self):
        resp = make_client(self.outsider).post(
            f"/api/requirement-analysis/knowledge-documents/{self.doc.id}/update-chunk/",
            {"chunk_id": "c1", "content": "x"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_chunk_global_non_admin_denied(self):
        resp = make_client(self.member).post(
            f"/api/requirement-analysis/knowledge-documents/{self.gdoc.id}/update-chunk/",
            {"chunk_id": "c1", "content": "x"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_chunk_global_admin_not_denied(self):
        """admin 通过访问层校验后进入原有逻辑（未配置 embedding 时会 400/500，但绝不 403）"""
        resp = make_client(self.admin).post(
            f"/api/requirement-analysis/knowledge-documents/{self.gdoc.id}/update-chunk/",
            {"chunk_id": "c1", "content": "x"}, format="json",
        )
        self.assertNotEqual(resp.status_code, 403)

    def test_process_outsider_denied(self):
        resp = make_client(self.outsider).post(
            f"/api/requirement-analysis/knowledge-documents/{self.doc.id}/process/",
            {}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_extract_outsider_denied(self):
        resp = make_client(self.outsider).post(
            f"/api/requirement-analysis/knowledge-documents/{self.doc.id}/extract/",
            {}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_destroy_outsider_denied(self):
        resp = make_client(self.outsider).delete(
            f"/api/requirement-analysis/knowledge-documents/{self.doc.id}/",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(KnowledgeDocument.objects.filter(pk=self.doc.pk).exists())

    def test_destroy_global_non_admin_denied(self):
        resp = make_client(self.member).delete(
            f"/api/requirement-analysis/knowledge-documents/{self.gdoc.id}/",
        )
        self.assertEqual(resp.status_code, 403)


class KnowledgeEntryViewAccessTest(TestCase):
    """KnowledgeEntryViewSet create/update/destroy：非空 project 校验"""

    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_user(username="o", password="x")
        self.member = U.objects.create_user(username="m", password="x")
        self.outsider = U.objects.create_user(username="s", password="x")
        self.p = Project.objects.create(name="P", owner=self.owner)
        ProjectMember.objects.create(project=self.p, user=self.member)
        self.entry = KnowledgeEntry.objects.create(
            name="e", content="c", project=self.p, created_by=self.owner,
        )

    def test_create_outsider_project_denied(self):
        resp = make_client(self.outsider).post(
            "/api/requirement-analysis/knowledge-entries/",
            {"name": "e2", "content": "c", "project": self.p.id}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_member_allowed(self):
        resp = make_client(self.member).post(
            "/api/requirement-analysis/knowledge-entries/",
            {"name": "e2", "content": "c", "project": self.p.id}, format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_update_outsider_denied(self):
        resp = make_client(self.outsider).patch(
            f"/api/requirement-analysis/knowledge-entries/{self.entry.id}/",
            {"name": "e2"}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_destroy_outsider_denied(self):
        resp = make_client(self.outsider).delete(
            f"/api/requirement-analysis/knowledge-entries/{self.entry.id}/",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(KnowledgeEntry.objects.filter(pk=self.entry.pk).exists())
