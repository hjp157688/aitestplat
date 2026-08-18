# -*- coding: utf-8 -*-
"""RagflowClient 基础方法测试(RAGFlow 知识库引擎迁移)

mock httpx.AsyncClient,断言真实行为:URL/HTTP 方法/Authorization header/
payload/错误码抛 RagflowError。按 Step 4 注:mock 模式适配真实实现 ——
「_request 内 async with httpx.AsyncClient() + client.request(method, ...)」,
故 mock async 上下文管理器返回的 client、并把 request 返回 fake response。
"""
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import SimpleTestCase
from apps.requirement_analysis.ragflow_client import RagflowClient, RagflowError


def fake_response(payload=None):
    # httpx.Response 的 json()/raise_for_status() 是同步方法(仅 client.request 是 awaitable)
    r = MagicMock()
    r.json.return_value = payload or {"code": 0, "data": {}}
    return r


def fake_client(payload=None):
    """async 上下文管理器 AsyncClient:enter 出自身,request 返回 fake response"""
    m = AsyncMock()
    m.request = AsyncMock(return_value=fake_response(payload))
    m.__aenter__.return_value = m
    return m


class RagflowClientTest(SimpleTestCase):
    def setUp(self):
        self.c = RagflowClient(base_url="http://rf:9380", api_key="k", timeout=5)

    # ---- health ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_health_ok(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 0, "data": {"datasets": []}})
        self.assertTrue(self._run(self.c.health()))
        args, _ = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "http://rf:9380/api/v1/datasets")

    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_health_down_on_error_code(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 102, "message": "down"})
        self.assertFalse(self._run(self.c.health()))

    # ---- create_dataset ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_create_dataset_returns_id(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 0, "data": {"id": "ds_1"}})
        did = self._run(self.c.create_dataset("aitestplat_global"))
        self.assertEqual(did, "ds_1")
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/v1/datasets", args[1])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k")
        self.assertEqual(kwargs["json"]["name"], "aitestplat_global")
        self.assertIsNone(kwargs["json"]["embedding_model"])
        self.assertEqual(kwargs["json"]["chunk_method"], "naive")

    # ---- list_datasets ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_list_datasets_default_and_filtered(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"datasets": [{"id": "ds_1", "name": "x"}]}})
        rows = self._run(self.c.list_datasets())
        self.assertEqual(rows[0]["id"], "ds_1")
        ClientCls.return_value.request.reset_mock()
        self._run(self.c.list_datasets(name="kb"))
        _, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(kwargs["params"]["page_size"], 30)
        self.assertEqual(kwargs["params"]["name"], "kb")

    # ---- upload_document ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_upload_document_returns_id(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"documents": [{"id": "doc_1"}]}})
        fid = self._run(self.c.upload_document(
            "ds_1", file_obj=b"hello", filename="a.md"))
        self.assertEqual(fid, "doc_1")
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/v1/datasets/ds_1/documents", args[1])
        self.assertEqual(kwargs["files"]["file"][0], "a.md")
        self.assertEqual(kwargs["files"]["file"][1], b"hello")

    # ---- document_status ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_document_status_returns_run_fields(self, ClientCls):
        doc = {"id": "doc_1", "run": "DONE", "progress": 1.0, "chunk_count": 3}
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"documents": [doc]}})
        result = self._run(self.c.document_status("ds_1", "doc_1"))
        self.assertEqual(result["run"], "DONE")
        self.assertEqual(result["chunk_count"], 3)
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn("/api/v1/datasets/ds_1/documents", args[1])
        self.assertEqual(kwargs["params"]["id"], "doc_1")

    # ---- delete_documents ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_delete_documents_sends_ids(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 0})
        self._run(self.c.delete_documents("ds_1", ["doc_1", "doc_2"]))
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "DELETE")
        self.assertEqual(kwargs["json"]["ids"], ["doc_1", "doc_2"])

    # ---- ensure_empty_document ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_ensure_empty_document_returns_id(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"documents": [{"id": "d1"}]}})
        did = self._run(self.c.ensure_empty_document("ds1", "empty_bot"))
        self.assertEqual(did, "d1")
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/v1/datasets/ds1/documents", args[1])
        self.assertEqual(kwargs["params"]["type"], "empty")
        self.assertEqual(kwargs["json"]["name"], "empty_bot")

    # ---- add_chunk ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_add_chunk_sends_tag(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"chunk": {"id": "c1"}}})
        cid = self._run(self.c.add_chunk(
            "ds1", "doc1", "内容", tag_kwd=["entry", "business_rule"]))
        self.assertEqual(cid, "c1")
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/v1/datasets/ds1/documents/doc1/chunks", args[1])
        self.assertEqual(kwargs["json"]["content"], "内容")
        self.assertEqual(kwargs["json"]["tag_kwd"], ["entry", "business_rule"])

    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_add_chunk_omits_tag_when_none(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"chunk": {"id": "c2"}}})
        self._run(self.c.add_chunk("ds1", "doc1", "内容"))
        _, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(kwargs["json"]["content"], "内容")
        self.assertNotIn("tag_kwd", kwargs["json"])

    # ---- update_chunk ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_update_chunk_sends_content(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 0})
        self._run(self.c.update_chunk("ds1", "doc1", "c1", "新内容"))
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "PATCH")
        self.assertIn("/api/v1/datasets/ds1/documents/doc1/chunks/c1", args[1])
        self.assertEqual(kwargs["json"]["content"], "新内容")

    # ---- list_chunks ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_list_chunks_returns_list(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"chunks": [{"id": "c1", "content": "x"}]}})
        rows = self._run(self.c.list_chunks("ds1", "doc1"))
        self.assertEqual(rows[0]["id"], "c1")
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn("/api/v1/datasets/ds1/documents/doc1/chunks", args[1])
        self.assertEqual(kwargs["params"]["page_size"], 100)

    # ---- delete_chunks ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_delete_chunks_sends_ids(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 0})
        self._run(self.c.delete_chunks("ds1", "doc1", ["c1", "c2"]))
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "DELETE")
        self.assertIn("/api/v1/datasets/ds1/documents/doc1/chunks", args[1])
        self.assertEqual(kwargs["json"]["chunk_ids"], ["c1", "c2"])

    # ---- retrieval ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_retrieval_payload(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"chunks": [{"id": "c1"}]}})
        data = self._run(self.c.retrieval(
            ["g", "p"], "问题", top_k=10, rerank_id="r1", use_kg=True))
        self.assertEqual(data["chunks"], [{"id": "c1"}])
        args, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/api/v1/retrieval", args[1])
        self.assertEqual(kwargs["json"]["question"], "问题")
        self.assertEqual(kwargs["json"]["dataset_ids"], ["g", "p"])
        self.assertEqual(kwargs["json"]["top_k"], 10)
        self.assertTrue(kwargs["json"]["keyword"])
        self.assertTrue(kwargs["json"]["use_kg"])
        self.assertEqual(kwargs["json"]["rerank_id"], "r1")

    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_retrieval_omits_rerank_when_empty(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": {"chunks": []}})
        self._run(self.c.retrieval(["g"], "q", top_k=5))
        _, kwargs = ClientCls.return_value.request.call_args
        self.assertEqual(kwargs["json"]["keyword"], True)
        self.assertFalse(kwargs["json"]["use_kg"])
        self.assertNotIn("rerank_id", kwargs["json"])

    # ---- create_dataset list 防护(裁定) ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_create_dataset_list_guard(self, ClientCls):
        ClientCls.return_value = fake_client(
            {"code": 0, "data": [{"id": "ds_1", "name": "x"}]})
        did = self._run(self.c.create_dataset("aitestplat_global"))
        self.assertEqual(did, "ds_1")

    # ---- 错误语义 ----
    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_error_code_raises(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 102, "message": "bad"})
        with self.assertRaises(RagflowError):
            self._run(self.c.create_dataset("x"))

    @patch("apps.requirement_analysis.ragflow_client.httpx.AsyncClient")
    def test_error_code_message_contains_code(self, ClientCls):
        ClientCls.return_value = fake_client({"code": 102, "message": "bad"})
        with self.assertRaises(RagflowError) as ctx:
            self._run(self.c.create_dataset("x"))
        self.assertEqual(ctx.exception.code, 102)
        self.assertIn("102", str(ctx.exception))

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)
