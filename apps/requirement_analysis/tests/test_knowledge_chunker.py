# -*- coding: utf-8 -*-
"""KnowledgeChunker 语义分块测试

verify: 注入 embedding_model 时走 SemanticChunker 语义分块；
无模型或模型异常时回退到段落拆分。
"""
import math

from django.test import SimpleTestCase


class _FakeEmbeddings:
    """返回确定性的伪向量，供 SemanticChunker 计算语义边界"""

    def __init__(self, dim=8, noise=0.5):
        self.dim = dim
        self.noise = noise

    def _vec(self, text):
        # 基于文本 hash 的确定性向量
        h = 0
        for ch in text:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        base = [(h >> (i * 3)) % 257 / 257.0 for i in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in base)) or 1.0
        return [v / norm for v in base]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class _BrokenEmbeddings:
    """semantic 分块必然失败的模型，用于验证回退"""

    def embed_documents(self, texts):
        raise RuntimeError('embedding API down')


class KnowledgeChunkerSemanticTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.requirement_analysis.knowledge_chunker import KnowledgeChunker
        cls.KnowledgeChunker = KnowledgeChunker

    def test_paragraph_fallback_without_embedding_model(self):
        text = ('第一段内容。' * 10 + '\n\n' + '第二段内容。' * 10)
        chunker = self.KnowledgeChunker()
        sections = chunker.chunk(text)
        self.assertEqual(len(sections), 1)
        self.assertTrue(len(sections[0].paragraphs) >= 2)

    def test_semantic_split_with_embedding_model(self):
        # 两段差异明显的文本，注入可用的 embedding 模型
        text = ('模块A负责登录与权限管理。' * 20 + '\n\n' + '模块B负责报表与数据分析。' * 20)
        chunker = self.KnowledgeChunker(embedding_model=_FakeEmbeddings())
        sections = chunker.chunk(text)
        self.assertEqual(len(sections), 1)
        self.assertGreater(len(sections[0].paragraphs), 0)

    def test_breaks_at_paragraphs_when_semantic_splitting_fails(self):
        # SemanticChunker 内部会吞掉 embedding 异常，这里直接让 create_documents 抛错
        import langchain_experimental.text_splitter as ts
        from unittest import mock

        text = ('第一段内容。' * 10 + '\n\n' + '第二段内容。' * 10)
        chunker = self.KnowledgeChunker(embedding_model=_BrokenEmbeddings())
        with mock.patch.object(
            ts.SemanticChunker, 'create_documents', side_effect=RuntimeError('boom')
        ):
            sections = chunker.chunk(text)
        # 语义分块失败时应回退到段落拆分，不抛异常
        self.assertEqual(len(sections), 1)
        self.assertTrue(len(sections[0].paragraphs) >= 2)

    def test_header_split_ignores_embedding(self):
        text = '# 总标题\n\n## 子章节一\n\n内容甲。' * 5 + '\n\n## 子章节二\n\n内容乙。' * 5
        chunker = self.KnowledgeChunker(embedding_model=_FakeEmbeddings())
        sections = chunker.chunk(text)
        self.assertGreaterEqual(len(sections), 2)
