# -*- coding: utf-8 -*-
"""项目隔离加固：assert_project_access / is_admin

覆盖：
- assert_project_access：成员/owner 放行、外人拒绝、superuser/staff 放行、
  project_id=None 放行、项目不存在拒绝、匿名用户拒绝
- is_admin：superuser/staff 为 True，普通用户为 False
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.projects.models import Project, ProjectMember
from apps.requirement_analysis.permissions import assert_project_access, is_admin


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
