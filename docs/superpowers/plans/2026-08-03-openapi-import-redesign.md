# OpenAPI 导入解析与前端展示优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild OpenAPI import parsing with prance for $ref resolution, extract security/auth/response schemas, and display results in Apifox-style editable tables with schema preview.

**Architecture:** Backend uses a four-stage pipeline (SpecLoader → SecurityExtractor → EndpointExtractor → RequestConverter) to convert dereferenced OpenAPI specs into ApiRequest records. Frontend enhances InterfaceManagement with Auth/Schema tabs, table-mode JSON body editing, and enriched import preview.

**Tech Stack:** Python 3 + Django 4.2 + prance, Vue 3 + Element Plus

## Global Constraints

- `prance>=0.22.0` for $ref dereferencing
- Swagger 2.0 specs auto-converted to OpenAPI 3.0 by prance
- `params` and `headers` stored as array format `[{key, value, enabled, description}]`
- `body` stored as `{type, data}` dict
- New `ApiRequest` fields (`auth_spec`, `request_schema`, `response_schemas`, `deprecated`) have sensible defaults
- Backward compatible: existing ApiRequest records unaffected
- `KeyValueEditor` prop type already fixed to `[Object, Array]` in prior commit

---

### Task 1: Install prance dependency

**Files:**
- Modify: `requirements.txt` (or `pyproject.toml`)

- [ ] **Step 1: Add prance to requirements**

```bash
source .venv/bin/activate
pip install prance>=0.22.0
```

- [ ] **Step 2: Freeze dependency**

```bash
pip freeze | grep prance >> requirements.txt
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from prance import ResolvingParser; print('prance OK')"
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "build: add prance>=0.22.0 for OpenAPI parsing"
```

---

### Task 2: Create openapi package skeleton

**Files:**
- Create: `apps/api_testing/openapi/__init__.py`
- Create: `apps/api_testing/openapi/loader.py`
- Create: `apps/api_testing/openapi/security.py`
- Create: `apps/api_testing/openapi/endpoints.py`
- Create: `apps/api_testing/openapi/converter.py`
- Create: `apps/api_testing/openapi/example_generator.py`

- [ ] **Step 1: Create the package directory and empty files**

```bash
mkdir -p apps/api_testing/openapi
touch apps/api_testing/openapi/__init__.py
touch apps/api_testing/openapi/loader.py
touch apps/api_testing/openapi/security.py
touch apps/api_testing/openapi/endpoints.py
touch apps/api_testing/openapi/converter.py
touch apps/api_testing/openapi/example_generator.py
```

- [ ] **Step 2: Write `__init__.py` with public API**

```python
# apps/api_testing/openapi/__init__.py
from .loader import SpecLoader
from .security import SecurityExtractor
from .endpoints import EndpointExtractor
from .converter import RequestConverter

__all__ = ['SpecLoader', 'SecurityExtractor', 'EndpointExtractor', 'RequestConverter']
```

- [ ] **Step 3: Commit**

```bash
git add apps/api_testing/openapi/
git commit -m "feat: add openapi package skeleton"
```

---

### Task 3: Implement example_generator.py

**Files:**
- Create: `apps/api_testing/openapi/example_generator.py`

**Interfaces:**
- Produces: `generate_example(schema: dict) -> Any`

- [ ] **Step 1: Write the example generator**

```python
# apps/api_testing/openapi/example_generator.py
"""从 JSON Schema 生成有意义的示例值"""

FORMAT_EXAMPLES = {
    'date': '2024-01-01',
    'date-time': '2024-01-01T00:00:00Z',
    'email': 'user@example.com',
    'uri': 'https://example.com',
    'url': 'https://example.com',
    'uuid': '550e8400-e29b-41d4-a716-446655440000',
    'hostname': 'example.com',
    'ipv4': '192.168.1.1',
    'ipv6': '::1',
    'byte': 'U3dhZ2dlciByb2Nrcw==',
    'binary': 'binary',
    'password': 'password123',
    'phone': '+86-13800138000',
}


def generate_example(schema: dict):
    """从 JSON Schema 生成有意义的示例值

    优先级: example > default > enum[0] > 类型默认值

    Args:
        schema: dereferenced JSON Schema dict

    Returns:
        生成的示例值，无法生成时返回 None
    """
    if not isinstance(schema, dict):
        return None

    if 'example' in schema:
        return schema['example']
    if 'default' in schema:
        return schema['default']
    if 'enum' in schema and schema['enum']:
        return schema['enum'][0]

    schema_type = schema.get('type', 'object')

    if schema_type == 'object':
        result = {}
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            val = generate_example(prop_schema)
            if val is not None:
                result[prop_name] = val
            else:
                result[prop_name] = 'string'
        return result

    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        item = generate_example(items_schema)
        return [item] if item is not None else ['string']

    elif schema_type == 'string':
        if 'format' in schema:
            return FORMAT_EXAMPLES.get(schema['format'], 'string')
        return 'string'

    elif schema_type == 'integer':
        minimum = schema.get('minimum')
        if minimum is not None:
            return minimum
        return 1

    elif schema_type == 'number':
        minimum = schema.get('minimum')
        if minimum is not None:
            return float(minimum)
        return 1.0

    elif schema_type == 'boolean':
        return False

    return None
```

- [ ] **Step 2: Verify with quick test**

```bash
source .venv/bin/activate
python -c "
from apps.api_testing.openapi.example_generator import generate_example
schema = {'type': 'object', 'properties': {'name': {'type': 'string'}, 'age': {'type': 'integer'}}}
print(generate_example(schema))
"
```

Expected output: `{'name': 'string', 'age': 1}`

- [ ] **Step 3: Commit**

```bash
git add apps/api_testing/openapi/example_generator.py
git commit -m "feat: add schema-to-example generator with format support"
```

---

### Task 4: Implement loader.py (SpecLoader)

**Files:**
- Modify: `apps/api_testing/openapi/loader.py`

**Interfaces:**
- Produces: `SpecLoader.load(file_path: str) -> dict` — returns fully dereferenced OpenAPI spec

- [ ] **Step 1: Write SpecLoader**

```python
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
```

- [ ] **Step 2: Verify with a sample spec**

```bash
source .venv/bin/activate
python -c "
from apps.api_testing.openapi.loader import SpecLoader
import os, glob
# find a sample .json or .yaml file in media/api_docs/
files = glob.glob('media/api_docs/**/*.json', recursive=True) + glob.glob('media/api_docs/**/*.yaml', recursive=True)
if files:
    loader = SpecLoader()
    spec = loader.load(files[0])
    print('title:', spec.get('info', {}).get('title'))
    print('paths:', len(spec.get('paths', {})))
else:
    print('No test files found in media/api_docs/')
"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api_testing/openapi/loader.py
git commit -m "feat: add SpecLoader with prance $ref resolution"
```

---

### Task 5: Implement security.py (SecurityExtractor)

**Files:**
- Modify: `apps/api_testing/openapi/security.py`

**Interfaces:**
- Produces: `SecurityExtractor.extract(spec: dict) -> dict` — returns `{"global": [...], "by_operation_id": {...}}`

- [ ] **Step 1: Write SecurityExtractor**

```python
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
        schemes = spec.get('components', {}).get('securitySchemes', {})
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/api_testing/openapi/security.py
git commit -m "feat: add SecurityExtractor for OpenAPI auth schemes"
```

---

### Task 6: Implement endpoints.py (EndpointExtractor)

**Files:**
- Modify: `apps/api_testing/openapi/endpoints.py`

**Interfaces:**
- Consumes: `generate_example` from `example_generator.py`
- Produces: `EndpointExtractor.extract(spec: dict) -> list[dict]`

- [ ] **Step 1: Write EndpointExtractor**

```python
# apps/api_testing/openapi/endpoints.py
"""从 dereferenced spec 中提取所有端点"""
import logging
from .example_generator import generate_example

logger = logging.getLogger(__name__)

HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace'}


class EndpointExtractor:
    """从 dereferenced OpenAPI spec 提取端点列表

    每个端点包含:
    - path, method, summary, description, operation_id, tags
    - parameters (query/path/header/cookie, 含 schema)
    - request_body (content_type, schema, example, required)
    - response_schemas (按 status code 索引)
    - security, servers, deprecated
    """

    def extract(self, spec: dict) -> list[dict]:
        endpoints = []
        paths = spec.get('paths', {})
        global_servers = spec.get('servers', [])

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            path_parameters = path_item.get('parameters', [])

            for method in path_item:
                if method.lower() not in HTTP_METHODS:
                    continue
                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                ep = self._extract_operation(
                    spec, path, method.upper(), operation,
                    path_parameters, global_servers,
                )
                endpoints.append(ep)

        return endpoints

    def _extract_operation(self, spec: dict, path: str, method: str,
                           operation: dict, path_parameters: list,
                           global_servers: list) -> dict:
        operation_id = operation.get('operationId', '')
        summary = operation.get('summary', '')
        description = operation.get('description', '')
        tags = operation.get('tags', [])
        deprecated = operation.get('deprecated', False)
        name = summary or operation_id or f"{method} {path}"

        # 合并 path 级 + operation 级 parameters
        all_params = list(path_parameters) + operation.get('parameters', [])
        parameters = self._extract_parameters(spec, all_params)

        # 提取 requestBody
        request_body = self._extract_request_body(spec, operation)

        # 提取响应 schema
        response_schemas = self._extract_response_schemas(spec, operation)

        # 操作级 servers 覆盖全局
        op_servers = operation.get('servers') or global_servers
        servers = [{'url': s.get('url', '')} for s in op_servers if isinstance(s, dict)]

        security = operation.get('security')

        return {
            'path': path,
            'method': method,
            'summary': summary,
            'description': description,
            'operation_id': operation_id,
            'tags': tags,
            'deprecated': deprecated,
            'name': name,
            'parameters': parameters,
            'request_body': request_body,
            'response_schemas': response_schemas,
            'security': security,
            'servers': servers,
        }

    def _extract_parameters(self, spec: dict, params: list) -> list:
        result = []
        for param in params:
            if not isinstance(param, dict):
                continue
            param_in = param.get('in', 'query')
            result.append({
                'name': param.get('name', ''),
                'in': param_in,
                'required': param.get('required', False),
                'description': param.get('description', ''),
                'schema': param.get('schema', {}),
                'example': param.get('example'),
            })
        return result

    def _extract_request_body(self, spec: dict, operation: dict) -> dict | None:
        request_body = operation.get('requestBody')
        if not request_body or not isinstance(request_body, dict):
            return None

        content = request_body.get('content', {})
        if not content:
            return None

        # 优先 JSON
        for ct in ['application/json', '*/*']:
            if ct in content:
                return self._parse_content_entry(ct, content[ct], request_body)

        # 处理 form 类型
        for ct in ['application/x-www-form-urlencoded', 'multipart/form-data']:
            if ct in content:
                return self._parse_content_entry(ct, content[ct], request_body)

        # 兜底：取第一个 content type
        first_ct = list(content.keys())[0]
        return self._parse_content_entry(first_ct, content[first_ct], request_body)

    def _parse_content_entry(self, content_type: str, entry: dict,
                             request_body: dict) -> dict:
        schema = entry.get('schema', {})
        example = entry.get('example')
        if example is None and isinstance(schema, dict):
            example = generate_example(schema)
        return {
            'content_type': content_type,
            'schema': schema,
            'example': example if example is not None else {},
            'required': request_body.get('required', False),
            'description': request_body.get('description', ''),
        }

    def _extract_response_schemas(self, spec: dict, operation: dict) -> dict:
        """提取响应 JSON Schema，按 status code 索引"""
        result = {}
        responses = operation.get('responses', {})
        for status_code, response in responses.items():
            if not isinstance(response, dict):
                continue
            content = response.get('content', {})
            json_content = content.get('application/json') or content.get('*/*')
            if json_content and isinstance(json_content, dict):
                schema = json_content.get('schema', {})
                if schema:
                    result[str(status_code)] = schema
        return result
```

- [ ] **Step 2: Commit**

```bash
git add apps/api_testing/openapi/endpoints.py
git commit -m "feat: add EndpointExtractor with response schema support"
```

---

### Task 7: Implement converter.py (RequestConverter)

**Files:**
- Modify: `apps/api_testing/openapi/converter.py`

**Interfaces:**
- Consumes: `generate_example` from `example_generator.py`
- Produces: `RequestConverter.convert(endpoint: dict, auth_headers: list, base_url: str) -> dict`

- [ ] **Step 1: Write RequestConverter**

```python
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
        url = f"{{{{baseUrl}}}}{path}" if base else path

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
        if 'json' in ct:
            return {
                'type': 'json',
                'data': request_body.get('example') or {},
            }
        elif 'form-urlencoded' in ct:
            return {
                'type': 'x-www-form-urlencoded',
                'data': request_body.get('example') or {},
            }
        elif 'form-data' in ct:
            return {
                'type': 'form-data',
                'data': request_body.get('example') or {},
            }
        return {'type': 'none', 'data': {}}

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
```

- [ ] **Step 2: Commit**

```bash
git add apps/api_testing/openapi/converter.py
git commit -m "feat: add RequestConverter with auth spec and schema fields"
```

---

### Task 8: Add model fields and migration

**Files:**
- Modify: `apps/api_testing/models.py` (ApiRequest class)

- [ ] **Step 1: Add new fields to ApiRequest model**

Open `apps/api_testing/models.py` and add these fields to the `ApiRequest` class after the existing `assertions` field:

```python
# 在 assertions = models.JSONField(...) 之后添加
auth_spec = models.JSONField(default=dict, verbose_name='认证配置')
request_schema = models.JSONField(default=dict, verbose_name='请求体Schema')
response_schemas = models.JSONField(default=dict, verbose_name='响应Schema')
deprecated = models.BooleanField(default=False, verbose_name='是否已废弃')
```

- [ ] **Step 2: Generate and run migration**

```bash
source .venv/bin/activate
python manage.py makemigrations api_testing
python manage.py migrate api_testing
```

- [ ] **Step 3: Verify migration applied**

```bash
python manage.py showmigrations api_testing | grep -E "auth_spec|request_schema"
```

- [ ] **Step 4: Commit**

```bash
git add apps/api_testing/models.py apps/api_testing/migrations/
git commit -m "feat: add auth_spec, request_schema, response_schemas, deprecated fields to ApiRequest"
```

---

### Task 9: Update ApiRequestSerializer

**Files:**
- Modify: `apps/api_testing/serializers.py` (ApiRequestSerializer)

- [ ] **Step 1: Add new fields to serializer**

Open `apps/api_testing/serializers.py`, find `class ApiRequestSerializer`, and add the new fields to `Meta.fields`:

```python
class ApiRequestSerializer(serializers.ModelSerializer):
    # ... existing fields ...

    class Meta:
        model = ApiRequest
        fields = [
            'id', 'name', 'description', 'request_type', 'method', 'url',
            'headers', 'params', 'body', 'auth', 'pre_request_script',
            'post_request_script', 'assertions', 'collection', 'order',
            'parent_request_id', 'parent_request_name', 'test_cases_count',
            'auth_spec', 'request_schema', 'response_schemas', 'deprecated',  # new fields
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
```

- [ ] **Step 2: Commit**

```bash
git add apps/api_testing/serializers.py
git commit -m "feat: add new fields to ApiRequestSerializer"
```

---

### Task 10: Wire up pipeline in services.py

**Files:**
- Modify: `apps/api_testing/services.py` (OpenAPIParser class)

**Interfaces:**
- Consumes: `SpecLoader`, `SecurityExtractor`, `EndpointExtractor`, `RequestConverter` from `openapi/` package

- [ ] **Step 1: Rewrite OpenAPIParser.parse() to use new pipeline**

Replace the `parse` method in `OpenAPIParser` class:

```python
@staticmethod
def parse(file_path: str) -> dict:
    """使用 prance + 四阶段管道解析 OpenAPI 文件"""
    from .openapi import SpecLoader, SecurityExtractor, EndpointExtractor

    # 阶段 1: 加载并 dereference
    loader = SpecLoader()
    spec = loader.load(file_path)

    # 阶段 2: 提取安全认证
    sec_extractor = SecurityExtractor()
    auth_info = sec_extractor.extract(spec)

    # 阶段 3: 提取端点
    ep_extractor = EndpointExtractor()
    endpoints = ep_extractor.extract(spec)

    # 阶段 4: 转换 (在 import_to_collection 中按需调用 RequestConverter)

    # 提取 base URL
    servers = spec.get('servers', [])
    base_url = servers[0].get('url', '') if servers else ''

    # 兼容 Swagger 2.0
    if not base_url and 'host' in spec:
        scheme = spec.get('schemes', ['https'])[0]
        base_path = spec.get('basePath', '')
        base_url = f"{scheme}://{spec['host']}{base_path}"

    info = spec.get('info', {})

    # 为每个端点挂载 auth headers
    for ep in endpoints:
        op_id = ep.get('operation_id', '')
        ep['_auth_headers'] = auth_info['by_operation_id'].get(op_id) or auth_info['global']

    # 按 tag 分组
    tag_endpoints = {}
    untagged = []
    all_tags = set()
    for ep in endpoints:
        tags = ep.get('tags', [])
        if not tags:
            untagged.append(ep)
        else:
            for tag in tags:
                all_tags.add(tag)
                tag_endpoints.setdefault(tag, []).append(ep)

    groups = []
    for tag in sorted(all_tags):
        if tag in tag_endpoints:
            groups.append({'tag': tag, 'endpoints': tag_endpoints[tag]})
    if untagged:
        groups.append({'tag': 'default', 'endpoints': untagged})

    return {
        'spec_version': OpenAPIParser.detect_spec_version(spec),
        'title': info.get('title', 'Untitled API'),
        'description': info.get('description', ''),
        'version': info.get('version', ''),
        'base_url': base_url,
        'endpoints': endpoints,
        'tags': sorted(list(all_tags)),
        'endpoint_count': len(endpoints),
        'groups': groups,
    }
```

- [ ] **Step 2: Update `endpoint_to_request_data` to use RequestConverter**

```python
@staticmethod
def endpoint_to_request_data(endpoint: dict, base_url: str = '') -> dict:
    """将单个端点转换为 ApiRequest 创建所需的数据（使用 RequestConverter）"""
    from .openapi import RequestConverter
    converter = RequestConverter()
    auth_headers = endpoint.get('_auth_headers', [])
    return converter.convert(endpoint, auth_headers, base_url)
```

- [ ] **Step 3: Update `import_to_collection` to save new fields**

Replace the `ApiRequest.objects.create` calls inside `import_to_collection` to include the new fields:

```python
# In the by_tag branch:
ApiRequest.objects.create(
    collection=sub, name=rd['name'], method=rd['method'],
    url=rd['url'], headers=rd['headers'], params=rd['params'],
    body=rd['body'], description=rd['description'],
    auth_spec=rd.get('auth_spec', {}),
    request_schema=rd.get('request_schema', {}),
    response_schemas=rd.get('response_schemas', {}),
    deprecated=rd.get('deprecated', False),
    request_type=sub.project.project_type if sub.project else 'HTTP',
    order=i, created_by=user,
)

# In the non-by_tag branch:
ApiRequest.objects.create(
    collection=parent_collection, name=rd['name'], method=rd['method'],
    url=rd['url'], headers=rd['headers'], params=rd['params'],
    body=rd['body'], description=rd['description'],
    auth_spec=rd.get('auth_spec', {}),
    request_schema=rd.get('request_schema', {}),
    response_schemas=rd.get('response_schemas', {}),
    deprecated=rd.get('deprecated', False),
    request_type=parent_collection.project.project_type if parent_collection.project else 'HTTP',
    order=i, created_by=user,
)
```

- [ ] **Step 4: Verify import works end-to-end**

```bash
source .venv/bin/activate
python -c "
import os, glob
from apps.api_testing.services import OpenAPIParser
files = glob.glob('media/api_docs/**/*.json', recursive=True) + glob.glob('media/api_docs/**/*.yaml', recursive=True)
if files:
    result = OpenAPIParser.parse(files[0])
    print('Title:', result['title'])
    print('Endpoints:', result['endpoint_count'])
    if result['endpoints']:
        ep = result['endpoints'][0]
        print('First endpoint:', ep['method'], ep['path'])
        print('Has auth headers:', bool(ep.get('_auth_headers')))
        print('Has request_body:', bool(ep.get('request_body')))
        if ep.get('request_body'):
            print('Body example:', ep['request_body'].get('example'))
else:
    print('No test files found')
"
```

- [ ] **Step 5: Commit**

```bash
git add apps/api_testing/services.py
git commit -m "feat: wire up four-stage pipeline in OpenAPIParser"
```

---

### Task 11: Frontend — Body tab table mode for JSON

**Files:**
- Modify: `frontend/src/views/api-testing/InterfaceManagement.vue`

**Interfaces:**
- Consumes: `setBodyFromJson` (already defined), `bodyType`, `rawBody`, `formData` refs
- Produces: JSON body displayed as editable table rows by default

- [ ] **Step 1: Update `onNodeClick` body handling to default to table mode**

In `onNodeClick`, modify the `body.type === 'json'` branch to always use `setBodyFromJson` when data is a non-empty object, regardless of nesting:

```javascript
// 在 onNodeClick 中，替换 body.type === 'json' 的处理逻辑：
if (requestData.body.type === 'json') {
  const data = requestData.body.data
  if (typeof data === 'string') {
    try {
      const parsed = JSON.parse(data)
      setBodyFromJson(parsed)
    } catch (e) {
      bodyType.value = 'raw'
      rawType.value = 'json'
      rawBody.value = data
    }
  } else if (data && typeof data === 'object' && !Array.isArray(data)) {
    // 默认进入表格模式，无论是否有嵌套
    setBodyFromJson(data)
  } else {
    bodyType.value = 'raw'
    rawType.value = 'json'
    rawBody.value = data ? JSON.stringify(data, null, 2) : ''
  }
}
```

- [ ] **Step 2: Update `setBodyFromJson` to handle nested objects as JSON strings**

In `setBodyFromJson`, nested objects and arrays should be displayed as JSON strings in the table value column:

```javascript
const setBodyFromJson = (data) => {
  if (!data || typeof data !== 'object') return

  const items = []
  Object.entries(data).forEach(([key, value]) => {
    if (value === null || value === undefined) {
      items.push({ key, value: '', enabled: true, description: '', type: 'text' })
    } else if (typeof value === 'object') {
      // 嵌套对象/数组：显示为 JSON 字符串
      items.push({
        key,
        value: JSON.stringify(value),
        enabled: true,
        description: 'object/array',
        type: 'text'
      })
    } else {
      items.push({
        key,
        value: String(value),
        enabled: true,
        description: '',
        type: 'text'
      })
    }
  })

  bodyType.value = 'form-data'
  formData.value = items
  _originalJsonBody.value = data
}
```

- [ ] **Step 3: Add a "切换到 Raw" button in the body tab template**

In the template, add a toggle button near the body type radio group:

```html
<el-button
  size="small"
  type="info"
  text
  @click="toggleBodyMode"
  style="margin-left: 8px"
>
  {{ bodyType === 'raw' ? '切换到表格' : '切换到 Raw' }}
</el-button>
```

Add the toggle function:

```javascript
const toggleBodyMode = () => {
  if (bodyType.value === 'raw') {
    // raw → table: parse rawBody back to form-data
    try {
      const parsed = JSON.parse(rawBody.value)
      setBodyFromJson(parsed)
    } catch (e) {
      ElMessage.warning('无法解析为 JSON，请检查格式')
    }
  } else {
    // table → raw: rebuild raw JSON from formData
    const jsonData = {}
    const items = formData.value || []
    items.forEach(item => {
      if (item.key) {
        const val = item.value || ''
        try {
          jsonData[item.key] = JSON.parse(val)
        } catch {
          jsonData[item.key] = val
        }
      }
    })
    bodyType.value = 'raw'
    rawType.value = 'json'
    rawBody.value = JSON.stringify(jsonData, null, 2)
  }
}
```

- [ ] **Step 4: Update `saveRequest` to handle form-data mode with `_originalJsonBody`**

The existing `saveRequest` already handles `_originalJsonBody` for form-data → json conversion. Ensure it also works for the table-mode body:

```javascript
// In saveRequest, bodyData for form-data should stay as-is:
} else if (bodyType.value === 'form-data') {
  if (_originalJsonBody.value) {
    // Was originally JSON → save as JSON
    const jsonData = {}
    const items = formData.value || []
    items.forEach(item => {
      if (item.key) {
        const val = item.value || ''
        try {
          jsonData[item.key] = JSON.parse(val)
        } catch {
          jsonData[item.key] = val
        }
      }
    })
    bodyData = {
      type: 'json',
      data: jsonData
    }
    _originalJsonBody.value = null
  } else {
    bodyData = {
      type: 'form-data',
      data: formData.value || []
    }
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/api-testing/InterfaceManagement.vue
git commit -m "feat: add table/raw toggle for JSON body editing"
```

---

### Task 12: Frontend — Add Schema tab

**Files:**
- Modify: `frontend/src/views/api-testing/InterfaceManagement.vue`

**Interfaces:**
- Consumes: `selectedRequest.request_schema`, `selectedRequest.response_schemas`

- [ ] **Step 1: Add Schema tab to template**

After the Body tab, add:

```html
<el-tab-pane label="Schema" name="schema" v-if="selectedRequest && (selectedRequest.request_schema || selectedRequest.response_schemas)">
  <div class="schema-viewer">
    <div v-if="selectedRequest.request_schema && Object.keys(selectedRequest.request_schema).length > 0" class="schema-section">
      <h4>{{ $t('apiTesting.interface.requestSchema') }}</h4>
      <div class="schema-tree">
        <SchemaNode
          :schema="selectedRequest.request_schema"
          :name="selectedRequest.request_schema.title || 'root'"
          :required-fields="selectedRequest.request_schema.required || []"
        />
      </div>
    </div>

    <div v-if="selectedRequest.response_schemas && Object.keys(selectedRequest.response_schemas).length > 0" class="schema-section">
      <h4>{{ $t('apiTesting.interface.responseSchema') }}</h4>
      <div v-for="(schema, statusCode) in selectedRequest.response_schemas" :key="statusCode" class="schema-status-group">
        <h5>Status: {{ statusCode }}</h5>
        <SchemaNode
          :schema="schema"
          :name="schema.title || 'response'"
          :required-fields="schema.required || []"
        />
      </div>
    </div>

    <div v-if="(!selectedRequest.request_schema || Object.keys(selectedRequest.request_schema).length === 0) && (!selectedRequest.response_schemas || Object.keys(selectedRequest.response_schemas).length === 0)" class="empty-tip">
      {{ $t('apiTesting.interface.noSchema') }}
    </div>
  </div>
</el-tab-pane>
```

- [ ] **Step 2: Create SchemaNode component**

Create `frontend/src/views/api-testing/components/SchemaNode.vue`:

```vue
<template>
  <div class="schema-node">
    <div class="schema-node-header" @click="expanded = !expanded" v-if="hasChildren">
      <el-icon><component :is="expanded ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
      <span class="schema-prop-name">{{ name }}</span>
      <span class="schema-prop-type">{{ typeLabel }}</span>
      <el-tag v-if="isRequired" size="small" type="danger">required</el-tag>
      <span v-if="description" class="schema-prop-desc">{{ description }}</span>
    </div>
    <div class="schema-node-leaf" v-else>
      <span class="schema-prop-name">{{ name }}</span>
      <span class="schema-prop-type">{{ typeLabel }}</span>
      <el-tag v-if="isRequired" size="small" type="danger">required</el-tag>
      <span v-if="description" class="schema-prop-desc">{{ description }}</span>
    </div>
    <div v-if="expanded && hasChildren" class="schema-node-children">
      <SchemaNode
        v-for="(propSchema, propName) in children"
        :key="propName"
        :schema="propSchema"
        :name="propName"
        :required-fields="schema.required || []"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  schema: { type: Object, default: () => ({}) },
  name: { type: String, default: '' },
  requiredFields: { type: Array, default: () => [] },
})

const expanded = ref(true)

const isRequired = computed(() => props.requiredFields.includes(props.name))
const description = computed(() => props.schema.description || '')

const schemaType = computed(() => {
  if (props.schema.enum) return 'enum'
  return props.schema.type || 'object'
})

const typeLabel = computed(() => {
  const t = schemaType.value
  if (t === 'enum') return `enum: ${props.schema.enum?.join(', ')}`
  if (t === 'string' && props.schema.format) return `string(${props.schema.format})`
  return t
})

const hasChildren = computed(() => {
  return schemaType.value === 'object' && props.schema.properties
})

const children = computed(() => {
  if (schemaType.value === 'object' && props.schema.properties) {
    return props.schema.properties
  }
  return {}
})
</script>

<style scoped>
.schema-node { margin-left: 16px; font-size: 13px; }
.schema-node-header { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 0; }
.schema-node-leaf { display: flex; align-items: center; gap: 6px; padding: 4px 0; }
.schema-prop-name { font-weight: 500; color: #268bd2; }
.schema-prop-type { color: #909399; font-family: monospace; }
.schema-prop-desc { color: #606266; font-size: 12px; margin-left: 8px; }
.schema-node-children { border-left: 1px dashed #e4e7ed; }
.schema-section { margin-bottom: 16px; }
.schema-section h4 { margin: 0 0 8px; font-size: 14px; }
.schema-status-group h5 { margin: 8px 0 4px; font-size: 13px; color: #409eff; }
</style>
```

- [ ] **Step 3: Import and register SchemaNode in InterfaceManagement.vue**

```javascript
import SchemaNode from './components/SchemaNode.vue'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/api-testing/components/SchemaNode.vue
git add frontend/src/views/api-testing/InterfaceManagement.vue
git commit -m "feat: add Schema tab with tree view for request/response schemas"
```

---

### Task 13: Frontend — Add Auth tab

**Files:**
- Modify: `frontend/src/views/api-testing/InterfaceManagement.vue`

- [ ] **Step 1: Add Auth tab to template**

After the Headers tab, add:

```html
<el-tab-pane label="Auth" name="auth" v-if="selectedRequest && selectedRequest.auth_spec && Object.keys(selectedRequest.auth_spec).length > 0">
  <div class="auth-display">
    <div class="auth-info">
      <span class="auth-label">{{ $t('apiTesting.interface.authType') }}:</span>
      <el-tag type="primary">{{ selectedRequest.auth_spec.type || '-' }}</el-tag>
    </div>
    <div class="auth-header-row">
      <span class="auth-label">{{ selectedRequest.auth_spec.header_name }}</span>
      <el-input
        :model-value="selectedRequest.auth_spec.header_value"
        readonly
        class="auth-value-input"
      />
      <el-tooltip :content="$t('apiTesting.interface.authSource')" placement="top">
        <el-icon class="auth-source-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>
    <div class="auth-hint">
      {{ $t('apiTesting.interface.authHint') }}
    </div>
  </div>
</el-tab-pane>
```

- [ ] **Step 2: Add auth display styles**

```css
.auth-display { padding: 16px; }
.auth-info { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.auth-header-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.auth-label { font-weight: 500; min-width: 120px; }
.auth-value-input { flex: 1; max-width: 400px; }
.auth-source-icon { color: #909399; cursor: help; }
.auth-hint { color: #909399; font-size: 12px; margin-top: 8px; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/api-testing/InterfaceManagement.vue
git commit -m "feat: add Auth tab displaying imported security scheme info"
```

---

### Task 14: Frontend — Import preview enhancement

**Files:**
- Modify: `frontend/src/views/api-testing/components/ImportOpenApiDialog.vue`

- [ ] **Step 1: Add info columns to endpoint table**

In the group preview table, add a column showing params/body/auth summary:

```html
<el-table-column :label="$t('apiTesting.importOpenApi.info')" min-width="120">
  <template #default="{ row }">
    <div class="endpoint-info">
      <span v-if="row.parameters && row.parameters.length > 0" class="info-tag">
        {{ row.parameters.filter(p => p.in === 'query').length > 0 ? 'Query' : '' }}
        {{ row.parameters.filter(p => p.in === 'path').length > 0 ? 'Path' : '' }}
      </span>
      <span v-if="row.request_body" class="info-tag body-tag">
        Body: {{ row.request_body.content_type?.includes('json') ? 'JSON' : row.request_body.content_type }}
      </span>
      <span v-if="row._auth_headers && row._auth_headers.length > 0" class="info-tag auth-tag">
        Auth: {{ row._auth_headers[0].description }}
      </span>
    </div>
  </template>
</el-table-column>
```

- [ ] **Step 2: Add styles for info tags**

```css
.endpoint-info { display: flex; flex-wrap: wrap; gap: 4px; }
.info-tag {
  font-size: 11px; padding: 1px 6px; border-radius: 3px;
  background: var(--el-fill-color-light); color: var(--el-text-color-secondary);
}
.body-tag { background: #ecf5ff; color: #409eff; }
.auth-tag { background: #fef0f0; color: #f56c6c; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/api-testing/components/ImportOpenApiDialog.vue
git commit -m "feat: add params/body/auth info column to import preview"
```

---

### Task 15: Frontend — Deprecated style in tree nodes

**Files:**
- Modify: `frontend/src/views/api-testing/InterfaceManagement.vue`

- [ ] **Step 1: Add deprecated class to tree node**

In the tree node template, add a conditional class:

```html
<div class="tree-node" :class="{ 'testcase-node': data.type === 'testcase', 'deprecated-node': data.deprecated }">
```

- [ ] **Step 2: Add deprecated CSS**

```css
.deprecated-node .node-label {
  color: #c0c4cc;
  text-decoration: line-through;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/api-testing/InterfaceManagement.vue
git commit -m "feat: add deprecated styling for tree nodes"
```

---

### Task 16: Frontend — i18n entries

**Files:**
- Modify: `frontend/src/locales/zh-cn/api-testing.js`
- Modify: `frontend/src/locales/en/api-testing.js`

- [ ] **Step 1: Add Chinese i18n entries**

```javascript
// In zh-cn/api-testing.js, add:
interface: {
  // ... existing entries ...
  authType: '认证类型',
  authSource: '来源: OpenAPI securitySchemes',
  authHint: '认证配置由 OpenAPI 文档的安全方案自动生成，变量值请根据实际环境替换',
  requestSchema: '请求体 Schema',
  responseSchema: '响应 Schema',
  noSchema: '无 Schema 信息',
  switchToRaw: '切换到 Raw',
  switchToTable: '切换到表格',
}
```

- [ ] **Step 2: Add English i18n entries**

```javascript
// In en/api-testing.js, add:
interface: {
  // ... existing entries ...
  authType: 'Auth Type',
  authSource: 'Source: OpenAPI securitySchemes',
  authHint: 'Auth config auto-generated from OpenAPI security schemes. Replace variable values for your environment.',
  requestSchema: 'Request Schema',
  responseSchema: 'Response Schema',
  noSchema: 'No Schema Available',
  switchToRaw: 'Switch to Raw',
  switchToTable: 'Switch to Table',
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/locales/zh-cn/api-testing.js frontend/src/locales/en/api-testing.js
git commit -m "feat: add i18n entries for Auth, Schema, and body toggle"
```

---

### Task 17: End-to-end verification

**Files:**
- No new files; verify all changes work together

- [ ] **Step 1: Start backend and verify import API**

```bash
source .venv/bin/activate
python manage.py runserver
```

- [ ] **Step 2: Test import via API**

```bash
# Upload a test OpenAPI spec
curl -X POST http://localhost:8000/api/api-testing/api-docs/ \
  -H "Authorization: Bearer <token>" \
  -F "file=@media/api_docs/2026/08/默认模块.swagger.json" \
  -F "title=test" \
  -F "project=1"

# Parse it (replace <doc_id> with the returned ID)
curl -X POST http://localhost:8000/api/api-testing/api-docs/<doc_id>/parse/ \
  -H "Authorization: Bearer <token>"

# Import it
curl -X POST http://localhost:8000/api/api-testing/api-docs/<doc_id>/import/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "base_url": "http://localhost:8000"}'
```

- [ ] **Step 3: Verify frontend**

```bash
cd frontend
npm run dev
```

Open the app, navigate to API testing, import an OpenAPI document, and verify:
- Import preview shows params/body/auth info
- Clicking an imported request shows Headers with auth headers
- Body tab shows table-mode editable fields
- Body tab toggle switches between table and raw
- Schema tab shows tree view
- Auth tab shows auth config
- Deprecated endpoints show gray + strikethrough in tree

- [ ] **Step 4: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes for OpenAPI import"
```