from django.http import FileResponse
from rest_framework import generics, permissions, status, pagination
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import models
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

from .models import TestCase, TestCaseStep, TestCaseAttachment, TestCaseComment, TestCaseImportRecord
from .serializers import (
    TestCaseSerializer, TestCaseListSerializer, TestCaseCreateSerializer, TestCaseUpdateSerializer,
    TestCaseImportRecordListSerializer, TestCaseImportRecordDetailSerializer
)
from apps.projects.models import Project
from .services import TestCaseImportTemplateService, TestCaseExcelImportService
from .tasks import import_testcases_from_excel

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


class TestCaseImportTemplateDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        template_stream = TestCaseImportTemplateService.build_template()
        return FileResponse(
            template_stream,
            as_attachment=True,
            filename='testcase_import_template_v1.xlsx',
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
            template_version='v1'
        )

        celery_task = import_testcases_from_excel.delay(record.id)
        record.celery_task_id = celery_task.id
        record.save(update_fields=['celery_task_id', 'updated_at'])

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
    """导出测试用例到禅道（有 zentao_case_id 走更新，无则新建并回写）"""

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

        cases = TestCase.objects.filter(id__in=case_ids)
        success_count = 0
        failures = []

        for tc in cases:
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

        return JsonResponse({
            'success_count': success_count,
            'failed_count': len(failures),
            'failures': failures,
        })


@method_decorator(csrf_exempt, name='dispatch')
class TestCaseZentaoImportView(APIView):
    """从禅道导入测试用例（自动同步需求 + 按 zentao_case_id 去重）"""

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

        from apps.requirement_analysis.models import Requirement
        from apps.projects.models import Project as P

        try:
            project = P.objects.get(id=project_id)
        except P.DoesNotExist:
            return JsonResponse({'error': '项目不存在'}, status=400)

        created = 0
        updated = 0
        failures = []

        for story_id in story_ids:
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
                        created_by=request.user if request.user.is_authenticated else None,
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
                                author=request.user if request.user.is_authenticated else None,
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

        return JsonResponse({
            'created': created,
            'updated': updated,
            'failed': len(failures),
            'failures': failures,
        })
