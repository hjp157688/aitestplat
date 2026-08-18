"""
ChromaDB 向量存储服务
统一管理文档分块和知识条目的向量化存储
"""
import os
import json
import logging
from typing import List, Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """
    ChromaDB 向量存储

    一个项目一个 Collection，同时存储 chunk 和 entry
    通过 metadata.type 区分两种类型

    Collection 命名规则:
    - 全局知识: kb_global
    - 项目知识: kb_project_{project_id}
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            try:
                import chromadb  # noqa: F401 —— 仅顶层导入失败才算“未安装”
            except ImportError:
                raise ImportError("chromadb 未安装，请运行: pip install chromadb")
            from chromadb.config import Settings

            persist_dir = os.path.join(settings.BASE_DIR, 'chroma_data')
            os.makedirs(persist_dir, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB 初始化完成，持久化目录: {persist_dir}")

        return self._client

    def get_or_create_collection(self, project_id: Optional[int] = None):
        """
        获取或创建项目对应的 Collection

        Args:
            project_id: 项目ID，None 表示全局知识

        Returns:
            ChromaDB Collection 对象
        """
        collection_name = f"kb_project_{project_id}" if project_id else "kb_global"
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_sections(
        self,
        project_id: Optional[int],
        sections,
        embedding_service,
        document_name: str = "",
        document_id: int = None,
    ):
        """
        将文档分块存入 ChromaDB（Small-to-Big：索引用段落，返回用章节）

        Args:
            project_id: 项目ID
            sections: Section 对象列表（来自 KnowledgeChunker.chunk()）
            embedding_service: 向量化服务实例
            document_name: 文档名称
            document_id: 文档数据库ID
        """
        collection = self.get_or_create_collection(project_id)

        all_paragraph_texts = []
        all_metadatas = []
        all_ids = []

        for section in sections:
            for para in section.paragraphs:
                all_paragraph_texts.append(para.content)
                all_ids.append(f"chunk_{project_id or 'global'}_{document_id}_{para.index}")
                all_metadatas.append({
                    "type": "chunk",
                    "section_title": section.title,
                    "section_content": section.content,  # 父级章节全文（Small-to-Big）
                    "paragraph_index": para.index,
                    "document_name": document_name,
                    "document_id": document_id or 0,
                    "project_id": project_id or 0,
                    "header_level": section.metadata.get("header_level", 0),
                })

        if not all_paragraph_texts:
            logger.warning(f"文档 {document_name} 没有可索引的段落")
            return 0

        # 批量生成 embedding
        try:
            embeddings = embedding_service.embed(all_paragraph_texts)
        except Exception as e:
            logger.error(f"生成 embedding 失败: {e}")
            raise

        # 批量存入 ChromaDB
        # 幂等：先清掉该文档已有的分块（ID 由 project/document/index 确定性生成，
        # 直接 add 会在重复处理时撞 ID 抛 “Expected IDs to be unique”）
        collection.delete(where={"document_id": document_id or 0})
        collection.add(
            ids=all_ids,
            documents=all_paragraph_texts,
            embeddings=embeddings,
            metadatas=all_metadatas,
        )

        logger.info(f"存入 {len(all_paragraph_texts)} 个段落到 collection (project_id={project_id})")
        return len(all_paragraph_texts)

    def add_entry(
        self,
        project_id: Optional[int],
        entry_id: int,
        entry_name: str,
        entry_content: str,
        category: str,
        embedding_service,
        document_name: str = "",
        knowledge_level: str = "global",
    ):
        """
        将知识条目向量化并存入 ChromaDB

        Args:
            project_id: 项目ID
            entry_id: 条目数据库ID
            entry_name: 条目名称
            entry_content: 条目内容
            category: 分类
            embedding_service: 向量化服务实例
            document_name: 来源文档名称
            knowledge_level: 知识级别
        """
        collection = self.get_or_create_collection(project_id)

        try:
            embedding = embedding_service.embed_single(entry_content)
        except Exception as e:
            logger.error(f"生成条目 embedding 失败 (entry_id={entry_id}): {e}")
            raise

        doc_id = f"entry_{entry_id}"
        collection.add(
            ids=[doc_id],
            documents=[entry_content],
            embeddings=[embedding],
            metadatas=[{
                "type": "entry",
                "entry_id": entry_id,
                "entry_name": entry_name,
                "entry_content": entry_content,
                "category": category,
                "knowledge_level": knowledge_level,
                "project_id": project_id or 0,
                "document_name": document_name,
            }],
        )
        logger.info(f"存入知识条目 entry_{entry_id} 到 ChromaDB")

    def update_entry(
        self,
        project_id: Optional[int],
        entry_id: int,
        entry_name: str,
        entry_content: str,
        category: str,
        embedding_service,
        document_name: str = "",
        knowledge_level: str = "global",
    ):
        """更新知识条目：先删除再添加"""
        self.remove_entry(entry_id)
        self.add_entry(
            project_id=project_id,
            entry_id=entry_id,
            entry_name=entry_name,
            entry_content=entry_content,
            category=category,
            embedding_service=embedding_service,
            document_name=document_name,
            knowledge_level=knowledge_level,
        )

    def remove_entry(self, entry_id: int):
        """删除知识条目（从所有可能的 collection 中删除）"""
        # ChromaDB 不支持跨 collection 删除，需要尝试删除
        # 由于我们不知道条目在哪个 collection，需要遍历
        try:
            collections = self.client.list_collections()
            for col in collections:
                try:
                    col.delete(ids=[f"entry_{entry_id}"])
                except Exception:
                    pass  # 条目可能不在这个 collection 中
            logger.info(f"删除知识条目 entry_{entry_id} 的 ChromaDB 记录")
        except Exception as e:
            logger.warning(f"清理 ChromaDB 条目 entry_{entry_id} 时出错: {e}")

    def remove_by_document(self, project_id: Optional[int], document_id: int):
        """删除文档对应的所有 chunks"""
        try:
            collection = self.get_or_create_collection(project_id)
            collection.delete(where={"document_id": document_id})
            logger.info(f"删除文档 {document_id} 的所有 ChromaDB chunks")
        except ImportError:
            # ChromaDB 未安装：根本没有向量数据可清理，静默跳过
            logger.debug("ChromaDB 未安装，跳过向量清理")
        except Exception as e:
            logger.warning(f"清理 ChromaDB 文档 {document_id} 时出错: {e}")

    def get_chunks(
        self,
        project_id: Optional[int],
        document_id: int,
    ) -> List[Dict[str, Any]]:
        """
        获取文档的所有分块（按段落顺序）

        Args:
            project_id: 项目ID
            document_id: 文档数据库ID

        Returns:
            分块列表，每项含 id / content / section_title / paragraph_index
        """
        collection = self.get_or_create_collection(project_id)
        result = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )

        chunks = []
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        for i, chunk_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            chunks.append({
                "id": chunk_id,
                "content": documents[i] if i < len(documents) else "",
                "section_title": meta.get("section_title", ""),
                "paragraph_index": meta.get("paragraph_index", 0),
                "header_level": meta.get("header_level", 0),
            })

        chunks.sort(key=lambda c: c.get("paragraph_index", 0))
        logger.info(f"获取文档 {document_id} 的分块: {len(chunks)} 个")
        return chunks

    def update_chunk(
        self,
        project_id: Optional[int],
        chunk_id: str,
        content: str,
        embedding_service,
    ) -> bool:
        """
        更新单个分块内容并重新向量化

        同时同步刷新父级章节全文（Small-to-Big），保证检索返回最新文本。

        Args:
            project_id: 项目ID
            chunk_id: ChromaDB chunk id
            content: 更新后的分块内容
            embedding_service: 向量化服务实例

        Returns:
            bool 是否成功
        """
        collection = self.get_or_create_collection(project_id)

        existing = collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas"],
        )
        old_content = (existing.get("documents") or [None])[0]
        old_meta = (existing.get("metadatas") or [{}])[0] or {}

        # 若该段落文本仍包含在父级章节中，替换为编辑后的文本
        section_content = old_meta.get("section_content", "") or ""
        if old_content and old_content in section_content:
            section_content = section_content.replace(old_content, content, 1)

        # 重新向量化
        embedding = embedding_service.embed_single(content)

        new_meta = dict(old_meta)
        new_meta["section_content"] = section_content

        collection.update(
            ids=[chunk_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[new_meta],
        )
        logger.info(f"更新分块 {chunk_id} 完成")
        return True

    def search(
        self,
        project_id: Optional[int],
        query_embedding: List[float],
        top_k: int = 20,
    ) -> Dict[str, Any]:
        """
        向量检索（同时召回 chunk 和 entry）

        Args:
            project_id: 项目ID
            query_embedding: 查询向量
            top_k: 返回数量

        Returns:
            ChromaDB 查询结果
        """
        collection = self.get_or_create_collection(project_id)

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            return results
        except Exception as e:
            logger.error(f"ChromaDB 检索失败: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def delete_collection(self, project_id: Optional[int] = None):
        """删除整个 collection"""
        collection_name = f"kb_project_{project_id}" if project_id else "kb_global"
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"删除 ChromaDB collection: {collection_name}")
        except Exception as e:
            logger.warning(f"删除 collection {collection_name} 失败: {e}")


# 全局单例
vector_store = VectorStoreService()