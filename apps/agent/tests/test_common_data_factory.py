import asyncio
import json
from django.test import TransactionTestCase
from apps.agent.tools.common import list_projects
from apps.agent.tools.data_factory import list_data_factory_tools, generate_test_data
from apps.agent.service_identity import get_service_user
from apps.projects.models import Project


# 工具函数已异步化（asyncio.to_thread 在工作线程执行 Django ORM）。
# 工作线程使用独立数据库连接，只能看到已提交数据，
# 因此用 TransactionTestCase（提交型）而非 TestCase（事务回滚型）。
class CommonToolsTests(TransactionTestCase):
    def test_list_projects(self):
        Project.objects.create(name='Alpha', owner=get_service_user())
        out = json.loads(asyncio.run(list_projects()))
        self.assertIn('Alpha', [p['name'] for p in out])


class DataFactoryToolsTests(TransactionTestCase):
    def test_list_tools(self):
        out = json.loads(asyncio.run(list_data_factory_tools()))
        self.assertGreater(len(out), 0)
        names = [t['tool_name'] for t in out]
        self.assertIn('generate_chinese_phone', names)

    def test_generate_test_data_json(self):
        out = json.loads(asyncio.run(generate_test_data('format_json', 'json', {'json_str': '{"a": 1}'})))
        self.assertNotIn('error', out)

    def test_generate_test_data_unknown_tool(self):
        out = json.loads(asyncio.run(generate_test_data('nope', 'string', {'text': 'x'})))
        self.assertIn('error', out)
