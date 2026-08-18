import json
from unittest import mock
from django.test import TransactionTestCase
from apps.agent.tools.requirement_gen import (
    generate_testcases_from_text, get_generation_task, adopt_generated_testcases)
from apps.agent.service_identity import get_service_user
from apps.projects.models import Project
from apps.requirement_analysis.models import AIModelConfig, PromptConfig, TestCaseGenerationTask
from apps.testcases.models import TestCase as TestCaseModel

import asyncio


# 工具函数已异步化（asyncio.to_thread 在工作线程执行 Django ORM），
# 工作线程用独立连接只能看到已提交数据，故用 TransactionTestCase。
class RequirementGenTests(TransactionTestCase):
    def setUp(self):
        self.user = get_service_user()
        self.project = Project.objects.create(name='Req', owner=self.user)
        # 建真实配置行：_create_generation_task 走 serializer 的 FK 校验，
        # 提交的 writer/reviewer 模型与提示词配置 id 必须真实存在于库中。
        self.writer_cfg = AIModelConfig.objects.create(
            name='writer', model_type='deepseek', role='writer',
            base_url='http://x', model_name='deepseek-chat', created_by=self.user)
        self.reviewer_cfg = AIModelConfig.objects.create(
            name='reviewer', model_type='deepseek', role='reviewer',
            base_url='http://x', model_name='deepseek-chat', created_by=self.user)
        self.writer_prompt = PromptConfig.objects.create(
            name='writer prompt', prompt_type='writer', content='写用例提示词')
        self.reviewer_prompt = PromptConfig.objects.create(
            name='reviewer prompt', prompt_type='reviewer', content='评审提示词')

    def _active_cfg(self, role, model_type=None, user=None, scope='global'):
        return {'writer': self.writer_cfg, 'reviewer': self.reviewer_cfg}.get(role)

    def _active_prompt(self, prompt_type):
        return {'writer': self.writer_prompt, 'reviewer': self.reviewer_prompt}.get(prompt_type)

    @mock.patch('apps.requirement_analysis.views._start_generation_thread')
    @mock.patch('apps.ai.resolver.ConfigResolver.active')
    @mock.patch('apps.requirement_analysis.models.PromptConfig.get_active_config')
    def test_generate_creates_task(self, prompt, config, thread):
        config.side_effect = self._active_cfg
        prompt.side_effect = self._active_prompt
        out = json.loads(asyncio.run(generate_testcases_from_text(
            title='登录用例', requirement_text='用户输入账号密码后登录',
            project_id=self.project.id)))
        self.assertNotIn('error', out)
        task = TestCaseGenerationTask.objects.get(task_id=out['task_id'])
        self.assertEqual(task.title, '登录用例')
        self.assertEqual(task.project_id, self.project.id)
        thread.assert_called_once()

    def test_get_generation_task_not_found(self):
        out = json.loads(asyncio.run(get_generation_task('TASK_NOPE')))
        self.assertIn('error', out)

    def test_get_generation_task_summary(self):
        task = TestCaseGenerationTask.objects.create(
            task_id='TASK_GET1', title='t', requirement_text='r',
            status='completed', progress=100,
            final_test_cases=json.dumps(
                [{'title': '正向校验', 'steps': [{'desc': 'step1', 'expect': 'ok'}], 'priority': '高'}],
                ensure_ascii=False),
            created_by=self.user, project=self.project)
        out = json.loads(asyncio.run(get_generation_task(task.task_id, include_full=False)))
        self.assertEqual(out['status'], 'completed')
        self.assertEqual(out['cases_count'], 1)
        self.assertEqual(out['cases_summary'][0]['title'], '正向校验')
        self.assertNotIn('final_test_cases', out)

    def test_get_generation_task_summary_by_default(self):
        """默认（include_full=False）只返回摘要，不附 final_test_cases 原文（I1 回归）。"""
        task = TestCaseGenerationTask.objects.create(
            task_id='TASK_GET2', title='t', requirement_text='r',
            status='completed', progress=100,
            final_test_cases=json.dumps(
                [{'title': '默认摘要', 'steps': [{'desc': 's', 'expect': 'e'}]}],
                ensure_ascii=False),
            created_by=self.user, project=self.project)
        out = json.loads(asyncio.run(get_generation_task(task.task_id)))
        self.assertNotIn('final_test_cases', out)
        self.assertEqual(out['cases_summary'][0]['title'], '默认摘要')
        full = json.loads(asyncio.run(get_generation_task(task.task_id, include_full=True)))
        self.assertIn('final_test_cases', full)

    def test_adopt_full(self):
        task = TestCaseGenerationTask.objects.create(
            task_id='TASK_ADOPT1', title='t', requirement_text='r',
            status='completed', progress=100,
            final_test_cases=json.dumps(
                [{'title': 'A', 'steps': [{'desc': 's', 'expect': 'e'}]},
                 {'title': 'B', 'steps': [{'desc': 's', 'expect': 'e'}]}],
                ensure_ascii=False),
            created_by=self.user, project=self.project)
        out = json.loads(asyncio.run(adopt_generated_testcases(task.task_id)))
        self.assertEqual(out['imported_count'], 2)
        self.assertEqual(TestCaseModel.objects.filter(project=self.project).count(), 2)
        task.refresh_from_db()
        self.assertTrue(task.is_saved_to_records)

    def test_adopt_selected(self):
        task = TestCaseGenerationTask.objects.create(
            task_id='TASK_ADOPT2', title='t', requirement_text='r',
            status='completed', progress=100,
            final_test_cases=json.dumps(
                [{'title': 'A', 'steps': [{'desc': 's', 'expect': 'e'}]},
                 {'title': 'B', 'steps': [{'desc': 's', 'expect': 'e'}]}],
                ensure_ascii=False),
            created_by=self.user, project=self.project)
        out = json.loads(asyncio.run(adopt_generated_testcases(task.task_id, case_indices=[0])))
        self.assertEqual(out['imported_count'], 1)
        self.assertEqual(TestCaseModel.objects.filter(project=self.project).count(), 1)

    def test_adopt_requires_completed(self):
        task = TestCaseGenerationTask.objects.create(
            task_id='TASK_ADOPT3', title='t', requirement_text='r',
            status='generating', progress=10, created_by=self.user, project=self.project)
        out = json.loads(asyncio.run(adopt_generated_testcases(task.task_id)))
        self.assertIn('error', out)
