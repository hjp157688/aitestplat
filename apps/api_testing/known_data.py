"""接口自动化用例生成的"已知数据"采集与池化。

数据源：
1. 环境变量 Environment.variables（指定环境，或项目激活环境）
2. 手动登记 ApiKnownData（Task 1）
3. 历史成功执行 RequestHistory（近 30 天、2xx，提炼关键字段）
仅供生成 prompt 与保存回填使用，不参与运行时解析。
"""
import json
import logging
from datetime import timedelta

from django.utils import timezone

from .models import ApiKnownData, Environment, RequestHistory

logger = logging.getLogger(__name__)


def collect_known_data(project_id, environment_id=None, history_limit=20):
    """采集项目已知数据。返回 {environment, known_data, history}。"""
    env_vars = _collect_environment(project_id, environment_id)

    known_data = []
    if project_id:
        rows = ApiKnownData.objects.filter(project_id=project_id).order_by('name')
        known_data = [{'name': r.name, 'value': r.value, 'description': r.description} for r in rows]

    history = _collect_history(project_id, history_limit)

    return {
        'environment': env_vars,
        'known_data': known_data,
        'history': history,
    }


def _collect_environment(project_id, environment_id):
    env_vars = {}
    env = None
    if environment_id:
        filter_kwargs = {'id': environment_id}
        if project_id is not None:
            filter_kwargs['project_id'] = project_id
        env = Environment.objects.filter(**filter_kwargs).first()
    elif project_id:
        env = (Environment.objects.filter(project_id=project_id, scope='LOCAL', is_active=True).first()
               or Environment.objects.filter(scope='GLOBAL', is_active=True).first())
    if env and env.variables:
        env_vars = {k: _stringify(v) for k, v in env.variables.items()}
    return env_vars


def _collect_history(project_id, limit=20):
    if not project_id:
        return []
    cutoff = timezone.now() - timedelta(days=30)
    qs = (RequestHistory.objects
          .select_related('request')
          .filter(request__collection__project_id=project_id,
                  status_code__gte=200, status_code__lt=300,
                  executed_at__gte=cutoff,
                  response_data__isnull=False)
          .order_by('-executed_at')[:limit])
    samples = []
    for h in qs:
        fields = {}
        fields.update(_extract_request_fields(h.request_data))
        fields.update(_extract_response_fields(h.response_data))
        if not fields:
            continue
        samples.append({
            'request': f"{h.request.method} {h.request.name}",
            'fields': fields,
        })
    return samples


def _stringify(v):
    if v is None:
        return ''
    if isinstance(v, dict):
        return str(v.get('currentValue') or v.get('initialValue') or v)
    return str(v)


def _extract_fields(data, max_fields=8, prefix=''):
    """从（可能嵌套的）dict 提取标量字段，键名去前缀，长字符串丢弃。"""
    if not isinstance(data, dict):
        return {}
    out = {}
    for k, v in data.items():
        if len(out) >= max_fields:
            break
        key = f"{prefix}{k}".lstrip('.')
        if isinstance(v, dict):
            out.update(_extract_fields(v, max_fields - len(out), ''))
        elif isinstance(v, bool):
            out[key] = str(v).lower()
        elif isinstance(v, (int, float)):
            out[key] = str(v)
        elif isinstance(v, str) and 0 < len(v) <= 64 and not v.startswith('{') and not v.startswith('<'):
            out[key] = v
    return out


def _extract_request_fields(request_data, max_fields=4):
    data = (request_data or {}).get('params') or {}
    out = {}
    if isinstance(data, dict):
        out.update(_extract_fields({k: v for k, v in data.items() if k not in ('token', 'password')}, max_fields=max_fields))
    body = (request_data or {}).get('body')
    if isinstance(body, dict):
        body_data = body.get('data') if isinstance(body, dict) else body
        out.update(_extract_fields(body_data, max_fields=max_fields))
    return out


def _extract_response_fields(response_data, max_fields=8):
    if not isinstance(response_data, dict):
        return {}
    json_data = response_data.get('json')
    if isinstance(json_data, dict):
        return _extract_fields(json_data, max_fields=max_fields)
    body = response_data.get('body')
    if isinstance(body, str) and len(body) < 4000:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return _extract_fields(parsed, max_fields=max_fields)
        except (ValueError, TypeError):
            pass
    return {}


def build_known_data_prompt(known_data):
    """把 known_data 转成拼进 user_message 的中文文本。"""
    lines = ['【项目已知数据】（优先使用以下真实值，禁止编造）']
    env = known_data.get('environment') or {}
    if env:
        lines.append('1. 环境变量：')
        for k, v in list(env.items())[:30]:
            lines.append(f'   - {k} = {v}')
    kd = known_data.get('known_data') or []
    if kd:
        lines.append('2. 已登记测试数据：')
        for item in kd[:50]:
            desc = f'（{item.get("description", "")}）' if item.get('description') else ''
            lines.append(f'   - {item["name"]} = {item["value"]}{desc}')
    hist = known_data.get('history') or []
    if hist:
        lines.append('3. 历史成功请求样例：')
        for sample in hist[:10]:
            flds = '，'.join(f'{k}={v}' for k, v in list(sample['fields'].items())[:8])
            lines.append(f'   - {sample["request"]}：{flds}')
    return '\n'.join(lines)


def flatten_pool(known_data):
    """把三个数据源拍平成 {变量名: 值}，供保存时回填用例级变量。"""
    pool = dict(known_data.get('environment') or {})
    for item in known_data.get('known_data') or []:
        pool[item['name']] = item['value']
    for sample in known_data.get('history') or []:
        pool.update(sample['fields'])
    return pool