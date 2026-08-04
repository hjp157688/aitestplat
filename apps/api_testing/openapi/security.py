# apps/api_testing/openapi/security.py
"""提取 OpenAPI securitySchemes 并转为请求头"""
import logging

logger = logging.getLogger(__name__)

# 安全方案类型 → 请求头模板
SECURITY_HEADER_TEMPLATES = {
    'http': {
        'bearer': ('Authorization', 'Bearer {{{{bearer_token}}}}'),
        'basic': ('Authorization', 'Basic {{{{basic_auth}}}}'),
    },
    'apiKey': None,   # 动态处理，name 来自 spec
    'oauth2': ('Authorization', 'Bearer {{{{oauth_token}}}}'),
    'openIdConnect': ('Authorization', 'Bearer {{{{oidc_token}}}}'),
}


class SecurityExtractor:
    """从 OpenAPI spec 提取安全认证方案并生成请求头

    返回格式:
    {
        "global": [
            {"key": "Authorization", "value": "Bearer {{bearer_token}}",
             "enabled": True, "description": "BearerAuth"}
        ],
        "by_operation_id": {
            "createPet": [
                {"key": "X-API-Key", "value": "{{api_key}}",
                 "enabled": True, "description": "ApiKeyAuth"}
            ]
        }
    }
    """

    def extract(self, spec: dict) -> dict:
        # OpenAPI 3: components.securitySchemes；Swagger 2.0: securityDefinitions
        schemes = (spec.get('components', {}).get('securitySchemes', {})
                   or spec.get('securityDefinitions', {}))
        if not schemes:
            return {"global": [], "by_operation_id": {}}

        global_security = spec.get('security', [])
        global_headers = self._resolve_security(schemes, global_security)

        by_operation_id = {}
        for path, path_item in spec.get('paths', {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() not in {'get', 'post', 'put', 'delete',
                                          'patch', 'head', 'options', 'trace'}:
                    continue
                if not isinstance(operation, dict):
                    continue
                op_security = operation.get('security')
                if op_security is None:
                    continue
                op_id = operation.get('operationId', '')
                headers = self._resolve_security(schemes, op_security)
                if headers and op_id:
                    by_operation_id[op_id] = headers

        return {"global": global_headers, "by_operation_id": by_operation_id}

    def _resolve_security(self, schemes: dict,
                          requirements: list) -> list:
        """将 security requirements 列表转为请求头列表"""
        headers = []
        for req in requirements:
            if not isinstance(req, dict):
                continue
            for scheme_name in req:
                scheme = schemes.get(scheme_name)
                if not scheme:
                    continue
                header = self._scheme_to_header(scheme_name, scheme)
                if header:
                    headers.append(header)
        return headers

    def _scheme_to_header(self, name: str, scheme: dict) -> dict | None:
        """将单个 securityScheme 转为请求头"""
        scheme_type = scheme.get('type', '')

        # Swagger 2.0 basic / oauth2 类型
        if scheme_type in ('basic',):
            tmpl = SECURITY_HEADER_TEMPLATES.get('http', {}).get('basic')
            if tmpl:
                return {
                    'key': tmpl[0],
                    'value': tmpl[1],
                    'enabled': True,
                    'description': f'{name} (basic)',
                }

        if scheme_type == 'http':
            http_scheme = scheme.get('scheme', 'bearer')
            tmpl = SECURITY_HEADER_TEMPLATES.get('http', {}).get(http_scheme)
            if tmpl:
                return {
                    'key': tmpl[0],
                    'value': tmpl[1],
                    'enabled': True,
                    'description': f'{name} ({http_scheme})',
                }

        elif scheme_type == 'apiKey':
            apikey_in = scheme.get('in', 'header')
            apikey_name = scheme.get('name', 'X-API-Key')
            if apikey_in == 'header':
                return {
                    'key': apikey_name,
                    'value': '{{{{api_key}}}}',
                    'enabled': True,
                    'description': f'{name} (apiKey)',
                }
            elif apikey_in == 'query':
                return {
                    'key': apikey_name,
                    'value': '{{{{api_key}}}}',
                    'enabled': True,
                    'description': f'{name} (apiKey/query)',
                }

        elif scheme_type in ('oauth2', 'openIdConnect'):
            tmpl = SECURITY_HEADER_TEMPLATES.get(scheme_type)
            if tmpl:
                return {
                    'key': tmpl[0],
                    'value': tmpl[1],
                    'enabled': True,
                    'description': f'{name} ({scheme_type})',
                }

        return None