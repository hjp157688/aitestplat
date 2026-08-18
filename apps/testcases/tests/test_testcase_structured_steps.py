"""TestCase 模型字段变更测试：禅道字段 + steps结构化 + 删除 expected_result"""
import json
from django.test import TestCase
from apps.testcases.models import TestCase as TC
from apps.projects.models import Project
from django.contrib.auth import get_user_model

User = get_user_model()


class TestCaseModelFieldsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test_tc_user', password='x')
        self.project = Project.objects.create(name='p', owner=self.user)

    def test_zentao_fields_exist(self):
        tc = TC.objects.create(
            project=self.project, author=self.user, title='t',
            steps='[]', priority='medium',
        )
        tc.zentao_case_id = 'case_500'
        tc.product_id = 1
        tc.module_id = 2
        tc.story_id = 3
        tc.save()
        tc.refresh_from_db()
        self.assertEqual(tc.zentao_case_id, 'case_500')
        self.assertEqual(tc.product_id, 1)
        self.assertEqual(tc.module_id, 2)
        self.assertEqual(tc.story_id, 3)

    def test_expected_result_removed(self):
        self.assertFalse(any(
            f.name == 'expected_result' for f in TC._meta.get_fields()
        ))

    def test_requirement_fk_exists(self):
        from apps.requirement_analysis.models import Requirement
        req = Requirement.objects.create(
            project=self.project, source_type='manual', title='r',
        )
        tc = TC.objects.create(
            project=self.project, author=self.user, title='t',
            steps='[]', priority='medium', requirement=req,
        )
        self.assertEqual(tc.requirement_id, req.id)
        self.assertEqual(
            list(req.testcases.filter(id=tc.id)), [tc]
        )

    def test_steps_stores_structured_json(self):
        steps_data = [{'desc': '点击登录', 'expect': '跳转主页'}]
        tc = TC.objects.create(
            project=self.project, author=self.user, title='t',
            steps=json.dumps(steps_data, ensure_ascii=False),
            priority='medium',
        )
        tc.refresh_from_db()
        parsed = json.loads(tc.steps)
        self.assertEqual(parsed, steps_data)

    def test_empty_steps_defaults_to_array(self):
        tc = TC.objects.create(
            project=self.project, author=self.user, title='t',
            steps='[]', priority='medium',
        )
        self.assertEqual(tc.steps, '[]')

    def test_steps_migration_rule_old_format(self):
        """模拟旧 steps + expected_result -> 结构化 JSON 的转换规则"""
        import re
        # 旧格式：文本步骤换行 + 独立的预期结果
        old_steps = '1. 步骤一\n2. 步骤二'
        old_expected = '预期结果A'
        steps_list = []
        for line in re.split(r'[\r\n]+', old_steps):
            line = re.sub(r'^\d+[\.\)、]\s*', '', line).strip()
            if line:
                steps_list.append({'desc': line, 'expect': ''})
        if old_expected:
            steps_list.append({'desc': '', 'expect': old_expected})
        output = json.dumps(steps_list, ensure_ascii=False)
        parsed = json.loads(output)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]['desc'], '步骤一')
        self.assertEqual(parsed[2]['expect'], '预期结果A')
