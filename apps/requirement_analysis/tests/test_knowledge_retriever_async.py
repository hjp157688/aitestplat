# -*- coding: utf-8 -*-
"""知识检索器异步调用路径测试

verify: 在 async 上下文（视图使用 new_event_loop().run_until_complete 调用）中，
retriever.retrieve() 能安全完成查询向量化并返回结果；
不再因同步 ORM（SynchronousOnlyOperation）或 nest_asyncio 缺失而静默返回空列表。
"""
import asyncio
from unittest import mock

from django.test import SimpleTestCase


FAKE_EMBEDDING = [0.1] * 8


def _raw_results():
    return {
        "ids": [["chunk_g_9_1", "entry_42"]],
        "documents": [["段落内容", "条目内容"]],
        "metadatas": [[
            {
                "type": "chunk",
                "section_title": "第一章",
                "section_content": "第一章全文",
                "paragraph_index": 1,
                "header_level": 1,
                "document_name": "doc.pdf",
                "document_id": 9,
                "project_id": 0,
            },
            {
                "type": "entry",
                "entry_id": 42,
                "entry_name": "业务规则",
                "entry_content": "条目内容",
                "category": "business_rule",
                "project_id": 0,
                "document_name": "doc.pdf",
            },
        ]],
        "distances": [[0.1, 0.2]],
    }


class KnowledgeRetrieverAsyncTests(SimpleTestCase):

    def test_retrieve_in_async_context_returns_results(self):
        from apps.requirement_analysis.knowledge_retriever import KnowledgeRetriever

        fake_vector = mock.Mock()
        fake_vector.search.return_value = _raw_results()

        fake_embedding = mock.Mock()

        async def embed_single_async(text):
            return FAKE_EMBEDDING

        fake_embedding.embed_single_async = embed_single_async

        retriever = KnowledgeRetriever(
            vector_store=fake_vector,
            embedding_service=fake_embedding,
            llm_service=None,
        )

        async def run():
            return await retriever.retrieve(
                query='登录功能需求',
                project_id=None,
                writer_config=None,
                top_k=10,
            )

        results = asyncio.run(run())

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['type'], 'chunk')
        self.assertEqual(results[1]['type'], 'entry')
        fake_vector.search.assert_called_once()
        fake_vector.search.assert_called_with(
            project_id=None,
            query_embedding=FAKE_EMBEDDING,
            top_k=30,
        )

    def test_retrieve_merges_global_and_project_collections(self):
        from apps.requirement_analysis.knowledge_retriever import KnowledgeRetriever

        def fake_search(project_id=None, query_embedding=None, top_k=20):
            if project_id is None:
                return {
                    "ids": [["entry_1"]],
                    "documents": [["全局知识"]],
                    "metadatas": [[{
                        "type": "entry",
                        "entry_id": 1,
                        "entry_name": "全局规则",
                        "entry_content": "全局知识",
                        "category": "business_rule",
                        "project_id": 0,
                        "document_name": "doc.pdf",
                    }]],
                    "distances": [[0.1]],
                }
            return {
                "ids": [["entry_2"]],
                "documents": [["项目知识"]],
                "metadatas": [[{
                    "type": "entry",
                    "entry_id": 2,
                    "entry_name": "项目规则",
                    "entry_content": "项目知识",
                    "category": "module",
                    "project_id": 1,
                    "document_name": "doc.pdf",
                }]],
                "distances": [[0.2]],
            }

        fake_vector = mock.Mock()
        fake_vector.search.side_effect = fake_search
        fake_embedding = mock.Mock()

        async def embed_single_async(text):
            return FAKE_EMBEDDING

        fake_embedding.embed_single_async = embed_single_async

        retriever = KnowledgeRetriever(
            vector_store=fake_vector,
            embedding_service=fake_embedding,
            llm_service=None,
        )

        async def run():
            return await retriever.retrieve(
                query='登录功能需求',
                project_id=1,
                writer_config=None,
                top_k=10,
            )

        results = asyncio.run(run())

        names = {it['name'] for it in results}
        self.assertEqual(names, {'全局规则', '项目规则'})
        # 项目上下文应同时检索全局集合与项目集合
        self.assertEqual(fake_vector.search.call_count, 2)
        searched_projects = {c.kwargs['project_id'] for c in fake_vector.search.call_args_list}
        self.assertEqual(searched_projects, {None, 1})
        for c in fake_vector.search.call_args_list:
            self.assertEqual(c.kwargs['top_k'], 30)
