# -*- coding: utf-8 -*-
"""AI 用例生成流程的 JSONL 处理管线测试：排序 / 修复末尾截断 / 重新编号。

覆盖：JSONL 输出下的 sort_test_cases_by_id、fix_incomplete_last_case、
renumber_test_cases 三个静态方法（旧实现为 Markdown 表格专用，JSONL 化后
必须对这些场景正确工作，且对非 JSONL 输入保持安全空操作）。
"""
import json

from django.test import SimpleTestCase

from apps.requirement_analysis.models import AIModelService
from apps.requirement_analysis.views import TestCaseGenerationTaskViewSet


def _jsonl(cases):
    return '\n'.join(json.dumps(c, ensure_ascii=False) for c in cases)


class SortTestCasesByIdTests(SimpleTestCase):

    def test_reorders_by_numeric_id(self):
        content = _jsonl([
            {'case_id': 'TC-004', 'title': 'D'},
            {'case_id': 'TC-001', 'title': 'A'},
            {'case_id': 'TC-003', 'title': 'C'},
            {'case_id': 'TC-002', 'title': 'B'},
        ])
        result = AIModelService.sort_test_cases_by_id(content)
        titles = [json.loads(line)['title'] for line in result.split('\n')]
        self.assertEqual(titles, ['A', 'B', 'C', 'D'])

    def test_stable_for_duplicate_numbers(self):
        content = _jsonl([
            {'case_id': 'TC-002', 'title': 'first'},
            {'case_id': 'TC-001', 'title': 'one'},
            {'case_id': 'TC-002', 'title': 'second'},
        ])
        result = AIModelService.sort_test_cases_by_id(content)
        titles = [json.loads(line)['title'] for line in result.split('\n')]
        # TC-002 两行保持原有的相对顺序（不丢行、不重排）
        self.assertEqual(titles, ['one', 'first', 'second'])

    def test_unparseable_line_sinks_to_end(self):
        content = _jsonl([
            {'case_id': 'TC-002', 'title': 'B'},
            {'case_id': 'TC-001', 'title': 'A'},
        ]) + '\n{bad json'  # 无法解析的原始行，原样保留在末尾
        result = AIModelService.sort_test_cases_by_id(content)
        lines = result.split('\n')
        self.assertEqual(json.loads(lines[0])['case_id'], 'TC-001')
        self.assertEqual(json.loads(lines[1])['case_id'], 'TC-002')
        self.assertEqual(lines[2], '{bad json')

    def test_chinese_prefix_sorts(self):
        content = _jsonl([
            {'case_id': '登录_002', 'title': 'B'},
            {'case_id': '登录_001', 'title': 'A'},
        ])
        result = AIModelService.sort_test_cases_by_id(content)
        self.assertEqual(json.loads(result.split('\n')[0])['case_id'], '登录_001')

    def test_non_jsonl_returned_unchanged(self):
        content = '| 编号 | 场景 |\n|--|--|\n| TC-001 | 登录 |'
        self.assertEqual(AIModelService.sort_test_cases_by_id(content), content)

    def test_empty_and_single_line(self):
        self.assertEqual(AIModelService.sort_test_cases_by_id(''), '')
        single = _jsonl([{'case_id': 'TC-001', 'title': 'A'}])
        self.assertEqual(AIModelService.sort_test_cases_by_id(single), single)


class FixIncompleteLastCaseTests(SimpleTestCase):

    def test_complete_content_unchanged(self):
        content = _jsonl([
            {'case_id': 'TC-001', 'title': 'A'},
            {'case_id': 'TC-002', 'title': 'B'},
        ])
        self.assertEqual(AIModelService.fix_incomplete_last_case(content), content)

    def test_drops_truncated_trailing_line(self):
        content = _jsonl([
            {'case_id': 'TC-001', 'title': 'A'},
        ]) + '\n{"case_id":"TC-002","title":"B","steps":['  # 未闭合 JSON
        result = AIModelService.fix_incomplete_last_case(content)
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['case_id'], 'TC-001')

    def test_drops_trailing_non_case_json(self):
        content = _jsonl([
            {'case_id': 'TC-001', 'title': 'A'},
        ]) + '\n{"foo": 1}'
        result = AIModelService.fix_incomplete_last_case(content)
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_trailing_blank_lines_normalized(self):
        result = AIModelService.fix_incomplete_last_case('{"case_id":"TC-001","title":"A"}\n\n\n')
        self.assertEqual(result, '{"case_id":"TC-001","title":"A"}')

    def test_empty_unchanged(self):
        self.assertEqual(AIModelService.fix_incomplete_last_case(''), '')


class RenumberTestCasesTests(SimpleTestCase):

    def test_fills_gaps_preserving_width_and_prefix(self):
        content = _jsonl([
            {'case_id': 'TC-001', 'title': 'A'},
            {'case_id': 'TC-003', 'title': 'C'},
        ])
        result = AIModelService.renumber_test_cases(content)
        ids = [json.loads(line)['case_id'] for line in result.split('\n')]
        self.assertEqual(ids, ['TC-001', 'TC-002'])

    def test_multiple_prefixes_independent_counters(self):
        content = _jsonl([
            {'case_id': 'LOGIN_003', 'title': 'A'},
            {'case_id': 'LOGIN_001', 'title': 'B'},
            {'case_id': 'REGISTER_001', 'title': 'C'},
        ])
        result = AIModelService.renumber_test_cases(content)
        ids = [json.loads(line)['case_id'] for line in result.split('\n')]
        self.assertEqual(ids, ['LOGIN_001', 'LOGIN_002', 'REGISTER_001'])

    def test_single_width_preserved(self):
        content = _jsonl([
            {'case_id': 'TC-5', 'title': 'A'},
            {'case_id': 'TC-9', 'title': 'B'},
        ])
        result = AIModelService.renumber_test_cases(content)
        ids = [json.loads(line)['case_id'] for line in result.split('\n')]
        self.assertEqual(ids, ['TC-1', 'TC-2'])

    def test_non_numeric_id_unchanged(self):
        content = _jsonl([
            {'case_id': 'CASE-A', 'title': 'A'},
            {'case_id': 'TC-001', 'title': 'B'},
        ])
        result = AIModelService.renumber_test_cases(content)
        ids = [json.loads(line)['case_id'] for line in result.split('\n')]
        self.assertEqual(ids, ['CASE-A', 'TC-001'])

    def test_other_fields_preserved(self):
        content = _jsonl([
            {'case_id': 'TC-007', 'title': '验证中文步骤', 'steps': [{'desc': '步骤一', 'expect': '预期一'}], 'priority': 'P1'},
        ])
        result = AIModelService.renumber_test_cases(content)
        obj = json.loads(result)
        self.assertEqual(obj['case_id'], 'TC-001')
        self.assertEqual(obj['title'], '验证中文步骤')
        self.assertEqual(obj['steps'][0]['desc'], '步骤一')

    def test_non_jsonl_returned_unchanged(self):
        content = '| TC-001 | 登录 |'
        self.assertEqual(AIModelService.renumber_test_cases(content), content)

    def test_empty_unchanged(self):
        self.assertEqual(AIModelService.renumber_test_cases(''), '')

    def test_drops_non_object_json_lines(self):
        """裸 null / 数字 / 字符串等非对象行应被丢弃，而不是原样保留。"""
        content = _jsonl([
            {'case_id': 'TC-001', 'title': 'A'},
            {'case_id': 'TC-003', 'title': 'C'},
        ]) + '\nnull\n42\n"裸字符串"'
        result = AIModelService.renumber_test_cases(content)
        lines = [l for l in result.split('\n') if l.strip()]
        self.assertEqual(len(lines), 2)
        ids = [json.loads(line)['case_id'] for line in lines]
        self.assertEqual(ids, ['TC-001', 'TC-002'])


class FullPipelineTests(SimpleTestCase):
    """fix → sort → renumber 全链路：混乱输出收敛为连续编号的 JSONL。"""

    def test_pipeline_cleans_messy_output(self):
        # 顺序乱、有跳号、末尾带截断行
        content = _jsonl([
            {'case_id': 'TC-003', 'title': 'C'},
            {'case_id': 'TC-001', 'title': 'A'},
        ]) + '\n{"case_id":"TC-002","title":"B","steps":[{"desc":'

        fixed = AIModelService.fix_incomplete_last_case(content)
        sorted_ = AIModelService.sort_test_cases_by_id(fixed)
        renumbered = AIModelService.renumber_test_cases(sorted_)

        ids = [json.loads(line)['case_id'] for line in renumbered.split('\n')]
        titles = [json.loads(line)['title'] for line in renumbered.split('\n')]
        self.assertEqual(ids, ['TC-001', 'TC-002'])
        self.assertEqual(titles, ['A', 'C'])


class ParseTestCasesContentTests(SimpleTestCase):
    """save_to_records 的 JSONL 解析需免疫非对象行（回归：裸 null 行崩 .get）。"""

    def setUp(self):
        self.parser = TestCaseGenerationTaskViewSet()

    def test_skips_non_object_json_lines(self):
        content = ('{"case_id":"TC-001","title":"A","precondition":"","steps":[],"priority":"P1"}\n'
                   'null\n'
                   '42\n'
                   '{"case_id":"TC-002","title":"B","precondition":"","steps":[],"priority":"P2"}\n')
        cases = self.parser._parse_test_cases_content(content)
        self.assertEqual(len(cases), 2)
        self.assertEqual([c['caseId'] for c in cases], ['TC-001', 'TC-002'])

    def test_blank_and_invalid_lines_ignored(self):
        content = '{"case_id":"TC-001","title":"A"}\n\n{bad json\n'
        cases = self.parser._parse_test_cases_content(content)
        self.assertEqual(len(cases), 1)
