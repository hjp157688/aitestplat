"""自动化用例转化与执行的服务层：来源抽取、AI 消息构造、结果解析、变量渲染。

本模块不直接写库（除只读查询），供 automation_tasks / automation_views 调用。
"""
import json
import re

from apps.ai.prompt_registry import get_prompt_content_raw

PLACEHOLDER_RE = re.compile(r'\{\{(\w+)\}\}')


def extract_source_data(source_type, source_obj):
    """从 GeneratedTestCase / testcases.TestCase 抽取统一的转化输入。"""
    if source_type == 'generated':
        return {
            'title': source_obj.title,
            'precondition': source_obj.precondition or '',
            'steps_text': source_obj.test_steps or '',
            'expected_text': source_obj.expected_result or '',
            'priority': source_obj.priority or '',
        }
    # testcase（手动用例）：steps 为 JSON 字符串，预期内嵌在步骤里
    return {
        'title': source_obj.title,
        'precondition': getattr(source_obj, 'preconditions', '') or '',
        'steps_text': source_obj.steps or '',
        'expected_text': '',
        'priority': source_obj.priority or '',
    }


def build_conversion_messages(source_data, variable_keys=None):
    """构造转写请求消息。提示词含裸 JSON 花括号，必须用 raw 版本读取。"""
    system_prompt = get_prompt_content_raw('automation_case_converter')
    variable_keys = [k for k in (variable_keys or []) if k]
    user_message = (
        f"用例标题：{source_data.get('title', '')}\n"
        f"前置条件：{source_data.get('precondition') or '无'}\n"
        f"测试步骤：\n{source_data.get('steps_text') or '无'}\n"
        f"预期结果：{source_data.get('expected_text') or '见步骤描述'}\n\n"
        f"可用环境变量：{', '.join(variable_keys) if variable_keys else '无'}"
    )
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_message},
    ]


def parse_conversion_result(raw_text):
    """解析 AI 返回的步骤 JSON，容忍 ```json 围栏与前后噪声文本。

    返回 [{index, action, verify}]；无有效步骤或非法 JSON 时抛 ValueError，
    由调用方将用例标记为转写失败。
    """
    text = (raw_text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()
    # raw_decode 从每个 '[' 起点尝试解析首个合法 JSON 值，天然忽略数组前后的
    # 噪声文本（AI 常在 JSON 后补解释文字，json.loads 会报 Extra data 失败）。
    decoder = json.JSONDecoder()
    steps = None
    pos = text.find('[')
    while pos != -1 and steps is None:
        try:
            candidate, _end = decoder.raw_decode(text[pos:])
            steps = candidate
        except json.JSONDecodeError:
            pos = text.find('[', pos + 1)
    if steps is None:
        raise ValueError(f'AI 返回内容不是有效的步骤 JSON（原始输出开头：{text[:120]}）')
    if not isinstance(steps, list):
        raise ValueError('AI 返回的步骤不是数组')
    normalized = []
    for index, step in enumerate(steps, start=1):
        step = step or {}
        action = str(step.get('action') or '').strip()
        if not action:
            continue
        normalized.append({
            'index': index,
            'action': action,
            'verify': str(step.get('verify') or '').strip(),
        })
    if not normalized:
        raise ValueError('AI 未返回任何有效步骤')
    return normalized


def build_environment_context(environment):
    """把环境配置展平成 {{key}} -> value 的渲染上下文。"""
    context = {}
    for var in (environment.variables or []):
        key = str((var or {}).get('key') or '').strip()
        if key:
            context[key] = str((var or {}).get('value') or '')
    if environment.base_url:
        context.setdefault('base_url', environment.base_url)
    if environment.username:
        context.setdefault('username', environment.username)
    if environment.password:
        context.setdefault('password', environment.password)
    return context


def render_text(text, context):
    """替换 {{key}} 占位；未知占位保持原样，便于排查配置遗漏。"""
    return PLACEHOLDER_RE.sub(lambda m: str(context.get(m.group(1), m.group(0))), str(text or ''))


def build_case_task_description(case, environment):
    """把自动化用例渲染成 browser-use 的完整任务描述。"""
    context = build_environment_context(environment)
    lines = []
    if case.precondition:
        lines.append(f'前置条件：{render_text(case.precondition, context)}')
    for step in (case.steps or []):
        line = f"{step.get('index')}. {render_text(step.get('action', ''), context)}"
        verify = render_text(step.get('verify') or '', context)
        if verify:
            line += f'\n   完成后验证：{verify}'
        lines.append(line)
    return '\n'.join(lines)


def build_login_task_description(environment):
    """预置登录任务：不写死表单结构，交给 browser-use 自适应。"""
    return (
        f'打开登录页 {environment.login_url}，'
        f'在登录表单中输入用户名 {environment.username}、密码 {environment.password} 并提交，完成登录。'
    )
