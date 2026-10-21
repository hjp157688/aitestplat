"""自动化用例模块模型测试：字段、约束与 source_type 推导。"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.projects.models import Project
from apps.requirement_analysis.models import (
    AutomationCase,
    AutomationEnvironment,
    AutomationExecution,
    AutomationExecutionSession,
)

User = get_user_model()


class AutomationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('auto-user', password='x')
        self.project = Project.objects.create(name='自动化项目', owner=self.user)

    def test_automation_case_inline_source_type(self):
        case = AutomationCase.objects.create(
            project=self.project, title='登录成功用例', steps=[], created_by=self.user)
        self.assertEqual(case.source_type, 'inline')
        self.assertEqual(str(case), '登录成功用例')
        self.assertEqual(case.convert_status, 'processing')

    def test_environment_variables_default_list(self):
        env = AutomationEnvironment.objects.create(project=self.project, name='测试环境')
        self.assertEqual(env.variables, [])
        self.assertTrue(env.is_active)
        self.assertEqual(str(env), '测试环境')

    def test_session_and_execution_defaults(self):
        env = AutomationEnvironment.objects.create(project=self.project, name='测试环境')
        case = AutomationCase.objects.create(project=self.project, title='用例A', steps=[])
        session = AutomationExecutionSession.objects.create(
            project=self.project, environment=env, triggered_by=self.user)
        execution = AutomationExecution.objects.create(
            case=case, session=session, environment=env)
        self.assertEqual(session.status, 'pending')
        self.assertEqual(session.login_status, 'not_required')
        self.assertEqual(execution.status, 'pending')
        self.assertEqual(str(session), f'执行会话#{session.pk}')
        self.assertEqual(str(execution), f'执行记录#{execution.pk}')
