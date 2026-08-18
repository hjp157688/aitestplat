"""测试用例按需求筛选"""
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.requirement_analysis.models import Requirement
from apps.testcases.models import TestCase
from apps.users.models import User


class TestCaseRequirementFilterTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test123')
        self.project = Project.objects.create(name='测试项目', owner=self.user)
        self.req_a = Requirement.objects.create(title='需求A', project=self.project, created_by=self.user)
        self.req_b = Requirement.objects.create(title='需求B', project=self.project, created_by=self.user)
        self.case_a = TestCase.objects.create(title='用例A1', project=self.project, author=self.user,
                                              requirement=self.req_a)
        self.case_b = TestCase.objects.create(title='用例B1', project=self.project, author=self.user,
                                              requirement=self.req_b)
        self.client.force_authenticate(self.user)

    def test_filter_by_requirement(self):
        resp = self.client.get('/api/testcases/', {'requirement': self.req_a.id})
        self.assertEqual(resp.status_code, 200)
        ids = [tc['id'] for tc in resp.data.get('results', resp.data)]
        self.assertIn(self.case_a.id, ids)
        self.assertNotIn(self.case_b.id, ids)

    def test_no_filter_returns_all(self):
        resp = self.client.get('/api/testcases/')
        self.assertEqual(resp.status_code, 200)
        ids = [tc['id'] for tc in resp.data.get('results', resp.data)]
        self.assertIn(self.case_a.id, ids)
        self.assertIn(self.case_b.id, ids)