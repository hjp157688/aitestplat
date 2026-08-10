# -*- coding: utf-8 -*-
"""AI 生成文本清洗工具：去除 Markdown/HTML 残留，规整用例步骤结构。

AI 产出（writer JSONL 或兼容旧 Markdown 表格）偶尔会夹带这类残留：
- 加粗 `**内容**` / `*内容*` / `__内容__`
- 步骤内的 `<br>` / `<br/>` HTML 换行
- 行首 Markdown 标题 `#`
- HTML 实体 `&#124;`(竖线) / `&nbsp;`

这些残留若直接入库会导致 testcases 模块展示异常（标题两侧带 `**`、
步骤带 `<br>`、每步「预期结果」为空）。本模块在采纳/解析时做兜底清洗。
"""
import re

_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
# 成对强调标记 -> 保留内容
_BOLD_PAIRED = [
    (re.compile(r'\*\*([^*]+?)\*\*', re.S), r'\1'),
    (re.compile(r'__([^_]+?)__', re.S), r'\1'),
    (re.compile(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', re.S), r'\1'),
]
_HEADING_RE = re.compile(r'^#{1,6}\s*')
# 步骤行首序号/符号：1. 1、 -  • *
_STEP_PREFIX_RE = re.compile(r'^\s*(?:\d+[\.\、\)]|[-*•])\s*')

# 期望标签：AI 偶发把期望输出成独立「预期: xxx」步骤，或把「预期:」写进 expect 字段。
# 需要「预期」后跟冒号/空白/结尾，避免误伤「预期测试某功能」这类动作描述。
_EXPECT_LABEL_RE = re.compile(r'^\s*(?:预期结果|预期|期望结果|期望)(?:\s*[:：]|\s+|$)(.*)$', re.S)

_ENTITY_MAP = {
    '&#124;': '|',
    '&#x7c;': '|',
    '&#x7C;': '|',
    '&nbsp;': ' ',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
}


def _unescape(text: str) -> str:
    for key, value in _ENTITY_MAP.items():
        text = text.replace(key, value)
    return text


def clean_text(text) -> str:
    """去除 Markdown/HTML 残留，返回规整后的纯文本。

    `<br>` 先转为换行，再逐行剥离 加粗/行首标题/孤立强调符，最后合并。
    """
    if not text:
        return ''
    raw = str(text).replace('\r\n', '\n').replace('\r', '\n')
    raw = _BR_RE.sub('\n', raw)
    raw = _unescape(raw)
    raw = _HTML_TAG_RE.sub('', raw)

    cleaned_lines = []
    for line in raw.split('\n'):
        s = line
        for pattern, repl in _BOLD_PAIRED:
            s = pattern.sub(repl, s)
        # 兜底：去掉孤立的首尾强调符（如只有单个 *）
        s = s.strip().strip('*').strip('_')
        s = _HEADING_RE.sub('', s).strip()
        if s:
            cleaned_lines.append(s)

    return '\n'.join(cleaned_lines)


def _split_step_lines(desc: str, expect: str = '') -> list:
    """把含换行的步骤文本拆成多个 {desc, expect}，预期挂到最后一步。"""
    lines = [ln.strip() for ln in desc.split('\n') if ln and ln.strip()]
    if len(lines) <= 1:
        return [{'desc': lines[0] if lines else desc, 'expect': expect}]
    steps = []
    total = len(lines)
    for i, line in enumerate(lines):
        step = _STEP_PREFIX_RE.sub('', line).strip()
        if not step:
            continue
        exp = expect if i == total - 1 else ''
        steps.append({'desc': step, 'expect': exp})
    return steps


def _strip_expect_label(text: str) -> str:
    """去掉行首的「预期/预期结果[:： 空间]」标签，返回剩余内容。"""
    m = _EXPECT_LABEL_RE.match(str(text).strip())
    if m:
        return m.group(1).strip()
    return str(text).strip()


def _merge_expected_steps(steps: list) -> list:
    """把「预期: xxx」形式的独立步骤并入上一步的 expect。

    AI 偶发把每条期望输出成独立步骤（desc 以「预期/预期结果」开头、expect 为空），
    而不是挂在对应步骤的 expect 字段。desc 内换行夹带「预期: ...」在 _split_step_lines
    拆分后同样是「预期:」独立步。若直接透传，会出现用户反馈的
    「步骤和预期没有对应、预期挤在步骤里、每步预期为空」。故在此合并：
    - 「预期:」开头的步骤 → 并入上一步 expect（多行追加，不互相覆盖）
    - 首步即是「预期:」时无可并入，保留为独立步骤并去掉标签前缀
    - expect 字段自带「预期:」前缀时，也清理掉前缀
    """
    merged = []
    for step in steps:
        raw = dict(step or {})
        desc = (raw.get('desc') or '').strip()
        expect = (raw.get('expect') or '').strip()

        # 期望标签步：并入上一步的 expect；无上一步时保留为独立步骤（去掉标签前缀）
        if desc and _EXPECT_LABEL_RE.match(desc):
            content = _strip_expect_label(desc)
            if expect:
                content = f"{content}\n{expect}" if content else expect
            if merged:
                prev = merged[-1]
                if prev.get('expect'):
                    prev['expect'] = f"{prev['expect']}\n{content}"
                else:
                    prev['expect'] = content
                continue
            raw['desc'] = content
            raw['expect'] = ''
            merged.append(raw)
            continue

        # 即使 expect 字段本身带了「预期:」前缀也清理掉，避免展示重复标签
        if expect:
            raw['expect'] = _strip_expect_label(expect)
        merged.append(raw)
    return merged


def normalize_steps(raw) -> list:
    """规整 steps 为 [{desc, expect}] 列表。

    - raw 为 list：逐项清洗；若某项 desc 含换行（如 "**1…**<br>**2…**"），
      拆成多步并把该项 expect 挂到最后一步。
    - raw 为 str：先 clean_text，再按行拆成多步（去掉行首序号）。
    - 统一做「预期:」独立步合并，保证步骤与预期一一对应。
    """
    if not raw:
        return []
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, dict):
                desc = clean_text(item.get('desc') or '')
                exp = clean_text(item.get('expect') or '')
                result.extend(_split_step_lines(desc, exp))
            elif isinstance(item, str):
                result.extend(normalize_steps(item))
        return _merge_expected_steps(result)

    if isinstance(raw, str):
        text = clean_text(raw)
        return _merge_expected_steps(_split_step_lines(text, ''))

    return []
