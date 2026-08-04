"""
API Testing 服务层：OpenAPI 解析 + AI 测试用例生成
"""
import json
import logging
import re
import threading
import uuid
from typing import Optional, Callable

import requests
import yaml
from django.conf import settings
from django.db import transaction

from apps.api_testing.models import (
    ApiCollection, ApiDocument, ApiRequest, ApiProject, AIServiceConfig, TestSuite,
    ApiPromptConfig,
)

logger = logging.getLogger(__name__)


class OpenAPIParser:
    """解析 OpenAPI/Swagger 规范文档，提取端点并转换为 ApiRequest 数据"""

    @staticmethod
    def detect_format(content: str) -> str:
        """检测内容是 JSON 还是 YAML"""
        content = content.strip()
        if content.startswith('{') or content.startswith('['):
            return 'json'
        return 'yaml'

    @staticmethod
    def parse_content(content: str) -> dict:
        """解析 JSON 或 YAML 内容为 Python dict"""
        fmt = OpenAPIParser.detect_format(content)
        if fmt == 'json':
            return json.loads(content)
        else:
            return yaml.safe_load(content)

    @staticmethod
    def detect_spec_version(spec: dict) -> str:
        """检测 OpenAPI/Swagger 规范版本"""
        if 'openapi' in spec:
            version = spec['openapi']
            if isinstance(version, str):
                if version.startswith('3.1'):
                    return 'openapi_3.1'
                if version.startswith('3.0'):
                    return 'openapi_3.0'
                if version.startswith('3.'):
                    return 'openapi_3.0'
            return 'openapi_3.0'
        if 'swagger' in spec:
            return 'swagger_2.0'
        return 'unknown'

    @staticmethod
    def resolve_ref(spec: dict, ref: str) -> Optional[dict]:
        """解析 $ref 引用（仅支持内部引用 #/components/... 或 #/definitions/...）"""
        if not ref or not ref.startswith('#/'):
            return None
        path = ref[2:].split('/')
        result = spec
        for part in path:
            # 处理 JSON Pointer 转义 (~0 = ~, ~1 = /)
            part = part.replace('~1', '/').replace('~0', '~')
            if isinstance(result, dict) and part in result:
                result = result[part]
            else:
                return None
        return result

    @staticmethod
    def extract_schema_example(spec: dict, schema: dict, depth: int = 0) -> dict:
        """从 schema 中提取示例数据"""
        if depth > 5:
            return None

        if schema is None:
            return None

        # 如果 schema 本身是 $ref
        if isinstance(schema, dict) and '$ref' in schema:
            resolved = OpenAPIParser.resolve_ref(spec, schema['$ref'])
            if resolved:
                return OpenAPIParser.extract_schema_example(spec, resolved, depth + 1)
            # $ref 解析失败，返回空
            return None

        if not isinstance(schema, dict):
            return None

        # 如果有 example 字段，直接返回
        if 'example' in schema:
            return schema['example']

        # 处理 allOf (取第一个 schema 合并)
        if 'allOf' in schema and isinstance(schema['allOf'], list):
            merged = {}
            for sub_schema in schema['allOf']:
                if isinstance(sub_schema, dict):
                    resolved = sub_schema
                    if '$ref' in resolved:
                        resolved = OpenAPIParser.resolve_ref(spec, resolved['$ref'])
                    if resolved and isinstance(resolved, dict):
                        sub_example = OpenAPIParser.extract_schema_example(spec, resolved, depth + 1)
                        if isinstance(sub_example, dict):
                            merged.update(sub_example)
            return merged if merged else None

        # 处理 oneOf/anyOf (取第一个)
        if 'oneOf' in schema and isinstance(schema['oneOf'], list) and len(schema['oneOf']) > 0:
            return OpenAPIParser.extract_schema_example(spec, schema['oneOf'][0], depth + 1)
        if 'anyOf' in schema and isinstance(schema['anyOf'], list) and len(schema['anyOf']) > 0:
            return OpenAPIParser.extract_schema_example(spec, schema['anyOf'][0], depth + 1)

        schema_type = schema.get('type', 'object')

        if schema_type == 'object':
            result = {}
            properties = schema.get('properties', {})
            required = set(schema.get('required', []))
            for prop_name, prop_schema in properties.items():
                val = OpenAPIParser.extract_schema_example(spec, prop_schema, depth + 1)
                if val is not None:
                    result[prop_name] = val
                else:
                    result[prop_name] = 'string'
            return result

        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            item_example = OpenAPIParser.extract_schema_example(spec, items_schema, depth + 1)
            return [item_example] if item_example is not None else ['string']

        elif schema_type == 'string':
            if 'enum' in schema and schema['enum']:
                return schema['enum'][0]
            if 'format' in schema:
                format_map = {
                    'date': '2024-01-01',
                    'date-time': '2024-01-01T00:00:00Z',
                    'email': 'user@example.com',
                    'uri': 'https://example.com',
                    'uuid': '550e8400-e29b-41d4-a716-446655440000',
                }
                return format_map.get(schema['format'], 'string')
            return 'string'

        elif schema_type == 'integer':
            return 1

        elif schema_type == 'number':
            return 1.0

        elif schema_type == 'boolean':
            return True

        return None

    @staticmethod
    def extract_parameters(spec: dict, operation: dict, path_item: dict) -> list:
        """提取请求参数列表"""
        params = []

        # path 级别的 parameters
        path_params = path_item.get('parameters', [])
        # operation 级别的 parameters
        op_params = operation.get('parameters', [])

        all_params = path_params + op_params
        for param in all_params:
            if isinstance(param, dict):
                if '$ref' in param:
                    resolved = OpenAPIParser.resolve_ref(spec, param['$ref'])
                    if resolved:
                        param = resolved
                    else:
                        continue

                param_info = {
                    'name': param.get('name', ''),
                    'in': param.get('in', 'query'),
                    'required': param.get('required', False),
                    'description': param.get('description', ''),
                    'type': 'string',
                }

                # 获取参数类型
                param_schema = param.get('schema', {})
                if isinstance(param_schema, dict):
                    if '$ref' in param_schema:
                        resolved = OpenAPIParser.resolve_ref(spec, param_schema['$ref'])
                        if resolved:
                            param_schema = resolved
                    param_info['type'] = param_schema.get('type', 'string')
                    param_info['example'] = param_schema.get('example', None)
                    if 'enum' in param_schema:
                        param_info['enum'] = param_schema['enum']

                # 兼容 Swagger 2.0 的 type 直接在 param 层级
                if 'type' in param:
                    param_info['type'] = param['type']

                params.append(param_info)

        return params

    @staticmethod
    def extract_request_body(spec: dict, operation: dict) -> Optional[dict]:
        """提取请求体信息"""
        if 'requestBody' not in operation:
            # 兼容 Swagger 2.0: body parameter
            for param in operation.get('parameters', []):
                if isinstance(param, dict) and param.get('in') == 'body':
                    schema = param.get('schema', {})
                    example = OpenAPIParser.extract_schema_example(spec, schema)
                    return {
                        'content_type': 'application/json',
                        'schema': schema,
                        'example': example,
                        'description': param.get('description', ''),
                        'required': param.get('required', False),
                    }
            return None

        request_body = operation['requestBody']
        if isinstance(request_body, dict) and '$ref' in request_body:
            resolved = OpenAPIParser.resolve_ref(spec, request_body['$ref'])
            if resolved:
                request_body = resolved

        content = request_body.get('content', {})

        # 优先处理 application/json
        json_content = content.get('application/json') or content.get('*/*')
        if json_content:
            schema = json_content.get('schema', {})
            example = json_content.get('example')
            if example is None and isinstance(schema, dict):
                example = OpenAPIParser.extract_schema_example(spec, schema)
            if example is None:
                example = {}
            return {
                'content_type': 'application/json',
                'schema': schema,
                'example': example,
                'description': request_body.get('description', ''),
                'required': request_body.get('required', False),
            }

        # 处理 form-data / x-www-form-urlencoded
        for ct in ['application/x-www-form-urlencoded', 'multipart/form-data']:
            if ct in content:
                schema = content[ct].get('schema', {})
                example = OpenAPIParser.extract_schema_example(spec, schema)
                return {
                    'content_type': ct,
                    'schema': schema,
                    'example': example or {},
                    'description': request_body.get('description', ''),
                    'required': request_body.get('required', False),
                }

        # 兜底：取第一个 content type
        if content:
            first_ct = list(content.keys())[0]
            schema = content[first_ct].get('schema', {})
            example = OpenAPIParser.extract_schema_example(spec, schema)
            return {
                'content_type': first_ct,
                'schema': schema,
                'example': example or {},
                'description': request_body.get('description', ''),
                'required': request_body.get('required', False),
            }

        return None

    @staticmethod
    def extract_endpoints(spec: dict) -> list[dict]:
        """从 OpenAPI spec 中提取所有端点"""
        endpoints = []
        paths = spec.get('paths', {})

        if not paths:
            return endpoints

        http_methods = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace'}

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # 提取 path 级别的公共 parameters
            for method in path_item:
                if method.lower() not in http_methods:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                method_upper = method.upper()
                summary = operation.get('summary', '')
                description = operation.get('description', '')
                operation_id = operation.get('operationId', '')
                tags = operation.get('tags', [])

                # 生成名称
                name = summary or operation_id or f"{method_upper} {path}"

                # 提取参数
                parameters = OpenAPIParser.extract_parameters(spec, operation, path_item)

                # 提取请求体
                request_body = OpenAPIParser.extract_request_body(spec, operation)

                # 提取安全要求
                security = operation.get('security', spec.get('security', []))

                endpoint = {
                    'path': path,
                    'method': method_upper,
                    'summary': summary,
                    'description': description,
                    'operation_id': operation_id,
                    'tags': tags,
                    'parameters': parameters,
                    'request_body': request_body,
                    'security': security,
                    'name': name,
                }

                endpoints.append(endpoint)

        return endpoints

    @staticmethod
    def endpoint_to_request_data(endpoint: dict, base_url: str = '') -> dict:
        """将单个端点转换为 ApiRequest 创建所需的数据（使用 RequestConverter）"""
        from .openapi import RequestConverter
        converter = RequestConverter()
        auth_headers = endpoint.get('_auth_headers', [])
        return converter.convert(endpoint, auth_headers, base_url)

    @staticmethod
    def import_to_collection(endpoints: list[dict], collection_id: int, user,
                             base_url: str = '', by_tag: bool = False) -> int:
        """批量导入端点到 Collection，支持按 tag 创建子 Collection"""
        parent_collection = ApiCollection.objects.get(id=collection_id)
        created_count = 0

        with transaction.atomic():
            if by_tag:
                tag_groups = {}
                for ep in endpoints:
                    tags = ep.get('tags', [])
                    tag_key = tags[0] if tags else 'default'
                    if tag_key not in tag_groups:
                        tag_groups[tag_key] = []
                    tag_groups[tag_key].append(ep)

                for tag, tag_endpoints in tag_groups.items():
                    sub = ApiCollection.objects.create(
                        name=tag,
                        project=parent_collection.project,
                        parent=parent_collection,
                    )
                    for i, ep in enumerate(tag_endpoints):
                        rd = OpenAPIParser.endpoint_to_request_data(ep, base_url)
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
                        created_count += 1
            else:
                for i, ep in enumerate(endpoints):
                    rd = OpenAPIParser.endpoint_to_request_data(ep, base_url)
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
                    created_count += 1

        logger.info(f"Imported {created_count} requests to collection {collection_id}, by_tag={by_tag}")
        # Debug: 输出第一个请求的数据样例
        if endpoints and created_count > 0:
            first = OpenAPIParser.endpoint_to_request_data(endpoints[0], base_url)
            logger.info(f"Sample request: method={first['method']}, url={first['url']}, "
                        f"headers_count={len(first['headers'])}, params_count={len(first['params'])}, "
                        f"body_type={first['body']['type']}, body_data_keys={list(first['body']['data'].keys()) if isinstance(first['body']['data'], dict) else 'not_dict'}")
        return created_count

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

        spec_version = OpenAPIParser.detect_spec_version(spec)
        info = spec.get('info', {})

        # 为每个端点挂载 auth headers
        for ep in endpoints:
            op_id = ep.get('operation_id', '')
            ep['_auth_headers'] = auth_info['by_operation_id'].get(op_id) or auth_info['global']

        # 统计信息
        endpoints_with_body = [e for e in endpoints if e.get('request_body')]
        logger.info(
            f"Parsed {len(endpoints)} endpoints, "
            f"{len(endpoints_with_body)} with request body, "
            f"spec: {spec_version}, base_url: {base_url}"
        )

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
            'spec_version': spec_version,
            'title': info.get('title', 'Untitled API'),
            'description': info.get('description', ''),
            'version': info.get('version', ''),
            'base_url': base_url,
            'endpoints': endpoints,
            'tags': sorted(list(all_tags)),
            'endpoint_count': len(endpoints),
            'groups': groups,
        }


# 存储生成任务状态的字典（key: task_id, value: {status, progress, result, ...}）
_generation_tasks = {}


class ApiTestCaseGenerator:
    """使用 AI 为选中的 ApiRequest 生成测试用例变体"""

    @staticmethod
    def build_prompt(requests_data: list[dict]) -> str:
        """构建 AI prompt"""
        requests_json = json.dumps(requests_data, ensure_ascii=False, indent=2)

        system_prompt = """你是一个专业的API接口测试专家。你的任务是根据给定的API接口定义，生成多种场景的测试用例。

对每个接口，你需要生成以下类型的测试用例：
1. **正向用例**：使用合法的参数值，验证接口正常返回（期望200/201等成功状态码）
2. **异常用例**：使用缺失必填参数、错误类型等，验证接口返回错误（期望400/404等）
3. **边界值用例**：使用空值、超长字符串、特殊字符等边界值，验证接口的健壮性

请严格按以下JSON格式输出，每个接口对应一个数组：

```json
{
  "test_cases": {
    "<request_id>": [
      {
        "name": "用例名称（描述场景，如：创建用户-正向验证）",
        "params_override": {"key": "value"},
        "body_override": {"key": "value"},
        "assertions": [
          {"type": "status_code", "operator": "equals", "expected": 200},
          {"type": "json_path", "operator": "exists", "path": "$.id"},
          {"type": "json_path", "operator": "equals", "path": "$.name", "expected": "Buddy"}
        ]
      }
    ]
  }
}
```

断言类型说明：
- type: "status_code" - 验证HTTP状态码
- type: "json_path" - 验证JSON响应体中的字段
- operator: "equals", "not_equals", "contains", "exists", "not_exists", "greater_than", "less_than"
- path: JSONPath表达式（如 $.data.id, $.code）

注意：
- params_override 和 body_override 只需要包含需要覆盖的字段，未覆盖的字段保持原样
- 每个接口至少生成3条用例（正向、异常、边界值各至少1条）
- 断言必须具体、可验证"""

        user_message = f"""请为以下API接口生成测试用例：

{requests_json}

请为每个接口生成正向用例、异常用例和边界值用例，严格按照JSON格式返回。"""

        return system_prompt, user_message

    @staticmethod
    def _call_ai(system_prompt: str, user_message: str, config) -> dict:
        """调用 AI 服务（非流式），config 可以是 AIModelConfig 或 AIServiceConfig"""
        headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json',
        }

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ]

        payload = {
            'model': config.model_name,
            'messages': messages,
            'max_tokens': config.max_tokens,
            'temperature': config.temperature,
        }

        try:
            base_url = config.base_url.rstrip('/')
            response = requests.post(
                f'{base_url}/chat/completions',
                json=payload,
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']

            # 尝试解析 JSON
            try:
                # 提取 JSON 部分（可能包裹在 markdown 代码块中）
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
                if json_match:
                    content = json_match.group(1).strip()
                return json.loads(content)
            except (json.JSONDecodeError, KeyError):
                logger.warning(f"Failed to parse AI response as JSON: {content[:200]}")
                return {'raw_content': content, 'test_cases': {}}

        except requests.exceptions.Timeout:
            raise Exception('AI 服务请求超时')
        except requests.exceptions.RequestException as e:
            raise Exception(f'AI 服务请求失败: {str(e)}')

    @staticmethod
    def generate(request_ids: list[int], config_id: int, user) -> str:
        """启动生成任务，返回 task_id"""
        task_id = f"APITASK_{uuid.uuid4().hex[:8].upper()}"

        # 初始化任务状态
        _generation_tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'result': None,
            'error': None,
        }

        # 启动后台线程
        thread = threading.Thread(
            target=ApiTestCaseGenerator._run_generation,
            args=(task_id, request_ids, config_id, user),
            daemon=True,
        )
        thread.start()

        return task_id

    @staticmethod
    def _run_generation(task_id: str, request_ids: list[int], config_id: int, user):
        """后台执行生成任务"""
        try:
            _generation_tasks[task_id]['status'] = 'generating'
            _generation_tasks[task_id]['progress'] = 10

            # 获取请求数据
            requests_qs = ApiRequest.objects.filter(id__in=request_ids)
            requests_data = []
            for req in requests_qs:
                requests_data.append({
                    'id': req.id,
                    'name': req.name,
                    'method': req.method,
                    'url': req.url,
                    'headers': req.headers,
                    'params': req.params,
                    'body': req.body,
                    'description': req.description,
                })

            _generation_tasks[task_id]['progress'] = 30

            # 获取 AI 配置（从 requirement_analysis.AIModelConfig 查找）
            if config_id:
                from apps.requirement_analysis.models import AIModelConfig
                config = AIModelConfig.objects.get(id=config_id)
            else:
                from apps.requirement_analysis.models import AIModelConfig
                config = AIModelConfig.objects.filter(
                    role='api_testcase_generator', is_active=True
                ).first()
                if not config:
                    raise Exception('未找到可用的 AI 配置（role=api_testcase_generator, is_active=True）')

            _generation_tasks[task_id]['progress'] = 50

            # 构建 prompt 并调用 AI
            system_prompt, user_message = ApiTestCaseGenerator.build_prompt(requests_data)
            result = ApiTestCaseGenerator._call_ai(system_prompt, user_message, config)

            _generation_tasks[task_id]['progress'] = 90
            _generation_tasks[task_id]['result'] = result
            _generation_tasks[task_id]['status'] = 'completed'
            _generation_tasks[task_id]['progress'] = 100

        except Exception as e:
            logger.exception(f"Generation task {task_id} failed")
            _generation_tasks[task_id]['status'] = 'failed'
            _generation_tasks[task_id]['error'] = str(e)
            _generation_tasks[task_id]['progress'] = 0

    @staticmethod
    def get_progress(task_id: str) -> Optional[dict]:
        """查询生成进度"""
        return _generation_tasks.get(task_id)

    @staticmethod
    def save_generated_cases(task_id: str, selected_cases: list[dict],
                             user, suite_name: str = None, collection_id: int = None,
                             project_id: int = None) -> dict:
        """将选中的生成用例保存为 ApiRequest 记录"""
        task = _generation_tasks.get(task_id)
        if not task or task['status'] != 'completed':
            raise Exception('生成任务未完成或不存在')

        created_count = 0
        suite = None

        # 获取 collection
        collection = None
        if collection_id:
            collection = ApiCollection.objects.get(id=collection_id)

        with transaction.atomic():
            if suite_name and project_id:
                suite = TestSuite.objects.create(
                    name=suite_name,
                    project_id=project_id,
                    created_by=user,
                )

            for case in selected_cases:
                request_id = case.get('request_id')
                parent_request = ApiRequest.objects.get(id=request_id)

                # 获取原始请求数据作为基础
                headers = parent_request.headers
                params = dict(parent_request.params) if isinstance(parent_request.params, dict) else {}
                body = dict(parent_request.body) if isinstance(parent_request.body, dict) else {'type': 'json', 'data': {}}

                # 覆盖参数
                if case.get('params_override'):
                    if isinstance(params, list):
                        for override_key, override_value in case['params_override'].items():
                            for p in params:
                                if p.get('key') == override_key:
                                    p['value'] = str(override_value)
                    else:
                        params.update(case['params_override'])

                # 覆盖请求体
                if case.get('body_override'):
                    if isinstance(body, dict):
                        if 'data' in body and isinstance(body['data'], dict):
                            body['data'] = {**body['data'], **case['body_override']}
                        else:
                            body = {'type': 'json', 'data': case['body_override']}

                # 创建新请求
                new_request = ApiRequest.objects.create(
                    collection=collection or parent_request.collection,
                    parent_request=parent_request,
                    name=case.get('name', f'{parent_request.name} - 测试用例'),
                    method=parent_request.method,
                    url=parent_request.url,
                    headers=headers,
                    params=params,
                    body=body,
                    description=f'AI 生成的测试用例\n原始请求: {parent_request.name}',
                    assertions=case.get('assertions', []),
                    request_type=parent_request.request_type,
                    created_by=user,
                )

                # 关联到测试套件
                if suite:
                    from apps.api_testing.models import TestSuiteRequest
                    TestSuiteRequest.objects.create(
                        test_suite=suite,
                        request=new_request,
                        order=created_count,
                        assertions=case.get('assertions', []),
                    )

                created_count += 1

        return {
            'created_count': created_count,
            'suite_id': suite.id if suite else None,
            'suite_name': suite.name if suite else None,
        }