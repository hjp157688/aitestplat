# -*- coding: utf-8 -*-
"""RAGFlow 知识库引擎 HTTP 客户端(httpx,async)

封装 RAGFlow REST API(/api/v1)基础方法;失败统一抛 RagflowError。
RAGFlow API 响应约定:{"code": 0, "data": {...}}。
"""
import httpx
from django.conf import settings


class RagflowError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"RAGFlow error {code}: {message}")


class RagflowClient:
    """RAGFlow HTTP API 客户端(httpx,async);失败抛 RagflowError"""

    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (base_url or settings.RAGFLOW["BASE_URL"]).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.RAGFLOW["API_KEY"]
        self.timeout = timeout or settings.RAGFLOW["TIMEOUT"]

    async def _request(self, method, path, *, params=None, json=None, files=None) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(method, f"{self.base_url}{path}",
                                        params=params, json=json, files=files, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise RagflowError(body.get("code"), body.get("message", ""))
        return body.get("data") or {}

    async def health(self) -> bool:
        try:
            await self._request("GET", "/api/v1/datasets", params={"page_size": 1})
            return True
        except Exception:
            return False

    async def create_dataset(self, name, embedding_model=""):
        data = await self._request("POST", "/api/v1/datasets", json={
            "name": name,
            "embedding_model": embedding_model or None,
            "chunk_method": "naive",
        })
        # 部分 RAGFlow 版本 dataset 端点返回 list,同文件 upload_document 一致防护
        if isinstance(data, list):
            return (data[0] or {}).get("id") if data else ""
        return data.get("id") or data.get("dataset_id")

    async def list_datasets(self, name=""):
        params = {"page_size": 30}
        if name:
            params["name"] = name
        data = await self._request("GET", "/api/v1/datasets", params=params)
        return data if isinstance(data, list) else (data.get("datasets") or [])

    async def upload_document(self, dataset_id, file_obj, filename):
        files = {"file": (filename, file_obj)}
        data = await self._request(
            "POST", f"/api/v1/datasets/{dataset_id}/documents", files=files)
        docs = data if isinstance(data, list) else (data.get("documents") or [])
        return (docs[0] or {}).get("id") if docs else ""

    async def document_status(self, dataset_id, document_id):
        data = await self._request(
            "GET", f"/api/v1/datasets/{dataset_id}/documents",
            params={"id": document_id, "page_size": 1})
        docs = data if isinstance(data, list) else (data.get("documents") or [])
        return (docs[0] or {}) if docs else {}

    async def delete_documents(self, dataset_id, ids):
        await self._request("DELETE", f"/api/v1/datasets/{dataset_id}/documents",
                            json={"ids": ids})

    # ---- chunk / retrieval ----
    async def ensure_empty_document(self, dataset_id, name):
        data = await self._request(
            "POST", f"/api/v1/datasets/{dataset_id}/documents",
            params={"type": "empty"}, json={"name": name})
        docs = data if isinstance(data, list) else (data.get("documents") or [])
        return (docs[0] or {}).get("id") if docs else ""

    async def add_chunk(self, dataset_id, document_id, content, tag_kwd=None):
        payload = {"content": content}
        if tag_kwd:
            payload["tag_kwd"] = tag_kwd
        data = await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            json=payload)
        return (data.get("chunk") or {}).get("id") or ""

    async def update_chunk(self, dataset_id, document_id, chunk_id, content):
        await self._request(
            "PATCH",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}",
            json={"content": content})

    async def list_chunks(self, dataset_id, document_id):
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            params={"page_size": 100})
        return data.get("chunks") or [] if isinstance(data, dict) else (data or [])

    async def delete_chunks(self, dataset_id, document_id, chunk_ids):
        await self._request(
            "DELETE",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            json={"chunk_ids": chunk_ids})

    async def retrieval(self, dataset_ids, question, top_k,
                        rerank_id="", keyword=True, use_kg=False):
        payload = {
            "question": question, "dataset_ids": dataset_ids, "top_k": top_k,
            "keyword": keyword, "use_kg": use_kg,
        }
        if rerank_id:
            payload["rerank_id"] = rerank_id
        return await self._request("POST", "/api/v1/retrieval", json=payload)


# 模块级单例:按 settings.RAGFLOW 初始化;测试用自定义实例
ragflow_client = RagflowClient()
