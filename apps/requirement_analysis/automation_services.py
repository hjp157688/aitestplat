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


SUCCESS_TRACE_MAX_CHARS = 2000

# 成功路径记忆里排除的非浏览器动作：不描述页面操作，注入任务描述没有意义
_TRACE_EXCLUDED_ACTIONS = {
    'done', 'mark_task_complete', 'mark_task_failed', 'mark_task_skipped',
    'update_task_status',
}


def format_browser_action(action_dict):
    """把单个 browser-use 动作 dict 格式化成中文短句（沿用执行日志的风格）。"""
    for name, params in (action_dict or {}).items():
        if params is None and name not in ('scroll_down', 'scroll_up', 'wait'):
            continue
        p = params if isinstance(params, dict) else {}
        if name in ('go_to_url', 'navigate'):
            return f"访问: {p.get('url')}"
        if name in ('click_element', 'click'):
            return f"点击[{p.get('index')}]"
        if name in ('input_text', 'input'):
            text = p.get('text')
            return f"输入: '{text}'"
        if name == 'select_dropdown_option':
            return f"选择: {p.get('text')}"
        if name == 'done':
            return '任务完成' if p.get('success') else '任务失败'
        if name in ('scroll_down', 'scroll_up'):
            return '下滚' if name == 'scroll_down' else '上滚'
        if name == 'wait':
            return f"等待 {p.get('seconds', '')}秒".strip()
        if name == 'switch_tab':
            return f"切换标签[{p.get('tab_id')}]"
        if name == 'close_tab':
            return '关闭标签页'
        if name == 'open_new_tab':
            return '新建标签页'
        return f"{name}: {json.dumps(params, ensure_ascii=False)[:80]}"
    return ''


def _iter_history_steps(history):
    """兼容 AgentHistoryList（.history）与普通 list 两种历史形态。"""
    steps = getattr(history, 'history', None)
    if steps is None:
        steps = history if isinstance(history, (list, tuple)) else []
    return steps


def extract_execution_detail(history):
    """把执行历史转成结构化步骤列表，供前端时间线渲染。

    每步：{index, url, title, actions, thinking, evaluation, next_goal,
    error, result, duration}。无 model_output 的步骤（如初始导航）也保留，
    只回填已知字段。
    """
    detail = []
    for i, step in enumerate(_iter_history_steps(history), start=1):
        output = getattr(step, 'model_output', None)
        state = getattr(step, 'state', None)
        metadata = getattr(step, 'metadata', None)
        actions = []
        thinking = evaluation = next_goal = ''
        if output is not None:
            thinking = getattr(output, 'thinking', '') or ''
            evaluation = getattr(output, 'evaluation_previous_goal', '') or ''
            next_goal = getattr(output, 'next_goal', '') or ''
            for action in (getattr(output, 'action', None) or []):
                dump = action.model_dump() if hasattr(action, 'model_dump') else {}
                formatted = format_browser_action(dump)
                if formatted:
                    actions.append(formatted)
        error = ''
        result_text = ''
        for r in (getattr(step, 'result', None) or []):
            error = error or (getattr(r, 'error', None) or '')
            result_text = result_text or (getattr(r, 'extracted_content', None) or '')
        entry = {
            'index': i,
            'url': getattr(state, 'url', '') or '',
            'title': getattr(state, 'title', '') or '',
            'actions': actions,
            'thinking': thinking,
            'evaluation': evaluation,
            'next_goal': next_goal,
            'error': error,
            'result': result_text,
            'duration': getattr(metadata, 'duration_seconds', None),
        }
        detail.append(entry)
    return detail


def extract_success_trace(history):
    """提取成功路径记忆：[{url, actions: [格式化动作]}]，只保留有浏览器动作的步骤。"""
    trace = []
    for step in _iter_history_steps(history):
        output = getattr(step, 'model_output', None)
        if output is None:
            continue
        actions = []
        for action in (getattr(output, 'action', None) or []):
            dump = action.model_dump() if hasattr(action, 'model_dump') else {}
            if not dump or (_TRACE_EXCLUDED_ACTIONS & set(dump.keys())):
                continue
            formatted = format_browser_action(dump)
            if formatted:
                actions.append(formatted)
        if not actions:
            continue
        state = getattr(step, 'state', None)
        trace.append({
            'url': getattr(state, 'url', '') or '',
            'actions': actions,
        })
    return trace


def render_success_trace(trace, max_chars=SUCCESS_TRACE_MAX_CHARS):
    """把成功执行路径渲染成任务描述里的参考文本，超长截断。"""
    lines = []
    for item in (trace or []):
        url = (item.get('url') or '').strip()
        actions = [a for a in (item.get('actions') or []) if a]
        if not url and not actions:
            continue
        prefix = f'  页面 {url}:\n' if url else ''
        lines.append(prefix + '\n'.join(f'    {a}' for a in actions))
    text = '\n'.join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + '\n  （超长截断，仅供参考）'
    return text


def build_case_task_description(case, environment, logged_in=False):
    """把自动化用例渲染成 browser-use 的完整任务描述。

    带上次失败总结（失败后 AI 总结、成功后清除）或成功路径记忆
    （成功后覆盖记录）时，注入对应参考段，帮助 agent 少走弯路。
    logged_in=True（会话级登录已完成）时注入跳过登录指令，避免
    会话登录 + 用例自带登录步骤重复登录。
    """
    context = build_environment_context(environment)
    lines = []
    if logged_in:
        lines.append(
            '注意：当前浏览器已完成登录，无需再登录。若步骤中包含「打开登录页/'
            '输入账号密码/点击登录」之类的登录操作，直接跳过该步骤，'
            '从登录后的主页继续执行后续步骤；不要访问登录页，也不要注销或重复登录。')
    failure_summary = (case.last_failure_summary or '').strip()
    if failure_summary:
        lines.append(f'上次执行失败原因（务必避免重蹈覆辙）：{failure_summary}')
    if case.precondition:
        lines.append(f'前置条件：{render_text(case.precondition, context)}')
    for step in (case.steps or []):
        line = f"{step.get('index')}. {render_text(step.get('action', ''), context)}"
        verify = render_text(step.get('verify') or '', context)
        if verify:
            line += f'\n   完成后验证：{verify}'
        lines.append(line)
    trace_text = render_success_trace(case.success_trace)
    if trace_text:
        lines.append(
            '上次成功执行路径参考（尽量复用同样的元素与操作顺序，元素序号可能变化，'
            '按元素语义定位）：\n' + trace_text)
    return '\n'.join(lines)


def build_login_task_description(environment):
    """预置登录任务：不写死表单结构，交给 browser-use 自适应。

    明确「点可见元素」与「离开登录页才算成功」，避免 agent 点到隐藏的
    同名元素（登录页常见多处「登录」字样）后误判任务完成。
    """
    return (
        f'打开登录页 {environment.login_url}，在登录表单中输入账号 {environment.username}、'
        f'密码 {environment.password}。然后点击页面上【可见的】登录提交元素完成登录'
        f'（如文字为「立即登录」「登录」「Sign in」的按钮或可点击区域；如果某个元素'
        f'点击后页面没有变化，说明它可能是隐藏元素，改点另一个可见的）。'
        f'登录成功的判定标准：页面离开登录页（URL 或界面不再是登录页），进入系统主页。'
        f'提交后等待页面跳转并确认已进入主页，再结束任务；若出现错误提示，如实报告错误内容。'
    )
