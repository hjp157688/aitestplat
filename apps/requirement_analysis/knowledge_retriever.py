"""
统一向量检索器

ChromaDB 一次搜索同时召回 chunk 和 entry
→ chunk 去重（同一章节的多个段落只保留一个）
→ LLM Rerank 重排序
"""
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


RERANK_PROMPT = """你是一个知识检索评估专家。请评估以下知识片段与用户需求的相关性。

用户需求：
{query}

知识片段：
{candidates_text}

请对每个片段打分（1-10分），分数含义：
- 9-10: 高度相关，直接回答了需求中的问题
- 7-8: 相关，提供了有用的背景信息
- 5-6: 部分相关，有一定参考价值
- 1-4: 不相关，对需求没有帮助

返回 JSON 格式（只返回 JSON，不要输出其他内容）：
[{{"id": "片段ID", "score": 8, "reason": "评分理由（一句话）"}}]

只返回 score >= 6 的片段，按分数从高到低排列。"""


class KnowledgeRetriever:
    """统一向量检索器"""

    def __init__(self, vector_store, embedding_service, llm_service):
        """
        Args:
            vector_store: VectorStoreService 实例
            embedding_service: 向量化服务
            llm_service: LLM 调用服务（AIModelService）
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    async def retrieve(
        self,
        query: str,
        project_id: Optional[int] = None,
        writer_config = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        检索相关知识

        Args:
            query: 查询文本（需求描述）
            project_id: 项目ID（None 表示只查全局知识）
            writer_config: AIModelConfig（用于 Rerank 的 LLM）
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        logger.info(f"开始检索: query='{query[:50]}...', project_id={project_id}, top_k={top_k}")

        # 1. 查询向量化
        try:
            query_embedding = self.embedding_service.embed_single(query)
        except Exception as e:
            logger.error(f"查询向量化失败: {e}")
            return []

        # 2. ChromaDB 统一搜索（同时召回 chunk 和 entry）
        raw_results = self.vector_store.search(
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=top_k * 3,  # 多召回一些，Rerank 后再截断
        )

        if not raw_results or not raw_results.get("ids") or not raw_results["ids"][0]:
            logger.info("检索无结果")
            return []

        # 3. 整理结果并去重
        merged = self._parse_and_deduplicate(raw_results)

        logger.info(f"召回 {len(merged)} 条结果（去重后）")

        # 4. LLM Rerank 重排序
        if writer_config and merged:
            try:
                merged = await self._rerank(query, merged, writer_config)
            except Exception as e:
                logger.error(f"Rerank 失败: {e}，使用原始排序")

        # 5. 返回 Top-K
        return merged[:top_k]

    def _parse_and_deduplicate(self, raw_results: Dict) -> List[Dict[str, Any]]:
        """解析 ChromaDB 结果并去重"""
        merged = []
        seen_sections = set()  # 用于 chunk 去重（同一章节只保留一个）

        for i, doc_id in enumerate(raw_results["ids"][0]):
            meta = raw_results["metadatas"][0][i]
            distance = raw_results["distances"][0][i]
            score = round(1 - distance, 4)  # 余弦距离转相似度

            if meta.get("type") == "chunk":
                section_title = meta.get("section_title", "")
                # 去重：同一章节的多个段落只保留得分最高的
                if section_title in seen_sections:
                    continue
                seen_sections.add(section_title)

                merged.append({
                    "id": doc_id,
                    "type": "chunk",
                    "name": section_title,
                    "content": meta.get("section_content", ""),  # Small-to-Big：返回章节全文
                    "score": score,
                    "source": {
                        "document_name": meta.get("document_name", ""),
                        "document_id": meta.get("document_id", 0),
                    },
                })

            elif meta.get("type") == "entry":
                merged.append({
                    "id": doc_id,
                    "type": "entry",
                    "name": meta.get("entry_name", ""),
                    "content": meta.get("entry_content", ""),
                    "category": meta.get("category", "other"),
                    "score": score,
                    "source": {
                        "document_name": meta.get("document_name", ""),
                    },
                })

        # 按原始相似度排序
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged

    async def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        config,
    ) -> List[Dict[str, Any]]:
        """LLM 重排序"""
        # 限制候选数量（prompt 长度控制）
        candidates_to_rerank = candidates[:20]

        # 格式化候选列表
        candidate_lines = []
        for i, c in enumerate(candidates_to_rerank):
            content_preview = c["content"][:200].replace("\n", " ")
            candidate_lines.append(
                f"[ID: {c['id']}] 类型: {c['type']} | 名称: {c.get('name', '')}\n"
                f"内容: {content_preview}..."
            )

        candidates_text = "\n\n---\n\n".join(candidate_lines)
        prompt = RERANK_PROMPT.format(query=query, candidates_text=candidates_text)

        try:
            response = await self.llm_service.call_openai_compatible_api(
                config,
                [
                    {"role": "system", "content": "你是一个知识检索评估专家，请严格按 JSON 格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
            )
            result_text = response['choices'][0]['message']['content']

            # 清理 JSON
            result_text = result_text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            scored = json.loads(result_text.strip())

            # 合并分数
            score_map = {}
            for item in scored:
                score_map[item["id"]] = {
                    "score": float(item.get("score", 0)),
                    "reason": item.get("reason", ""),
                }

            for c in candidates:
                if c["id"] in score_map:
                    c["rerank_score"] = score_map[c["id"]]["score"]
                    c["rerank_reason"] = score_map[c["id"]]["reason"]
                    # 用 Rerank 分数替换原始相似度
                    c["score"] = score_map[c["id"]]["score"]

            # 按 Rerank 分数排序
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

            logger.info(f"Rerank 完成，排序后 Top-3 分数: {[c.get('score') for c in candidates[:3]]}")

            # 过滤低分结果 (score < 6)
            candidates = [c for c in candidates if c.get("score", 0) >= 6]

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"Rerank 解析失败: {e}")
            # 保持原始排序

        return candidates