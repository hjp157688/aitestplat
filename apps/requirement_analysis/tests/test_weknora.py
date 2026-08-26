# -*- coding: utf-8 -*-
"""WeKnora 接入单元测试：配置单例行、客户端工具调用/SSE 解析、项目绑定 API upsert"""
import json
import unittest
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model

from apps.projects.models import Project
from apps.requirement_analysis.models import WeKnoraConfig, WeKnoraProjectBinding
from apps.requirement_analysis.weknora_client import WeKnoraClient


class FakeResp:
    """模拟 httpx 响应的最小桩"""

    def __init__(self, status_code=200, body=None, stream_lines=()):
        self.status_code = status_code
        self._body = body
        self._stream_lines = list(stream_lines)

    def json(self):
        return self._body

    def read(self):
        if isinstance(self._body, (dict, list)):
            return json.dumps(self._body).encode()
        return str(self._body or "").encode()

    def iter_lines(self):
        return iter(self._stream_lines)


class FakeStreamClient:
    """模拟 httpx.Client --- stream() 上下文管理器"""

    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, method, url, **kwargs):
        return _StreamCtx(self._resp)

    # 普通请求(list_agents / create_session)
    def request(self, method, url, **kwargs):
        return self._resp


class _StreamCtx:
    def __init__(self, resp):
        self.resp = resp

    def __enter__(self):
        return self.resp

    def __exit__(self, *a):
        return False


def _sse(*events):
    """把事件 dict 组装成 SSE data 行"""
    lines = []
    for evt in events:
        lines.append(f"data: {json.dumps(evt, ensure_ascii=False)}")
    return lines


class WeKnoraConfigTest(TestCase):
    def test_get_solo_singleton(self):
        cfg = WeKnoraConfig.get_solo()
        self.assertEqual(cfg.pk, 1)
        # 二次取到同一行
        again = WeKnoraConfig.get_solo()
        self.assertEqual(again.pk, 1)

    def test_updated_matches(self):
        cfg = WeKnoraConfig.get_solo()
        cfg.base_url = "http://kb.test:8080"
        cfg.enabled = True
        cfg.save()
        self.assertEqual(WeKnoraConfig.get_solo().base_url, "http://kb.test:8080")

    def test_field_defaults(self):
        cfg = WeKnoraConfig.get_solo()
        self.assertEqual(cfg.base_url, "http://localhost:8080")
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.knowledge_base_ids, [])


class WeKnoraClientTest(unittest.TestCase):
    def test_agent_answer_aggregates_sse(self):
        events = [
            {"id": "r1", "response_type": "thinking", "content": "先检索登录相关文档", "done": False},
            {"id": "r1", "response_type": "tool_call", "content": "", "done": False,
             "data": {"tool_name": "web_search", "arguments": {"query": "登录"}}},
            {"id": "r1", "response_type": "references", "content": "", "done": False,
             "knowledge_references": [
                 {"id": "chunk-1", "knowledge_title": "登录指南", "knowledge_filename": "login.md",
                  "chunk_index": 3, "score": 0.95},
                 {"id": "chunk-2", "knowledge_title": "权限说明", "knowledge_filename": "perm.pdf",
                  "chunk_index": 0, "score": 0.88},
             ]},
            {"id": "r1", "response_type": "answer", "content": "答案", "done": False},
            {"id": "r1", "response_type": "answer", "content": "片段二", "done": False},
            {"id": "r1", "response_type": "answer", "content": "", "done": True},
        ]
        resp = FakeResp(200, body={"success": True}, stream_lines=_sse(*events))
        client = WeKnoraClient("http://kb.test", "sk-1", 30)
        with mock.patch.object(client, "create_session", return_value="sess-1"), \
             mock.patch("apps.requirement_analysis.weknora_client.httpx.Client",
                        return_value=FakeStreamClient(resp)):
            result = client.agent_answer("q", "agent-a", ["kb-1"])
        self.assertEqual(result["answer"], "答案片段二")
        self.assertEqual(len(result["references"]), 2)
        self.assertEqual(result["references"][0]["filename"], "login.md")
        self.assertEqual(result["references"][0]["title"], "登录指南")
        # 思考过程：thinking + tool_call（references/answer 不进 steps）
        kinds = [s["type"] for s in result["steps"]]
        self.assertEqual(kinds, ["thinking", "tool_call"])
        self.assertEqual(result["steps"][1]["name"], "web_search")

    def test_agent_answer_dedups_references(self):
        events = [
            {"id": "r1", "response_type": "references", "content": "", "done": False,
             "knowledge_references": [{"id": "c1", "knowledge_filename": "a.pdf", "score": 0.9}]},
            {"id": "r1", "response_type": "references", "content": "", "done": False,
             "knowledge_references": [{"id": "c1", "knowledge_filename": "a.pdf", "score": 0.9}]},
            {"id": "r1", "response_type": "answer", "content": "ok", "done": True},
        ]
        resp = FakeResp(200, body={"success": True}, stream_lines=_sse(*events))
        client = WeKnoraClient("http://kb.test", "sk-1")
        with mock.patch.object(client, "create_session", return_value="sess-1"), \
             mock.patch("apps.requirement_analysis.weknora_client.httpx.Client",
                        return_value=FakeStreamClient(resp)):
            result = client.agent_answer("q", "agent-a")
        self.assertEqual(len(result["references"]), 1)

    def test_agent_answer_empty_for_no_answer_event(self):
        events = [{"id": "r1", "response_type": "references", "content": "", "done": False}]
        resp = FakeResp(200, body={"success": True}, stream_lines=_sse(*events))
        client = WeKnoraClient("http://kb.test", "sk-1")
        with mock.patch.object(client, "create_session", return_value="sess-1"), \
             mock.patch("apps.requirement_analysis.weknora_client.httpx.Client",
                        return_value=FakeStreamClient(resp)):
            result = client.agent_answer("q", "agent-a")
        self.assertEqual(result["answer"], "")
        self.assertEqual(result["references"], [])

    def test_agent_answer_error_status_raises(self):
        resp = FakeResp(
            403,
            body={"success": False, "error": {"code": 1001, "message": "Unauthorized"}},
            stream_lines=[],
        )
        client = WeKnoraClient("http://kb.test", "bad-key")
        with mock.patch.object(client, "create_session", return_value="sess-1"), \
             mock.patch("apps.requirement_analysis.weknora_client.httpx.Client",
                        return_value=FakeStreamClient(resp)):
            with self.assertRaises(Exception):
                client.agent_answer("q", "agent-a")

    def test_list_agents(self):
        resp = FakeResp(200, body={
            "success": True,
            "data": [
                {"id": "builtin-quick-answer", "name": "快速问答", "is_builtin": True},
                {"id": "abc", "name": "我的智能体", "is_builtin": False},
            ],
        })
        client = WeKnoraClient("http://kb.test", "sk-1")
        with mock.patch("apps.requirement_analysis.weknora_client.httpx.Client",
                        return_value=FakeStreamClient(resp)):
            agents = client.list_agents()
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0]["id"], "builtin-quick-answer")


class WeKnoraProjectBindingAPITest(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_superuser(username="su", password="x")
        self.p = Project.objects.create(name="P", owner=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_binding_create_and_upsert(self):
        url = "/api/requirement-analysis/weknora-bindings/"
        r1 = self.client.post(url, {
            "project": self.p.id, "agent_id": "a1", "agent_name": "智能体1", "enabled": True,
        }, format="json")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(WeKnoraProjectBinding.objects.count(), 1)

        # 同一项目再次创建 → upsert，不新增行
        r2 = self.client.post(url, {
            "project": self.p.id, "agent_id": "a2", "agent_name": "智能体2", "enabled": True,
        }, format="json")
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(WeKnoraProjectBinding.objects.count(), 1)
        self.assertEqual(WeKnoraProjectBinding.objects.get(project=self.p).agent_id, "a2")

    def test_list_filter_by_project(self):
        WeKnoraProjectBinding.objects.create(
            project=self.p, agent_id="a1", enabled=True)
        r = self.client.get(f"/api/requirement-analysis/weknora-bindings/?project={self.p.id}")
        self.assertEqual(r.status_code, 200)
        data = r.data.get("results", r.data) if isinstance(r.data, dict) else r.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["agent_id"], "a1")
