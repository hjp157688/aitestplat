"""转化服务层测试：抽取、消息构造、AI 结果解析、变量渲染。"""
import json

from django.test import TestCase

from apps.projects.models import Project
from apps.requirement_analysis.automation_services import (
    build_case_task_description,
    build_conversion_messages,
    build_environment_context,
    build_login_task_description,
    extract_source_data,
    parse_conversion_result,
    render_text,
)
from apps.requirement_analysis.models import (
    AutomationCase,
    AutomationEnvironment,
    GeneratedTestCase,
    Requirement,
)


class ExtractSourceDataTests(TestCase):
    def setUp(self):
        # 注意：Project.owner 为必填外键，先创建用户再传入。
        from apps.users.models import User
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.project = Project.objects.create(name='p', owner=self.user)
        self.requirement = Requirement.objects.create(project=self.project, title='需求A')

    def test_extract_from_generated_case(self):
        gen = GeneratedTestCase.objects.create(
            requirement=self.requirement, case_id='TC-001', title='登录成功',
            priority='P1', precondition='已有账号', test_steps='1. 打开登录页\n2. 输入账号密码',
            expected_result='登录成功进入首页')
        data = extract_source_data('generated', gen)
        self.assertEqual(data['title'], '登录成功')
        self.assertIn('打开登录页', data['steps_text'])
        self.assertEqual(data['expected_text'], '登录成功进入首页')

    def test_extract_from_manual_case(self):
        from apps.testcases.models import TestCase as ManualTestCase
        manual = ManualTestCase.objects.create(
            project=self.project, title='新增用户', preconditions='管理员已登录',
            author=self.user,
            steps=json.dumps([{'action': '进入用户管理', 'expected': '列表可见'}], ensure_ascii=False))
        data = extract_source_data('testcase', manual)
        self.assertEqual(data['title'], '新增用户')
        self.assertIn('用户管理', data['steps_text'])


class ParseConversionResultTests(TestCase):
    def test_parse_plain_json(self):
        raw = json.dumps([
            {'action': '打开 {{base_url}}/login', 'verify': '页面加载完成'},
            {'action': '输入用户名 {{username}}', 'verify': ''},
        ], ensure_ascii=False)
        steps = parse_conversion_result(raw)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]['index'], 1)
        self.assertEqual(steps[0]['action'], '打开 {{base_url}}/login')

    def test_parse_with_markdown_fence_and_noise(self):
        raw = '好的，以下是转写结果：\n```json\n[{"action": "打开登录页", "verify": "出现表单"}]\n```\n'
        steps = parse_conversion_result(raw)
        self.assertEqual(steps, [{'index': 1, 'action': '打开登录页', 'verify': '出现表单'}])

    def test_invalid_json_marks_error_not_crash(self):
        with self.assertRaises(ValueError):
            parse_conversion_result('这不是 JSON')

    def test_empty_steps_rejected(self):
        with self.assertRaises(ValueError):
            parse_conversion_result('[{"action": "", "verify": ""}]')


class RenderTests(TestCase):
    def setUp(self):
        from apps.users.models import User
        user = User.objects.create_user(username='tester2', password='pass1234')
        self.project = Project.objects.create(name='p2', owner=user)
        self.env = AutomationEnvironment.objects.create(
            project=self.project, name='默认环境', base_url='https://demo.example.com',
            login_url='https://demo.example.com/login', username='admin', password='secret',
            variables=[{'key': 'product', 'value': '手机X', 'description': ''}])

    def test_environment_context_contains_login_and_vars(self):
        ctx = build_environment_context(self.env)
        self.assertEqual(ctx['base_url'], 'https://demo.example.com')
        self.assertEqual(ctx['username'], 'admin')
        self.assertEqual(ctx['password'], 'secret')
        self.assertEqual(ctx['product'], '手机X')

    def test_render_replaces_known_and_keeps_unknown(self):
        ctx = {'base_url': 'https://x.com'}
        self.assertEqual(render_text('打开 {{base_url}}/a {{nope}}', ctx), '打开 https://x.com/a {{nope}}')

    def test_build_case_task_description(self):
        case = AutomationCase.objects.create(
            project=self.project, title='登录', precondition='系统可访问',
            steps=[{'index': 1, 'action': '打开 {{base_url}}/login', 'verify': '出现登录表单'}])
        text = build_case_task_description(case, self.env)
        self.assertIn('https://demo.example.com/login', text)
        self.assertIn('完成后验证：出现登录表单', text)

    def test_build_login_task_description(self):
        text = build_login_task_description(self.env)
        self.assertIn('https://demo.example.com/login', text)
        self.assertIn('admin', text)
        self.assertIn('secret', text)
