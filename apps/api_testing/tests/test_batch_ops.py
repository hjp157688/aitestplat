"""接口管理树节点批量操作后端测试"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.api_testing.models import (
    ApiProject, ApiCollection, ApiRequest,
    TestSuite, TestSuiteRequest, OperationLog,
)


class GenerateCapTests(TestCase):
    """generate-testcases 批量上限防御"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cap', password='x12345')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_too_many_requests_rejected(self):
        with patch(
            'apps.api_testing.services.ApiTestCaseGenerator.generate',
            return_value='task-1',
        ):
            resp = self.client.post(
                '/api/api-testing/requests/generate-testcases/',
                {'request_ids': list(range(1, 22))}, format='json',
            )
        self.assertEqual(resp.status_code, 400)

    def test_empty_list_rejected(self):
        resp = self.client.post(
            '/api/api-testing/requests/generate-testcases/',
            {'request_ids': []}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_within_limit_forwards_to_generator(self):
        with patch(
            'apps.api_testing.services.ApiTestCaseGenerator.generate',
            return_value='task-1',
        ) as mock_gen:
            resp = self.client.post(
                '/api/api-testing/requests/generate-testcases/',
                {'request_ids': [1, 2, 3]}, format='json',
            )
        self.assertEqual(resp.status_code, 201)
        mock_gen.assert_called_once()
