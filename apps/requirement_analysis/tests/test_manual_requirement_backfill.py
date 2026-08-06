"""手动粘贴/上传任务无需求关联时，保存/采纳自动回填 Requirement"""
import json

from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.requirement_analysis.models import Requirement, TestCaseGenerationTask
from apps.testcases.models import TestCase
from apps.users.models import User


def _make_task(user, project, title='粘贴的需求', requirement_text='需求描述：能正常登录', requirement=None, index=1):
    # task_id 无默认值（仅序列化器自动生成），直接 ORM 创建必须显式给唯一值
    return TestCaseGenerationTask.objects.create(
        task_id=f'TASK_TEST_{index:04d}',
        title=title,
        requirement_text=requirement_text,
        status='completed',
        progress=100,
        output_mode='stream',
        created_by=user,
        project=project,
        requirement=requirement,
    )


class ManualRequirementBackfillTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='test123')
        self.project = Project.objects.create(name='测试项目', owner=self.user)
        # 已有需求关联的任务：无 requirement（模拟粘贴/上传生成）
        self.task = _make_task(self.user, self.project)
        self.task.final_test_cases = json.dumps(
            {'case_id': 'TC-001', 'title': '登录校验', 'precondition': '已注册',
             'steps': [{'desc': '输入账号密码', 'expect': '登录成功'}], 'priority': 'P2'},
            ensure_ascii=False,
        )
        self.task.save()
        self.client.force_authenticate(self.user)

    def test_batch_adopt_backfills_requirement(self):
        resp = self.client.post(f'/api/requirement-analysis/testcase-generation/{self.task.task_id}/batch_adopt/')
        self.assertEqual(resp.status_code, 200)

        tc = TestCase.objects.filter(title='登录校验').first()
        self.assertIsNotNone(tc)
        self.assertIsNotNone(tc.requirement)
        self.assertTrue(tc.requirement.title.endswith('（手动导入）'))
        self.assertEqual(tc.requirement.source_type, 'manual')
        self.assertEqual(tc.requirement.spec, self.task.requirement_text)

        # 回填后用需求过滤能查到该用例
        filter_resp = self.client.get('/api/testcases/', {'requirement': tc.requirement_id})
        ids = [c['id'] for c in filter_resp.data.get('results', filter_resp.data)]
        self.assertIn(tc.id, ids)

    def test_same_title_reuses_same_requirement(self):
        resp = self.client.post(f'/api/requirement-analysis/testcase-generation/{self.task.task_id}/batch_adopt/')
        self.assertEqual(resp.status_code, 200)
        first = TestCase.objects.first().requirement

        # 同标题复用测试改为传不同 task_id
        task2 = _make_task(self.user, self.project, index=2)  # 同标题
        task2.final_test_cases = self.task.final_test_cases
        task2.save()
        self.client.post(f'/api/requirement-analysis/testcase-generation/{task2.task_id}/batch_adopt/')

        second = TestCase.objects.filter(title='登录校验').last().requirement
        self.assertEqual(first.id, second.id)

    def test_existing_requirement_not_overwritten(self):
        req = Requirement.objects.create(title='管理需求', project=self.project,
                                         created_by=self.user, source_type='manual')
        task = _make_task(self.user, self.project, title='管理需求', requirement=req, index=3)
        task.final_test_cases = self.task.final_test_cases
        task.save()
        self.client.post(f'/api/requirement-analysis/testcase-generation/{task.task_id}/batch_adopt/')

        tc = TestCase.objects.filter(title='登录校验').first()
        self.assertEqual(tc.requirement_id, req.id)