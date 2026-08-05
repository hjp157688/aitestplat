# -*- coding: utf-8 -*-
"""分块预览 / 编辑（ChromaDB 读写）测试

verify: get_chunks 按段落排序返回；update_chunk 重新向量化并刷新父级章节全文。
"""
from unittest import mock

from django.test import SimpleTestCase


def _fake_collection(chunks):
    """构造一个行为类似 ChromaDB Collection 的假对象"""
    records = {}
    for i, c in enumerate(chunks):
        records[c['id']] = dict(c)

    class FakeCollection:
        def get(self, where=None, ids=None, include=None):
            if ids is not None:
                items = [records[i] for i in ids if i in records]
            else:
                items = [r for r in records.values() if where.get('document_id') == r['document_id']]
            return {
                'ids': [r['id'] for r in items],
                'documents': [r['document'] for r in items],
                'metadatas': [{
                    'section_title': r['section_title'],
                    'section_content': r['section_content'],
                    'paragraph_index': r['paragraph_index'],
                    'header_level': r['header_level'],
                    'document_id': r['document_id'],
                } for r in items],
            }

        def update(self, ids, documents=None, embeddings=None, metadatas=None):
            for i, cid in enumerate(ids):
                rec = records[cid]
                if documents is not None:
                    rec['document'] = documents[i]
                if metadatas is not None:
                    rec['section_content'] = metadatas[i]['section_content']
                rec['embedding'] = embeddings[i] if embeddings else None

        @property
        def upserted(self):
            return {(k, v['document']) for k, v in records.items()}

    return FakeCollection(), records


class VectorStoreChunksTests(SimpleTestCase):

    def setUp(self):
        from apps.requirement_analysis.vector_store import VectorStoreService
        self.service = VectorStoreService()

    def test_get_chunks_sorted_by_paragraph_index(self):
        fake, _ = _fake_collection([
            {'id': 'chunk_0', 'document': '段落B', 'section_title': '章节二', 'section_content': '章节二全文',
             'paragraph_index': 2, 'header_level': 2, 'document_id': 9},
            {'id': 'chunk_1', 'document': '段落A', 'section_title': '章节一', 'section_content': '章节一全文',
             'paragraph_index': 1, 'header_level': 2, 'document_id': 9},
        ])
        fake_client = mock.Mock()
        fake_client.get_or_create_collection.return_value = fake

        with mock.patch.object(self.service, '_client', fake_client):
            chunks = self.service.get_chunks(1, 9)

        self.assertEqual([c['id'] for c in chunks], ['chunk_1', 'chunk_0'])
        self.assertEqual(chunks[0]['content'], '段落A')
        self.assertEqual(chunks[0]['section_title'], '章节一')

    def test_update_chunk_reeimbeds_and_refreshes_section_content(self):
        fake, records = _fake_collection([
            {'id': 'chunk_x', 'document': '旧段落文本', 'section_title': '章节一',
             'section_content': '章节一全文包含旧段落文本结尾', 'paragraph_index': 1,
             'header_level': 2, 'document_id': 9},
        ])
        fake_client = mock.Mock()
        fake_client.get_or_create_collection.return_value = fake

        embed_svc = mock.Mock()
        embed_svc.embed_single.return_value = [0.1, 0.2, 0.3]

        with mock.patch.object(self.service, '_client', fake_client):
            ok = self.service.update_chunk(1, 'chunk_x', '新段落文本', embed_svc)

        self.assertTrue(ok)
        emb, = embed_svc.embed_single.call_args.args
        self.assertEqual(emb, '新段落文本')
        rec = records['chunk_x']
        self.assertEqual(rec['document'], '新段落文本')
        # 父级章节中的旧文本被替换为新的
        self.assertEqual(rec['section_content'], '章节一全文包含新段落文本结尾')
        self.assertEqual(rec['embedding'], [0.1, 0.2, 0.3])

    def test_update_chunk_keeps_section_content_when_not_embedded(self):
        fake, records = _fake_collection([
            {'id': 'chunk_y', 'document': '独立段落', 'section_title': '章节一', 'section_content': '其他内容',
             'paragraph_index': 1, 'header_level': 2, 'document_id': 9},
        ])
        fake_client = mock.Mock()
        fake_client.get_or_create_collection.return_value = fake
        embed_svc = mock.Mock()
        embed_svc.embed_single.return_value = [0.5]

        with mock.patch.object(self.service, '_client', fake_client):
            self.service.update_chunk(1, 'chunk_y', '改后的段落', embed_svc)

        self.assertEqual(records['chunk_y']['section_content'], '其他内容')
