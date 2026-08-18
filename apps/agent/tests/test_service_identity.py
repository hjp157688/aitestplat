from django.test import TestCase
from apps.agent.service_identity import get_service_user, resolve_project
from apps.users.models import User
from apps.projects.models import Project


class ServiceIdentityTests(TestCase):
    def test_get_service_user_idempotent(self):
        u1 = get_service_user()
        u2 = get_service_user()
        self.assertEqual(u1.id, u2.id)
        self.assertEqual(u1.username, 'mcp_agent')

    def test_resolve_project(self):
        owner = get_service_user()
        p = Project.objects.create(name='P', owner=owner)
        self.assertEqual(resolve_project(p.id).id, p.id)
        self.assertIsNone(resolve_project(None))
        with self.assertRaises(ValueError):
            resolve_project(999999)
