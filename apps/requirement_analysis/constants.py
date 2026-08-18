# -*- coding: utf-8 -*-
"""requirement_analysis 常量（RAGFlow 知识库引擎迁移）"""

# 知识条目写入 RAGFlow 时的文档名前缀（区分「文档」与「提取条目」两类载体）
ENTRY_DOC_PREFIX = "kb_entry_"

# 相似度分数换算比例：RAGFlow 相似度(0-1) × SCORE_SCALE_DEFAULT → 0-10 分
SCORE_SCALE_DEFAULT = 10
