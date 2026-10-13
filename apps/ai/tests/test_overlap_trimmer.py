"""续写轮重叠裁剪测试（纯逻辑，不涉及 HTTP）

根因：chat_stream 截断自动续写时，模型常无视"不要重复"指令从中间重发已有内容，
逐字节一致 → 重叠部分在放行前应被裁掉（callback/yield 都只放行裁剪后内容）。
"""
from django.test import TestCase

from apps.ai.client import _OverlapTrimmer


class OverlapTrimmerTests(TestCase):
    def test_first_round_is_pass_through(self):
        """无前文（首轮不应构造 trimmer，但空前文也不丢内容）"""
        t = _OverlapTrimmer('')
        out = ''.join(t.feed(c) for c in '全新的输出内容' * 30)
        out += t.flush()
        self.assertEqual(out, '全新的输出内容' * 30)

    def test_clean_continuation_passes_through(self):
        """干净续写（无重叠）：缓冲超限后整体放行，内容无损"""
        prev = '已有内容' * 100
        t = _OverlapTrimmer(prev)
        new_text = '这是真正的续写内容' * 30  # 与前文无重叠
        out = ''.join(t.feed(c) for c in new_text)
        out += t.flush()
        self.assertEqual(out, new_text)

    def test_overlap_at_tail_is_trimmed(self):
        """模型从末尾附近重发（典型续写重启）：重叠部分被裁掉，只放行新内容"""
        prev = ''.join(f'第{i}句前文内容各不相同' for i in range(20))
        overlap = prev[-80:]  # 重发末尾 80 字符
        t = _OverlapTrimmer(prev)
        round_content = overlap + '真正的新内容' * 5
        out = ''.join(t.feed(c) for c in round_content)
        out += t.flush()
        self.assertEqual(out, '真正的新内容' * 5)
        self.assertEqual(t.emitted, prev + '真正的新内容' * 5)

    def test_restart_from_early_position_long_overlap(self):
        """重启点在很早位置：跨 chunk 的长重叠也要裁干净"""
        prev = ''.join(f'段落{i}，' for i in range(50)) + 'B' * 20
        t = _OverlapTrimmer(prev)
        head = prev[:len(prev) - 20]  # 重发到接近末尾的位置
        round_content = head + 'TAIL'
        out = ''.join(t.feed(c) for c in round_content)
        out += t.flush()
        self.assertEqual(out, 'TAIL')

    def test_chunked_overlap_across_many_chunks(self):
        """重叠跨越多个 chunk（每个 chunk 5 字符）也能正确跳过"""
        prev = ''.join(f'句子{i}的内容，' for i in range(40))
        t = _OverlapTrimmer(prev)
        overlap = prev[-120:]
        round_content = overlap + 'NEW'
        out = ''.join(t.feed(round_content[i:i + 5]) for i in range(0, len(round_content), 5))
        out += t.flush()
        self.assertEqual(out, 'NEW')

    def test_short_round_flushed_entirely(self):
        """续写轮总长不足锚点长度：flush 时整体放行，不丢内容"""
        prev = '已有内容' * 50
        t = _OverlapTrimmer(prev)
        out = ''.join(t.feed(c) for c in '短')
        out += t.flush()
        self.assertEqual(out, '短')
