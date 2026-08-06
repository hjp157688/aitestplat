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


def request_body_kwargs(body_type, body_content) -> dict:
    """把解析后的 body 组装成 requests.request 的发送参数。

    - x-www-form-urlencoded：列表 → data dict（requests 会按 urlencoded 编码）
    - form-data：列表 → files（multipart 文本字段）
    - raw：字符串原样 → data
    - 其余（json 等）：→ json
    """
    if body_type == 'x-www-form-urlencoded':
        enabled = [it for it in (body_content or []) if it.get('enabled', True) and it.get('key')]
        return {'data': {it['key']: it.get('value') or '' for it in enabled}}
    if body_type == 'form-data':
        enabled = [it for it in (body_content or []) if it.get('enabled', True) and it.get('key')]
        return {'files': {it['key']: (None, it.get('value') or '') for it in enabled}}
    if body_type == 'raw':
        return {'data': body_content}
    return {'json': body_content}


def execute_assertions(response, assertions):
    """执行断言验证"""
    results = []
    
    for assertion in assertions:
        result = {
            'name': assertion.get('name', '未命名断言'),
            'type': assertion.get('type'),
            'passed': False,
            'expected': assertion.get('expected'),
            'actual': None,
            'error': None
        }
        
        try:
            assertion_type = assertion.get('type')
            expected = assertion.get('expected')
            actual = None
            passed = False
            
            if assertion_type == 'status_code':
                actual = response.status_code
                passed = actual == expected
                
            elif assertion_type == 'response_time':
                # 响应时间断言在调用方处理
                actual = assertion.get('actual_time')
                passed = actual <= expected if actual else False
                
            elif assertion_type == 'contains':
                text = response.text or ''
                pattern = str(expected)
                actual = text[:200] + '...' if len(text) > 200 else text
                passed = pattern in str(text)
                
            elif assertion_type == 'json_path':
                json_path = assertion.get('json_path', '')
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
                    passed = str(actual) == str(expected_value)
                    
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
                expected_value = assertion.get('expected_value')
                actual = response.headers.get(header_name)
                passed = actual == expected_value
                
            elif assertion_type == 'equals':
                actual = response.text.strip()
                passed = actual == str(expected).strip()
            
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
                params = api_request.params.copy() if api_request.params else {}
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
        params = api_request.params.copy() if api_request.params else {}
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
