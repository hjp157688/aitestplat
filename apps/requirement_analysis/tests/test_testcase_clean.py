# -*- coding: utf-8 -*-
"""AI 生成文本清洗（text_cleaner / parse/adopt 接线）测试。

覆盖：Markdown/HTML 残留清洗、JSONL 与旧表格两种格式的步骤规整、评审改进
提示词不再声明 Markdown 加粗规则。
"""
import json

from django.test import SimpleTestCase

from apps.requirement_analysis.text_cleaner import clean_text, normalize_steps
from apps.requirement_analysis.models import AIModelService


class CleanTextTests(SimpleTestCase):

    def test_strip_bold_markers(self):
        self.assertEqual(clean_text('**验证同一账号多端登录**'), '验证同一账号多端登录')
        self.assertEqual(clean_text('__下划线加粗__ 和 *斜体*'), '下划线加粗 和 斜体')

    def test_preserve_underscores_inside_identifiers(self):
        self.assertEqual(clean_text('LOGIN_001'), 'LOGIN_001')
        self.assertEqual(clean_text('user_id'), 'user_id')

    def test_br_to_newline(self):
        self.assertEqual(clean_text('步骤A<br>步骤B<br/>步骤C'), '步骤A\n步骤B\n步骤C')

    def test_html_entities_and_tags(self):
        self.assertEqual(clean_text('值 a&#124;b 与 &amp; 符号'), '值 a|b 与 & 符号')

    def test_heading_marker_stripped(self):
        self.assertEqual(clean_text('## 登录模块测试用例'), '登录模块测试用例')

    def test_empty_and_none(self):
        self.assertEqual(clean_text(''), '')
        self.assertEqual(clean_text(None), '')


class NormalizeStepsTests(SimpleTestCase):

    def test_list_of_step_dicts_kept(self):
        out = normalize_steps([
            {'desc': '输入手机号', 'expect': '号码显示'},
            {'desc': '点击登录', 'expect': '跳转主页'},
        ])
        self.assertEqual(out[0]['desc'], '输入手机号')
        self.assertEqual(out[0]['expect'], '号码显示')
        self.assertEqual(out[1]['expect'], '跳转主页')

    def test_single_dict_with_br_desc_splits_into_multiple_steps(self):
        out = normalize_steps([{'desc': '**1. 输入正确手机号**<br>**2. 点击登录按钮**', 'expect': ''}])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], {'desc': '输入正确手机号', 'expect': ''})
        self.assertEqual(out[1], {'desc': '点击登录按钮', 'expect': ''})

    def test_flat_string_with_numbering_splits(self):
        out = normalize_steps('1. 打开登录页<br>2. 输入用户名<br>3. 点击登录')
        self.assertEqual(out, [
            {'desc': '打开登录页', 'expect': ''},
            {'desc': '输入用户名', 'expect': ''},
            {'desc': '点击登录', 'expect': ''},
        ])

    def test_empty_inputs(self):
        self.assertEqual(normalize_steps(None), [])
        self.assertEqual(normalize_steps([]), [])
        self.assertEqual(normalize_steps(''), [])

    def test_expected_prefix_steps_merged_into_previous(self):
        """AI 偶发把每条期望输出成独立「预期:」步骤：应并入上一步 expect，而不是挤在步骤里。"""
        out = normalize_steps([
            {'desc': '打开登录页', 'expect': ''},
            {'desc': '预期: 登录页正常显示，文字和背景对比度清晰', 'expect': ''},
            {'desc': '检查输入框和按钮', 'expect': ''},
            {'desc': '预期: 输入框和按钮在深色模式下无颜色冲突，可正常操作', 'expect': ''},
        ])
        self.assertEqual(out, [
            {'desc': '打开登录页', 'expect': '登录页正常显示，文字和背景对比度清晰'},
            {'desc': '检查输入框和按钮', 'expect': '输入框和按钮在深色模式下无颜色冲突，可正常操作'},
        ])

    def test_expected_prefix_in_newline_merged(self):
        """desc 内换行夹带「预期:」：拆分后仍应合并回上一步 expect。"""
        out = normalize_steps([
            {'desc': '打开登录页\n预期: 登录页正常显示', 'expect': ''},
            {'desc': '输入手机号', 'expect': ''},
        ])
        self.assertEqual(out, [
            {'desc': '打开登录页', 'expect': '登录页正常显示'},
            {'desc': '输入手机号', 'expect': ''},
        ])

    def test_expect_field_prefixed_label_stripped(self):
        """expect 字段本身带「预期:」前缀也应清理，避免展示时重复标签。"""
        out = normalize_steps([{'desc': '点击登录', 'expect': '预期: 跳转主页'}])
        self.assertEqual(out[0]['desc'], '点击登录')
        self.assertEqual(out[0]['expect'], '跳转主页')

    def test_expected_prefix_accumulates_on_multi_step(self):
        """同一动作后跟多个「预期:」步骤：追加合并，不互相覆盖。"""
        out = normalize_steps([
            {'desc': '点击登录', 'expect': ''},
            {'desc': '预期: 按钮进入加载状态', 'expect': ''},
            {'desc': '预期: 登录成功后跳转主页', 'expect': ''},
        ])
        self.assertEqual(out, [{
            'desc': '点击登录',
            'expect': '按钮进入加载状态\n登录成功后跳转主页',
        }])

    def test_expected_prefix_first_step_kept_without_merge(self):
        """首步即是「预期:」时无可并入上一步，保留为独立步骤（仅去掉标签前缀）。"""
        out = normalize_steps([
            {'desc': '预期: 输入框正常显示', 'expect': ''},
            {'desc': '输入手机号', 'expect': ''},
        ])
        self.assertEqual(out[0]['desc'], '输入框正常显示')
        self.assertEqual(out[1]['desc'], '输入手机号')

    def test_action_step_containing_label_word_not_mangled(self):
        """动作行以「预期」起头但无冒号/无标签语义（如「预期测试某功能」）不应被误合并。"""
        out = normalize_steps([{'desc': '预期测试某功能的展示', 'expect': ''}])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['desc'], '预期测试某功能的展示')
        self.assertEqual(out[0]['expect'], '')


class ParseTestCasesContentTests(SimpleTestCase):
    """_parse_test_cases_content 对 JSONL 与旧表格两种输入的清洗行为"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.requirement_analysis.views import TestCaseGenerationTaskViewSet
        cls.viewset = TestCaseGenerationTaskViewSet()

    def test_jsonl_with_markdown_residue_cleaned(self):
        content = (
            '{"case_id":"LOGIN_001","title":"**验证手机号格式校验**",'
            '"precondition":"在登录页","steps":[{"desc":"**输入10位手机号**","expect":"提示格式不正确"},'
            '{"desc":"点击获取验证码","expect":"提示手机号格式不正确"}],"priority":"P1"}'
        )
        cases = self.viewset._parse_test_cases_content(content)
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case['title'], '验证手机号格式校验')
        self.assertNotIn('**', case['title'])
        self.assertEqual(case['steps'][0]['desc'], '输入10位手机号')
        self.assertEqual(case['steps'][0]['expect'], '提示格式不正确')

    def test_jsonl_with_br_in_single_desc_splits(self):
        content = (
            '{"case_id":"LOGIN_001","title":"验证登录","steps":'
            '[{"desc":"**1. 输入手机号**<br>**2. 点击登录**","expect":""}],"priority":"P1"}'
        )
        cases = self.viewset._parse_test_cases_content(content)
        steps = cases[0]['steps']
        self.assertEqual(len(steps), 2)
        self.assertEqual([s['desc'] for s in steps], ['输入手机号', '点击登录'])

    def test_legacy_table_parsed_with_steps_and_expected(self):
        content = "\n".join([
            '| 用例ID | 测试目标 | 前置条件 | 操作步骤 | 预期结果 | 优先级 | 测试类型 | 关联需求 |',
            '|--------|--------|--------|--------|--------|--------|--------|--------|',
            '| LOGIN_001 | **验证正常登录流程** | 已注册账号 | 1. 输入手机号<br>2. 点击登录 | 登录成功，跳转首页 | P0 | 功能验证 | 登录模块 |',
        ])
        cases = self.viewset._parse_test_cases_content(content)
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case['scenario'], '验证正常登录流程')
        self.assertNotIn('**', case['scenario'])
        steps = case['steps']
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]['desc'], '输入手机号')
        # 表格行整体预期挂到最后一步
        self.assertEqual(steps[1]['expect'], '登录成功，跳转首页')

    def test_reconstruct_outputs_jsonl_not_markdown(self):
        cases = [{
            'caseId': 'LOGIN_001',
            'scenario': '验证登录',
            'precondition': '在登录页',
            'steps': [{'desc': '输入手机号', 'expect': ''}, {'desc': '点击登录', 'expect': '跳转首页'}],
            'expected': '',
            'priority': 'P0',
        }]
        content = self.viewset._reconstruct_test_cases_content(cases)
        self.assertNotIn('|', content)
        self.assertNotIn('<br', content)
        obj = json.loads(content)
        self.assertEqual(obj['title'], '验证登录')
        self.assertEqual(obj['steps'], cases[0]['steps'])


class BuildReviseUserMessageTests(SimpleTestCase):
    """评审改进阶段提示词必须与 JSONL 约定一致（删除 Markdown 加粗规则）"""

    def test_message_uses_jsonl_and_forbids_markdown(self):
        msg = AIModelService._build_revise_user_message(
            '{"case_id":"TC-001","title":"t","steps":[]}', '评审意见', '【颗粒度：中】')
        self.assertIn('JSONL', msg)
        self.assertIn('禁止 Markdown', msg)

    def test_no_bold_marker_rule_or_html_pipe_rule(self):
        msg = AIModelService._build_revise_user_message('x', 'y', '')
        self.assertNotIn('对整个新增的测试用例进行加粗', msg)
        self.assertNotIn('加粗标记规则', msg)
        self.assertNotIn('&#124;', msg)
