# apps/api_testing/tests/test_generation_json.py
"""ApiTestCaseGenerator AI JSON 解析容错单元测试

解析采用：标准 json.loads（strict=False）快速路径 + json_repair 兜底，
覆盖 LLM 输出的常见不规范 JSON：
- 包裹在 ```json 代码块中 / 前后带解释性文字
- 值里出现 Python 重复表达式（"a".repeat(1000) / "a" * 3）→ json_repair 归一化
- 对象/数组末尾多余逗号
- 字符串里出现字面控制字符
- 截断/缺括号 → json_repair 可恢复
- 完全非 JSON 的响应应返回 None
"""
from django.test import SimpleTestCase

from apps.api_testing.services import _safe_json_loads


class SafeJsonLoadsTests(SimpleTestCase):

    def test_fenced_clean_json(self):
        content = '说明如下：\n```json\n{"test_cases": {"270": [{"name": "正向"}]}}\n```\n以上供参考。'
        result = _safe_json_loads(content)
        self.assertEqual(result['test_cases']['270'][0]['name'], '正向')

    def test_json_with_trailing_prose(self):
        content = '{"test_cases": {"270": [{"name": "a"}]}} 以上是生成的用例。'
        result = _safe_json_loads(content)
        self.assertIn('270', result['test_cases'])

    def test_python_repeat_expression(self):
        content = '{"test_cases": {"270": [{"name": "边界", "body_override": {"username": "a".repeat(1000)}}]}}'
        result = _safe_json_loads(content)
        value = result['test_cases']['270'][0]['body_override']['username']
        self.assertIsInstance(value, str)
        self.assertTrue(value)  # json_repair 归一化后保留可用的字符串值

    def test_star_repeat_and_trailing_comma(self):
        content = '{"test_cases": {"270": [{"name": "x", "params_override": {"k": "z" * 5},},]}}'
        result = _safe_json_loads(content)
        self.assertEqual(result['test_cases']['270'][0]['params_override']['k'], 'z')

    def test_literal_control_char_in_string(self):
        content = '{"test_cases": {"270": [{"name": "line1\nline2", "assertions": []}]}}'
        result = _safe_json_loads(content)
        self.assertEqual(result['test_cases']['270'][0]['name'], 'line1\nline2')

    def test_truncated_json_recovers(self):
        content = '{"test_cases": {"270": [{"name": "unfinished", "params_override": {"a": "b"}}'
        result = _safe_json_loads(content)
        self.assertEqual(result['test_cases']['270'][0]['name'], 'unfinished')

    def test_garbage_returns_none(self):
        self.assertIsNone(_safe_json_loads('对不起，我无法生成。'))
        self.assertIsNone(_safe_json_loads(''))
