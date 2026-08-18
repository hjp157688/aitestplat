from apps.agent.service_identity import get_service_user, resolve_project


def list_projects():
    from apps.projects.models import Project
    return [
        {'id': p.id, 'name': p.name, 'description': p.description, 'status': p.status}
        for p in Project.objects.all().order_by('-id')
    ]


def list_data_factory_tools():
    from apps.data_factory.tool_list import get_tool_list
    return [
        {'tool_name': t.get('name'), 'tool_category': t.get('scenario'),
         'display_name': t.get('display_name'), 'description': t.get('description', '')}
        for t in get_tool_list()
    ]


def generate_test_data(tool_name, tool_category, input_data):
    from apps.data_factory.views import DataFactoryViewSet
    result = DataFactoryViewSet().execute_tool(tool_name, tool_category, input_data or {})
    if 'error' in result:
        raise ValueError(result['error'])
    return result


def generate_testcases_from_text(title, requirement_text, project_id=None,
                                 case_type='', granularity='medium', output_mode=None):
    """复用 TestCaseGenerationRequestSerializer.generate 的编排：解析配置→建任务→起线程。"""
    from types import SimpleNamespace
    from apps.ai.resolver import ConfigResolver
    from apps.requirement_analysis.models import PromptConfig
    from apps.requirement_analysis.views import _create_generation_task

    user = get_service_user()
    writer_config = ConfigResolver.active(role='writer', user=user)
    if not writer_config:
        raise ValueError('未找到可用的测试用例编写模型配置')
    writer_prompt = PromptConfig.get_active_config('writer')
    if not writer_prompt:
        raise ValueError('未找到可用的测试用例编写提示词配置')
    reviewer_config = ConfigResolver.active(role='reviewer', user=user)
    reviewer_prompt = PromptConfig.get_active_config('reviewer')
    if not reviewer_config or not reviewer_prompt:
        raise ValueError('未找到可用的评审模型/提示词配置')

    task_data = {
        'title': title,
        'requirement_text': requirement_text,
        'writer_model_config': writer_config.id,
        'reviewer_model_config': reviewer_config.id,
        'writer_prompt_config': writer_prompt.id,
        'reviewer_prompt_config': reviewer_prompt.id,
        'case_type': case_type or '',
        'granularity': granularity,
    }
    if output_mode in ('stream', 'complete'):
        task_data['output_mode'] = output_mode
    if project_id:
        resolve_project(project_id)  # 校验项目存在，不存在抛 ValueError
        task_data['project'] = project_id

    task, error_response = _create_generation_task(
        task_data, [], SimpleNamespace(user=user))
    if error_response is not None:
        raise ValueError(str(getattr(error_response, 'data', error_response)))
    return {'task_id': task.task_id, 'status': task.status, 'message': '测试用例生成任务已创建'}


def get_generation_task(task_id, include_full=False):
    from apps.requirement_analysis import views as ra_views
    from apps.requirement_analysis.models import TestCaseGenerationTask
    task = TestCaseGenerationTask.objects.filter(task_id=task_id).first()
    if not task:
        raise ValueError(f'任务不存在: {task_id}')
    viewset = ra_views.TestCaseGenerationTaskViewSet()
    parsed = viewset._parse_test_cases_content(task.final_test_cases)
    data = {
        'task_id': task.task_id,
        'status': task.status,
        'progress': task.progress,
        'error_message': task.error_message,
        'cases_count': len(parsed),
        'cases_summary': [
            {'index': i, 'title': c.get('title', ''), 'priority': c.get('priority', ''),
             'steps_count': len(c.get('steps', []) or [])}
            for i, c in enumerate(parsed)
        ],
    }
    if include_full:
        data['final_test_cases'] = task.final_test_cases
    return data


def adopt_generated_testcases(task_id, project_id=None, case_indices=None):
    """采纳最终用例进 apps.testcases.TestCase（复用 save_to_records 的解析/入库/幂等逻辑）。"""
    import json as _json
    from django.db import transaction
    from django.db.models import Q
    from django.utils import timezone
    from apps.projects.models import Project
    from apps.requirement_analysis import views as ra_views
    from apps.requirement_analysis.models import TestCaseGenerationTask
    from apps.requirement_analysis.views import _ensure_task_requirement
    from apps.requirement_analysis.text_cleaner import normalize_steps
    from apps.testcases.models import TestCase

    task = TestCaseGenerationTask.objects.filter(task_id=task_id).first()
    if not task:
        raise ValueError(f'任务不存在: {task_id}')
    if task.status != 'completed':
        raise ValueError('只能采纳已完成的测试用例生成任务')
    if not task.final_test_cases:
        raise ValueError('没有最终测试用例可以采纳')
    if task.is_saved_to_records:
        return {'message': '测试用例已经保存到记录中', 'already_saved': True, 'imported_count': 0}

    viewset = ra_views.TestCaseGenerationTaskViewSet()
    parsed = viewset._parse_test_cases_content(task.final_test_cases)
    if not parsed:
        raise ValueError('最终用例无法解析为测试用例，无法采纳')

    if case_indices is not None:
        indices = sorted({int(i) for i in case_indices})
        parsed = [parsed[i] for i in indices if 0 <= i < len(parsed)]
        if not parsed:
            raise ValueError('case_indices 未选中任何用例')

    # 项目定位：project_id → task.project → 服务账号可访问项目 → 自动建默认项目（与现有行为一致）
    user = task.created_by
    if project_id:
        project = resolve_project(project_id)
    elif task.project:
        project = task.project
    else:
        project = Project.objects.filter(Q(owner=user) | Q(members=user)).distinct().first()
        if not project:
            project = Project.objects.create(
                name='默认项目', owner=user, description='系统自动创建的默认项目')

    with transaction.atomic():
        adopted_count = 0
        for tc in parsed:
            parsed_steps = normalize_steps(tc.get('steps', []))
            TestCase.objects.create(
                project=project,
                author=task.created_by,
                title=tc.get('title') or tc.get('scenario') or '测试用例',
                description=tc.get('title') or tc.get('scenario') or '',
                preconditions=tc.get('precondition', ''),
                steps=_json.dumps(parsed_steps, ensure_ascii=False),
                priority=viewset._map_priority(tc.get('priority', '中')),
                test_type='functional',
                status='draft',
                requirement=_ensure_task_requirement(task),
            )
            adopted_count += 1

    task.is_saved_to_records = True
    task.saved_at = timezone.now()
    task.save(update_fields=['is_saved_to_records', 'saved_at'])
    return {'message': f'成功采纳 {adopted_count} 条测试用例', 'imported_count': adopted_count,
            'project_id': project.id}


def generate_api_testcases(request_ids, environment_id=None, ai_config_id=None):
    from apps.api_testing.services import ApiTestCaseGenerator
    from apps.api_testing.views import MAX_BATCH_GENERATE
    if not request_ids:
        raise ValueError('request_ids 不能为空')
    if len(request_ids) > MAX_BATCH_GENERATE:
        raise ValueError(f'单次最多批量生成 {MAX_BATCH_GENERATE} 个接口的用例')
    task_id = ApiTestCaseGenerator.generate(
        request_ids, ai_config_id, get_service_user(), environment_id=environment_id)
    return {'task_id': task_id, 'status': 'generating'}


def get_api_generation_task(task_id):
    from apps.api_testing.services import ApiTestCaseGenerator
    progress = ApiTestCaseGenerator.get_progress(task_id)
    if not progress:
        raise ValueError(f'任务不存在: {task_id}')
    # result 为 {'test_cases': {group: [case, ...], ...}}（见 ApiTestCaseGenerator），
    # 逐组累计真实用例数，避免恒等于 1。
    result = progress.get('result')
    case_groups = (result.get('test_cases') or {}) if isinstance(result, dict) else {}
    cases_count = sum(len(v) for v in case_groups.values() if isinstance(v, list))
    return {
        'task_id': task_id,
        'status': progress.get('status'),
        'progress': progress.get('progress'),
        'error': progress.get('error'),
        'cases_count': cases_count,
    }


def save_api_testcases(task_id, cases, project_id=None, collection_id=None, suite_name=None):
    from apps.api_testing.services import ApiTestCaseGenerator
    if not cases:
        raise ValueError('cases 不能为空')
    return ApiTestCaseGenerator.save_generated_cases(
        task_id=task_id, selected_cases=cases, user=get_service_user(),
        suite_name=suite_name, collection_id=collection_id, project_id=project_id)


def _stub_request():
    from types import SimpleNamespace
    return SimpleNamespace(user=get_service_user(), data={})


def list_api_test_suites(project_id=None):
    from apps.api_testing.models import TestSuite
    qs = TestSuite.objects.all()
    if project_id:
        resolve_project(project_id)
        qs = qs.filter(project_id=project_id)
    return [{'id': s.id, 'name': s.name, 'project_id': s.project_id}
            for s in qs.order_by('-id')[:200]]


def list_api_requests(project_id=None, collection_id=None):
    from apps.api_testing.models import ApiCollection, ApiRequest
    qs = ApiRequest.objects.all()
    if project_id:
        col_ids = ApiCollection.objects.filter(project_id=project_id).values_list('id', flat=True)
        qs = qs.filter(collection_id__in=list(col_ids))
    if collection_id:
        qs = qs.filter(collection_id=collection_id)
    return [{'id': r.id, 'name': r.name, 'method': r.method, 'url': r.url}
            for r in qs.order_by('-id')[:200]]


def run_api_request(request_id):
    from apps.api_testing.models import ApiRequest
    from apps.api_testing.views import ApiRequestViewSet
    api_request = ApiRequest.objects.filter(id=request_id).first()
    if not api_request:
        raise ValueError(f'接口不存在: {request_id}')
    viewset = ApiRequestViewSet()
    stub = _stub_request()
    viewset.request = stub
    viewset.kwargs = {'pk': request_id}
    viewset.get_object = lambda: api_request  # 进程内注入，绕过项目成员过滤
    resp = viewset.execute(stub, pk=request_id)
    if resp.status_code >= 400:
        raise ValueError(resp.data.get('error') or str(resp.data))
    return resp.data


def run_api_test_suite(suite_id):
    from apps.api_testing.models import TestSuite
    from apps.api_testing.views import TestSuiteViewSet
    suite = TestSuite.objects.filter(id=suite_id).first()
    if not suite:
        raise ValueError(f'测试套件不存在: {suite_id}')
    viewset = TestSuiteViewSet()
    stub = _stub_request()
    viewset.request = stub
    viewset.kwargs = {'pk': suite_id}
    viewset.get_object = lambda: suite
    resp = viewset.execute(stub, pk=suite_id)
    if resp.status_code >= 400:
        raise ValueError(resp.data.get('error') or str(resp.data))
    return resp.data


def get_api_execution(execution_id):
    from apps.api_testing.models import TestExecution
    ex = TestExecution.objects.filter(id=execution_id).first()
    if not ex:
        raise ValueError(f'执行记录不存在: {execution_id}')
    return {
        'id': ex.id,
        'status': ex.status,
        'test_suite_id': ex.test_suite_id,
        'total_requests': ex.total_requests,
        'passed_requests': ex.passed_requests,
        'failed_requests': ex.failed_requests,
        'executed_by': ex.executed_by_id,
        'start_time': ex.start_time.isoformat() if ex.start_time else None,
        'end_time': ex.end_time.isoformat() if ex.end_time else None,
        'results': ex.results,
    }


def run_ui_automation_adhoc(task_description, project_id=None,
                            execution_mode='text', enable_gif=True):
    from types import SimpleNamespace
    from apps.ui_automation.views import AIExecutionRecordViewSet
    if not task_description:
        raise ValueError('缺少任务描述参数')
    stub = SimpleNamespace(user=get_service_user(), data={
        'task_description': task_description,
        'project_id': project_id,
        'execution_mode': execution_mode,
        'enable_gif': enable_gif,
    })
    resp = AIExecutionRecordViewSet().run_adhoc(stub)  # 复用现成编排：建记录+起浏览器 agent 线程
    if resp.status_code not in (200, 201):
        raise ValueError(resp.data.get('error') or str(resp.data))
    return resp.data  # {'message', 'execution_id'}


def get_ui_execution(record_id, include_full=False):
    from apps.ui_automation.models import AIExecutionRecord
    rec = AIExecutionRecord.objects.filter(id=record_id).first()
    if not rec:
        raise ValueError(f'执行记录不存在: {record_id}')
    data = {
        'execution_id': rec.id,
        'status': rec.status,
        'case_name': rec.case_name,
        'task_description': rec.task_description,
        'execution_mode': rec.execution_mode,
        'duration': rec.duration,
        'project_id': rec.project_id,
        'steps_completed': rec.steps_completed,
        'screenshots_sequence': rec.screenshots_sequence or [],
        'gif_path': rec.gif_path,
        'start_time': rec.start_time.isoformat() if rec.start_time else None,
    }
    if include_full:
        data['logs'] = rec.logs
        data['planned_tasks'] = rec.planned_tasks
    return data


def stop_ui_execution(record_id):
    from django.utils import timezone
    from apps.ui_automation.models import AIExecutionRecord
    from apps.ui_automation.views import STOP_SIGNALS
    record_id = int(record_id)
    if record_id in STOP_SIGNALS:
        STOP_SIGNALS[record_id] = True
        return {'stopped': True, 'message': '已发送停止信号'}
    rec = AIExecutionRecord.objects.filter(id=record_id).first()
    if not rec:
        raise ValueError(f'执行记录不存在: {record_id}')
    if rec.status == 'running':
        rec.status = 'stopped'
        rec.end_time = timezone.now()
        rec.save(update_fields=['status', 'end_time'])
        return {'stopped': True, 'message': '任务已标记为停止'}
    return {'stopped': False, 'message': '任务不在运行中'}
