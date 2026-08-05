# -*- coding: utf-8 -*-
"""需求管理「勾选后批量AI生成用例」接口测试"""
import threading
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.requirement_analysis.models import (
    AIModelConfig, PromptConfig, Requirement, TestCaseGenerationTask,
)


class RequirementBatchGenerationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='batch_gen_user', password='x')

        cls.project = Project.objects.create(name='批量生成测试项目', owner=cls.user)

        # 编写/评审模型与提示词配置（is_active 默认 True）
        cls.writer_model = AIModelConfig.objects.create(
            name='编写模型', model_type='deepseek', role='writer',
            base_url='http://example.com/v1', model_name='test-writer', created_by=cls.user,
        )
        cls.reviewer_model = AIModelConfig.objects.create(
            name='评审模型', model_type='deepseek', role='reviewer',
            base_url='http://example.com/v1', model_name='test-reviewer', created_by=cls.user,
        )
        cls.writer_prompt = PromptConfig.objects.create(
            name='编写提示词', prompt_type='writer', content='你是测试用例编写专家', created_by=cls.user,
        )
        cls.reviewer_prompt = PromptConfig.objects.create(
            name='评审提示词', prompt_type='reviewer', content='你是测试评审专家', created_by=cls.user,
        )

        cls.req1 = Requirement.objects.create(
            project=cls.project, title='订单支付', spec='支持在线支付与退款',
            created_by=cls.user,
        )
        cls.req2 = Requirement.objects.create(
            project=cls.project, title='用户登录', spec='支持手机号+验证码登录',
            created_by=cls.user,
        )

    def _client(self):
        client = APIClient()
        client.force_authenticate(self.user)
        return client

    def _mock_thread(self):
        return mock.patch.object(threading, 'Thread', autospec=True)

    def test_missing_ids_rejected(self):
        resp = self._client().post(
            '/api/requirement-analysis/requirements-manage/generate_test_cases/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ids', resp.data)

    def test_empty_ids_rejected(self):
        resp = self._client().post(
            '/api/requirement-analysis/requirements-manage/generate_test_cases/',
            {'ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_nonexistent_requirement_rejected(self):
        req_ids = [self.req1.id, 999999]
        resp = self._client().post(
            '/api/requirement-analysis/requirements-manage/generate_test_cases/',
            {'ids': req_ids}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('不存在', resp.data['error'])

    def test_batch_creates_one_task_per_requirement(self):
        client = self._client()
        tasks_before = TestCaseGenerationTask.objects.count()

        # 按需求ID分组的业务知识：每条需求拥有各自独立的上下文
        knowledge_by_req = {
            str(self.req1.id): [
                {'id': 1, 'type': 'entry', 'name': '支付规则', 'content': '单笔订单仅支持一次退款'},
            ],
            str(self.req2.id): [
                {'id': 2, 'type': 'chunk', 'name': '登录规范', 'content': '验证码 5 分钟内有效'},
            ],
        }

        with self._mock_thread() as fake_thread:
            resp = client.post(
                '/api/requirement-analysis/requirements-manage/generate_test_cases/',
                {
                    'ids': [self.req1.id, self.req2.id],
                    'output_mode': 'complete',
                    'granularity': 'fine',
                    'case_type': '以接口为主',
                    'use_reviewer_model': True,
                    'selected_knowledge': knowledge_by_req,
                },
                format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['success'])
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(resp.data['failed'], [])
        self.assertEqual(TestCaseGenerationTask.objects.count(), tasks_before + 2)
        self.assertTrue(fake_thread.called)

        # 逐条校验：每条需求的任务只携带其自身对应的业务知识
        knowledge_by_task = {}
        for call in fake_thread.call_args_list:
            task, knowledge = call.kwargs['args']
            knowledge_by_task[task.title] = knowledge
        self.assertEqual(knowledge_by_task['订单支付'], knowledge_by_req[str(self.req1.id)])
        self.assertEqual(knowledge_by_task['用户登录'], knowledge_by_req[str(self.req2.id)])

        # 校验任务字段：标题/需求文本/项目/输出模式/颗粒度/用例类型
        tasks = TestCaseGenerationTask.objects.order_by('id')
        task1 = tasks.filter(title='订单支付').first()
        task2 = tasks.filter(title='用户登录').first()
        self.assertIsNotNone(task1)
        self.assertIsNotNone(task2)
        self.assertEqual(task1.project, self.project)
        self.assertIn('订单支付', task1.requirement_text)
        self.assertIn('支持在线支付与退款', task1.requirement_text)
        self.assertEqual(task1.output_mode, 'complete')
        self.assertEqual(task1.granularity, 'fine')
        self.assertEqual(task1.case_type, '以接口为主')
        self.assertEqual(task1.writer_model_config, self.writer_model)
        self.assertEqual(task1.reviewer_model_config, self.reviewer_model)

    def test_batch_uses_default_output_mode_when_omitted(self):
        with self._mock_thread():
            resp = self._client().post(
                '/api/requirement-analysis/requirements-manage/generate_test_cases/',
                {'ids': [self.req1.id]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        task = TestCaseGenerationTask.objects.filter(title='订单支付').latest('id')
        # 未指定时回退到生成行为配置默认值（无配置则为 stream）
        self.assertIn(task.output_mode, ('stream', 'complete'))

    def test_missing_writer_config_rejected(self):
        AIModelConfig.objects.filter(role='writer', is_active=True).update(is_active=False)
        resp = self._client().post(
            '/api/requirement-analysis/requirements-manage/generate_test_cases/',
            {'ids': [self.req1.id]}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('编写模型', resp.data['error'])

    def test_missing_reviewer_config_rejected_when_required(self):
        AIModelConfig.objects.filter(role='reviewer', is_active=True).update(is_active=False)
        resp = self._client().post(
            '/api/requirement-analysis/requirements-manage/generate_test_cases/',
            {'ids': [self.req1.id], 'use_reviewer_model': True}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('评审模型', resp.data['error'])
