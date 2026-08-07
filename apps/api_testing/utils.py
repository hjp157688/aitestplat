import json
import re
import time
from django.utils import timezone
from .models import RequestHistory
from .variable_resolver import VariableResolver


def merge_variables(env_variables, case_variables):
    """用例级变量优先，环境变量兜底。"""
    env = dict(env_variables) if env_variables else {}
    case = dict(case_variables) if case_variables else {}
    return {**env, **case}


def _base_url_from_variables(variables) -> str:
    """大小写不敏感地取环境变量里的 base URL（base_url / baseUrl / Base-Url 等）。"""
    for key, value in (variables or {}).items():
        norm = re.sub(r'[^a-z0-9]', '', str(key).lower())
        if norm == 'baseurl':
            if isinstance(value, dict):
                # 环境变量支持 {currentValue, initialValue} 结构，取当前值
                return str(value.get('currentValue') or value.get('initialValue') or '')
            return str(value) if value is not None else ''
    return ''


def normalize_base_url(url, variables) -> str:
    """URL 规范化：去掉可能残留的 {{baseurl}} 占位（任意大小写），缺 scheme 时用环境 base 补齐。

    若 URL 仍无 scheme 且环境没有 base → 抛中文可读异常（替代 requests 的
    MissingSchema，让"请求没发出去"的原因一目了然）。
    """
    if url is None:
        url = ''
    url = str(url)
    base = _base_url_from_variables(variables)
    # 老数据可能存了 {{baseUrl}}，_replace_variables 按 key 精确匹配不会替换，
    # 这里先剥掉大小写不敏感的 {{baseurl}} 占位
    cleaned = re.sub(r'\{\{\s*baseurl\s*\}\}', '', url, flags=re.IGNORECASE)
    if '://' in cleaned:
        return cleaned
    if base:
        return f"{base.rstrip('/')}/{cleaned.lstrip('/')}"
    raise Exception(
        '请求 URL 缺少协议(http/https)且未配置 base_url 环境变量，无法发送。'
        '请在所选环境中配置 base_url，或在请求 URL 里填写完整地址（如 https://host/path）。')


def _params_to_dict(params):
    """归一化 query 参数：行数组或字典 → {key: value}（仅启用且有 key 的行）。

    前端保存/导入会以行数组（[{key,value,enabled,description,param_type,required}]）
    持久化 params，执行链的 DB 兜底需要此归一化；字典形态原样返回。
    """
    if isinstance(params, dict):
        return dict(params)
    result = {}
    for row in (params or []):
        if isinstance(row, dict) and row.get('enabled', True) and row.get('key'):
            result[row['key']] = row.get('value') or ''
    return result


def _replace_path_params(url, path_params, variables, resolver):
    """把 URL 里的 {name} 路径参数模板替换成 path_params 行值。

    - 负向后视 (?<!\{) 只匹配单花括号 {name}，绝不破坏 {{var}} / {{{...}}} 序列；
    - 参数值本身先做变量替换与函数解析（支持 {{var}} / ${func()}）；
    - 仅替换启用且值非空的行；没有对应行的占位符原样保留（避免误删 token）。
    """
    if not isinstance(url, str) or not path_params:
        return url
    if isinstance(path_params, dict):
        mapping = dict(path_params)
    else:
        mapping = {}
        for row in (path_params or []):
            if isinstance(row, dict) and row.get('enabled', True) and row.get('key'):
                mapping[row['key']] = row.get('value')
    result = url
    for key, value in mapping.items():
        raw = str(value or '')
        if not key or not raw:
            continue
        resolved = resolver.resolve(_replace_variables(raw, variables))
        if resolved == '':
            continue
        # 负向后视 (?<!\{) 只匹配 {key}，不碰 {{var}} / {{{...}}}；
        # 用函数替换避免替换串里的 $ / \ 被当作 re 组展开
        pattern = r'(?<!\{)\{' + re.escape(key) + r'\}'
        result = re.sub(pattern, lambda m: resolved, result)
    return result


def request_body_kwargs(body_type, body_content) -> dict:
    """把解析后的 body 组装成 requests.request 的发送参数。

    - x-www-form-urlencoded：列表 → data dict（requests 会按 urlencoded 编码）
    - form-data：列表 → files（multipart 文本字段）
    - raw：字符串原样 → data
    - 其余（json 等）：→ json

    兼容历史导入的字典格式 body（{"key": "value"}），统一转成行列表再处理。
    """
    if body_type in ('x-www-form-urlencoded', 'form-data'):
        if isinstance(body_content, dict):
            body_content = [
                {'key': k, 'value': str(v), 'enabled': True}
                for k, v in body_content.items()
            ]
    if body_type == 'x-www-form-urlencoded':
        enabled = [it for it in (body_content or []) if it.get('enabled', True) and it.get('key')]
        return {'data': {it['key']: it.get('value') or '' for it in enabled}}
    if body_type == 'form-data':
        enabled = [it for it in (body_content or []) if it.get('enabled', True) and it.get('key')]
        return {'files': {it['key']: (None, it.get('value') or '') for it in enabled}}
    if body_type == 'raw':
        return {'data': body_content}
    return {'json': body_content}


# 断言支持的 JSONPath 操作符（AI 生成格式与系统执行语义统一）
JSON_PATH_OPERATOR_CN = {
    'equals': '等于',
    'not_equals': '不等于',
    'contains': '包含',
    'not_contains': '不包含',
    'exists': '存在',
    'not_exists': '不存在',
    'greater_than': '大于',
    'less_than': '小于',
    'greater_or_equal': '大于等于',
    'less_or_equal': '小于等于',
}


def _values_equal(actual, expected):
    """宽松相等：数值按数值比，其余按字符串比，布尔不误等数字。"""
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return str(actual) == str(expected)
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return str(actual) == str(expected)


def _compare(actual, expected, operator):
    """按操作符比较 actual/expected；数值类操作符尽力转 float。"""
    operator = operator or 'equals'
    if operator == 'equals':
        return _values_equal(actual, expected)
    if operator == 'not_equals':
        return not _values_equal(actual, expected)
    if operator == 'contains':
        return expected is not None and str(expected) in str(actual if actual is not None else '')
    if operator == 'not_contains':
        return not (expected is not None and str(expected) in str(actual if actual is not None else ''))
    try:
        a = float(actual)
        e = float(expected)
    except (TypeError, ValueError):
        return False
    if operator == 'greater_than':
        return a > e
    if operator == 'less_than':
        return a < e
    if operator == 'greater_or_equal':
        return a >= e
    if operator == 'less_or_equal':
        return a <= e
    return False


def describe_assertion(assertion: dict) -> str:
    """根据断言字段生成可读名称（name 缺失时兜底）。"""
    a_type = assertion.get('type') or ''
    op = assertion.get('operator') or 'equals'
    op_cn = JSON_PATH_OPERATOR_CN.get(op, op)
    if a_type == 'status_code':
        return f'状态码{op_cn}{assertion.get("expected", "")}'
    if a_type == 'response_time':
        return f'响应时间不超过 {assertion.get("expected", "")}ms'
    if a_type == 'json_path':
        path = assertion.get('json_path') or assertion.get('path') or ''
        if op in ('exists', 'not_exists'):
            return f'JSON {path} {op_cn}'.strip()
        return (f'JSON {path} {op_cn} {assertion.get("expected", "")}').strip()
    if a_type == 'header':
        name = assertion.get('header_name') or assertion.get('path') or ''
        val = assertion.get('expected_value', assertion.get('expected', ''))
        return (f'响应头 {name} {op_cn} {val}').strip()
    if a_type == 'contains':
        return f'响应包含 {assertion.get("expected", "")}'
    if a_type == 'equals':
        return f'响应等于 {assertion.get("expected", "")}'
    return (f'{a_type} {op_cn} {assertion.get("json_path") or assertion.get("path") or ""} '
            f'{assertion.get("expected", "")}').strip()


def normalize_assertions(assertions) -> list:
    """把 AI/外部输入的断言统一成系统 schema，幂等。

    AI 生成格式：{"type","operator","path","expected"}（见 API_TESTCASE_GENERATOR_PROMPT）
    系统 schema ：{"name","type","json_path","operator","expected"}（接口编辑器 + execute_assertions）
    这里做：path→json_path、补 name、operator 默认 equals。修复"生成用例断言
    存储后 json_path 为空、name 为空、operator 语义丢失"的问题。
    """
    normalized = []
    for a in assertions or []:
        if not isinstance(a, dict):
            continue
        out = dict(a)
        a_type = out.get('type')
        if a_type == 'json_path':
            if not out.get('json_path') and out.get('path'):
                out['json_path'] = str(out.pop('path', '')) or ''
            out.pop('path', None)
        elif a_type == 'header':
            if not out.get('header_name') and out.get('path'):
                out['header_name'] = str(out.pop('path', '')) or ''
            if out.get('expected_value') is None and out.get('expected') is not None:
                out['expected_value'] = out['expected']
        op = out.get('operator') or 'equals'
        if op not in JSON_PATH_OPERATOR_CN:
            op = 'equals'
        out['operator'] = op
        if not out.get('name'):
            out['name'] = describe_assertion(out)
        normalized.append(out)
    return normalized


def execute_assertions(response, assertions):
    """执行断言验证"""
    results = []

    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        assertion_type = assertion.get('type')
        expected = assertion.get('expected')
        operator = assertion.get('operator') or 'equals'
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion_type,
            'passed': False,
            'expected': expected,
            'actual': None,
            'error': None
        }

        try:
            actual = None
            passed = False

            if assertion_type == 'status_code':
                actual = response.status_code
                passed = _compare(actual, expected, operator)

            elif assertion_type == 'response_time':
                # 响应时间断言在调用方处理（actual_time 由调用方写入）
                actual = assertion.get('actual_time')
                # 默认语义"不超过期望时间"
                passed = _compare(actual, expected, operator if operator != 'equals' else 'less_or_equal')

            elif assertion_type == 'contains':
                text = response.text or ''
                pattern = str(expected)
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = pattern in str(text)

            elif assertion_type == 'json_path':
                # 兼容 AI 生成的 path 字段以及归一化后的 json_path 字段
                json_path = assertion.get('json_path', '') or assertion.get('path', '')
                expected_value = assertion.get('expected')
                actual = None
                passed = False

                try:
                    # 检查响应是否为JSON格式
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        raise ValueError(f"响应不是JSON格式，Content-Type: {content_type}")

                    response_json = json.loads(response.text)

                    # 检查JSONPath表达式是否为空
                    if not json_path:
                        raise ValueError("JSON路径表达式不能为空")

                    from jsonpath_ng import parse
                    matches = parse(json_path).find(response_json)
                    actual = matches[0].value if matches else None
                    if operator in ('exists', 'not_exists'):
                        # 存在性断言不需要期望值
                        exists = bool(matches)
                        passed = exists if operator == 'exists' else (not exists)
                    else:
                        passed = _compare(actual, expected_value, operator)

                    # 确保actual值被正确设置到result中
                    result['actual'] = actual
                except json.JSONDecodeError as e:
                    actual = None
                    passed = False
                    result['error'] = f"JSON解析失败: {str(e)}"
                    result['actual'] = actual
                except ImportError as e:
                    actual = None
                    passed = False
                    result['error'] = f"缺少依赖库: {str(e)}，请安装jsonpath-ng"
                    result['actual'] = actual
                except Exception as e:
                    actual = None
                    passed = False
                    result['error'] = f"执行错误: {str(e)}"
                    result['actual'] = actual

            elif assertion_type == 'header':
                header_name = assertion.get('header_name', '')
                expected_value = assertion.get('expected_value', assertion.get('expected'))
                actual = response.headers.get(header_name)
                passed = _compare(actual, expected_value, operator)

            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = _values_equal(actual, str(expected).strip() if expected is not None else None)
            
            # 确保在所有情况下都设置actual值
            if 'actual' not in result or result['actual'] is None:
                result['actual'] = actual
            result['passed'] = passed
            
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
        
        results.append(result)
    
    return results


def execute_test_suite(test_suite, environment, executed_by):
    """执行测试套件并返回结果"""
    from .models import TestExecution, RequestHistory
    import requests
    import time
    
    try:
        # 创建变量解析器
        resolver = VariableResolver()
        
        # 创建执行记录
        execution = TestExecution.objects.create(
            test_suite=test_suite,
            status='RUNNING',
            start_time=timezone.now(),
            executed_by=executed_by
        )
        
        # 获取套件中的请求
        suite_requests = test_suite.testsuiterequest_set.filter(enabled=True).order_by('order')
        
        execution.total_requests = suite_requests.count()
        execution.save()
        
        results = []
        passed_count = 0
        failed_count = 0
        
        # 执行每个请求
        for suite_request in suite_requests:
            api_request = suite_request.request
            
            try:
                # 解析环境变量
                variables = {}
                if environment:
                    variables.update(environment.variables)

                # 用例级变量优先于环境变量
                variables = merge_variables(variables, getattr(api_request, 'variables', None) or {})

                # 替换URL中的变量（先解析动态函数，再替换环境变量）
                url = _replace_variables(api_request.url, variables)
                url = resolver.resolve(url)
                # 替换路径参数 {name}（值来自 path_params 行）
                url = _replace_path_params(
                    url, getattr(api_request, 'path_params', None), variables, resolver)
                # 缺 scheme 时自动用环境 base_url 补齐；仍无 base 则抛出清晰错误
                url = normalize_base_url(url, variables)
                
                # 准备请求头
                headers = {}
                if isinstance(api_request.headers, list):
                    for header_item in api_request.headers:
                        if header_item.get('enabled', True) and header_item.get('key'):
                            key = header_item['key']
                            value = _replace_variables(str(header_item.get('value', '')), variables)
                            value = resolver.resolve(value)
                            headers[key] = value
                else:
                    headers = api_request.headers.copy()
                    for key, value in headers.items():
                        headers[key] = _replace_variables(str(value), variables)
                        headers[key] = resolver.resolve(headers[key])
                
                # 准备请求参数
                params = _params_to_dict(api_request.params)
                for key, value in params.items():
                    params[key] = _replace_variables(str(value), variables)
                    params[key] = resolver.resolve(params[key])
                
                # 准备请求体（按 body type 正确处理 urlencoded/form-data/raw/json）
                body_data = None
                body_type = 'none'
                if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
                    body_type = api_request.body.get('type', 'none')
                    body_content = api_request.body.get('data')
                    if body_type == 'json':
                        if isinstance(body_content, dict):
                            body_data = _replace_variables_in_dict(body_content, variables)
                            body_data = _resolve_variables_in_dict(body_data, resolver)
                        else:
                            body_data = body_content
                    elif body_type == 'raw':
                        if isinstance(body_content, str):
                            body_data = _replace_variables(body_content, variables)
                            body_data = resolver.resolve(body_data)
                        else:
                            body_data = body_content
                    elif body_type in ('form-data', 'x-www-form-urlencoded'):
                        if isinstance(body_content, list):
                            body_data = _replace_variables_in_dict(body_content, variables)
                            body_data = _resolve_variables_in_dict(body_data, resolver)
                        else:
                            body_data = body_content
                    else:
                        body_data = body_content

                # 执行请求
                start_time = time.time()
                send_kwargs = request_body_kwargs(body_type, body_data)
                response = requests.request(
                    method=api_request.method,
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=30,
                    **send_kwargs
                )
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                # 执行断言验证
                assertions = api_request.assertions or []
                for assertion in assertions:
                    if assertion.get('type') == 'response_time':
                        assertion['actual_time'] = response_time
                
                assertions_results = execute_assertions(response, assertions)
                
                # 检查所有断言是否通过
                passed = True
                error_message = ''
                
                # 检查套件请求的断言
                for assertion in suite_request.assertions:
                    if assertion.get('type') == 'status_code':
                        expected = assertion.get('value')
                        if response.status_code != expected:
                            passed = False
                            error_message = f'状态码断言失败: 期望 {expected}, 实际 {response.status_code}'
                            break
                
                # 检查接口自身的断言
                if passed and assertions_results:
                    for assertion_result in assertions_results:
                        if not assertion_result.get('passed', True):
                            passed = False
                            error_message = f"断言失败: {assertion_result.get('name', '未命名断言')} - {assertion_result.get('error', '断言不通过')}"
                            break
                
                if passed:
                    passed_count += 1
                else:
                    failed_count += 1
                
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'passed': passed,
                    'error': error_message,
                    'assertions_results': assertions_results
                })
                
                # 保存请求历史
                RequestHistory.objects.create(
                    request=api_request,
                    environment=environment,
                    request_data={
                        'url': url,
                        'method': api_request.method,
                        'headers': headers,
                        '极速版params': params,
                        'body': body_data
                    },
                    response_data={
                        'headers': dict(response.headers),
                        'body': response.text,
                        'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                    },
                    status_code=response.status_code,
                    response_time=response_time,
                    assertions_results=assertions_results,
                    executed_by=executed_by
                )
                
            except Exception as e:
                failed_count += 1
                results.append({
                    'name': api_request.name,
                    'method': api_request.method,
                    'url': api_request.url,
                    'passed': False,
                    'error': str(e)
                })
        
        # 更新执行结果
        execution.end_time = timezone.now()
        execution.passed_requests = passed_count
        execution.failed_requests = failed_count
        execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
        execution.results = results
        execution.save()
        
        return {
            'success': True,
            'execution_id': execution.id,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'total_count': execution.total_requests,
            'results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def execute_api_request(api_request, environment, executed_by):
    """执行单个API请求并返回结果"""
    import requests
    import time
    
    try:
        # 创建变量解析器
        resolver = VariableResolver()
        
        # 解析环境变量
        variables = {}
        if environment:
            variables.update(environment.variables)

        # 用例级变量优先于环境变量
        variables = merge_variables(variables, getattr(api_request, 'variables', None) or {})

        # 替换URL中的变量（先解析动态函数，再替换环境变量）
        url = _replace_variables(api_request.url, variables)
        url = resolver.resolve(url)
        # 替换路径参数 {name}（值来自 path_params 行）
        url = _replace_path_params(
            url, getattr(api_request, 'path_params', None), variables, resolver)
        # 缺 scheme 时自动用环境 base_url 补齐；仍无 base 则抛出清晰错误
        url = normalize_base_url(url, variables)
        
        # 准备请求头
        headers = {}
        if isinstance(api_request.headers, list):
            for header_item in api_request.headers:
                if header_item.get('enabled', True) and header_item.get('key'):
                    key = header_item['key']
                    value = _replace_variables(str(header_item.get('value', '')), variables)
                    value = resolver.resolve(value)
                    headers[key] = value
        else:
            headers = api_request.headers.copy()
            for key, value in headers.items():
                headers[key] = _replace_variables(str(value), variables)
                headers[key] = resolver.resolve(headers[key])
        
        # 准备请求参数
        params = _params_to_dict(api_request.params)
        for key, value in params.items():
            params[key] = _replace_variables(str(value), variables)
            params[key] = resolver.resolve(params[key])
        
        # 准备请求体（按 body type 正确处理 urlencoded/form-data/raw/json）
        body_data = None
        body_type = 'none'
        if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
            body_type = api_request.body.get('type', 'none')
            body_content = api_request.body.get('data')
            if body_type == 'json':
                if isinstance(body_content, dict):
                    body_data = _replace_variables_in_dict(body_content, variables)
                    body_data = _resolve_variables_in_dict(body_data, resolver)
                else:
                    body_data = body_content
            elif body_type == 'raw':
                if isinstance(body_content, str):
                    body_data = _replace_variables(body_content, variables)
                    body_data = resolver.resolve(body_data)
                else:
                    body_data = body_content
            elif body_type in ('form-data', 'x-www-form-urlencoded'):
                if isinstance(body_content, list):
                    body_data = _replace_variables_in_dict(body_content, variables)
                    body_data = _resolve_variables_in_dict(body_data, resolver)
                else:
                    body_data = body_content
            else:
                body_data = body_content

        # 执行请求
        start_time = time.time()
        send_kwargs = request_body_kwargs(body_type, body_data)
        response = requests.request(
            method=api_request.method,
            url=url,
            headers=headers,
            params=params,
            timeout=30,
            **send_kwargs
        )
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        
        # 执行断言验证
        assertions = api_request.assertions or []
        for assertion in assertions:
            if assertion.get('type') == 'response_time':
                assertion['actual_time'] = response_time
        
        assertions_results = execute_assertions(response, assertions)
        
        # 保存请求历史
        history = RequestHistory.objects.create(
            request=api_request,
            environment=environment,
            request_data={
                'url': url,
                'method': api_request.method,
                'headers': headers,
                'params': params,
                'body': body_data
            },
            response_data={
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            },
            status_code=response.status_code,
            response_time=response_time,
            assertions_results=assertions_results,
            executed_by=executed_by
        )
        
        return {
            'success': True,
            'history_id': history.id,
            'status_code': response.status_code,
            'response_time': response_time,
            'assertions_results': assertions_results,
            'response_data': {
                'headers': dict(response.headers),
                'body': response.text,
                'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def _replace_variables(text, variables):
    """替换文本中的变量"""
    if not isinstance(text, str):
        return text
    
    result = text
    for key, value in (variables or {}).items():
        if isinstance(value, dict):
            replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
        else:
            replacement = str(value) if value is not None else ''
        result = result.replace(f'{{{{{key}}}}}', replacement)
    return result

def _replace_variables_in_dict(data, variables):
    """递归替换字典中的变量"""
    if isinstance(data, dict):
        return {k: _replace_variables_in_dict(v, variables) for k, v in data.items()}
    elif isinstance(data, list):
        return [_replace_variables_in_dict(item, variables) for item in data]
    elif isinstance(data, str):
        return _replace_variables(data, variables)
    else:
        return data

def _resolve_variables_in_dict(data, resolver):
    """递归解析字典中的动态函数占位符"""
    if isinstance(data, dict):
        return {k: _resolve_variables_in_dict(v, resolver) for k, v in data.items()}
    elif isinstance(data, list):
        return [_resolve_variables_in_dict(item, resolver) for item in data]
    elif isinstance(data, str):
        return resolver.resolve(data)
    else:
        return data
