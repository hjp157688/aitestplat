"""
向量化服务封装
复用项目现有的 AIModelConfig，调用 embedding API
"""
import asyncio
import logging
from typing import List, Optional

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# 知识库分词/向量化模型的角色优先级（高 → 低）
EMBEDDING_ROLE_PRIORITY = ['tokenizer', 'embedding', 'writer']


class EmbeddingService:
    """
    向量化服务

    复用项目现有的 AIModelConfig（role=tokenizer / embedding）
    调用 OpenAI 兼容的 embedding API

    分词模型优先级：tokenizer → embedding → writer
    """

    def __init__(self):
        self._embedding_config = None

    def get_embedding_config(self, refresh: bool = False):
        """
        获取活跃的 embedding 模型配置

        Args:
            refresh: 为 True 时绕过缓存（配置变更后需重新查询）

        Returns:
            AIModelConfig 实例
        """
        from apps.requirement_analysis.models import AIModelConfig

        if self._embedding_config is None or refresh:
            config = None
            # 按优先级查找分词/嵌入模型配置
            for role in EMBEDDING_ROLE_PRIORITY:
                config = AIModelConfig.objects.filter(
                    role=role, is_active=True
                ).first()
                if config:
                    break

            if config:
                logger.info(f"使用分词模型: {config.name} ({config.model_name}, role={config.role})")
            else:
                logger.warning("未找到可用的分词/嵌入模型配置")

            self._embedding_config = config

        return self._embedding_config

    def clear_cache(self):
        """清空缓存的分词模型配置（配置变更后调用）"""
        self._embedding_config = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成 embedding（同步包装）

        Args:
            texts: 待向量化的文本列表

        Returns:
            embedding 向量列表
        """
        from apps.requirement_analysis.models import AIModelService

        config = self.get_embedding_config()
        if not config:
            raise Exception("未找到可用的分词/嵌入模型配置，请在配置中心配置一个分词模型")

        try:
            # 在已有事件循环中运行
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 创建新的事件循环
                import nest_asyncio
                nest_asyncio.apply()
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(
                        AIModelService.generate_embeddings(config, texts)
                    )
                finally:
                    new_loop.close()
            else:
                return loop.run_until_complete(
                    AIModelService.generate_embeddings(config, texts)
                )
        except RuntimeError:
            # 没有运行中的事件循环
            return asyncio.run(AIModelService.generate_embeddings(config, texts))

    def embed_single(self, text: str) -> List[float]:
        """
        生成单个文本的 embedding

        Args:
            text: 待向量化的文本

        Returns:
            embedding 向量
        """
        embeddings = self.embed([text])
        return embeddings[0]

    async def embed_async(self, texts: List[str]) -> List[List[float]]:
        """
        异步批量生成 embedding（可在 async 上下文安全调用）

        与同步 embed() 不同，配置查询通过 sync_to_async 执行，
        避免在运行中的事件循环内直接调用 ORM 触发 SynchronousOnlyOperation。
        """
        from apps.requirement_analysis.models import AIModelService

        config = await sync_to_async(self.get_embedding_config)()
        if not config:
            raise Exception("未找到可用的分词/嵌入模型配置")

        return await AIModelService.generate_embeddings(config, texts)

    async def embed_single_async(self, text: str) -> List[float]:
        """异步生成单个文本的 embedding"""
        embeddings = await self.embed_async([text])
        return embeddings[0]

    def get_langchain_embedding_model(self):
        """
        构造一个实现 LangChain Embeddings 接口的适配器

        语义分块使用（langchain_experimental.SemanticChunker），内部委托给
        本服务的 embed()/embed_single()，与向量化共用同一套 OpenAI 兼容
        embedding HTTP 调用路径，保证模型与参数完全一致。

        Returns:
            Embeddings 适配器实例；未配置分词/嵌入模型时返回 None
        """
        config = self.get_embedding_config()
        if not config:
            logger.warning("未找到可用的分词/嵌入模型配置，无法构造 LangChain embedding 模型")
            return None
        return _LangChainEmbeddingAdapter(self, config)


class _LangChainEmbeddingAdapter:
    """
    LangChain Embeddings 接口适配器

    仅做接口适配（embed_documents / embed_query），不包含任何分块逻辑。
    """

    def __init__(self, service: EmbeddingService, config):
        self.service = service
        self.config = config

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """LangChain 接口：批量向量化"""
        return self.service.embed(texts)

    def embed_query(self, text: str) -> List[float]:
        """LangChain 接口：单条向量化"""
        return self.service.embed_single(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await self.service.embed_async(texts)

    async def aembed_query(self, text: str) -> List[float]:
        embeddings = await self.service.embed_async([text])
        return embeddings[0]


# 全局单例
embedding_service = EmbeddingService()
