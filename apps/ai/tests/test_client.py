# -*- coding: utf-8 -*-
"""apps.ai 客户端——HTTP 调用与可观测落库测试（全部走 mock，不发真实请求）。"""

import asyncio
import json
from unittest import mock

import httpx
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai.client import AIClient
from apps.ai.models import AiCallRecord
from apps.ai.observability import set_scenario, reset_scenario
from apps.requirement_analysis.models import AIModelConfig

User = get_user_model()


class _FakeResponse:
    def __init__(self, status_code=200, text='', payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                'error', request=mock.Mock(), response=mock.Mock(status_code=self.status_code,
                                                                text=self.text))
        return None

    def json(self):
        return self._payload

    async def aread(self):
        return self.text.encode('utf-8')


class _FakeAsyncClient:
    """模拟 httpx.AsyncClient（上下文管理器 + post/get）。"""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        if self.exc:
            raise self.exc
        return self.response

    async def get(self, url, headers=None):
        if self.exc:
            raise self.exc
        return self.response


def _sse_line(obj):
    return f"data: {json.dumps(obj)}"


class ClientEmitTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='eve', password='x')
        self.config = AIModelConfig.objects.create(
            name='cfg', model_type='deepseek', role='writer', api_key='sk-x',
            base_url='https://api.deepseek.com', model_name='deepseek-chat',
            max_tokens=4096, temperature=0.7, top_p=0.9,
            is_active=True, created_by=self.user)

    def test_chat_success_emits_record_with_tokens(self):
        payload = {
            'choices': [{'message': {'content': 'ok'}}],
            'usage': {'prompt_tokens': 11, 'completion_tokens': 22, 'total_tokens': 33},
        }
        with mock.patch('apps.ai.client.httpx.AsyncClient',
                        return_value=_FakeAsyncClient(response=_FakeResponse(payload=payload))):
            result = asyncio.run(AIClient.chat(self.config, [{'role': 'user', 'content': 'hi'}]))
        self.assertEqual(result['choices'][0]['message']['content'], 'ok')
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'success')
        self.assertEqual(rec.prompt_tokens, 11)
        self.assertEqual(rec.completion_tokens, 22)
        self.assertEqual(rec.role, 'writer')

    def test_chat_scenario_contextvar(self):
        payload = {'choices': [{'message': {'content': 'ok'}}], 'usage': {}}
        token = set_scenario('swriter')
        try:
            with mock.patch('apps.ai.client.httpx.AsyncClient',
                            return_value=_FakeAsyncClient(response=_FakeResponse(payload=payload))):
                asyncio.run(AIClient.chat(self.config, [{'role': 'user', 'content': 'hi'}],
                                          scenario=None))
        finally:
            reset_scenario(token)
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.scenario, 'swriter')

    def test_chat_failure_emits_failed_record(self):
        with mock.patch('apps.ai.client.httpx.AsyncClient',
                        return_value=_FakeAsyncClient(
                            exc=httpx.TimeoutException('boom'))):
            with self.assertRaises(Exception) as ctx:
                asyncio.run(AIClient.chat(self.config, [{'role': 'user', 'content': 'hi'}]))
        self.assertIn('DeepSeek', str(ctx.exception))
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'failed')
        self.assertIn('timeout', rec.error_message)

    def test_chat_sync_success(self):
        payload = {'choices': [{'message': {'content': 'sync'}}],
                   'usage': {'prompt_tokens': 1, 'completion_tokens': 2}}
        with mock.patch('apps.ai.client.httpx.Client') as fake_cls:
            fake_cls.return_value.__enter__.return_value.post.return_value = _FakeResponse(
                payload=payload)
            result = AIClient.chat_sync(self.config, [{'role': 'user', 'content': 'hi'}])
        self.assertEqual(result['choices'][0]['message']['content'], 'sync')
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'success')
        self.assertEqual(rec.total_tokens, 3)


class _FakeStreamResponse:
    """模拟 httpx 的流式响应对象。"""

    def __init__(self, lines, status_code=200):
        self.lines = lines
        self.status_code = status_code
        self.text = ''

    async def aread(self):
        return self.text.encode('utf-8')

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                'error', request=mock.Mock(), response=mock.Mock(status_code=self.status_code,
                                                                text=self.text))
        return None

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class _FakeStreamClient:
    """模拟 httpx.AsyncClient.stream() 返回的响应。"""

    def __init__(self, responses):
        # responses: list of _FakeStreamResponse，按序每次 stream() 消费一个
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, headers=None, json=None):
        response = self._responses.pop(0)
        return _FakeStreamEnvelope(response)


class _FakeStreamEnvelope:
    """让 `async with client.stream(...) as response` 拿到 _FakeStreamResponse。"""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


class ClientStreamTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='frank', password='x')
        self.config = AIModelConfig.objects.create(
            name='cfg', model_type='deepseek', role='writer', api_key='sk-x',
            base_url='https://api.deepseek.com', model_name='deepseek-chat',
            max_tokens=4096, temperature=0.7, top_p=0.9,
            is_active=True, created_by=self.user)

    def _lines(self, texts, finish_reason='stop', usage=None):
        lines = []
        for t in texts:
            lines.append(_sse_line({'choices': [{'delta': {'content': t}, 'finish_reason': None}]}))
        chunk = {'choices': [{'delta': {}, 'finish_reason': finish_reason}]}
        if usage:
            chunk['usage'] = usage
        lines.append(_sse_line(chunk))
        lines.append('data: [DONE]')
        return lines

    def test_stream_emits_success(self):
        lines = self._lines(['hello', ' world'], finish_reason='stop',
                            usage={'prompt_tokens': 5, 'completion_tokens': 11})
        client = _FakeStreamClient([_FakeStreamResponse(lines)])
        with mock.patch('apps.ai.client.httpx.AsyncClient', return_value=client):
            chunks = []

            async def runner():
                async for c in AIClient.chat_stream(self.config,
                                                    [{'role': 'user', 'content': 'x'}],
                                                    callback=None):
                    chunks.append(c)

            asyncio.run(runner())
        self.assertEqual(''.join(chunks), 'hello world')
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'success')
        self.assertEqual(rec.total_tokens, 16)

    def test_stream_continuation_on_length(self):
        # 第一次 finish_reason=length 触发续写，第二次 stop 结束，内容拼接
        first = self._lines(['part1'], finish_reason='length')
        second = self._lines(['part2'], finish_reason='stop',
                             usage={'prompt_tokens': 2, 'completion_tokens': 10})
        client = _FakeStreamClient([_FakeStreamResponse(first), _FakeStreamResponse(second)])
        with mock.patch('apps.ai.client.httpx.AsyncClient', return_value=client):
            chunks = []

            async def runner():
                async for c in AIClient.chat_stream(self.config,
                                                    [{'role': 'user', 'content': 'x'}],
                                                    callback=None):
                    chunks.append(c)

            asyncio.run(runner())
        self.assertEqual(''.join(chunks), 'part1part2')
        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'success')

    def test_stream_failure_emits_failed(self):
        client = _FakeStreamClient([_FakeStreamResponse(['?'], status_code=500)])
        with mock.patch('apps.ai.client.httpx.AsyncClient', return_value=client):
            with self.assertRaises(Exception):
                asyncio.run(self._collect())

        rec = AiCallRecord.objects.latest('id')
        self.assertEqual(rec.status, 'failed')
        self.assertEqual(rec.scenario, 'general')

    async def _collect(self):
        async for _c in AIClient.chat_stream(self.config, [{'role': 'user', 'content': 'x'}]):
            pass
