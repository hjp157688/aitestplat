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
            # Swagger 2.0: body/formData 参数归入 request_body，不重复列为普通参数
            if param_in in ('body', 'formData'):
                continue
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
            return self._extract_swagger2_body(operation)

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

    def _extract_swagger2_body(self, operation: dict) -> dict | None:
        """Swagger 2.0: in:body / in:formData 参数 → request_body"""
        parameters = operation.get('parameters', [])
        if not isinstance(parameters, list):
            return None

        body_params = [p for p in parameters
                       if isinstance(p, dict) and p.get('in') == 'body']
        if body_params:
            body_param = body_params[0]
            schema = body_param.get('schema', {})
            example = generate_example(schema) if schema else {}
            return {
                'content_type': 'application/json',
                'schema': schema,
                'example': example if example is not None else {},
                'required': body_param.get('required', False),
                'description': body_param.get('description', ''),
            }

        form_params = [p for p in parameters
                       if isinstance(p, dict) and p.get('in') == 'formData']
        if form_params:
            consumes = operation.get('consumes', [])
            if any('multipart' in c for c in consumes):
                content_type = 'multipart/form-data'
            else:
                content_type = 'application/x-www-form-urlencoded'

            properties = {}
            required = []
            for p in form_params:
                name = p.get('name', '')
                prop = {}
                if p.get('type'):
                    prop['type'] = p['type']
                if p.get('format'):
                    prop['format'] = p['format']
                if p.get('enum') is not None:
                    prop['enum'] = p['enum']
                if p.get('default') is not None:
                    prop['default'] = p['default']
                properties[name] = prop
                if p.get('required'):
                    required.append(name)

            schema = {'type': 'object', 'properties': properties}
            if required:
                schema['required'] = required

            example = generate_example(schema)
            return {
                'content_type': content_type,
                'schema': schema,
                'example': example if example is not None else {},
                'required': bool(required),
                'description': '',
            }

        return None

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
        """提取响应 JSON Schema，按 status code 索引（兼容 OpenAPI 3 / Swagger 2.0）"""
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
                    continue
            # Swagger 2.0: schema 直接挂在 response 下
            schema = response.get('schema')
            if schema:
                result[str(status_code)] = schema
        return result