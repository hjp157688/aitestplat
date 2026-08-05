# -*- coding: utf-8 -*-
"""用例生成「用例类型 + 颗粒度」字段与行为测试"""
from django.contrib.auth import get_user_model
from django.test import TestCase


class GenerationOptionModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='gen_opt_model_user', password='x')

    def test_defaults(self):
        from apps.requirement_analysis.models import TestCaseGenerationTask
        task = TestCaseGenerationTask.objects.create(
            task_id='OPT001', title='t', requirement_text='r', created_by=self.user)
        self.assertEqual(task.granularity, 'medium')
        self.assertEqual(task.case_type, '')
        self.assertEqual(task.get_granularity_display(), '中粒度')

    def test_custom_values_persist(self):
        from apps.requirement_analysis.models import TestCaseGenerationTask
        task = TestCaseGenerationTask.objects.create(
            task_id='OPT002', title='t', requirement_text='r', created_by=self.user,
            case_type=' 以接口为主 ', granularity='coarse')
        task.refresh_from_db()
        self.assertEqual(task.granularity, 'coarse')
        self.assertEqual(task.case_type, ' 以接口为主 ')


class GenerationPreferenceTests(TestCase):

    def test_preferences_medium_default(self):
        from apps.requirement_analysis.models import AIModelService
        block = AIModelService._build_preferences_block('', '')
        self.assertIn('【颗粒度：中】', block)
        self.assertNotIn('【用户补充要求】', block)

    def test_preferences_coarse_and_fine(self):
        from apps.requirement_analysis.models import AIModelService
        self.assertIn('【颗粒度：粗】', AIModelService._build_preferences_block('', 'coarse'))
        self.assertIn('【颗粒度：细】', AIModelService._build_preferences_block('', 'fine'))
        self.assertNotIn('【颗粒度：中】', AIModelService._build_preferences_block('', 'fine'))

    def test_preferences_append_user_case_type_trimmed(self):
        from apps.requirement_analysis.models import AIModelService
        block = AIModelService._build_preferences_block('  以接口为主  ', 'fine')
        self.assertIn('【用户补充要求】以接口为主', block)

    def test_writer_user_message_fine_keeps_detailed_instructions(self):
        from apps.requirement_analysis.models import AIModelService
        msg = AIModelService._build_writer_user_message(
            '需求：用户登录', '【业务知识】...\n', '补充XX场景', 'fine')
        self.assertIn('深度遍历策略', msg)
        self.assertIn('拒绝合并', msg)
        self.assertIn('场景扩展库', msg)
        self.assertIn('【用户补充要求】补充XX场景', msg)
        self.assertNotIn('【颗粒度：细】', msg)
        self.assertIn('输出顺序要求', msg)
        self.assertIn('特殊字符处理', msg)
        self.assertIn('需求：用户登录', msg)

    def test_writer_user_message_medium_uses_terse_block(self):
        from apps.requirement_analysis.models import AIModelService
        msg = AIModelService._build_writer_user_message('需求：用户登录', '【业务知识】...\n', '', 'medium')
        self.assertIn('【颗粒度：中】', msg)
        self.assertNotIn('拒绝合并', msg)
        self.assertIn('输出顺序要求', msg)

    def test_writer_user_message_coarse_uses_terse_block(self):
        from apps.requirement_analysis.models import AIModelService
        msg = AIModelService._build_writer_user_message('需求：用户登录', '【业务知识】...\n', '', 'coarse')
        self.assertIn('【颗粒度：粗】', msg)
        self.assertNotIn('拒绝合并', msg)
        self.assertIn('特殊字符处理', msg)

    def test_writer_message_numbered_instructions_on_new_line(self):
        from apps.requirement_analysis.models import AIModelService
        coarse = AIModelService._build_writer_user_message('需求：用户登录', '【业务知识】...\n', '', 'coarse')
        medium = AIModelService._build_writer_user_message('需求：用户登录', '【业务知识】...\n', '', 'medium')
        fine = AIModelService._build_writer_user_message('需求：用户登录', '【业务知识】...\n', '', 'fine')
        self.assertIn('\n5. **⚠️ 输出顺序要求', coarse)
        self.assertIn('\n5. **⚠️ 输出顺序要求', medium)
        self.assertIn('\n5. **⚠️ 输出顺序要求', fine)


class GenerationOptionSerializerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='gen_opt_ser_user', password='x')

    def test_request_serializer_defaults(self):
        from apps.requirement_analysis.serializers import TestCaseGenerationRequestSerializer
        s = TestCaseGenerationRequestSerializer(data={'title': 't', 'requirement_text': 'r'})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data.get('granularity'), 'medium')
        self.assertEqual(s.validated_data.get('case_type'), '')

    def test_request_serializer_accepts_values(self):
        from apps.requirement_analysis.serializers import TestCaseGenerationRequestSerializer
        data = {'title': 't', 'requirement_text': 'r', 'case_type': '以接口为主', 'granularity': 'fine'}
        s = TestCaseGenerationRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['granularity'], 'fine')
        self.assertEqual(s.validated_data['case_type'], '以接口为主')

    def test_request_serializer_rejects_bad_granularity(self):
        from apps.requirement_analysis.serializers import TestCaseGenerationRequestSerializer
        s = TestCaseGenerationRequestSerializer(
            data={'title': 't', 'requirement_text': 'r', 'granularity': 'huge'})
        self.assertFalse(s.is_valid())

    def test_task_serializer_outputs_options(self):
        from apps.requirement_analysis.models import TestCaseGenerationTask
        from apps.requirement_analysis.serializers import TestCaseGenerationTaskSerializer
        task = TestCaseGenerationTask.objects.create(
            task_id='OPT003', title='t', requirement_text='r', created_by=self.user,
            case_type='x', granularity='fine')
        data = TestCaseGenerationTaskSerializer(task).data
        self.assertEqual(data['case_type'], 'x')
        self.assertEqual(data['granularity'], 'fine')
        self.assertEqual(data['granularity_display'], '细粒度')


class GenerateEndpointOptionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='gen_opt_ep_user', password='x')

    def test_generate_persists_case_type_and_granularity(self):
        import threading as _th
        from unittest import mock
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)

        with mock.patch.object(_th, 'Thread', autospec=True) as fake_thread:
            resp = client.post('/api/requirement-analysis/testcase-generation/generate/', {
                'title': '登录需求',
                'requirement_text': '用户登录',
                'use_writer_model': False,
                'use_reviewer_model': False,
                'output_mode': 'stream',
                'case_type': '以接口为主',
                'granularity': 'fine',
            }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        task = resp.data['task']
        self.assertEqual(task['case_type'], '以接口为主')
        self.assertEqual(task['granularity'], 'fine')
        self.assertTrue(fake_thread.called)
