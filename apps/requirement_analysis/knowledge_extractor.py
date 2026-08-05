"""
LLM 知识条目提取器

三阶段流水线：
1. 结构分析：理解文档全貌
2. 逐章提取：按章节提取结构化知识条目
3. 去重合并：embedding 相似度去重
"""
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


STRUCTURE_ANALYSIS_PROMPT = """你是一个技术文档分析专家。请分析以下文档的整体结构。

文档内容：
{document_text}

请输出 JSON 格式（不要输出其他内容）：
{{
  "document_type": "系统设计文档",
  "summary": "一句话概括文档内容",
  "sections": [
    {{
      "title": "章节名",
      "topics": ["本章涉及的主题1", "主题2"],
      "key_entities": ["关键实体名1", "关键实体名2"]
    }}
  ],
  "global_knowledge": [
    "全局性知识，如技术栈选型、架构模式、通用规范等"
  ]
}}"""


SECTION_EXTRACT_PROMPT = """你是一个业务知识提取专家。请从以下文档章节中提取关键的业务知识。

【文档全局信息】
- 文档类型：{document_type}
- 文档概要：{summary}
- 全局知识：{global_knowledge}

【当前章节】
- 章节标题：{section_title}
- 章节内容：
{section_content}

【已提取的知识条目（请勿重复提取相同内容）】
{existing_entries_summary}

请提取以下类型的知识（如果某类知识在当前章节中不存在，跳过该类）：
1. **功能模块 (module)**：系统有哪些功能模块，每个模块的职责和边界
2. **数据模型 (data_model)**：涉及哪些数据实体、字段类型、字段含义、关联关系
3. **接口规范 (interface)**：API 路径、请求方法、参数、返回值、错误码
4. **业务规则 (business_rule)**：业务逻辑约束、状态流转、校验规则、计算公式
5. **命名约定 (naming)**：代码命名规范、数据库命名规范、接口命名规范
6. **约束条件 (constraint)**：性能要求、安全要求、兼容性要求、依赖关系

提取要求：
- 每个条目用一句话概括名称(name)，用 2-5 句话描述详细内容(content)
- 准确分类到上述 6 种类型之一(category)
- **只提取明确出现在文档中的信息，不要编造**
- 避免提取与已有条目重复的内容

返回 JSON 格式（只返回 JSON，不要输出其他内容）：
{{"entries": [{{"name": "条目名称", "category": "module", "content": "详细描述..."}}]}}
"""


class KnowledgeExtractor:
    """LLM 知识条目提取器"""

    def __init__(self, llm_service, embedding_service, chunker):
        """
        Args:
            llm_service: AI 模型调用服务（AIModelService）
            embedding_service: 向量化服务
            chunker: 分块器（KnowledgeChunker）
        """
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.chunker = chunker

    async def extract_from_document(
        self, document, writer_config, progress_callback=None
    ) -> List[Dict[str, Any]]:
        """
        从文档中提取知识条目

        Args:
            document: KnowledgeDocument 实例
            writer_config: AIModelConfig 实例（用于 LLM 调用）
            progress_callback: 异步进度回调 `async def cb(percent:int, message:str)`（可选）

        Returns:
            提取的知识条目列表
        """
        async def _report(percent: int, message: str):
            if progress_callback:
                try:
                    await progress_callback(percent, message)
                except Exception as e:
                    logger.warning(f"进度回调失败: {e}")

        raw_text = document.raw_text
        if not raw_text or not raw_text.strip():
            logger.warning(f"文档 {document.name} 没有文本内容，跳过提取")
            await _report(100, "文档无内容，跳过提取")
            return []

        # === 阶段 1：结构分析 ===
        logger.info(f"阶段 1: 分析文档结构 - {document.name}")
        await _report(5, "正在分析文档结构")
        structure_text = raw_text[:8000]  # 前 8000 字用于分析结构
        structure = await self._analyze_structure(structure_text, writer_config)
        await _report(10, "结构分析完成")

        # === 阶段 2：逐章提取 ===
        logger.info(f"阶段 2: 逐章提取知识条目 - {document.name}")
        sections = self.chunker._split_by_headers(raw_text)

        if not sections:
            # 无标题结构，整篇作为一个章节
            sections = [type('Section', (), {
                'title': structure.get('summary', '全文'),
                'content': raw_text,
            })()]

        total = len(sections)
        all_entries = []
        existing_summary = "暂无"

        for i, section in enumerate(sections):
            logger.info(f"  提取章节 [{i+1}/{total}]: {section.title}")

            # 章节内容限制 6000 字
            section_content = section.content[:6000]
            if len(section.content) > 6000:
                section_content += "\n...(内容过长，已截断)"

            percent = 10 + int(i / total * 80)
            await _report(percent, f"正在提取章节 {i+1}/{total}：{section.title}")

            entries = await self._extract_from_section(
                document_type=structure.get("document_type", "未知"),
                summary=structure.get("summary", ""),
                global_knowledge=structure.get("global_knowledge", []),
                section_title=section.title,
                section_content=section_content,
                existing_entries_summary=existing_summary,
                writer_config=writer_config,
            )

            # 增量去重
            all_entries = await self._deduplicate(all_entries, entries)

            # 更新已有条目摘要
            existing_summary = self._summarize_entries(all_entries)

            logger.info(f"  章节 [{i+1}] 提取 {len(entries)} 条，去重后累计 {len(all_entries)} 条")

        await _report(95, "正在合并去重，整理知识条目")
        logger.info(f"阶段 2 完成: 共提取 {len(all_entries)} 条知识条目")
        return all_entries

    async def _analyze_structure(self, text: str, config) -> Dict[str, Any]:
        """阶段 1：分析文档结构"""
        from apps.ai.prompt_registry import get_prompt_content_async
        from apps.ai import observability
        prompt = await get_prompt_content_async(
            'knowledge_structure', default=STRUCTURE_ANALYSIS_PROMPT,
            document_text=text)
        token = observability.set_scenario('knowledge_structure')
        try:
            response = await self.llm_service.call_openai_compatible_api(
                config,
                [
                    {"role": "system", "content": "你是一个技术文档分析专家，请严格按 JSON 格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
            )
            result_text = response['choices'][0]['message']['content']

            result = self._parse_json(result_text)
            if isinstance(result, dict):
                return result

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"结构分析失败: {e}")
        finally:
            observability.reset_scenario(token)

        return {
            "document_type": "未知",
            "summary": "无法分析文档结构",
            "sections": [],
            "global_knowledge": [],
        }

    async def _extract_from_section(
        self,
        document_type: str,
        summary: str,
        global_knowledge: List[str],
        section_title: str,
        section_content: str,
        existing_entries_summary: str,
        writer_config,
    ) -> List[Dict[str, Any]]:
        """阶段 2：从章节中提取知识条目"""
        from apps.ai.prompt_registry import get_prompt_content_async
        from apps.ai import observability
        prompt = await get_prompt_content_async(
            'knowledge_section', default=SECTION_EXTRACT_PROMPT,
            document_type=document_type,
            summary=summary,
            global_knowledge="\n".join(f"- {k}" for k in global_knowledge) if global_knowledge else "无",
            section_title=section_title,
            section_content=section_content,
            existing_entries_summary=existing_entries_summary,
        )

        # 输出预算：至少 8192（避免大章节 JSON 输出被截断），上限 16384
        # （不超主流模型输出上限；若模型上限较低，可在配置中心调小该模型的「最大Token数」）
        max_tokens = min(max(writer_config.max_tokens or 8192, 8192), 16384)

        token = observability.set_scenario('knowledge_section')
        try:
            response = await self.llm_service.call_openai_compatible_api(
                writer_config,
                [
                    {"role": "system", "content": "你是一个业务知识提取专家，请严格按 JSON 格式输出。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
            )
            result_text = response['choices'][0]['message']['content']

            result = self._parse_json(result_text)

            if isinstance(result, dict):
                return result.get("entries", [])
            if isinstance(result, list):
                # 直接返回对象列表（可能是截断后恢复的部分条目）
                return [e for e in result if isinstance(e, dict)]

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"章节提取失败 [{section_title}]: {e}")
        finally:
            observability.reset_scenario(token)

        return []

    def _parse_json(self, text: str):
        """
        解析 LLM 返回的 JSON

        先清理 markdown 代码块，再用标准库 json 解析；
        失败时交给 json_repair 修复（处理截断、缺引号、缺括号等常见问题）。
        """
        text = self._clean_json(text)

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            import json_repair
            result = json_repair.loads(text)
            logger.info("使用 json_repair 解析成功")
            return result
        except Exception as e:
            logger.warning(f"json_repair 解析失败: {e}")
            return None

    async def _deduplicate(
        self,
        existing: List[Dict[str, Any]],
        new_entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """阶段 3：去重合并"""
        if not new_entries:
            return existing

        if not existing:
            return new_entries

        # 计算已有条目的 embedding
        try:
            existing_texts = [e["content"] for e in existing]
            existing_embeddings = self.embedding_service.embed(existing_texts)
        except Exception as e:
            logger.warning(f"生成去重 embedding 失败: {e}，跳过去重")
            return existing + new_entries

        # 计算新条目的 embedding
        try:
            new_texts = [e["content"] for e in new_entries]
            new_embeddings = self.embedding_service.embed(new_texts)
        except Exception as e:
            logger.warning(f"生成新条目 embedding 失败: {e}")
            return existing + new_entries

        # 余弦相似度去重
        import numpy as np

        merged = list(existing)
        for i, new_entry in enumerate(new_entries):
            new_emb = np.array(new_embeddings[i])
            max_sim = 0.0

            for j, exist_emb in enumerate(existing_embeddings):
                exist_emb_arr = np.array(exist_emb)
                # 余弦相似度
                sim = np.dot(new_emb, exist_emb_arr) / (
                    np.linalg.norm(new_emb) * np.linalg.norm(exist_emb_arr) + 1e-10
                )
                max_sim = max(max_sim, sim)

            if max_sim > 0.85:
                # 高度相似，保留更完整的版本
                most_similar = existing[j]
                if len(new_entry.get("content", "")) > len(most_similar.get("content", "")):
                    most_similar["content"] = new_entry["content"]
                    most_similar["name"] = new_entry.get("name", most_similar["name"])
                logger.debug(f"去重: 跳过高度相似条目 '{new_entry.get('name', '')}' (相似度={max_sim:.3f})")
            else:
                merged.append(new_entry)

        return merged

    def _summarize_entries(self, entries: List[Dict[str, Any]]) -> str:
        """生成已有条目的摘要（用于防止重复提取）"""
        if not entries:
            return "暂无"

        summary_parts = []
        for i, entry in enumerate(entries[:30]):  # 最多 30 条
            summary_parts.append(
                f"{i+1}. [{entry.get('category', 'other')}] {entry.get('name', '未命名')}"
            )

        if len(entries) > 30:
            summary_parts.append(f"... 共 {len(entries)} 条，已省略后续条目")

        return "\n".join(summary_parts)

    def _clean_json(self, text: str) -> str:
        """清理 LLM 返回的 JSON 文本"""
        text = text.strip()

        # 移除 markdown 代码块标记
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return text.strip()