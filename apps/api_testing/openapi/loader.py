# apps/api_testing/openapi/loader.py
"""使用 prance 加载并 dereference OpenAPI spec"""
import logging

from prance import ResolvingParser, ValidationError
from prance.util.resolver import permissive_object_on_recursion

logger = logging.getLogger(__name__)

# 递归 schema（分类树、文件树等自引用结构）的最大展开深度。
# prance 展开到该深度后，更深层的引用会被替换为宽松的 object schema（带 x-recursive-ref 标记）。
DEFAULT_RECURSION_LIMIT = 5


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
                lazy=True,
                recursion_limit=DEFAULT_RECURSION_LIMIT,
                recursion_limit_handler=permissive_object_on_recursion,
            )
            try:
                parser.parse()
            except ValidationError as e:
                # openapi-spec-validator 对部分真实世界文件过严（如 type:''、缺失必填字段）。
                # prance 在校验前已完成 dereference，此时 parser.specification 已是完整解析结果，
                # 因此对“确实是 API spec 但存在轻微缺陷”的文件按宽松模式继续。
                # 若连 openapi/swagger 版本标识都没有，则判定不是 API 文件，抛出。
                spec_checked = parser.specification or {}
                if 'openapi' not in spec_checked and 'swagger' not in spec_checked:
                    raise
                logger.warning(
                    "OpenAPI spec 未通过 openapi-spec-validator 校验（宽松模式继续）: %s — %s",
                    file_path, str(e)[:200],
                )
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
