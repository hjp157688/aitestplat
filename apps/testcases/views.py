import uuid
import logging

from django.http import FileResponse
from rest_framework import generics, permissions, status, pagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import models
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

from .models import (
    TestCase, TestCaseStep, TestCaseAttachment, TestCaseComment, TestCaseImportRecord, ZentaoSyncTask,
    TestCaseVersion, TestCaseAiTask
)
from .serializers import (
    TestCaseSerializer, TestCaseListSerializer, TestCaseCreateSerializer, TestCaseUpdateSerializer,
    TestCaseImportRecordListSerializer, TestCaseImportRecordDetailSerializer, TestCaseVersionSerializer
)
from apps.projects.models import Project
from .services import (
    TestCaseImportTemplateService, TestCaseExcelImportService, execute_import_record,
    snapshot_case_version, CASE_CONTENT_FIELDS
)
from .tasks import import_testcases_from_excel

logger = logging.getLogger(__name__)

class TestCasePagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TestCaseImportRecordPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_user_accessible_projects(user):
    return Project.objects.filter(
        models.Q(owner=user) | models.Q(members=user)
    ).distinct()

class TestCaseListCreateView(generics.ListCreateAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TestCasePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['priority', 'test_type', 'requirement']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TestCaseCreateSerializer
        return TestCaseListSerializer

    def get_queryset(self):
        user = self.request.user
        accessible_projects = get_user_accessible_projects(user)
        queryset = TestCase.objects.filter(
            project__in=accessible_projects
        ).select_related(
            'author', 'assignee', 'project'
        ).prefetch_related(
            'versions'
        ).distinct()
        # 支持多项目过滤：project=1,2,3（单值 project=1 同样兼容）
        project_param = self.request.query_params.get('project')
        if project_param:
            project_ids = [int(pid) for pid in project_param.split(',') if pid.strip().isdigit()]
            if project_ids:
                queryset = queryset.filter(project_id__in=project_ids)
        return queryset
    
    def get_user_accessible_projects(self, user):
        """获取用户有权限访问的项目"""
        return get_user_accessible_projects(user)
    
    def perform_create(self, serializer):
        user = self.request.user
        project_id = self.request.data.get('project_id')
        
        # 获取用户有权限的项目
        accessible_projects = self.get_user_accessible_projects(user)
        
        if project_id:
            # 检查指定的项目是否存在且用户有权限
            try:
                project = accessible_projects.get(id=project_id)
            except Project.DoesNotExist:
                # 如果指定项目不存在或无权限，使用第一个可访问的项目
                project = accessible_projects.first()
                if not project:
                    # 如果用户没有任何项目，创建默认项目
                    project = Project.objects.create(
                        name="默认项目",
                        owner=user,
                        description='系统自动创建的默认项目'
                    )
        else:
            # 没有指定项目，使用第一个可访问的项目
            project = accessible_projects.first()
            if not project:
                # 如果用户没有任何项目，创建默认项目
                project = Project.objects.create(
                    name="默认项目",
                    owner=user,
                    description='系统自动创建的默认项目'
                )
        
        serializer.save(author=user, project=project)

class TestCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TestCaseUpdateSerializer
        return TestCaseSerializer
    
    def get_queryset(self):
        user = self.request.user
        accessible_projects = get_user_accessible_projects(user)
        return TestCase.objects.filter(
            project__in=accessible_projects
        ).select_related(
            'author', 'assignee', 'project'
        ).prefetch_related(
            'versions', 'step_details', 'attachments', 'comments'
        )
    
    def get_user_accessible_projects(self, user):
        """获取用户有权限访问的项目"""
        return get_user_accessible_projects(user)
    
    def perform_update(self, serializer):
        user = self.request.user
        project_id = self.request.data.get('project_id')

        # 快照用例编辑前的内容，保存后比较决定是否落版本
        from .services import case_content_dict, snapshot_case_version, ensure_baseline_version
        content_before = case_content_dict(serializer.instance)
        # 存量老用例无版本记录时，先补录初版 v1（编辑前内容），保证可对比
        ensure_baseline_version(serializer.instance, created_by=user)

        if project_id:
            # 检查指定的项目是否存在且用户有权限
            accessible_projects = self.get_user_accessible_projects(user)
            try:
                project = accessible_projects.get(id=project_id)
                serializer.save(project=project)
            except Project.DoesNotExist:
                # 如果指定项目不存在或无权限，保持原项目不变
                serializer.save()
        else:
            # 没有指定项目，保持原项目不变
            serializer.save()

        # 内容字段有变化才落版本（只改发布版本关联等不产生新版本）
        if case_content_dict(serializer.instance) != content_before:
            snapshot_case_version(
                serializer.instance,
                source='manual_edit',
                note=self.request.data.get('version_note', '') or '',
                created_by=user,
            )


class TestCaseImportTemplateDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        template_stream = TestCaseImportTemplateService.build_template()
        return FileResponse(
            template_stream,
            as_attachment=True,
            filename='testcase_import_template_v2.xlsx',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )


class TestCaseImportRecordListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TestCaseImportRecordPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        return TestCaseImportRecordListSerializer

    def get_queryset(self):
        return TestCaseImportRecord.objects.filter(
            project__in=get_user_accessible_projects(self.request.user)
        ).select_related('project', 'created_by')

    def create(self, request, *args, **kwargs):
        project_id = request.data.get('project_id')
        import_file = request.FILES.get('file')

        if not project_id:
            return Response({'error': '请选择导入项目'}, status=status.HTTP_400_BAD_REQUEST)
        if not import_file:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)
        if not import_file.name.lower().endswith('.xlsx'):
            return Response({'error': '仅支持 .xlsx 格式文件'}, status=status.HTTP_400_BAD_REQUEST)

        accessible_projects = get_user_accessible_projects(request.user)
        try:
            project = accessible_projects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': '项目不存在或无权限访问'}, status=status.HTTP_403_FORBIDDEN)

        record = TestCaseImportRecord.objects.create(
            import_no=TestCaseExcelImportService.generate_import_no(),
            project=project,
            import_file=import_file,
            created_by=request.user,
            template_version='v2'
        )

        # 优先异步导入；Redis/Celery 不可用（如本地无 Redis 的 runserver 环境）时
        # 降级为请求内同步导入，保证功能可用，不抛 500。
        try:
            celery_task = import_testcases_from_excel.delay(record.id)
        except Exception as exc:
            logger.warning('Redis/Celery 不可用，用例导入改为同步执行: %s', exc)
            try:
                execute_import_record(record.id)
            except Exception:
                # 失败信息已写入 record.status/error_message，由前端展示，不中断本次请求
                pass
        else:
            record.celery_task_id = celery_task.id
            record.save(update_fields=['celery_task_id', 'updated_at'])

        record.refresh_from_db()
        serializer = self.get_serializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TestCaseImportRecordDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TestCaseImportRecordDetailSerializer
    queryset = TestCaseImportRecord.objects.select_related('project', 'created_by')

    def get_queryset(self):
        return super().get_queryset().filter(
            project__in=get_user_accessible_projects(self.request.user)
        )


class TestCaseImportFailureReportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        record = TestCaseImportRecord.objects.filter(
            pk=pk,
            project__in=get_user_accessible_projects(request.user)
        ).first()

        if not record:
            return Response({'error': '导入记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        if not record.failure_report_file:
            return Response({'error': '当前记录没有失败明细文件'}, status=status.HTTP_404_NOT_FOUND)

        return FileResponse(
            record.failure_report_file.open('rb'),
            as_attachment=True,
            filename=record.failure_report_file.name.split('/')[-1],
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils import timezone
from apps.requirement_analysis.services import ZentaoService
from apps.requirement_analysis.models import ZentaoConfig


@method_decorator(csrf_exempt, name='dispatch')
class TestCaseZentaoExportView(APIView):
    """导出测试用例到禅道（有 zentao_case_id 走更新，无则新建并回写）

    大批量导出是慢操作（逐条调用禅道 API），改为后台线程 + 进度轮询，
    避免单请求过长撞前端超时。
    """

    def post(self, request):
        case_ids = request.data.get('case_ids', [])
        product_id = request.data.get('product_id')
        module_id = request.data.get('module_id') or 0
        story_id = request.data.get('story_id') or 0

        if not case_ids:
            return JsonResponse({'error': '未选择用例'}, status=400)

        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse({'error': '请先在配置中心配置禅道连接'}, status=400)

        task = ZentaoSyncTask.objects.create(
            task_id=uuid.uuid4().hex,
            task_type='export',
            status='pending',
            progress=0,
            input_params={
                'case_ids': case_ids,
                'product_id': product_id,
                'module_id': module_id,
                'story_id': story_id,
            },
            created_by=request.user if request.user.is_authenticated else None,
        )
        _start_zentao_thread(task)

        return JsonResponse({'task_id': task.task_id, 'status': task.status}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class TestCaseZentaoImportView(APIView):
    """从禅道导入测试用例（自动同步需求 + 按 zentao_case_id 去重）

    大批量导入同样是慢操作，改为后台线程 + 进度轮询。
    """

    def post(self, request):
        scope_type = request.data.get('scope_type')
        scope_id = request.data.get('scope_id')
        story_ids = request.data.get('story_ids', [])
        project_id = request.data.get('project_id')

        if not story_ids or not project_id:
            return JsonResponse({'error': '缺少 story_ids 或 project_id'}, status=400)

        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse({'error': '请先在配置中心配置禅道连接'}, status=400)

        from apps.projects.models import Project as P

        try:
            P.objects.get(id=project_id)
        except P.DoesNotExist:
            return JsonResponse({'error': '项目不存在'}, status=400)

        task = ZentaoSyncTask.objects.create(
            task_id=uuid.uuid4().hex,
            task_type='import',
            status='pending',
            progress=0,
            input_params={
                'scope_type': scope_type,
                'scope_id': scope_id,
                'story_ids': story_ids,
                'project_id': project_id,
            },
            created_by=request.user if request.user.is_authenticated else None,
        )
        _start_zentao_thread(task)

        return JsonResponse({'task_id': task.task_id, 'status': task.status}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ZentaoSyncTaskDetailView(APIView):
    """禅道同步任务进度查询"""

    def get(self, request, task_id):
        try:
            task = ZentaoSyncTask.objects.get(task_id=task_id)
        except ZentaoSyncTask.DoesNotExist:
            return JsonResponse({'error': '任务不存在'}, status=404)
        return JsonResponse({
            'task_id': task.task_id,
            'task_type': task.task_type,
            'status': task.status,
            'progress': task.progress,
            'result': task.result,
            'error_message': task.error_message,
            'completed_at': task.completed_at,
        })


def _start_zentao_thread(task):
    """在新线程中启动禅道同步任务。"""
    import threading

    def _run():
        try:
            _run_zentao_task(task)
        except Exception as e:
            try:
                ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
                    status='failed', error_message=str(e), completed_at=timezone.now(),
                )
            except Exception:
                pass

    try:
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
    except Exception as e:
        ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
            status='failed', error_message=str(e), completed_at=timezone.now(),
        )


def _run_zentao_task(task):
    """执行禅道同步任务（导出/导入共用分发入口）。"""
    if task.task_type == 'export':
        _run_zentao_export(task)
    elif task.task_type == 'import':
        _run_zentao_import(task)
    else:
        raise ValueError(f"未知任务类型: {task.task_type}")


def _run_zentao_export(task):
    """把用例逐条导到禅道，实时落进度与结果。"""
    params = task.input_params or {}
    case_ids = params.get('case_ids', [])
    product_id = params.get('product_id')
    module_id = params.get('module_id') or 0
    story_id = params.get('story_id') or 0

    config = ZentaoConfig.get_active_config()
    if not config:
        raise Exception('请先在配置中心配置禅道连接')

    cases = list(TestCase.objects.filter(id__in=case_ids))
    total = len(cases)
    success_count = 0
    failures = []

    for done, tc in enumerate(cases, start=1):
        progress = int(done * 100 / total) if total else 100
        ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
            status='running', progress=progress,
        )
        try:
            # 确定目标 product/module/story：禅道源 association 优先，否则手动指定
            if tc.requirement_id and tc.requirement.zentao_id:
                p_id = tc.requirement.product_id or product_id
                m_id = tc.requirement.module_id or module_id or 0
                s_id = tc.requirement.zentao_id or story_id or 0
            else:
                p_id = product_id
                m_id = module_id
                s_id = story_id
            if not p_id:
                raise Exception('未指定禅道产品')

            case_data = {
                'product': p_id,
                'module': m_id,
                'story': s_id,
                'title': tc.title,
                'precondition': tc.preconditions or '',
                'steps': ZentaoService.steps_to_zentao(tc.steps),
                'type': ZentaoService.map_type_to_zentao(tc.test_type),
                'stage': 'feature',
                'pri': ZentaoService.map_priority_to_zentao(tc.priority),
            }

            if tc.zentao_case_id:
                ZentaoService.update_testcase(config, tc.zentao_case_id, case_data)
            else:
                result = ZentaoService.create_testcase(config, p_id, case_data)
                new_id = result.get('id')
                if new_id:
                    tc.zentao_case_id = new_id
                    tc.product_id = p_id
                    tc.module_id = m_id
                    tc.story_id = s_id
                    tc.save(update_fields=[
                        'zentao_case_id', 'product_id', 'module_id', 'story_id'
                    ])
            success_count += 1
        except Exception as e:
            failures.append({'case_id': tc.id, 'title': tc.title, 'error': str(e)})

        ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
            result={'success_count': success_count, 'failed_count': len(failures), 'failures': failures},
        )

    ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
        status='succeeded', progress=100, completed_at=timezone.now(),
        result={'success_count': success_count, 'failed_count': len(failures), 'failures': failures},
    )


def _run_zentao_import(task):
    """从禅道逐条导入，实时落进度与结果。"""
    from apps.requirement_analysis.models import Requirement
    from apps.projects.models import Project as P

    params = task.input_params or {}
    scope_type = params.get('scope_type')
    scope_id = params.get('scope_id')
    story_ids = params.get('story_ids', [])
    project_id = params.get('project_id')

    config = ZentaoConfig.get_active_config()
    if not config:
        raise Exception('请先在配置中心配置禅道连接')

    try:
        project = P.objects.get(id=project_id)
    except P.DoesNotExist:
        raise Exception('项目不存在')

    created = 0
    updated = 0
    failures = []
    total = len(story_ids)

    for done, story_id in enumerate(story_ids, start=1):
        progress = int(done * 100 / total) if total else 100
        ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
            status='running', progress=progress,
        )
        story = None
        try:
            # 自动同步需求（若本地不存在则创建 Requirement）
            try:
                story = ZentaoService.get_story_detail(config, story_id)
            except Exception as e:
                failures.append({
                    'story_id': story_id,
                    'error': f'获取需求详情失败，跳过该需求(需先在禅道确认该需求存在且有权限): {e}',
                })
                continue
            zentao_id = story.get('id', story_id)
            product_id = story.get('product') or (
                scope_id if scope_type == 'product' else None
            )
            req = Requirement.objects.filter(zentao_id=zentao_id).first()
            if not req:
                req = Requirement.objects.create(
                    project=project,
                    source_type='zentao',
                    zentao_id=zentao_id,
                    product_id=product_id,
                    module_id=story.get('module'),
                    title=story.get('title', f'禅道需求{zentao_id}'),
                    spec=story.get('spec', ''),
                    status=story.get('status', 'active'),
                    raw_data=story,
                    synced_at=timezone.now(),
                    created_by=task.created_by,
                )
            else:
                req.product_id = req.product_id or product_id
                req.module_id = req.module_id or story.get('module')
                req.save(update_fields=['product_id', 'module_id'])

            cases = ZentaoService.get_story_testcases(config, zentao_id, product_id)
            for zc in cases:
                try:
                    case_id = zc.get('id')
                    # 列表接口不含步骤，逐条拉详情拿 steps
                    zc_detail = {}
                    try:
                        zc_detail = ZentaoService.get_testcase_detail(config, case_id)
                    except Exception:
                        zc_detail = zc  # 详情失败则退回列表数据（无步骤）
                    steps_json = ZentaoService.steps_from_zentao(zc_detail.get('steps'))
                    existing = TestCase.objects.filter(zentao_case_id=case_id).first()
                    if existing:
                        existing.title = zc_detail.get('title') or zc.get('title', existing.title)
                        existing.preconditions = (zc_detail.get('precondition') or zc.get('precondition')) or ''
                        existing.steps = steps_json
                        existing.priority = ZentaoService.map_priority_from_zentao(
                            zc_detail.get('pri') or zc.get('pri'))
                        existing.test_type = ZentaoService.map_type_from_zentao(
                            zc_detail.get('type') or zc.get('type'))
                        existing.requirement = req
                        existing.product_id = req.product_id
                        existing.module_id = req.module_id
                        existing.story_id = zentao_id
                        existing.save()
                        updated += 1
                    else:
                        TestCase.objects.create(
                            project=project,
                            author=task.created_by or req.created_by,
                            title=zc_detail.get('title') or zc.get('title', '禅道用例'),
                            description=zc_detail.get('title') or zc.get('title', ''),
                            preconditions=(zc_detail.get('precondition') or zc.get('precondition')) or '',
                            steps=steps_json,
                            priority=ZentaoService.map_priority_from_zentao(
                                zc_detail.get('pri') or zc.get('pri')),
                            test_type=ZentaoService.map_type_from_zentao(
                                zc_detail.get('type') or zc.get('type')),
                            status='draft',
                            requirement=req,
                            zentao_case_id=case_id,
                            product_id=req.product_id,
                            module_id=req.module_id,
                            story_id=zentao_id,
                        )
                        created += 1
                except Exception as e:
                    failures.append({'case_id': case_id, 'error': str(e)})
        except Exception as e:
            failures.append({'story_id': story_id, 'error': str(e)})

        ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
            result={'created': created, 'updated': updated, 'failed': len(failures), 'failures': failures},
        )

    ZentaoSyncTask.objects.filter(task_id=task.task_id).update(
        status='succeeded', progress=100, completed_at=timezone.now(),
        result={'created': created, 'updated': updated, 'failed': len(failures), 'failures': failures},
    )


class TestCaseVersionsListView(APIView):
    """用例版本历史时间线"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        accessible_projects = get_user_accessible_projects(self.request.user)
        return TestCase.objects.filter(project__in=accessible_projects)

    def get(self, request, pk):
        testcase = self.get_object_or_404(pk)
        # 存量老用例查历史时懒初始化：补录初版 v1
        from .services import ensure_baseline_version
        ensure_baseline_version(testcase, created_by=request.user)
        versions = testcase.version_history.order_by('version')
        serializer = TestCaseVersionSerializer(versions, many=True)
        return Response(serializer.data)

    def get_object_or_404(self, pk):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(self.get_queryset(), pk=pk)


class TestCaseVersionRestoreView(APIView):
    """回退用例到历史版本（回退动作本身落一条 restore 版本）"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, version):
        accessible_projects = get_user_accessible_projects(request.user)
        testcase = generics.get_object_or_404(TestCase, pk=pk, project__in=accessible_projects)
        try:
            target = testcase.version_history.get(version=version)
        except TestCaseVersion.DoesNotExist:
            return Response({'error': f'版本 v{version} 不存在'}, status=status.HTTP_404_NOT_FOUND)

        latest = testcase.version_history.order_by('-version').first()
        if latest and latest.version == target.version:
            return Response({'error': f'已是最新版本 v{version}，无需回退'}, status=status.HTTP_400_BAD_REQUEST)

        # 老用例无版本记录时先补录初版（覆盖前的内容）
        from .services import ensure_baseline_version
        ensure_baseline_version(testcase, created_by=request.user)

        # 用目标版本内容覆盖用例，再落一条 restore 版本（内容=回退后状态）
        for field in CASE_CONTENT_FIELDS:
            setattr(testcase, field, getattr(target, field))
        testcase.save()

        new_version = snapshot_case_version(
            testcase,
            source='restore',
            note=request.data.get('note', '') or f'回退到 v{version}',
            created_by=request.user,
        )
        return Response(TestCaseVersionSerializer(new_version).data, status=status.HTTP_200_OK)


class TestCaseAiModifyView(APIView):
    """AI 修改：勾选用例 + 修改意见 → 创建后台任务"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        case_ids = request.data.get('case_ids') or []
        note = (request.data.get('note') or '').strip()
        if not case_ids or not note:
            return Response({'error': '请选择要修改的用例并填写修改意见'}, status=status.HTTP_400_BAD_REQUEST)

        accessible_projects = get_user_accessible_projects(request.user)
        cases = list(TestCase.objects.filter(id__in=case_ids, project__in=accessible_projects))
        if len(cases) != len(set(case_ids)):
            return Response({'error': '存在无权访问或不存在用例'}, status=status.HTTP_400_BAD_REQUEST)

        task = TestCaseAiTask.objects.create(
            task_id=uuid.uuid4().hex[:32],
            mode='modify',
            note=note,
            project=cases[0].project,
            case_ids=list({c.id for c in cases}),
            created_by=request.user,
        )
        from .ai_tasks import start_ai_task
        start_ai_task(task)
        return Response({'task_id': task.task_id, 'status': task.status}, status=status.HTTP_201_CREATED)


class TestCaseAiSupplementView(APIView):
    """AI 补充：基于需求上下文 + 已有用例，生成新增用例"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        requirement_id = request.data.get('requirement_id')
        note = (request.data.get('note') or '').strip()
        if not requirement_id:
            return Response({'error': '请先选择需求'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.requirement_analysis.models import Requirement
        requirement = Requirement.objects.filter(id=requirement_id).first()
        if not requirement:
            return Response({'error': '需求不存在'}, status=status.HTTP_400_BAD_REQUEST)

        # 需求上下文：默认取需求描述，允许请求里覆盖（发起弹窗可编辑）
        requirement_text = (request.data.get('requirement_text') or requirement.spec or '').strip()
        if not requirement_text:
            return Response({'error': '需求描述为空，请填写需求上下文'}, status=status.HTTP_400_BAD_REQUEST)

        task = TestCaseAiTask.objects.create(
            task_id=uuid.uuid4().hex[:32],
            mode='supplement',
            note=note,
            requirement_text=requirement_text,
            requirement=requirement,
            project=requirement.project,
            created_by=request.user,
        )
        from .ai_tasks import start_ai_task
        start_ai_task(task)
        return Response({'task_id': task.task_id, 'status': task.status}, status=status.HTTP_201_CREATED)


class TestCaseAiTaskDetailView(APIView):
    """AI 任务进度查询（前端轮询）"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id):
        task = TestCaseAiTask.objects.filter(task_id=task_id).first()
        if not task:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'task_id': task.task_id,
            'mode': task.mode,
            'status': task.status,
            'note': task.note,
            'case_ids': task.case_ids,
            'created_cases': task.created_cases,
            'error_message': task.error_message,
            'completed_at': task.completed_at,
        })


class TestCaseVersionDeleteView(APIView):
    """删除历史版本（最新版不可删；编号不重排）"""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, version):
        accessible_projects = get_user_accessible_projects(request.user)
        testcase = generics.get_object_or_404(TestCase, pk=pk, project__in=accessible_projects)
        try:
            target = testcase.version_history.get(version=version)
        except TestCaseVersion.DoesNotExist:
            return Response({'error': f'版本 v{version} 不存在'}, status=status.HTTP_404_NOT_FOUND)

        latest = testcase.version_history.order_by('-version').first()
        if latest and latest.version == target.version:
            return Response(
                {'error': f'v{version} 是当前内容对应的最新版本，不可删除'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.delete()
        return Response({'message': f'已删除 v{version}'}, status=status.HTTP_200_OK)
