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


def normalize_steps(raw) -> list:
    """规整 steps 为 [{desc, expect}] 列表。

    - raw 为 list：逐项清洗；若某项 desc 含换行（如 "**1…**<br>**2…**"），
      拆成多步并把该项 expect 挂到最后一步。
    - raw 为 str：先 clean_text，再按行拆成多步（去掉行首序号）。
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
        return result

    if isinstance(raw, str):
        text = clean_text(raw)
        return _split_step_lines(text, '')

    return []
