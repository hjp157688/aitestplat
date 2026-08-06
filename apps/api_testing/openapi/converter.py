# apps/api_testing/openapi/converter.py
"""将 endpoint 转为 ApiRequest 创建数据"""
import json
import logging

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

        # 构建 params (query 参数)
        params = []
        for param in endpoint.get('parameters', []):
            param_in = param.get('in', 'query')
            if param_in == 'query':
                example_val = self._param_example(param)
                params.append({
                    'key': param['name'],
                    'value': example_val,
                    'enabled': param.get('required', False),
                    'description': param.get('description', ''),
                })
            elif param_in == 'header':
                example_val = self._param_example(param)
                headers.append({
                    'key': param['name'],
                    'value': example_val,
                    'enabled': param.get('required', False),
                    'description': param.get('description', ''),
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
            'body': body,
            'auth_spec': auth_spec,
            'request_schema': request_schema,
            'response_schemas': endpoint.get('response_schemas', {}),
            'deprecated': endpoint.get('deprecated', False),
            'description': self._build_description(endpoint),
            'assertions': [],
        }

    def _param_example(self, param: dict) -> str:
        if param.get('example') is not None:
            return str(param['example'])
        schema = param.get('schema', {})
        if schema.get('type') == 'integer':
            return str(schema.get('default', '0'))
        if schema.get('type') == 'boolean':
            return str(schema.get('default', 'false'))
        return ''

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
                'data': example or {},
            }
        elif 'form-data' in ct:
            return {
                'type': 'form-data',
                'data': example or {},
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