# -*- coding: utf-8 -*-
"""_execute_task 状态流转测试：

WeKnora 启用时任务应经历 retrieving（知识检索中）→ generating（生成中），
前端才能在注入阶段显示「正在检索知识库…」而不是一直卡在「生成中 10%」。
"""
from unittest import mock

from django.test import TestCase

from apps.requirement_analysis import views
from apps.requirement_analysis.models import TestCaseGenerationTask
from django.contrib.auth import get_user_model


class ExecuteTaskStatusFlowTest(TestCase):
    def _make_task(self):
        user = get_user_model().objects.create_user(username='u1', password='x')
        return TestCaseGenerationTask.objects.create(
            task_id='TASK_TEST_FLOW', title='t', requirement_text='r',
            output_mode='stream', created_by=user,
        )

    def test_weknora_enabled_sets_retrieving_then_generating(self):
        task = self._make_task()
        seen = {}

        class FakeWeKnoraClient:
            def __init__(self, *a, **k):
                pass

            def agent_answer(self, *a, **k):
                # 注入执行中：应处于「知识检索中」
                seen['during_weknora'] = TestCaseGenerationTask.objects.get(
                    task_id='TASK_TEST_FLOW').status
                return {'answer': '知识内容', 'references': [], 'steps': []}

        async def fake_stream(task, callback=None, selected_knowledge=None):
            # AI 生成开始：应已回到「生成中」
            seen['at_generation'] = task.status
            return '[{"case_id":"TC-001","title":"x","steps":[{"desc":"a","expect":"b"}]}]'

        fake_cfg = mock.Mock(enabled=True, base_url='http://kb.test', api_key='',
                             timeout=5, default_agent_id='agent-a',
                             default_agent_name='智能体A', knowledge_base_ids=[])
        fake_gen_config = mock.Mock(enable_auto_review=False, review_timeout=60)

        with mock.patch.object(views.WeKnoraConfig, 'get_solo', return_value=fake_cfg), \
                mock.patch.object(views.GenerationConfig, 'get_active_config',
                                  return_value=fake_gen_config), \
                mock.patch('apps.requirement_analysis.weknora_client.WeKnoraClient',
                           FakeWeKnoraClient), \
                mock.patch.object(views.AIModelService, 'generate_test_cases_stream',
                                  side_effect=fake_stream):
            views._execute_task(task, selected_knowledge=None)

        self.assertEqual(seen.get('during_weknora'), 'retrieving')
        self.assertEqual(seen.get('at_generation'), 'generating')
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')

    def test_weknora_disabled_skips_retrieving(self):
        """未启用 WeKnora：不应出现 retrieving 状态，直接 generating。"""
        task = self._make_task()
        seen = {}

        async def fake_stream(task, callback=None, selected_knowledge=None):
            seen['at_generation'] = task.status
            return '[]'

        fake_cfg = mock.Mock(enabled=False, default_agent_id=None)
        fake_gen_config = mock.Mock(enable_auto_review=False, review_timeout=60)

        with mock.patch.object(views.WeKnoraConfig, 'get_solo', return_value=fake_cfg), \
                mock.patch.object(views.GenerationConfig, 'get_active_config',
                                  return_value=fake_gen_config), \
                mock.patch.object(views.AIModelService, 'generate_test_cases_stream',
                                  side_effect=fake_stream):
            views._execute_task(task, selected_knowledge=None)

        self.assertEqual(seen.get('at_generation'), 'generating')
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
