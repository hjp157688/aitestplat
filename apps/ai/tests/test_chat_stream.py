# -*- coding: utf-8 -*-
"""AIClient.chat_stream 单元测试：

- provider_extra 透传进请求体（api_version 保留为 URL/头专用，不进 body）
- delta.reasoning / reasoning_content 识别为思考内容，不计入正文输出
- 零可见输出 + finish_reason='length' 快速报错（不再盲目续写 MAX_CONTINUATIONS 次）
- 有可见输出 + finish_reason='length' 仍走自动续写
"""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from apps.ai.client import AIClient


def _sse(delta=None, finish_reason=None):
    """构造一行 OpenAI 兼容 SSE data。"""
    chunk = {'choices': [{'delta': delta or {}, 'finish_reason': finish_reason}]}
    return 'data: ' + json.dumps(chunk, ensure_ascii=False)


class FakeAsyncStreamResp:
    def __init__(self, lines, status_code=200):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b'{"error": "stub"}'


class _FakeStreamCtx:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, *a):
        return False


class FakeAsyncClient:
    """记录每次 stream() 收到的 url/json body，按类级响应队列依次返回。"""

    resp_queue = []
    captured_requests = []
    captured_urls = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, headers=None, json=None):
        FakeAsyncClient.captured_requests.append(json)
        FakeAsyncClient.captured_urls.append(url)
        resp = (FakeAsyncClient.resp_queue.pop(0)
                if FakeAsyncClient.resp_queue
                else FakeAsyncStreamResp(['data: [DONE]']))
        return _FakeStreamCtx(resp)


def _make_config(provider_extra=None, max_tokens=4096):
    return SimpleNamespace(
        model_type='other', model_name='glm-5.3-flash-openai',
        base_url='http://stub/v1', api_key='sk-stub', role='reviewer',
        max_tokens=max_tokens, temperature=0.7, top_p=0.9,
        provider_extra=provider_extra or {},
    )


def _run_stream(config, resp_queue):
    """跑 chat_stream，返回 (chunks, callback_received)。"""
    FakeAsyncClient.resp_queue = list(resp_queue)
    FakeAsyncClient.captured_requests = []
    FakeAsyncClient.captured_urls = []
    received = []

    async def callback(text):
        received.append(text)

    async def collect():
        out = []
        gen = AIClient.chat_stream(config, [{'role': 'user', 'content': 'hi'}],
                                   callback=callback)
        async for chunk in gen:
            out.append(chunk)
        return out

    return asyncio.run(collect()), received


@mock.patch.object(AIClient, '_emit')
@mock.patch('apps.ai.client.httpx.AsyncClient', FakeAsyncClient)
class ChatStreamTest(unittest.TestCase):
    def test_max_tokens_falsy_omitted_from_body(self, *_):
        """max_tokens 为 None/0（不限制）时：请求体不含 max_tokens 键，由服务端按模型上限。"""
        for unlimited in (None, 0):
            cfg = _make_config(max_tokens=unlimited)
            chunks, _ = _run_stream(cfg, [FakeAsyncStreamResp([_sse({'content': 'ok'}), 'data: [DONE]'])])
            self.assertEqual(chunks, ['ok'])
            self.assertNotIn('max_tokens', FakeAsyncClient.captured_requests[0])

    def test_max_tokens_set_included_in_body(self, *_):
        """max_tokens 有值时照常进请求体。"""
        cfg = _make_config(max_tokens=123)
        _run_stream(cfg, [FakeAsyncStreamResp([_sse({'content': 'hi'}), 'data: [DONE]'])])
        self.assertEqual(FakeAsyncClient.captured_requests[0]['max_tokens'], 123)

    def test_provider_extra_merged_into_body(self, *_):
        """provider_extra 扩展参数应进入请求体；api_version 除外（Azure 专用，不进 body）。"""
        cfg = _make_config(provider_extra={
            'chat_template_kwargs': {'enable_thinking': False},
            'api_version': '2024-06-01',
        })
        chunks, _ = _run_stream(cfg, [FakeAsyncStreamResp([_sse({'content': '你好'}), 'data: [DONE]'])])
        self.assertEqual(chunks, ['你好'])
        body = FakeAsyncClient.captured_requests[0]
        self.assertEqual(body['chat_template_kwargs'], {'enable_thinking': False})
        self.assertNotIn('api_version', body)

    def test_reasoning_delta_not_treated_as_content(self, *_):
        """delta.reasoning / reasoning_content 是思考内容，不得 yield、不得进回调。"""
        cfg = _make_config()
        lines = [
            _sse({'role': 'assistant', 'content': ''}),
            _sse({'reasoning': '让我想想'}),
            _sse({'reasoning_content': '再想想'}),
            _sse({'content': '你好'}),
            _sse({}, finish_reason='stop'),
            'data: [DONE]',
        ]
        chunks, received = _run_stream(cfg, [FakeAsyncStreamResp(lines)])
        self.assertEqual(chunks, ['你好'])
        self.assertEqual(received, ['你好'])

    def test_zero_content_length_fails_fast(self, *_):
        """预算全耗在思考上、零可见输出时：只发一次请求，抛出含指引的错误，不盲目续写。"""
        cfg = _make_config(max_tokens=4096)
        lines = [
            _sse({'content': ''}),
            _sse({'reasoning': '思考'}),
            _sse({}, finish_reason='length'),
        ]
        with self.assertRaises(Exception) as ctx:
            _run_stream(cfg, [FakeAsyncStreamResp(lines)])
        self.assertIn('4096', str(ctx.exception))
        self.assertEqual(len(FakeAsyncClient.captured_requests), 1)

    def test_length_with_content_still_continues(self, *_):
        """有可见输出 + finish_reason='length'：保留既有自动续写语义（第二次请求）。"""
        cfg = _make_config()
        first = FakeAsyncStreamResp([_sse({'content': '第一段'}), _sse({}, finish_reason='length')])
        second = FakeAsyncStreamResp([_sse({'content': '第二段'}), _sse({}, finish_reason='stop')])
        chunks, _ = _run_stream(cfg, [first, second])
        self.assertEqual(chunks, ['第一段', '第二段'])
        second_body = FakeAsyncClient.captured_requests[1]
        self.assertEqual(second_body['messages'][-1]['role'], 'user')
        self.assertIn('继续', second_body['messages'][-1]['content'])


if __name__ == '__main__':
    unittest.main()
