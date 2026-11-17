"""转化服务层测试：抽取、消息构造、AI 结果解析、变量渲染。"""
import json

from django.test import TestCase

from apps.projects.models import Project
from apps.requirement_analysis.automation_services import (
    build_case_task_description,
    build_conversion_messages,
    build_environment_context,
    build_login_task_description,
    extract_execution_detail,
    extract_source_data,
    extract_success_trace,
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

    def test_parse_with_trailing_text_after_array(self):
        # AI 常在 JSON 数组后补解释文字，json.loads 会报 Extra data，解析须容忍
        raw = (
            '[\n'
            '  {"action": "打开 {{base_url}}/users", "verify": "列表可见"},\n'
            '  {"action": "点击新增", "verify": ""}\n'
            ']\n'
            '以上即为转写后的操作步骤，共 2 步，请查收。'
        )
        steps = parse_conversion_result(raw)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]['action'], '打开 {{base_url}}/users')

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

    def test_task_description_injects_failure_summary(self):
        """用例带 last_failure_summary 时，任务描述头部注入失败原因。"""
        case = AutomationCase.objects.create(
            project=self.project, title='登录', steps=[{'index': 1, 'action': '打开登录页'}],
            last_failure_summary='点击了隐藏的「登录」文字导致未提交')
        text = build_case_task_description(case, self.env)
        self.assertIn('上次执行失败原因', text)
        self.assertIn('点击了隐藏的「登录」文字导致未提交', text)
        self.assertIn('打开登录页', text)

    def test_task_description_no_failure_summary(self):
        """无失败总结时任务描述不含注入段。"""
        case = AutomationCase.objects.create(
            project=self.project, title='登录', steps=[{'index': 1, 'action': '打开登录页'}])
        text = build_case_task_description(case, self.env)
        self.assertNotIn('上次执行失败原因', text)

    def test_task_description_injects_success_trace(self):
        """用例带 success_trace 时，任务描述尾部注入成功路径参考。"""
        trace = [{'url': 'https://demo.example.com/login',
                  'actions': ['访问: https://demo.example.com/login', "输入: 'admin'"]}]
        case = AutomationCase.objects.create(
            project=self.project, title='登录', steps=[{'index': 1, 'action': '打开登录页'}],
            success_trace=trace)
        text = build_case_task_description(case, self.env)
        self.assertIn('上次成功执行路径', text)
        self.assertIn("输入: 'admin'", text)

    def test_task_description_truncates_long_trace(self):
        """过长的成功路径参考被截断，任务描述主体仍然完整。"""
        trace = [{'url': f'https://x.com/p{i}', 'actions': ['点击[1]'] * 200} for i in range(50)]
        case = AutomationCase.objects.create(
            project=self.project, title='登录', steps=[{'index': 1, 'action': '打开登录页'}],
            success_trace=trace)
        text = build_case_task_description(case, self.env)
        self.assertIn('打开登录页', text)
        self.assertLess(len(text), 8000)

    def test_build_login_task_description(self):
        text = build_login_task_description(self.env)
        self.assertIn('https://demo.example.com/login', text)
        self.assertIn('admin', text)
        self.assertIn('secret', text)

    def test_task_description_logged_in_skips_login_steps(self):
        """会话已登录时注入跳过登录指令，避免会话登录 + 用例登录步骤重复登录。"""
        case = AutomationCase.objects.create(
            project=self.project, title='用户管理',
            steps=[{'index': 1, 'action': '打开 {{base_url}}，在登录页输入账号 {{username}}、'
                    '密码 {{password}}，点击【登录】按钮'},
                   {'index': 2, 'action': '点击左侧菜单【用户管理】'}])
        text = build_case_task_description(case, self.env, logged_in=True)
        self.assertIn('已完成登录', text)
        self.assertIn('跳过', text)
        self.assertIn('点击【登录】按钮', text)

    def test_task_description_not_logged_in_no_skip_hint(self):
        """会话未登录（环境未配 login_url）时不注入跳过登录指令。"""
        case = AutomationCase.objects.create(
            project=self.project, title='用户管理',
            steps=[{'index': 1, 'action': '打开 {{base_url}}，输入账号密码登录'}])
        text = build_case_task_description(case, self.env)
        self.assertNotIn('跳过', text)


class _FakeAction:
    def __init__(self, d):
        self._d = d

    def model_dump(self):
        return self._d


class _FakeOutput:
    def __init__(self, actions, thinking='', evaluation='', next_goal=''):
        self.action = [_FakeAction(a) for a in actions]
        self.thinking = thinking
        self.evaluation_previous_goal = evaluation
        self.next_goal = next_goal


class _FakeResult:
    def __init__(self, error=None, extracted_content=None):
        self.error = error
        self.extracted_content = extracted_content


class _FakeState:
    def __init__(self, url, title=''):
        self.url = url
        self.title = title


class _FakeMeta:
    def __init__(self, duration):
        self.duration_seconds = duration


class _FakeStep:
    def __init__(self, output=None, results=None, url='', title='', duration=0.0):
        self.model_output = output
        self.result = results or []
        self.state = _FakeState(url, title)
        self.metadata = _FakeMeta(duration) if duration else None


class _FakeHistoryList:
    def __init__(self, steps):
        self.history = steps


class ExtractExecutionDetailTests(TestCase):
    """browser-use 执行历史 → 结构化步骤 / 成功路径记忆。"""

    def test_extract_detail_full_fields(self):
        history = _FakeHistoryList([
            _FakeStep(
                output=_FakeOutput(
                    [{'navigate': {'url': 'https://x.com'}}],
                    thinking='打开登录页', evaluation='初始状态', next_goal='导航'),
                url='https://x.com/login', title='登录页', duration=1.5),
            _FakeStep(),  # 无 model_output 的步骤（如初始导航）
        ])
        detail = extract_execution_detail(history)
        self.assertEqual(len(detail), 2)
        first = detail[0]
        self.assertEqual(first['index'], 1)
        self.assertEqual(first['url'], 'https://x.com/login')
        self.assertEqual(first['title'], '登录页')
        self.assertEqual(first['thinking'], '打开登录页')
        self.assertEqual(first['actions'], ['访问: https://x.com'])
        self.assertEqual(first['duration'], 1.5)

    def test_extract_detail_error_and_result(self):
        history = _FakeHistoryList([
            _FakeStep(
                output=_FakeOutput([{'click': {'index': 7}}]),
                results=[_FakeResult(error='元素不可见')],
                url='https://x.com', duration=0.5),
        ])
        detail = extract_execution_detail(history)
        self.assertEqual(detail[0]['error'], '元素不可见')

    def test_extract_success_trace_skips_non_browser_actions(self):
        """done/mark_task_complete 等非浏览器动作不进成功路径记忆。"""
        history = _FakeHistoryList([
            _FakeStep(
                output=_FakeOutput([{'input': {'index': 3, 'text': 'admin'}}]),
                url='https://x.com/login', duration=0.3),
            _FakeStep(
                output=_FakeOutput([{'mark_task_complete': {'task_id': 1}}]),
                url='https://x.com/login', duration=0.1),
            _FakeStep(output=_FakeOutput([{'done': {'success': True, 'text': 'ok'}}]),
                      url='https://x.com/home', duration=0.2),
        ])
        trace = extract_success_trace(history)
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]['url'], 'https://x.com/login')
        self.assertEqual(trace[0]['actions'], ["输入: 'admin'"])

    def test_extract_handles_plain_list(self):
        """history 为普通列表（旧版兼容）时同样可提取。"""
        detail = extract_execution_detail([
            _FakeStep(output=_FakeOutput([{'click': {'index': 7}}]), url='https://x.com')])
        self.assertEqual(detail[0]['actions'], ['点击[7]'])
