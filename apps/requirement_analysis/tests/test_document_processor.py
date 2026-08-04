"""DocumentProcessor.extract_text 单元测试

验证按文档类型分发提取逻辑，兼容两种模型:
- RequirementDocument: 使用 document_type 字段
- KnowledgeDocument: 使用 file_type 字段（含 xlsx，来自 KnowledgeDocumentUploadSerializer）
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase


def _doc(path='/tmp/test_doc', **attrs):
    return SimpleNamespace(file=SimpleNamespace(path=path), **attrs)


class DocumentProcessorExtractTextTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 延迟导入：services 在模块加载时引入 Django models，需等 app registry 就绪
        from apps.requirement_analysis.services import DocumentProcessor
        cls.DocumentProcessor = DocumentProcessor

    def test_requirement_document_dispatches_by_document_type(self):
        doc = _doc(document_type='pdf')
        with mock.patch.object(self.DocumentProcessor, 'extract_text_from_pdf', return_value='PDF-CONTENT') as m:
            result = self.DocumentProcessor.extract_text(doc)
        m.assert_called_once_with('/tmp/test_doc')
        self.assertEqual(result, 'PDF-CONTENT')

    def test_knowledge_document_dispatches_by_file_type_docx(self):
        doc = _doc(file_type='docx')
        with mock.patch.object(self.DocumentProcessor, 'extract_text_from_docx', return_value='DOCX-CONTENT') as m:
            result = self.DocumentProcessor.extract_text(doc)
        m.assert_called_once_with('/tmp/test_doc')
        self.assertEqual(result, 'DOCX-CONTENT')

    def test_knowledge_document_file_type_txt(self):
        doc = _doc(file_type='txt')
        with mock.patch.object(self.DocumentProcessor, 'extract_text_from_txt', return_value='TXT-CONTENT') as m:
            result = self.DocumentProcessor.extract_text(doc)
        m.assert_called_once_with('/tmp/test_doc')
        self.assertEqual(result, 'TXT-CONTENT')

    def test_knowledge_document_file_type_md(self):
        doc = _doc(file_type='md')
        with mock.patch.object(self.DocumentProcessor, 'extract_text_from_txt', return_value='MD-CONTENT') as m:
            result = self.DocumentProcessor.extract_text(doc)
        m.assert_called_once_with('/tmp/test_doc')
        self.assertEqual(result, 'MD-CONTENT')

    def test_knowledge_document_file_type_xlsx(self):
        doc = _doc(file_type='xlsx')
        with mock.patch.object(self.DocumentProcessor, 'extract_text_from_xlsx', return_value='XLSX-CONTENT') as m:
            result = self.DocumentProcessor.extract_text(doc)
        m.assert_called_once_with('/tmp/test_doc')
        self.assertEqual(result, 'XLSX-CONTENT')

    def test_unsupported_type_returns_friendly_message(self):
        doc = _doc(file_type='bmp')
        result = self.DocumentProcessor.extract_text(doc)
        self.assertEqual(result, '不支持的文档类型')

    def test_missing_type_attribute_does_not_crash(self):
        # 防御性：类型字段为空也不应抛 AttributeError
        doc = _doc(text='whatever')
        result = self.DocumentProcessor.extract_text(doc)
        self.assertEqual(result, '不支持的文档类型')
