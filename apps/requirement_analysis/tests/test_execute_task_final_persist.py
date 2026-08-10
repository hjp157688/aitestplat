# -*- coding: utf-8 -*-
"""回归测试：改进（revise）成功后，权威 final_test_cases 必须落库。

背景：_execute_task 的改进成功分支此前只做内存赋值不写库，
任务完成时 refresh_from_db() 会用 DB 值覆盖内存值，而流式回调的增量保存可能
失败/不完整，导致最终用例被清空（表现为「生成到评审报告就结束，无最终用例」）。
修复：改进成功后立即 task.save(update_fields=['final_test_cases'])。

本测试用 TransactionTestCase + 异步 mock 直接跑 _execute_task：
mock 的 revise 不触发任何流式回调（等价于回调增量保存全失败的最坏场景），
靠显式落库保证 final_test_cases 非空。
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from apps.requirement_analysis import views as ra_views
from apps.requirement_analysis.models import (
    AIModelConfig, AIModelService, PromptConfig, TestCaseGenerationTask,
)


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


class ExecuteTaskFinalPersistTests(TransactionTestCase):
    """改进成功后权威最终用例必须持久化（修复 #backend 空 final 回归）。"""

    # 生成的 JSONL：2 条完整用例，供 sort/renumber 处理
    GENERATED = (
        '{"case_id":"TC-001","title":"登录成功","precondition":"已注册",'
        '"steps":[{"desc":"输入账号密码","expect":"登录成功"}],"priority":"P1"}\n'
        '{"case_id":"TC-002","title":"密码错误","precondition":"已注册",'
        '"steps":[{"desc":"输入错误密码","expect":"提示密码错误"}],"priority":"P1"}\n'
    )
    REVISED = (
        '{"case_id":"TC-001","title":"登录成功（改进）","precondition":"已注册",'
        '"steps":[{"desc":"输入账号密码","expect":"跳转主页"}],"priority":"P0"}\n'
        '{"case_id":"TC-002","title":"密码错误（改进）","precondition":"已注册",'
        '"steps":[{"desc":"输入错误密码","expect":"提示密码错误"}],"priority":"P1"}\n'
        '{"case_id":"TC-003","title":"账号锁定（新增）","precondition":"已注册",'
        '"steps":[{"desc":"连续输错5次","expect":"提示锁定30分钟"}],"priority":"P1"}\n'
    )

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='exec_task_user', password='x')

        self.writer_model = AIModelConfig.objects.create(
            name='编写模型', model_type='deepseek', role='writer',
            base_url='http://example.com/v1', model_name='test-writer', created_by=self.user,
        )
        self.reviewer_model = AIModelConfig.objects.create(
            name='评审模型', model_type='deepseek', role='reviewer',
            base_url='http://example.com/v1', model_name='test-reviewer', created_by=self.user,
        )
        self.writer_prompt = PromptConfig.objects.create(
            name='编写提示词', prompt_type='writer', content='你是用例编写专家', created_by=self.user,
        )
        self.reviewer_prompt = PromptConfig.objects.create(
            name='评审提示词', prompt_type='reviewer', content='你是评审专家', created_by=self.user,
        )

        self.task = TestCaseGenerationTask.objects.create(
            title='回归测试任务', requirement_text='登录模块需求',
            writer_model_config=self.writer_model,
            reviewer_model_config=self.reviewer_model,
            writer_prompt_config=self.writer_prompt,
            reviewer_prompt_config=self.reviewer_prompt,
            output_mode='stream', created_by=self.user,
        )

    def test_stream_mode_revise_authoritative_final_persisted(self):
        """改进成功分支的权威 final_test_cases 必须落库（即使流式回调零增量保存）。"""
        with mock.patch.object(
            AIModelService, 'generate_test_cases_stream', new=_async_return(self.GENERATED)
        ), mock.patch.object(
            AIModelService, 'review_test_cases_stream', new=_async_return('评审意见：建议补充边界场景')
        ), mock.patch.object(
            AIModelService, 'revise_test_cases_based_on_review', new=_async_return(self.REVISED)
        ):
            ra_views._execute_task(self.task, [])

        task = TestCaseGenerationTask.objects.get(pk=self.task.pk)
        self.assertEqual(task.status, 'completed')
        self.assertTrue(task.final_test_cases, '改进成功后最终用例必须落库')
        self.assertIn('TC-003', task.final_test_cases)
        self.assertIn('登录成功（改进）', task.final_test_cases)

    def test_revise_exception_falls_back_to_generated_and_persists(self):
        """改进抛异常时回退到原始用例，且最终用例仍落库。"""
        async def _raise_revise(*args, **kwargs):
            raise RuntimeError('revise boom')

        with mock.patch.object(
            AIModelService, 'generate_test_cases_stream', new=_async_return(self.GENERATED)
        ), mock.patch.object(
            AIModelService, 'review_test_cases_stream', new=_async_return('评审意见')
        ), mock.patch.object(
            AIModelService, 'revise_test_cases_based_on_review', new=_raise_revise
        ):
            ra_views._execute_task(self.task, [])

        task = TestCaseGenerationTask.objects.get(pk=self.task.pk)
        self.assertEqual(task.status, 'completed')
        self.assertTrue(task.final_test_cases, '改进异常回退原始用例后最终用例必须落库')
        self.assertIn('TC-002', task.final_test_cases)
