# apps/api_testing/openapi/loader.py
"""使用 prance 加载并 dereference OpenAPI spec"""
import logging
from prance import ResolvingParser

logger = logging.getLogger(__name__)


class SpecLoader:
    """使用 prance.ResolvingParser 加载 OpenAPI 文件

    prance 自动处理:
    - 内部 $ref 引用 (#/components/schemas/Foo)
    - 外部文件引用 (./other.yaml#/paths/~1users)
    - 循环引用检测
    - JSON Pointer 转义 (~0/~1)
    - Swagger 2.0 → OpenAPI 3.0 转换
    - allOf/oneOf/anyOf 合并
    """

    def load(self, file_path: str) -> dict:
        """加载并完全 dereference OpenAPI spec

        Args:
            file_path: OpenAPI 文件路径 (JSON 或 YAML)

        Returns:
            完全 dereferenced 的 spec dict

        Raises:
            ValueError: 文件解析失败或 spec 格式无效
        """
        try:
            parser = ResolvingParser(
                file_path,
                backend='openapi-spec-validator',
                strict=False,
            )
            parser.parse()
            spec = parser.specification
            logger.info(
                "Loaded OpenAPI spec: title=%s, version=%s, paths=%d",
                spec.get('info', {}).get('title', 'Unknown'),
                spec.get('openapi', '') or spec.get('swagger', ''),
                len(spec.get('paths', {})),
            )
            return spec
        except Exception as e:
            logger.exception("Failed to load OpenAPI spec from %s", file_path)
            raise ValueError(f"无法解析 OpenAPI 文件: {e}") from e
