"""生成内容去重测试：续写机制导致模型重复输出同一条用例，落库前需去重。

根因：AIClient.chat_stream 截断自动续写时，模型常无视"不要重复"指令从中间重新输出，
generated/final 内容里出现逐字节相同的重复行（同一标题 x2/x3）。
"""
import json

from django.test import TestCase

from apps.requirement_analysis.models import AIModelService


def case_line(case_id, title, priority='P1'):
    return ('{"case_id":"%s","title":"%s","precondition":"前置",'
            '"steps":[{"desc":"步骤","expect":"预期"}],"priority":"%s"}'
            % (case_id, title, priority))


class DedupeTestCasesTests(TestCase):
    def test_removes_adjacent_exact_duplicates(self):
        content = '\n'.join([
            case_line('LOGIN_001', '验证登录成功'),
            case_line('LOGIN_001', '验证登录成功'),  # 续写重启导致的紧邻重复
            case_line('LOGIN_002', '验证密码错误'),
        ])
        result = AIModelService.dedupe_test_cases(content)
        titles = [json.loads(l)['title'] for l in result.splitlines() if l.strip()]
        self.assertEqual(titles, ['验证登录成功', '验证密码错误'])

    def test_keeps_first_occurrence_order(self):
        content = '\n'.join([
            case_line('LOGIN_001', 'A'),
            case_line('LOGIN_002', 'B'),
            case_line('LOGIN_001', 'A'),  # 非紧邻的远距离重复（后续续写轮重发）
            case_line('LOGIN_003', 'C'),
        ])
        result = AIModelService.dedupe_test_cases(content)
        titles = [json.loads(l)['title'] for l in result.splitlines() if l.strip()]
        self.assertEqual(titles, ['A', 'B', 'C'])

    def test_keeps_unparseable_lines_untouched(self):
        """非 JSON 行（模型杂文本）原样保留，不做去重判断"""
        content = '这是模型的说明文字\n' + case_line('LOGIN_001', '验证登录')
        result = AIModelService.dedupe_test_cases(content)
        self.assertIn('这是模型的说明文字', result)
        self.assertEqual(len([l for l in result.splitlines() if '"case_id"' in l]), 1)


class RenumberDedupesTests(TestCase):
    """final_test_cases 所有落库路径都经过 renumber_test_cases——去重挂在这里全覆盖"""

    def test_renumber_drops_duplicate_titles(self):
        content = '\n'.join([
            case_line('LOGIN_001', '验证登录成功'),
            case_line('LOGIN_001', '验证登录成功'),
            case_line('LOGIN_002', '验证密码错误'),
            case_line('LOGIN_002', '验证密码错误'),
        ])
        result = AIModelService.renumber_test_cases(content)
        lines = [l for l in result.splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        titles = [json.loads(l)['title'] for l in lines]
        self.assertEqual(titles, ['验证登录成功', '验证密码错误'])

    def test_renumber_still_renumbers_unique_cases(self):
        content = '\n'.join([
            case_line('LOGIN_005', 'A'),
            case_line('LOGIN_009', 'B'),
        ])
        result = AIModelService.renumber_test_cases(content)
        ids = [json.loads(l)['case_id'] for l in result.splitlines()]
        self.assertEqual(ids, ['LOGIN_001', 'LOGIN_002'])
