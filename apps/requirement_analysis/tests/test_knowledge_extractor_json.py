# -*- coding: utf-8 -*-
"""KnowledgeExtractor JSON 容错解析测试

verify: _parse_json 先标准 json 后 json_repair，截断/缺括号的 LLM 输出也能恢复条目
"""
import asyncio

from django.test import SimpleTestCase

TRUNCATED = '{"entries": [{"name": "模块A", "category": "module", "content": "负责登录与权限管理，包含用户认证、会话管理、角色权限校验等功能。系统支持基于角色的访问控制（RBAC）'
MISSING_BRACKET = '{"entries": [{"name": "A", "category": "module", "content": "内容A"}'


class KnowledgeExtractorJsonTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.requirement_analysis.knowledge_extractor import KnowledgeExtractor
        cls.extractor = KnowledgeExtractor(llm_service=None, embedding_service=None, chunker=None)

    def test_parse_valid_json(self):
        text = '{"entries": [{"name": "A", "category": "module", "content": "内容"}]}'
        result = self.extractor._parse_json(text)
        self.assertEqual(result["entries"][0]["name"], "A")

    def test_parse_truncated_string_recovers_entries(self):
        result = self.extractor._parse_json(TRUNCATED)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["name"], "模块A")
        self.assertEqual(result["entries"][0]["category"], "module")

    def test_parse_missing_bracket_recovers_entries(self):
        result = self.extractor._parse_json(MISSING_BRACKET)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["entries"]), 1)

    def test_parse_markdown_wrapped(self):
        from apps.requirement_analysis.knowledge_extractor import KnowledgeExtractor
        result = self.extractor._parse_json('```json\n{"entries": [{"name": "A", "category": "module", "content": "内容"}]}\n```')
        self.assertEqual(result["entries"][0]["name"], "A")

    def test_section_extract_returns_entries_from_truncated_response(self):
        from types import SimpleNamespace

        async def fake_call(config, messages, max_tokens=None):
            return {"choices": [{"message": {"content": TRUNCATED}}]}

        self.extractor.llm_service = SimpleNamespace(call_openai_compatible_api=fake_call)
        writer_config = SimpleNamespace(max_tokens=4096)

        async def run():
            return await self.extractor._extract_from_section(
                document_type="系统设计文档",
                summary="摘要",
                global_knowledge=["全局知识"],
                section_title="全文",
                section_content="内容",
                existing_entries_summary="暂无",
                writer_config=writer_config,
            )

        entries = asyncio.run(run())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "模块A")

    def test_extract_from_document_reports_progress(self):
        from types import SimpleNamespace

        # 构造一个有两段（无标题→单章节）的文档
        doc = SimpleNamespace(
            name="文档", raw_text="第一段内容。\n\n第二段内容。",
        )
        # 用假 chunker：_split_by_headers 直接返回固定章节
        class FakeSection:
            def __init__(self, title, content):
                self.title = title
                self.content = content
        chunker = SimpleNamespace(
            _split_by_headers=lambda text: [FakeSection("全文", text)],
        )

        async def fake_call(config, messages, max_tokens=None):
            content = '{"entries": [{"name": "条目A", "category": "module", "content": "内容A"}]}'
            return {"choices": [{"message": {"content": content}}]}

        self.extractor.llm_service = SimpleNamespace(call_openai_compatible_api=fake_call)
        self.extractor.embedding_service = SimpleNamespace(
            embed=lambda texts: [[0.1] * 4 for _ in texts],
        )
        self.extractor.chunker = chunker
        writer_config = SimpleNamespace(max_tokens=4096)

        progress = []

        async def on_progress(pct, msg):
            progress.append((pct, msg))

        async def run():
            return await self.extractor.extract_from_document(
                doc, writer_config, progress_callback=on_progress
            )

        entries = asyncio.run(run())
        self.assertEqual(len(entries), 1)
        # 进度应包含：结构分析(5/10)、逐章提取(10~90)、去重(95)
        pcts = [p for p, _ in progress]
        self.assertIn(5, pcts)
        self.assertIn(10, pcts)
        self.assertIn(95, pcts)
        self.assertTrue(all(0 <= p <= 100 for p in pcts))
