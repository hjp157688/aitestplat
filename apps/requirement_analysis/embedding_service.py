"""
向量化服务封装
复用项目现有的 AIModelConfig，调用 embedding API
"""
import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    向量化服务

    复用项目现有的 AIModelConfig（role=embedding）
    调用 OpenAI 兼容的 embedding API
    """

    def __init__(self):
        self._embedding_config = None

    def get_embedding_config(self):
        """
        获取活跃的 embedding 模型配置

        Returns:
            AIModelConfig 实例
        """
        from apps.requirement_analysis.models import AIModelConfig

        if self._embedding_config is None:
            # 优先查找 role=embedding 的配置
            self._embedding_config = AIModelConfig.objects.filter(
                role='embedding', is_active=True
            ).first()

            if not self._embedding_config:
                # 回退：使用 writer 角色的配置（大多数模型都支持 embedding API）
                self._embedding_config = AIModelConfig.objects.filter(
                    role='writer', is_active=True
                ).first()

            if self._embedding_config:
                logger.info(f"使用 embedding 模型: {self._embedding_config.name} ({self._embedding_config.model_name})")
            else:
                logger.warning("未找到可用的 embedding 模型配置")

        return self._embedding_config

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
            raise Exception("未找到可用的 embedding 模型配置，请在配置中心配置一个 embedding 模型")

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
        异步批量生成 embedding

        Args:
            texts: 待向量化的文本列表

        Returns:
            embedding 向量列表
        """
        from apps.requirement_analysis.models import AIModelService

        config = self.get_embedding_config()
        if not config:
            raise Exception("未找到可用的 embedding 模型配置")

        return await AIModelService.generate_embeddings(config, texts)


# 全局单例
embedding_service = EmbeddingService()