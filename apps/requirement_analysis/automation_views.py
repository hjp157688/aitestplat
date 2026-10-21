"""自动化用例 / 环境的 ViewSet（转化与执行 API，Task 6 补执行 actions）。"""
import logging

from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.testcases.models import TestCase as ManualTestCase

from . import automation_tasks
from .models import (
    AutomationCase,
    AutomationEnvironment,
    GeneratedTestCase,
    TestCaseGenerationTask,
)
from .serializers import AutomationCaseSerializer, AutomationEnvironmentSerializer
from .views import _ensure_task_requirement

logger = logging.getLogger(__name__)


class AutomationEnvironmentViewSet(viewsets.ModelViewSet):
    queryset = AutomationEnvironment.objects.all()
    serializer_class = AutomationEnvironmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


class AutomationCaseViewSet(viewsets.ModelViewSet):
    queryset = AutomationCase.objects.select_related('project', 'requirement')
    serializer_class = AutomationCaseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get('project'):
            queryset = queryset.filter(project_id=params['project'])
        if params.get('requirement'):
            queryset = queryset.filter(requirement_id=params['requirement'])
        if params.get('convert_status'):
            queryset = queryset.filter(convert_status=params['convert_status'])
        if params.get('search'):
            queryset = queryset.filter(title__icontains=params['search'])
        return queryset

    @action(detail=False, methods=['post'], url_path='batch-convert')
    def batch_convert(self, request):
        source_type = request.data.get('source_type')
        if source_type not in ('generated', 'testcase'):
            return Response({'error': 'source_type 必须是 generated 或 testcase'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            if source_type == 'testcase':
                created_ids, skipped_count = self._convert_from_testcases(request)
            elif isinstance(request.data.get('ids'), list):
                # 用例管理入口：直接按 AI 生成用例 id 批量转化
                created_ids, skipped_count = self._convert_from_generated(request)
            else:
                created_ids, skipped_count = self._convert_inline_from_task(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error('批量转化自动化用例失败: %s', exc)
            return Response({'error': f'批量转化失败: {exc}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        automation_tasks.start_conversion_tasks(created_ids)
        return Response({
            'created_count': len(created_ids),
            'skipped_count': skipped_count,
            'case_ids': created_ids,
        }, status=status.HTTP_201_CREATED)

    def _convert_from_testcases(self, request):
        ids = request.data.get('ids')
        if not isinstance(ids, list) or not ids:
            raise ValueError('ids 不能为空')
        created_ids, skipped_count = [], 0
        existing_ids = set(AutomationCase.objects.filter(
            source_test_case_id__in=ids).values_list('source_test_case_id', flat=True))
        for source in ManualTestCase.objects.filter(id__in=ids).select_related('requirement'):
            if source.id in existing_ids:
                skipped_count += 1
                continue
            case = AutomationCase.objects.create(
                project=source.project,
                requirement=source.requirement,
                source_test_case=source,
                title=source.title,
                precondition=source.preconditions or '',
                steps=[],
                convert_status='processing',
                created_by=request.user,
            )
            created_ids.append(case.id)
        return created_ids, skipped_count

    def _convert_from_generated(self, request):
        """按 AI 生成用例 id 批量转化；项目/需求取自用例所属需求。"""
        ids = request.data.get('ids')
        if not isinstance(ids, list) or not ids:
            raise ValueError('ids 不能为空')
        created_ids, skipped_count = [], 0
        existing_ids = set(AutomationCase.objects.filter(
            source_generated_case_id__in=ids).values_list('source_generated_case_id', flat=True))
        for source in GeneratedTestCase.objects.filter(id__in=ids).select_related('requirement'):
            if source.id in existing_ids:
                skipped_count += 1
                continue
            case = AutomationCase.objects.create(
                project=source.requirement.project,
                requirement=source.requirement,
                source_generated_case=source,
                title=source.title,
                precondition=source.precondition or '',
                steps=[],
                convert_status='processing',
                created_by=request.user,
            )
            created_ids.append(case.id)
        return created_ids, skipped_count

    def _convert_inline_from_task(self, request):
        task_id = request.data.get('task_id')
        cases = request.data.get('cases')
        if not task_id:
            raise ValueError('task_id 不能为空')
        if not isinstance(cases, list) or not cases:
            raise ValueError('cases 不能为空')
        try:
            # TestCaseGenerationTask 的 lookup 字段是 task_id（CharField），非整型 pk
            task = TestCaseGenerationTask.objects.get(task_id=task_id)
        except TestCaseGenerationTask.DoesNotExist:
            raise ValueError('生成任务不存在')
        project = task.project or self._fallback_project(request)
        requirement = _ensure_task_requirement(task)
        created_ids = []
        with transaction.atomic():
            for item in cases:
                title = str((item or {}).get('title') or '').strip()
                if not title:
                    continue
                case = AutomationCase.objects.create(
                    project=project,
                    requirement=requirement,
                    title=title,
                    precondition=str((item or {}).get('precondition') or ''),
                    steps=[],
                    convert_status='processing',
                    created_by=request.user,
                )
                created_ids.append(case.id)
        return created_ids, 0

    def _fallback_project(self, request):
        """与 views._ensure_task_requirement 的项目回退逻辑对齐：显式 project_id → 用户可访问的第一个项目。"""
        from apps.projects.models import Project
        project_id = request.data.get('project_id')
        if project_id:
            project = Project.objects.filter(pk=project_id).first()
            if project:
                return project
        return Project.objects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).distinct().first()

    @action(detail=True, methods=['post'], url_path='retry-convert')
    def retry_convert(self, request, pk=None):
        case = self.get_object()
        AutomationCase.objects.filter(pk=case.pk).update(
            convert_status='processing', convert_error='')
        automation_tasks.start_conversion_tasks([case.pk])
        return Response({'message': '已重新发起 AI 转写'}, status=status.HTTP_200_OK)
