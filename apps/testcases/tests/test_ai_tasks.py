"""AI 修改/补充用例测试（mock AIClient，不真正调模型）

- POST /api/testcases/ai-modify/ 创建后台任务并返回 task_id
- worker 执行：勾选用例被 AI 重写，逐条落 ai_modified 版本
- AI 失败：任务 failed，用例与版本不动
- POST /api/testcases/ai-supplement/ 基于需求创建补充任务
- worker 执行：新建 TestCase 行（tags 含 ai、版本 v1 source=ai_supplemented）
"""
import json
from unittest import mock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.testcases.models import TestCase as TestCaseModel
from apps.testcases.models import TestCaseAiTask
from apps.requirement_analysis.models import Requirement

User = get_user_model()

AI_MODIFY_OUTPUT_TEMPLATE = [
    {
        '编号': None, 'title': '登录失败5次锁定账号', 'precondition': '已注册账号',
        'steps': [{'desc': '连续输错密码5次', 'expect': '账号被锁定'}],
        'priority': 'P1',
    },
    {
        '编号': None, 'title': '验证验证码60秒有效期', 'precondition': '已获取验证码',
        'steps': [{'desc': '等待60秒后输入', 'expect': '提示验证码已失效'}],
        'priority': 'P2',
    },
]

AI_SUPPLEMENT_OUTPUT = json.dumps([
    {
        '编号': 'NEW_1', 'title': '补充：第三方登录场景', 'precondition': '已绑定微信',
        'steps': [{'desc': '点击微信登录', 'expect': '授权后进入主页'}],
        'priority': 'P2',
    },
    {
        '编号': 'NEW_2', 'title': '补充：登录会话超时', 'precondition': '已登录',
        'steps': [{'desc': '闲置30分钟', 'expect': '自动登出'}],
        'priority': 'P3',
    },
], ensure_ascii=False)


def _modify_output(id1, id2):
    """按真实用例 ID 构造 AI 返回（测试库自增 ID 不从 1 开始）"""
    items = json.loads(json.dumps(AI_MODIFY_OUTPUT_TEMPLATE))
    items[0]['编号'], items[1]['编号'] = id1, id2
    return json.dumps(items, ensure_ascii=False)


def _ai_return(content):
    return {'choices': [{'message': {'content': content}}]}


# worker 测试里保存真实用例 ID，供 mock 返回值动态引用
_IDS = [None, None]


def make_case(user, project, idx=1, **kw):
    data = dict(
        project=project, author=user, title=f'用例{idx}',
        preconditions='前置', steps=json.dumps([{'desc': '步骤', 'expect': '预期'}]),
        priority='medium', test_type='functional', tags=[],
    )
    data.update(kw)
    return TestCaseModel.objects.create(**data)


def make_requirement(user):
    project = Project.objects.create(name='项目A', owner=user)
    return Requirement.objects.create(
        project=project, source_type='manual', title='登录需求',
        spec='支持手机号验证码登录、密码登录，失败5次锁定',
    )


class AiModifyApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('aiuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name='p', owner=self.user)
        self.c1 = make_case(self.user, self.project, 1)
        self.c2 = make_case(self.user, self.project, 2)

    @mock.patch('apps.testcases.ai_tasks.start_ai_task')
    def test_post_ai_modify_creates_task(self, mock_start):
        resp = self.client.post(
            '/api/testcases/ai-modify/',
            {'case_ids': [self.c1.id, self.c2.id], 'note': '补充异常场景'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        task = TestCaseAiTask.objects.get(task_id=resp.json()['task_id'])
        self.assertEqual(task.mode, 'modify')
        self.assertEqual(task.status, 'pending')
        self.assertEqual(sorted(task.case_ids), sorted([self.c1.id, self.c2.id]))
        self.assertEqual(task.note, '补充异常场景')
        mock_start.assert_called_once()

    def test_post_ai_modify_requires_case_ids_and_note(self):
        resp = self.client.post('/api/testcases/ai-modify/', {'case_ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_task_poll_endpoint(self):
        task = TestCaseAiTask.objects.create(
            task_id='t123', mode='modify', note='n', case_ids=[self.c1.id], created_by=self.user,
        )
        resp = self.client.get('/api/testcases/ai-task/t123/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'pending')


class AiModifyWorkerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('worker', password='x')
        self.project = Project.objects.create(name='p', owner=self.user)
        self.c1 = make_case(self.user, self.project, 1)
        self.c2 = make_case(self.user, self.project, 2)
        _IDS[0], _IDS[1] = self.c1.id, self.c2.id
        self.task = TestCaseAiTask.objects.create(
            task_id='m1', mode='modify', note='补充异常场景',
            case_ids=[self.c1.id, self.c2.id], created_by=self.user,
        )

    @mock.patch(
        "apps.testcases.ai_tasks.AIClient.chat_sync",
        side_effect=lambda config, messages, **kw: _ai_return(_modify_output(_IDS[0], _IDS[1])),
    )
    @mock.patch('apps.testcases.ai_tasks.ConfigResolver')
    def test_run_modify_updates_cases_and_snapshots(self, mock_resolver, mock_chat):
        mock_resolver.active.return_value = mock.MagicMock()
        from apps.testcases.ai_tasks import run_ai_task
        run_ai_task(self.task)

        self.task.refresh_from_db()
        self.assertEqual(
            self.task.status, 'succeeded',
            f'worker failed: {self.task.error_message}',
        )
        self.c1.refresh_from_db()
        self.c2.refresh_from_db()
        self.assertEqual(self.c1.title, '登录失败5次锁定账号')
        self.assertEqual(self.c2.title, '验证验证码60秒有效期')
        self.assertEqual(json.loads(self.c2.steps), [{'desc': '等待60秒后输入', 'expect': '提示验证码已失效'}])
        self.assertEqual(self.c1.priority, 'high')  # P1 → high

        for case, prio_ver in [(self.c1, 'high'), (self.c2, 'medium')]:
            versions = list(case.version_history.order_by('version'))
            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[-1].source, 'ai_modified')
            self.assertEqual(versions[-1].note, '补充异常场景')
            self.assertEqual(versions[-1].priority, prio_ver)

    @mock.patch('apps.testcases.ai_tasks.AIClient.chat_sync', side_effect=Exception('模型超时'))
    @mock.patch('apps.testcases.ai_tasks.ConfigResolver')
    def test_run_modify_ai_error_marks_failed(self, mock_resolver, mock_chat):
        mock_resolver.active.return_value = mock.MagicMock()
        from apps.testcases.ai_tasks import run_ai_task
        run_ai_task(self.task)

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'failed')
        self.assertIn('模型超时', self.task.error_message)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.title, '用例1')  # 用例未被改动
        self.assertEqual(self.c1.version_history.count(), 1)

    @mock.patch('apps.testcases.ai_tasks.ConfigResolver')
    def test_run_modify_without_ai_config_fails(self, mock_resolver):
        mock_resolver.active.return_value = None
        from apps.testcases.ai_tasks import run_ai_task
        run_ai_task(self.task)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'failed')
        self.assertIn('AI', self.task.error_message)


class AiSupplementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('supuser', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.requirement = make_requirement(self.user)
        self.project = self.requirement.project
        self.existing = make_case(self.user, self.project, 1, requirement=self.requirement)

    @mock.patch('apps.testcases.ai_tasks.start_ai_task')
    def test_post_ai_supplement_creates_task(self, mock_start):
        resp = self.client.post(
            '/api/testcases/ai-supplement/',
            {'requirement_id': self.requirement.id, 'note': '补充安全类用例'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        task = TestCaseAiTask.objects.get(task_id=resp.json()['task_id'])
        self.assertEqual(task.mode, 'supplement')
        self.assertEqual(task.requirement_id, self.requirement.id)
        self.assertIn('验证码登录', task.requirement_text)  # 预填 Requirement.spec
        self.assertEqual(task.project_id, self.project.id)

    def test_post_ai_supplement_requires_requirement(self):
        resp = self.client.post('/api/testcases/ai-supplement/', {'note': 'n'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @mock.patch('apps.testcases.ai_tasks.AIClient.chat_sync', return_value=_ai_return(AI_SUPPLEMENT_OUTPUT))
    @mock.patch('apps.testcases.ai_tasks.ConfigResolver')
    def test_run_supplement_creates_new_cases(self, mock_resolver, mock_chat):
        mock_resolver.active.return_value = mock.MagicMock()
        task = TestCaseAiTask.objects.create(
            task_id='s1', mode='supplement', note='补充安全类用例',
            requirement=self.requirement, project=self.project, created_by=self.user,
        )
        from apps.testcases.ai_tasks import run_ai_task
        run_ai_task(task)

        task.refresh_from_db()
        self.assertEqual(
            task.status, 'succeeded',
            f'worker failed: {task.error_message}',
        )
        new_ids = task.created_cases
        self.assertEqual(len(new_ids), 2)
        for case in TestCaseModel.objects.filter(id__in=new_ids):
            self.assertEqual(case.project_id, self.project.id)
            self.assertEqual(case.requirement_id, self.requirement.id)
            self.assertIn('ai', case.tags)
            v1 = case.version_history.get()
            self.assertEqual(v1.version, 1)
            self.assertEqual(v1.source, 'ai_supplemented')
            self.assertEqual(v1.note, '补充安全类用例')
        # 原有用例不受影响
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.title, '用例1')
        self.assertEqual(self.existing.version_history.count(), 1)


class ParseCaseLinesTests(TestCase):
    """AI 返回内容解析：容忍思考型模型输出推理文字、对象粘连、pretty-print"""

    def _parser(self):
        from apps.testcases.ai_tasks import _parse_case_lines
        return _parse_case_lines

    def test_pure_jsonl(self):
        content = '{"编号":1,"title":"a","priority":"P1"}\n{"编号":2,"title":"b","priority":"P2"}'
        self.assertEqual(len(self._parser()(content)), 2)

    def test_json_array(self):
        content = json.dumps([{'编号': 1, 'title': 'a', 'priority': 'P1'}], ensure_ascii=False)
        self.assertEqual(len(self._parser()(content)), 1)

    def test_reasoning_prose_with_glued_json(self):
        """真实故障：GLM 输出推理文字，JSON 对象粘在句子末尾（行首不是 {）"""
        content = (
            'Precondition should also be updated: 系统中存在已禁用账号。\n\n'
            'Priority: keep P2 (feedback didn\'t mention priority). Actually, exception scenarios...\n\n'
            'Let me finalize:\n\n'
            '{\n"编号":1131,\n"title":"验证禁用或注销账号登录的异常场景",\n'
            '"precondition":"系统中分别存在一个已禁用账号","steps":[\n'
            '{"desc":"输入禁用账号及正确密码","expect":"登录被拒绝"}\n],\n"priority":"P2"\n}\n\n'
            'The output format example shows the JSON on one line.'
            '{"编号":1132,"title":"第二条","precondition":"前置","steps":[{"desc":"s","expect":"e"}],"priority":"P3"}'
        )
        cases = self._parser()(content)
        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]['编号'], 1131)
        self.assertEqual(cases[0]['title'], '验证禁用或注销账号登录的异常场景')
        self.assertEqual(cases[1]['编号'], 1132)

    def test_steps_subobject_not_treated_as_case(self):
        """嵌套的 steps 子对象不能被误判成用例（与 requirement_analysis 同样的坑）"""
        content = (
            '{"编号":1,"title":"正常用例","precondition":"p",'
            '"steps":[{"desc":"d","expect":"e"}],"priority":"P1"}'
        )
        self.assertEqual(len(self._parser()(content)), 1)


class JsonRepairFallbackTests(TestCase):
    """json_repair 兜底：轻度损坏（尾逗号/截断）的 JSON 也能救回"""

    def _parser(self):
        from apps.testcases.ai_tasks import _parse_case_lines
        return _parse_case_lines

    def test_trailing_comma_repaired(self):
        content = '{"编号":1,"title":"a","precondition":"p","steps":[{"desc":"d","expect":"e"}],"priority":"P1",}'
        cases = self._parser()(content)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['编号'], 1)

    def test_truncated_json_in_prose_rescued(self):
        """真实故障模式：GLM 思考吃掉 max_tokens → 末尾 JSON 截断（扫描器拿不到闭合对象）"""
        content = (
            'Let me finalize the output now. The case covers exception scenarios.\n'
            '{"编号":1131,"title":"验证登录异常","precondition":"已注册账号",'
            '"steps":[{"desc":"输入禁用账号及正确密码","expect":"登录被拒绝"}],"priority"'
        )
        cases = self._parser()(content)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['编号'], 1131)
        self.assertEqual(cases[0]['title'], '验证登录异常')
