"""
自适应分块器：有标题按标题层级分块，无标题按语义分块
支持 Small-to-Big 检索策略
"""
import re
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Paragraph:
    """段落"""
    content: str
    index: int = 0


@dataclass
class Section:
    """章节"""
    title: str
    content: str
    paragraphs: List[Paragraph] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class KnowledgeChunker:
    """
    自适应分块器

    策略：
    - 有标题结构 → MarkdownHeaderTextSplitter 按 ##/### 分章节，每章内 SemanticChunker 细分段落
    - 无标题结构 → 纯 SemanticChunker 语义分块
    - Small-to-Big：检索时索引段落，返回时替换为父级章节
    """

    def __init__(self, embedding_model=None):
        """
        Args:
            embedding_model: LangChain embedding 模型实例，用于 SemanticChunker
        """
        self.embedding_model = embedding_model

    def chunk(self, text: str) -> List[Section]:
        """
        主入口：对文本进行分块

        Args:
            text: 原始文本

        Returns:
            章节列表，每个章节包含段落列表
        """
        if not text or not text.strip():
            return []

        if self._has_headers(text):
            logger.info("检测到文档标题结构，使用 MarkdownHeaderTextSplitter")
            sections = self._split_by_headers(text)
        else:
            logger.info("未检测到标题结构，使用纯语义分块")
            sections = [Section(title="全文", content=text)]

        # 对每个章节内容进行段落级语义细分
        for section in sections:
            section.paragraphs = self._split_to_paragraphs(section.content)

        # 段落 index 必须是整篇文档唯一：vector_store.add_sections 用它生成
        # chunk ID（chunk_{project}_{doc}_{index}），且 paragraph_index 用于分块展示排序。
        # 各章节内部分割时 index 都从 0 起编，必须在此全局重排，否则多章节文档入库时撞 ID。
        paragraph_seq = 0
        for section in sections:
            for para in section.paragraphs:
                para.index = paragraph_seq
                paragraph_seq += 1

        logger.info(f"分块完成: {len(sections)} 个章节, 共 {sum(len(s.paragraphs) for s in sections)} 个段落")
        return sections

    def _has_headers(self, text: str) -> bool:
        """检测文本是否包含 Markdown 标题（# ## ### 等）"""
        return bool(re.search(r'^#{1,6}\s+\S', text, re.MULTILINE))

    def _split_by_headers(self, text: str) -> List[Section]:
        """
        按标题分割为章节

        使用正则手动分割，避免依赖 langchain 的 MarkdownHeaderTextSplitter
        （减少依赖，同时保持更灵活的控制）
        """
        sections = []
        # 匹配 ## 或 ### 标题
        header_pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)

        # 找到所有标题位置
        matches = list(header_pattern.finditer(text))

        if not matches:
            # 没有找到二级/三级标题，尝试用一级标题
            header_pattern = re.compile(r'^(#{1})\s+(.+)$', re.MULTILINE)
            matches = list(header_pattern.finditer(text))

        if not matches:
            return [Section(title="全文", content=text)]

        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.end()

            # 找到下一个同级或更高级标题的位置
            end = len(text)
            for j in range(i + 1, len(matches)):
                next_match = matches[j]
                next_level = len(next_match.group(1))
                if next_level <= level:
                    end = next_match.start()
                    break

            content = text[start:end].strip()
            if content:
                sections.append(Section(
                    title=title,
                    content=content,
                    metadata={"header_level": level, "header_text": title},
                ))

        return sections

    def _split_to_paragraphs(self, text: str) -> List[Paragraph]:
        """
        将文本拆分为段落

        优先使用 SemanticChunker（如果 embedding_model 可用），
        否则回退到基于自然段落的拆分
        """
        if self.embedding_model is not None:
            try:
                return self._split_by_semantic(text)
            except Exception as e:
                logger.warning(f"SemanticChunker 失败，回退到段落拆分: {e}")

        return self._split_by_paragraphs(text)

    def _split_by_semantic(self, text: str) -> List[Paragraph]:
        """使用 SemanticChunker 按语义边界拆分"""
        try:
            from langchain_experimental.text_splitter import SemanticChunker

            splitter = SemanticChunker(
                embeddings=self.embedding_model,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=90,
            )
            docs = splitter.create_documents([text])
            return [Paragraph(content=doc.page_content, index=i) for i, doc in enumerate(docs)]
        except ImportError:
            logger.warning("langchain_experimental 未安装，回退到段落拆分")
            return self._split_by_paragraphs(text)

    def _split_by_paragraphs(self, text: str) -> List[Paragraph]:
        """按自然段落拆分（备选方案）"""
        # 按双换行分段落
        paragraphs = re.split(r'\n\s*\n', text)
        result = []
        para_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落太长（>500字），按句号进一步拆分
            if len(para) > 500:
                sentences = re.split(r'(?<=[。.!！?？])\s*', para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) > 300 and current:
                        result.append(Paragraph(content=current.strip(), index=para_index))
                        para_index += 1
                        current = sent
                    else:
                        current += sent
                if current.strip():
                    result.append(Paragraph(content=current.strip(), index=para_index))
                    para_index += 1
            else:
                result.append(Paragraph(content=para, index=para_index))
                para_index += 1

        return result