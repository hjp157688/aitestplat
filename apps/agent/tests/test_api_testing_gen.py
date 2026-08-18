import asyncio
import json
from unittest import mock
from django.test import TransactionTestCase
from apps.agent.tools.api_testing_gen import (
    generate_api_testcases, get_api_generation_task, save_api_testcases)


# 工具函数已异步化（asyncio.to_thread 在工作线程执行），测试以 asyncio.run 调用。
class ApiGenTests(TransactionTestCase):
    @mock.patch('apps.api_testing.services.ApiTestCaseGenerator.generate',
                return_value='APITASK_TEST')
    def test_generate_api_testcases(self, gen):
        out = json.loads(asyncio.run(generate_api_testcases(request_ids=[1, 2])))
        self.assertNotIn('error', out)
        self.assertEqual(out['task_id'], 'APITASK_TEST')
        gen.assert_called_once()

    def test_too_many_rejected(self):
        out = json.loads(asyncio.run(generate_api_testcases(request_ids=list(range(25)))))
        self.assertIn('error', out)

    def test_get_progress(self):
        from apps.api_testing.services import _generation_tasks
        _generation_tasks['APITASK_X'] = {
            'status': 'generating', 'progress': 40, 'result': None,
            'error': None, 'known_data': None}
        try:
            out = json.loads(asyncio.run(get_api_generation_task('APITASK_X')))
            self.assertEqual(out['status'], 'generating')
            self.assertEqual(out['progress'], 40)
        finally:
            _generation_tasks.pop('APITASK_X', None)

    def test_get_progress_cases_count(self):
        """cases_count 按 result['test_cases'] 各分组的真实用例数累计。"""
        from apps.api_testing.services import _generation_tasks
        _generation_tasks['APITASK_Y'] = {
            'status': 'completed', 'progress': 100,
            'result': {'test_cases': {'POST /a': [{'name': 'c1'}, {'name': 'c2'}],
                                      'GET /b': [{'name': 'c3'}]}},
            'error': None, 'known_data': None}
        try:
            out = json.loads(asyncio.run(get_api_generation_task('APITASK_Y')))
            self.assertEqual(out['cases_count'], 3)
        finally:
            _generation_tasks.pop('APITASK_Y', None)

    def test_save_not_completed(self):
        out = json.loads(asyncio.run(save_api_testcases('APITASK_NOPE', [{'request_id': 1}])))
        self.assertIn('error', out)
