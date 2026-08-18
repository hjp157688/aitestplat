# apps/api_testing/openapi/converter.py
"""将 endpoint 转为 ApiRequest 创建数据"""
import json
import logging

from .example_generator import FORMAT_EXAMPLES, first_example_value

logger = logging.getLogger(__name__)


class RequestConverter:
    """将提取的 endpoint 转为 ApiRequest 模型所需的数据格式

    返回格式:
    {
        "name": "查询宠物列表",
        "method": "GET",
        "url": "{{baseUrl}}/pets",
        "headers": [
            {"key": "Accept", "value": "application/json", "enabled": True, "description": ""},
        ],
        "params": [
            {"key": "limit", "value": "10", "enabled": False, "description": "分页大小"},
        ],
        "body": {"type": "none", "data": {}},
        "auth_spec": {"type": "bearer", "scheme": "bearer", ...},
        "request_schema": {...},
        "response_schemas": {"200": {...}},
        "deprecated": False,
    }
    """

    def convert(self, endpoint: dict, auth_headers: list,
                base_url: str = '') -> dict:
        name = endpoint.get('name', '')
        method = endpoint.get('method', 'GET')
        path = endpoint.get('path', '')
        base = base_url.rstrip('/') if base_url else ''

        # URL: 保留路径参数模板 {param}
        url = f"{{{{base_url}}}}{path}" if base else path

        # 构建 headers: 认证头 + 标准头 + header 参数
        headers = []
        headers.extend(auth_headers)

        request_body = endpoint.get('request_body')
        if request_body:
            ct = request_body.get('content_type', 'application/json')
            headers.append({
                'key': 'Content-Type', 'value': ct,
                'enabled': True, 'description': '',
            })
        headers.append({
            'key': 'Accept', 'value': 'application/json',
            'enabled': True, 'description': '',
        })

        # 构建 params (query 参数) 与 path_params (路径参数)
        params = []
        path_params = []
        for param in endpoint.get('parameters', []):
            param_in = param.get('in', 'query')
            if param_in == 'query':
                params.append({
                    'key': param['name'],
                    'value': self._param_example(param),
                    'enabled': param.get('required', False),
                    'description': param.get('description', ''),
                    'param_type': self._param_type(param),
                    'required': param.get('required', False),
                })
            elif param_in == 'path':
                path_params.append({
                    'key': param['name'],
                    'value': self._param_example(param),
                    'enabled': param.get('required', True),
                    'description': param.get('description', ''),
                    'param_type': self._param_type(param),
                    'required': param.get('required', True),
                })
            elif param_in == 'header':
                headers.append({
                    'key': param['name'],
                    'value': self._param_example(param),
                    'enabled': param.get('required', False),
                    'description': param.get('description', ''),
                    'param_type': self._param_type(param),
                    'required': param.get('required', False),
                })

        # 构建 body
        body = self._build_body(request_body)

        # 认证配置
        auth_spec = self._build_auth_spec(auth_headers)

        # 请求体 schema
        request_schema = request_body.get('schema', {}) if request_body else {}

        return {
            'name': name,
            'method': method,
            'url': url,
            'headers': headers,
            'params': params,
            'path_params': path_params,
            'body': body,
            'auth_spec': auth_spec,
            'request_schema': request_schema,
            'response_schemas': endpoint.get('response_schemas', {}),
            'response_examples': endpoint.get('response_examples', {}),
            'deprecated': endpoint.get('deprecated', False),
            'description': self._build_description(endpoint),
            'assertions': [],
        }

    @staticmethod
    def _param_type(param: dict) -> str:
        """参数类型：Swagger2 直接在参数上标 type，OpenAPI3 在 schema 里"""
        return param.get('type') or (param.get('schema') or {}).get('type') or ''

    def _param_example(self, param: dict) -> str:
        """解析参数的示例值，导入的是文档自带的示例内容而不是空占位符

        优先级（越高越先用文档里真实定义的示例内容）:
        1. 参数级 x-example（YApi 等导出的扩展字段）
        2. 参数级 example（OpenAPI 3）
        3. 参数级 examples 映射（命名示例 / 媒体类型 → 值）
        4. 参数级 default / enum[0]（Swagger 2.0 直接挂在参数上）
        5. schema 级 example > default > enum[0]
        6. format 级示例（date/email/uuid/...）与类型兜底（string 无提示时留空）
        """
        for key in ('x-example', 'example'):
            if param.get(key) is not None:
                return self._row_value(param[key])
        named = first_example_value(param.get('examples'))
        if named is not None:
            return self._row_value(named)
        if param.get('default') is not None:
            return self._row_value(param['default'])
        if param.get('enum'):
            return self._row_value(param['enum'][0])

        schema = param.get('schema') or {}
        if schema:
            if schema.get('example') is not None:
                return self._row_value(schema['example'])
            if schema.get('default') is not None:
                return self._row_value(schema['default'])
            if schema.get('enum'):
                return self._row_value(schema['enum'][0])
            schema_type = schema.get('type')
            if schema_type == 'integer':
                return str(schema.get('minimum')) if schema.get('minimum') is not None else '0'
            if schema_type == 'number':
                return str(schema.get('minimum')) if schema.get('minimum') is not None else '1'
            if schema_type == 'boolean':
                return str(schema.get('default', False)).lower()
            if schema_type == 'string':
                return FORMAT_EXAMPLES.get(schema.get('format'), '')

        # 无 schema：Swagger 2.0 直接在参数上标类型，做类型兜底
        param_type = param.get('type')
        if param_type == 'integer':
            return '0'
        if param_type == 'number':
            return '1'
        if param_type == 'boolean':
            return 'false'
        return ''

    @staticmethod
    def _row_value(value):
        """form 字段值序列化为字符串：嵌套对象/数组 → JSON 字符串，其余 → str"""
        if value is None:
            return ''
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

    def _rows_from_example(self, example) -> list:
        """把 form 的 {key: value} 示例转成表格行数组格式（同前端 body.data 格式）"""
        if not example or not isinstance(example, dict):
            return []
        return [
            {'key': k, 'value': self._row_value(v), 'enabled': True, 'description': '', 'type': 'text'}
            for k, v in example.items()
        ]

    def _build_body(self, request_body: dict | None) -> dict:
        if not request_body:
            return {'type': 'none', 'data': {}}
        ct = request_body.get('content_type', 'application/json')
        example = request_body.get('example')
        if 'json' in ct:
            return {
                'type': 'json',
                'data': example or {},
            }
        elif 'form-urlencoded' in ct:
            return {
                'type': 'x-www-form-urlencoded',
                'data': self._rows_from_example(example),
            }
        elif 'form-data' in ct:
            return {
                'type': 'form-data',
                'data': self._rows_from_example(example),
            }
        # 其余 content-type（text/plain、xml、octet-stream 等）按 raw 保留原始 example，
        # 避免 body 数据在导入时丢失
        return {
            'type': 'raw',
            'data': example or '',
        }

    def _build_auth_spec(self, auth_headers: list) -> dict:
        if not auth_headers:
            return {}
        first = auth_headers[0]
        return {
            'type': first.get('description', ''),
            'header_name': first.get('key', ''),
            'header_value': first.get('value', ''),
        }

    def _build_description(self, endpoint: dict) -> str:
        parts = []
        if endpoint.get('summary'):
            parts.append(endpoint['summary'])
        if endpoint.get('description'):
            parts.append(endpoint['description'])
        return '\n'.join(parts)