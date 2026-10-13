"""批量采纳幂等与回链测试

- batch_adopt 创建的用例带 source_generation_task 回链
- 重复采纳不重复创建（全部已采 → 提示已采纳）
- 任务内容变更后增量采纳（只创建新增部分）
- 任务列表返回 adopted_count
"""
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import TestCaseGenerationTask
from apps.testcases.models import TestCase as TestCaseModel

User = get_user_model()

FINAL_JSONL = (
    '{"case_id":"LOGIN_001","title":"验证手机号格式校验","precondition":"在登录页",'
    '"steps":[{"desc":"输入10位手机号","expect":"提示格式不正确"}],"priority":"P1","test_type":"功能验证","module":"登录"}\n'
    '{"case_id":"LOGIN_002","title":"验证正确手机号登录","precondition":"已注册账号",'
    '"steps":[{"desc":"输入正确验证码并点击登录","expect":"跳转主页"}],"priority":"P0","test_type":"功能验证","module":"登录"}'
)


class BatchAdoptIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('adoptuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.task = TestCaseGenerationTask.objects.create(
            task_id='adopt-task-1',
            title='登录需求用例',
            requirement_text='登录需求',
            status='completed',
            final_test_cases=FINAL_JSONL,
            created_by=self.user,
            project=Project.objects.create(name='采纳测试项目', owner=self.user),
        )
        self.url = f'/api/requirement-analysis/testcase-generation/{self.task.task_id}/batch_adopt/'

    def test_batch_adopt_creates_cases_with_source_link(self):
        resp = self.client.post(self.url, format='json')
        self.assertEqual(resp.status_code, 200)
        cases = TestCaseModel.objects.filter(source_generation_task=self.task)
        self.assertEqual(cases.count(), 2)
        self.assertEqual(cases[0].project, self.task.project)

    def test_repeat_batch_adopt_does_not_duplicate(self):
        self.client.post(self.url, format='json')
        resp = self.client.post(self.url, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TestCaseModel.objects.filter(source_generation_task=self.task).count(), 2)
        body = resp.json()
        self.assertEqual(body.get('adopted_count', 0), 0)
        self.assertIn('已采纳', body.get('message', ''))

    def test_incremental_adopt_after_content_change(self):
        """任务内容变更（补了第 3 条）后再次采纳：只创建新增，跳过已存在"""
        self.client.post(self.url, format='json')
        extra = (
            '{"case_id":"LOGIN_003","title":"验证密码错误提示","precondition":"在登录页",'
            '"steps":[{"desc":"输入错误密码","expect":"提示密码错误"}],"priority":"P1","test_type":"功能验证","module":"登录"}'
        )
        self.task.final_test_cases = FINAL_JSONL + '\n' + extra
        self.task.save(update_fields=['final_test_cases'])

        resp = self.client.post(self.url, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TestCaseModel.objects.filter(source_generation_task=self.task).count(), 3)
        body = resp.json()
        self.assertEqual(body.get('adopted_count'), 1)
        self.assertIn('跳过', body.get('message', ''))

    def test_adopted_count_in_task_list(self):
        self.client.post(self.url, format='json')
        resp = self.client.get('/api/requirement-analysis/testcase-generation/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if hasattr(resp, 'data') else resp.json()['results']
        row = next(r for r in results if r['task_id'] == self.task.task_id)
        self.assertEqual(row.get('adopted_count'), 2)


class TaskCaseCountTests(TestCase):
    """任务列表返回 case_count（后端权威解析），前端不再自己数"""

    def setUp(self):
        self.user = User.objects.create_user('countuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.task = TestCaseGenerationTask.objects.create(
            task_id='count-task-1',
            title='计数测试',
            requirement_text='需求',
            status='completed',
            final_test_cases=FINAL_JSONL,
            created_by=self.user,
        )

    def test_case_count_in_task_list(self):
        resp = self.client.get('/api/requirement-analysis/testcase-generation/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results']
        row = next(r for r in results if r['task_id'] == self.task.task_id)
        self.assertEqual(row.get('case_count'), 2)

    def test_case_count_zero_when_empty(self):
        TestCaseGenerationTask.objects.create(
            task_id='count-task-2', title='空任务', requirement_text='需求',
            status='failed', final_test_cases='', created_by=self.user,
        )
        resp = self.client.get('/api/requirement-analysis/testcase-generation/')
        row = next(r for r in resp.data['results'] if r['task_id'] == 'count-task-2')
        self.assertEqual(row.get('case_count'), 0)
