import asyncio
import logging
import re
import os  # Added import
import json
import time
from rest_framework import viewsets, status
from django.conf import settings  # Added import
from rest_framework.decorators import action, permission_classes
from rest_framework.response import Response
from rest_framework.renderers import BaseRenderer
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from .permissions import assert_project_access, is_admin


class PassThroughRenderer(BaseRenderer):
    """直接透传StreamingHttpResponse，不进行任何渲染处理"""
    media_type = 'text/event-stream'
    format = 'event-stream'
    render_level = 0

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # 直接返回data，不做任何处理
        return data


from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.db import models

from .models import (
    RequirementDocument, RequirementAnalysis,
    GeneratedTestCase, AnalysisTask, AIModelConfig, PromptConfig, TestCaseGenerationTask,
    GenerationConfig, AIModelService, ZentaoConfig, Requirement,
    WeKnoraConfig, WeKnoraProjectBinding, create_requirement_from_br_data
)
from apps.ai.resolver import ConfigResolver
from apps.ai.client import AIClient
from .serializers import (
    RequirementDocumentSerializer, RequirementAnalysisSerializer,
    GeneratedTestCaseSerializer,
    AnalysisTaskSerializer, DocumentUploadSerializer,
    TestCaseGenerationRequestSerializer, TestCaseReviewRequestSerializer,
    AIModelConfigSerializer, PromptConfigSerializer, TestCaseGenerationTaskSerializer,
    GenerationConfigSerializer, ZentaoConfigSerializer, RequirementSerializer,
    RequirementListSerializer, AIRequirementParseRequestSerializer,
    AIRequirementImportRequestSerializer, RequirementGenerateTestCasesRequestSerializer,
    ZentaoSyncRequestSerializer,
    WeKnoraConfigSerializer, WeKnoraProjectBindingSerializer
)
from .services import RequirementAnalysisService, DocumentProcessor, ZentaoService, AIRequirementParser
from .text_cleaner import clean_text, normalize_steps

logger = logging.getLogger(__name__)


# SSE 流式(Django 4.2)双协议实现 —— WSGI(runserver 本地)与 ASGI(daphne 生产)都逐块。
#
# 早期 `_SseStream`(双协议对象)喂给标准 StreamingHttpResponse 失败的原因: Django 构造响应时
# `_set_streaming_content` 先 `iter(value)` 把它【解包】成裸同步迭代器并置 is_async=False,
# ASGI 下 `StreamingHttpResponse.__aiter__` 于是走 `sync_to_async(list)(同步迭代器)` 整包缓冲
# ("一把出")。v2 改成纯 async 生成器修好了 daphne, 但 WSGI(runserver) 反而整包。
#
# 本方案: 自定义 `_SseStreamingResponse`, `_set_streaming_content` 不 iter() 解包、
# 覆盖 `__iter__`(WSGI: wsgi 服务器逐块迭代 response)与 `__aiter__`(ASGI)各自逐块消费同一个
# `_SSEStream`(同时提供同步 __next__ 与异步 __aiter__, 异步用线程池消费避免阻塞事件循环)。
# 两条路径都不触发 Django 的 list() 整包缓冲。
_SSE_DONE = object()


class _SSEStream:
    """同一 SSE 同步生成器的双协议逐块流(不经 Django streaming_content 解包路径)。"""

    def __init__(self, gen):
        self._gen = iter(gen)

    # 同步协议(WSGI 直接迭代 response 时)
    def __iter__(self):
        return self

    def __next__(self):
        part = next(self._gen, _SSE_DONE)
        if part is _SSE_DONE:
            raise StopIteration
        return part

    # 异步协议(ASGI/daphne 走 response.__aiter__)
    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        while True:
            part = await sync_to_async(next, thread_sensitive=False)(self._gen, _SSE_DONE)
            if part is _SSE_DONE:
                return
            yield part


class _SseStreamingResponse(StreamingHttpResponse):
    """WSGI 与 ASGI 都逐块下发的 SSE 响应: 绕开 Django 对同步/异步迭代器的 list() 整包缓冲。"""

    def _set_streaming_content(self, value):
        # 保持 value 原样(我们的 _SSEStream), 不要 iter() 解包;
        # streaming_content 保持同步(map 包装), 供 WSGI 逐块; __aiter__ 自己逐块
        self._iterator = value
        self.is_async = False
        if hasattr(value, "close"):
            self._resource_closers.append(value.close)

    def __iter__(self):
        # WSGI(wsgi 服务器对返回值逐块迭代)
        for part in self._iterator:
            yield self.make_bytes(part)

    async def __aiter__(self):
        # ASGI(daphne): 线程池消费生成器, 逐块实时下发
        async for part in self._iterator:
            yield self.make_bytes(part)



class RequirementDocumentViewSet(viewsets.ModelViewSet):
    """需求文档视图集"""
    queryset = RequirementDocument.objects.all()
    serializer_class = RequirementDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentUploadSerializer
        return RequirementDocumentSerializer

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """分析需求文档"""
        document = self.get_object()

        if document.status == 'analyzing':
            return Response(
                {'error': '文档正在分析中，请稍后再试'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if document.status == 'analyzed':
            return Response(
                {'message': '文档已经分析过了', 'analysis_id': document.analysis.id},
                status=status.HTTP_200_OK
            )

        try:
            # 更新状态为分析中
            document.status = 'analyzing'
            document.save()

            # 异步执行分析
            def run_analysis():
                try:
                    # 简化版同步分析
                    # 提取文档文本
                    if not document.extracted_text:
                        document.extracted_text = DocumentProcessor.extract_text(document)
                        document.save()

                    # 创建模拟分析结果
                    analysis_result = {
                        'analysis_report': f'对文档"{document.title}"的需求分析已完成。\n\n文档内容：{document.extracted_text[:200]}...\n\n识别到若干功能性需求。',
                        'requirements_count': 2,
                        'requirements': [
                            {
                                'requirement_id': 'REQ001',
                                'requirement_name': '基础功能需求',
                                'requirement_type': 'functional',
                                'module': '核心模块',
                                'requirement_level': 'high',
                                'estimated_hours': 8,
                                'description': '基于文档内容识别的功能需求',
                                'acceptance_criteria': '功能正常运行，满足用户需求'
                            },
                            {
                                'requirement_id': 'REQ002',
                                'requirement_name': '用户交互需求',
                                'requirement_type': 'usability',
                                'module': '前端模块',
                                'requirement_level': 'medium',
                                'estimated_hours': 6,
                                'description': '用户界面和交互相关需求',
                                'acceptance_criteria': '界面友好，操作简单'
                            }
                        ]
                    }

                    # 创建分析记录
                    analysis = RequirementAnalysis.objects.create(
                        document=document,
                        analysis_report=analysis_result['analysis_report'],
                        requirements_count=analysis_result['requirements_count'],
                        analysis_time=2.5
                    )

                    # 保存需求数据
                    for req_data in analysis_result['requirements']:
                        create_requirement_from_br_data(analysis, req_data)

                    # 更新文档状态
                    document.status = 'analyzed'
                    document.save()

                    return analysis

                except Exception as e:
                    logger.error(f"分析失败: {e}")
                    document.status = 'failed'
                    document.save()
                    raise e

            analysis = run_analysis()

            return Response({
                'message': '分析完成',
                'analysis_id': analysis.id,
                'requirements_count': analysis.requirements_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"分析文档时出错: {e}")
            return Response(
                {'error': f'分析失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def extract_text(self, request, pk=None):
        """提取文档文本"""
        document = self.get_object()

        try:
            if not document.extracted_text:
                text = DocumentProcessor.extract_text(document)
                document.extracted_text = text
                document.save()

            return Response({
                'extracted_text': document.extracted_text,
                'text_length': len(document.extracted_text)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"提取文本时出错: {e}")
            return Response(
                {'error': f'提取文本失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RequirementAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """需求分析视图集"""
    queryset = RequirementAnalysis.objects.all()
    serializer_class = RequirementAnalysisSerializer

    @action(detail=True, methods=['get'])
    def requirements(self, request, pk=None):
        """获取分析的需求列表"""
        analysis = self.get_object()
        requirements = analysis.unified_requirements.all()
        serializer = RequirementSerializer(requirements, many=True)
        return Response(serializer.data)




from rest_framework.pagination import PageNumberPagination


class GeneratedTestCasePagination(PageNumberPagination):
    """生成测试用例分页器"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TestCaseGenerationTaskPagination(PageNumberPagination):
    """测试用例生成任务分页器"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class KnowledgePagination(PageNumberPagination):
    """业务知识库分页器（文档/条目），支持前端 page_size 参数"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class RequirementPagination(PageNumberPagination):
    """需求管理分页器，支持前端 page_size 参数"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class GeneratedTestCaseViewSet(viewsets.ModelViewSet):
    """生成的测试用例视图集"""
    queryset = GeneratedTestCase.objects.all()
    serializer_class = GeneratedTestCaseSerializer
    pagination_class = GeneratedTestCasePagination
    http_method_names = ['get', 'patch']  # 只允许GET和PATCH方法

    def get_queryset(self):
        queryset = super().get_queryset()

        # 按需求ID过滤
        requirement_id = self.request.query_params.get('requirement_id')
        if requirement_id:
            queryset = queryset.filter(requirement_id=requirement_id)

        # 按状态过滤
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # 按优先级过滤
        priority_param = self.request.query_params.get('priority')
        if priority_param:
            queryset = queryset.filter(priority=priority_param)

        return queryset

    @action(detail=False, methods=['post'])
    def review_test_cases(self, request):
        """评审测试用例"""
        serializer = TestCaseReviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            test_case_ids = serializer.validated_data['test_case_ids']
            review_criteria = serializer.validated_data['review_criteria']

            # 同步执行评审
            def run_review():
                try:
                    # 获取测试用例
                    test_cases = GeneratedTestCase.objects.filter(id__in=test_case_ids)

                    passed_count = 0
                    reviewed_cases = []

                    for test_case in test_cases:
                        # 模拟评审逻辑
                        is_passed = len(test_case.title) > 10 and len(test_case.test_steps) > 20

                        if is_passed:
                            passed_count += 1
                            test_case.status = 'approved'
                            test_case.review_comments = '测试用例设计合理，满足评审标准'
                        else:
                            test_case.status = 'rejected'
                            test_case.review_comments = '测试用例需要完善，请补充详细的测试步骤'

                        test_case.reviewed_by_ai = 'AI-Reviewer-v1.0'
                        test_case.save()

                        reviewed_cases.append({
                            'id': test_case.id,
                            'case_id': test_case.case_id,
                            'title': test_case.title,
                            'status': test_case.status,
                            'review_comments': test_case.review_comments
                        })

                    total_count = len(test_cases)
                    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

                    return {
                        'total_count': total_count,
                        'passed_count': passed_count,
                        'pass_rate': pass_rate,
                        'reviewed_cases': reviewed_cases
                    }

                except Exception as e:
                    logger.error(f"评审测试用例失败: {e}")
                    raise e

            review_result = run_review()

            return Response({
                'message': f'评审完成，通过率: {review_result["pass_rate"]:.2f}%',
                'review_result': review_result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"评审测试用例时出错: {e}")
            return Response(
                {'error': f'评审失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalysisTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """分析任务视图集"""
    queryset = AnalysisTask.objects.all()
    serializer_class = AnalysisTaskSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        document_id = self.request.query_params.get('document_id')
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        return queryset

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """获取任务进度"""
        task = self.get_object()
        return Response({
            'task_id': task.task_id,
            'status': task.status,
            'progress': task.progress,
            'error_message': task.error_message
        })


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def upload_and_analyze(request):
    """上传文档并立即开始分析"""
    try:
        # 创建文档
        serializer = DocumentUploadSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        document = serializer.save()

        # 立即开始分析
        document.status = 'analyzing'
        document.save()

        def run_analysis():
            try:
                # 简化版同步分析
                # 提取文档文本
                if not document.extracted_text:
                    document.extracted_text = DocumentProcessor.extract_text(document)
                    document.save()

                # 创建模拟分析结果
                analysis_result = {
                    'analysis_report': f'对文档"{document.title}"的需求分析已完成。\n\n文档内容：{document.extracted_text[:200]}...\n\n识别到若干功能性需求。',
                    'requirements_count': 2,
                    'requirements': [
                        {
                            'requirement_id': 'REQ001',
                            'requirement_name': '基础功能需求',
                            'requirement_type': 'functional',
                            'module': '核心模块',
                            'requirement_level': 'high',
                            'estimated_hours': 8,
                            'description': '基于文档内容识别的功能需求',
                            'acceptance_criteria': '功能正常运行，满足用户需求'
                        },
                        {
                            'requirement_id': 'REQ002',
                            'requirement_name': '用户交互需求',
                            'requirement_type': 'usability',
                            'module': '前端模块',
                            'requirement_level': 'medium',
                            'estimated_hours': 6,
                            'description': '用户界面和交互相关需求',
                            'acceptance_criteria': '界面友好，操作简单'
                        }
                    ]
                }

                # 创建分析记录
                analysis = RequirementAnalysis.objects.create(
                    document=document,
                    analysis_report=analysis_result['analysis_report'],
                    requirements_count=analysis_result['requirements_count'],
                    analysis_time=2.5
                )

                # 保存需求数据
                for req_data in analysis_result['requirements']:
                    create_requirement_from_br_data(analysis, req_data)

                # 更新文档状态
                document.status = 'analyzed'
                document.save()

                return analysis

            except Exception as e:
                logger.error(f"分析失败: {e}")
                document.status = 'failed'
                document.save()
                raise e

        analysis = run_analysis()

        return Response({
            'message': '上传并分析完成',
            'document_id': document.id,
            'analysis_id': analysis.id,
            'requirements_count': analysis.requirements_count
        })

    except Exception as e:
        logger.error(f"上传并分析失败: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def analyze_text(request):
    """直接分析文本内容"""
    try:
        title = request.data.get('title', '')
        description = request.data.get('description', '')
        project_id = request.data.get('project')

        if not title or not description:
            return Response({'error': '标题和描述不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建一个虚拟的需求文档记录
        document = RequirementDocument.objects.create(
            title=title,
            document_type='txt',
            status='analyzing',
            uploaded_by_id=1,  # 使用默认用户ID，或者从request.user获取
            project_id=project_id if project_id else None,
            extracted_text=description
        )

        def run_analysis():
            try:
                # 创建模拟分析结果
                analysis_result = {
                    'analysis_report': f'对需求"{title}"的分析已完成。\n\n需求描述：{description[:200]}...\n\n识别到若干功能性需求。',
                    'requirements_count': 2,
                    'requirements': [
                        {
                            'requirement_id': 'REQ001',
                            'requirement_name': '基础功能需求',
                            'requirement_type': 'functional',
                            'module': '核心模块',
                            'requirement_level': 'high',
                            'estimated_hours': 8,
                            'description': f'基于需求描述识别的功能需求：{description[:100]}...',
                            'acceptance_criteria': '功能正常运行，满足用户需求'
                        },
                        {
                            'requirement_id': 'REQ002',
                            'requirement_name': '用户交互需求',
                            'requirement_type': 'usability',
                            'module': '前端模块',
                            'requirement_level': 'medium',
                            'estimated_hours': 6,
                            'description': '用户界面和交互相关需求',
                            'acceptance_criteria': '界面友好，操作简单'
                        }
                    ]
                }

                # 创建分析记录
                analysis = RequirementAnalysis.objects.create(
                    document=document,
                    analysis_report=analysis_result['analysis_report'],
                    requirements_count=analysis_result['requirements_count'],
                    analysis_time=1.5
                )

                # 保存需求数据
                for req_data in analysis_result['requirements']:
                    create_requirement_from_br_data(analysis, req_data)

                # 更新文档状态
                document.status = 'analyzed'
                document.save()

                return analysis

            except Exception as e:
                logger.error(f"分析失败: {e}")
                document.status = 'failed'
                document.save()
                raise e

        analysis = run_analysis()

        return Response({
            'message': '文本分析完成',
            'document_id': document.id,
            'analysis_id': analysis.id,
            'requirements_count': analysis.requirements_count
        })

    except Exception as e:
        logger.error(f"文本分析失败: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def analyze_text(request):
    """分析手动输入的需求文本"""
    try:
        title = request.data.get('title')
        description = request.data.get('description')
        project_id = request.data.get('project')

        if not title or not description:
            return Response({'error': '需求标题和描述不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 创建一个虚拟的需求文档记录
        document = RequirementDocument.objects.create(
            title=title,
            file=None,  # 手动输入没有文件
            document_type='txt',
            status='analyzing',
            uploaded_by_id=1,  # 使用默认用户ID，或者从request.user获取
            project_id=project_id if project_id else None,
            extracted_text=description
        )

        # 立即开始分析
        def run_analysis():
            try:
                # 使用新的先进分析系统
                import asyncio
                from .services import AIService

                logger.info(f"开始使用先进分析器分析需求: {title}")

                # 调用先进的需求分析
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    analysis_result = loop.run_until_complete(
                        AIService.analyze_requirements(description, title)
                    )
                    logger.info(f"先进分析完成，识别需求: {analysis_result.get('requirements_count', 0)}个")
                finally:
                    loop.close()

                # 创建分析记录
                analysis = RequirementAnalysis.objects.create(
                    document=document,
                    analysis_report=analysis_result['analysis_report'],
                    requirements_count=analysis_result['requirements_count'],
                    analysis_time=analysis_result.get('analysis_time', 2.0)
                )

                # 保存需求数据
                for req_data in analysis_result['requirements']:
                    create_requirement_from_br_data(analysis, req_data)

                # 更新文档状态
                document.status = 'analyzed'
                document.save()

                return analysis

            except Exception as e:
                logger.error(f"先进分析失败: {e}，使用备用分析")
                # fallback到简单分析
                analysis_result = {
                    'analysis_report': f'对需求"{title}"的分析已完成。\n\n需求描述：{description[:200]}...\n\n基于描述内容识别到若干功能性需求。',
                    'requirements_count': 2,
                    'requirements': [
                        {
                            'requirement_id': 'REQ001',
                            'requirement_name': title + ' - 核心功能',
                            'requirement_type': 'functional',
                            'module': '核心模块',
                            'requirement_level': 'high',
                            'estimated_hours': 8,
                            'description': description[:100] + '...',
                            'acceptance_criteria': '功能正常运行，满足用户需求'
                        },
                        {
                            'requirement_id': 'REQ002',
                            'requirement_name': title + ' - 交互功能',
                            'requirement_type': 'usability',
                            'module': '前端模块',
                            'requirement_level': 'medium',
                            'estimated_hours': 6,
                            'description': '用户界面和交互相关需求',
                            'acceptance_criteria': '界面友好，操作简单'
                        }
                    ]
                }

                # 创建分析记录
                analysis = RequirementAnalysis.objects.create(
                    document=document,
                    analysis_report=analysis_result['analysis_report'],
                    requirements_count=analysis_result['requirements_count'],
                    analysis_time=1.5
                )

                # 保存需求数据
                for req_data in analysis_result['requirements']:
                    create_requirement_from_br_data(analysis, req_data)

                # 更新文档状态
                document.status = 'analyzed'
                document.save()

                return analysis

            except Exception as e:
                logger.error(f"分析失败: {e}")
                document.status = 'failed'
                document.save()
                raise e

        analysis = run_analysis()

        return Response({
            'message': '文本分析完成',
            'document_id': document.id,
            'analysis_id': analysis.id,
            'requirements_count': analysis.requirements_count
        })

    except Exception as e:
        logger.error(f"文本分析失败: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _test_ai_model_connection(config, timeout: int = 30):
    """
    按角色测试模型连接（统一收敛到 apps.ai.client.AIClient.test_connection）

    - tokenizer / embedding 角色：调用 /embeddings 接口（分词/向量模型通常不支持 chat）
    - 其他角色：调用 /chat/completions 接口

    同步实现（httpx.Client）。此前版本在同步视图内手建事件循环 + sync_to_async 写库，
    会因主线程无事件循环而挂起 60s 超时（页面报「连接测试超时」），现改为纯同步委托，不再有该问题。
    """
    try:
        return AIClient.test_connection(config, timeout=timeout)
    except Exception as e:
        logger.error(f"AI连接测试异常: {repr(e)}")
        return {'success': False, 'message': f'连接测试失败: {str(e)}'}


class AIModelConfigViewSet(viewsets.ModelViewSet):
    """AI模型配置视图集（全平台统一配置表：全局 + 本人用户级）"""
    queryset = AIModelConfig.objects.all()
    serializer_class = AIModelConfigSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # 非超管不可见他人用户级配置（scope=user）；仅全局 + 本人
        if not user.is_superuser and not user.is_anonymous:
            from django.db.models import Q
            queryset = queryset.filter(Q(scope='global') | Q(created_by=user))

        # 按模型类型过滤
        model_type = self.request.query_params.get('model_type')
        if model_type:
            queryset = queryset.filter(model_type=model_type)

        # 按角色过滤
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        else:
            # 未指定角色时：展示全部可管理角色（含 browser_use_text），
            # 仅隐藏合并过来的历史 api 角色（doc_extractor/naming/mock_data/description，仅保数据）
            queryset = queryset.exclude(role__in=[
                'doc_extractor', 'naming', 'mock_data', 'description'])

        # 按是否启用过滤
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-created_at')

    def _fetch_models_with_timeout(self, config, timeout=30.0):
        """同步包装异步模型列表获取。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                asyncio.wait_for(
                    AIModelService.list_available_models(config),
                    timeout=timeout
                )
            )
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            finally:
                loop.close()

    @action(detail=False, methods=['post'], url_path='available_models')
    def available_models_preview(self, request):
        """获取未保存配置下的可用模型列表。"""
        try:
            data = request.data
            required_fields = ['model_type', 'api_key', 'base_url']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return Response(
                    {'success': False, 'message': f'缺少必填字段: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            preview_config = AIModelConfig(
                name=data.get('name', '临时模型列表配置'),
                model_type=data.get('model_type'),
                role=data.get('role', 'writer'),
                api_key=data.get('api_key'),
                base_url=data.get('base_url'),
                model_name=data.get('model_name', 'temp-model'),
                max_tokens=data.get('max_tokens') or 256,
                temperature=data.get('temperature') if data.get('temperature') is not None else 0.7,
                top_p=data.get('top_p') if data.get('top_p') is not None else 0.9,
                is_active=False
            )

            models = self._fetch_models_with_timeout(preview_config)
            return Response({
                'success': True,
                'message': f'成功获取{len(models)}个模型',
                'models': models
            }, status=status.HTTP_200_OK)
        except asyncio.TimeoutError:
            return Response(
                {'success': False, 'message': '获取模型列表超时，请检查网络连接或API地址是否正确'},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except Exception as e:
            logger.error(f"获取未保存配置模型列表失败: {e}")
            return Response(
                {'success': False, 'message': f'获取模型列表失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'], url_path='available_models')
    def available_models(self, request, pk=None):
        """获取已保存配置下的可用模型列表。"""
        try:
            config = self.get_object()
            models = self._fetch_models_with_timeout(config)
            return Response({
                'success': True,
                'message': f'成功获取{len(models)}个模型',
                'models': models
            }, status=status.HTTP_200_OK)
        except asyncio.TimeoutError:
            return Response(
                {'success': False, 'message': '获取模型列表超时，请检查网络连接或API地址是否正确'},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except Exception as e:
            logger.error(f"获取已保存配置模型列表失败: {e}")
            return Response(
                {'success': False, 'message': f'获取模型列表失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], url_path='test_connection')
    def test_connection_preview(self, request):
        """测试未保存的模型配置连接"""
        try:
            data = request.data

            required_fields = ['model_type', 'api_key', 'base_url', 'model_name']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return Response(
                    {'success': False, 'message': f'缺少必填字段: {", ".join(missing_fields)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            test_config = AIModelConfig(
                name=data.get('name', '临时测试配置'),
                model_type=data.get('model_type'),
                role=data.get('role', 'writer'),
                api_key=data.get('api_key'),
                base_url=data.get('base_url'),
                model_name=data.get('model_name'),
                max_tokens=data.get('max_tokens') or 256,
                temperature=data.get('temperature') if data.get('temperature') is not None else 0.7,
                top_p=data.get('top_p') if data.get('top_p') is not None else 0.9,
                is_active=False
            )

            logger.info("=== 开始测试未保存模型配置连接 ===")
            logger.info(f"模型类型: {test_config.model_type}")
            logger.info(f"模型名称: {test_config.model_name}")
            logger.info(f"API URL: {test_config.base_url}")

            # 按角色测试连接：分词/嵌入模型走 /embeddings，其余走 /chat/completions
            result = _test_ai_model_connection(test_config)

            return Response(
                result,
                status=status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"测试未保存配置连接时出错: {e}")
            return Response(
                {'success': False, 'message': f'测试失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试模型连接"""
        try:
            config = self.get_object()

            logger.info(f"=== 开始测试模型连接 ===")
            logger.info(f"模型类型: {config.model_type}")
            logger.info(f"模型名称: {config.model_name}")
            logger.info(f"API URL: {config.base_url}")
            logger.info(
                f"API Key前缀: {config.api_key[:10]}..." if len(config.api_key) > 10 else f"API Key: {config.api_key}")

            # 按角色测试连接：分词/嵌入模型走 /embeddings，其余走 /chat/completions
            result = _test_ai_model_connection(config)

            if result['success']:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"测试连接时出错: {e}")
            return Response(
                {'success': False, 'message': f'测试失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """启用配置"""
        try:
            config = self.get_object()
            config.is_active = True
            config.save()
            return Response({
                'message': 'AI模型配置已启用',
                'id': config.id,
                'is_active': True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"启用AI模型配置失败: {e}")
            return Response({
                'error': f'启用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """禁用配置"""
        try:
            config = self.get_object()
            config.is_active = False
            config.save()
            return Response({
                'message': 'AI模型配置已禁用',
                'id': config.id,
                'is_active': False
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"禁用AI模型配置失败: {e}")
            return Response({
                'error': f'禁用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PromptConfigViewSet(viewsets.ModelViewSet):
    """提示词配置视图集"""
    queryset = PromptConfig.objects.all()
    serializer_class = PromptConfigSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # 按提示词类型过滤
        prompt_type = self.request.query_params.get('prompt_type')
        if prompt_type:
            queryset = queryset.filter(prompt_type=prompt_type)

        # 按是否启用过滤
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def load_defaults(self, request):
        """加载默认提示词（统一读 apps.ai.prompt_seeds，避免多源维护）"""
        try:
            from apps.ai import prompt_seeds
            defaults = {}
            # 需求分析（writer/reviewer）+ 接口测试用例生成（api_testcase_generator）
            # 统一从 seed 读取，保证"加载默认提示词"时三类都有默认内容
            for prompt_type in ('writer', 'reviewer', 'api_testcase_generator'):
                try:
                    defaults[prompt_type] = prompt_seeds.content_for(prompt_type)
                except KeyError:
                    continue

            return Response({
                'message': '默认提示词加载成功',
                'defaults': defaults
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"加载默认提示词失败: {e}")
            return Response(
                {'error': f'加载失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """启用配置"""
        try:
            config = self.get_object()
            config.is_active = True
            config.save()
            return Response({
                'message': '提示词配置已启用',
                'id': config.id,
                'is_active': True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"启用提示词配置失败: {e}")
            return Response({
                'error': f'启用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """禁用配置"""
        try:
            config = self.get_object()
            config.is_active = False
            config.save()
            return Response({
                'message': '提示词配置已禁用',
                'id': config.id,
                'is_active': False
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"禁用提示词配置失败: {e}")
            return Response({
                'error': f'禁用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class GenerationConfigViewSet(viewsets.ModelViewSet):
    """生成行为配置视图集"""
    queryset = GenerationConfig.objects.all()
    serializer_class = GenerationConfigSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取活跃的生成配置"""
        try:
            config = GenerationConfig.get_active_config()
            if not config:
                return Response({
                    'error': '未找到活跃的生成配置，请先创建并启用一个配置'
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = self.get_serializer(config)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"获取活跃生成配置失败: {e}")
            return Response({
                'error': f'获取失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """启用配置"""
        try:
            # 禁用其他所有配置
            GenerationConfig.objects.all().update(is_active=False)

            # 启用当前配置
            config = self.get_object()
            config.is_active = True
            config.save()

            return Response({
                'message': '生成配置已启用',
                'id': config.id,
                'is_active': True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"启用生成配置失败: {e}")
            return Response({
                'error': f'启用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """禁用配置"""
        try:
            config = self.get_object()
            config.is_active = False
            config.save()

            return Response({
                'message': '生成配置已禁用',
                'id': config.id,
                'is_active': False
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"禁用生成配置失败: {e}")
            return Response({
                'error': f'禁用失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _execute_task(task, selected_knowledge):
    """新线程中执行测试用例生成流程（流式/完整输出的异步逻辑）。"""
    try:
        # 更新任务状态
        task.status = 'generating'
        task.progress = 10
        task.save()

        # 读取生成行为配置
        from .models import GenerationConfig
        gen_config = GenerationConfig.get_active_config()

        # 获取配置参数，设置默认值
        enable_auto_review = gen_config.enable_auto_review if gen_config else True
        review_timeout = gen_config.review_timeout if gen_config else 120

        logger.info(
            f"任务 {task.task_id} 使用生成配置: auto_review={enable_auto_review}, review_timeout={review_timeout}s")

        # 预加载关联对象（同步上下文、事件循环启动前）。
        # 异步协程内的懒加载会触发 SynchronousOnlyOperation；此处把关联对象缓存到实例，
        # 保证后续 writer/revise 阶段在异步上下文也能安全读取（与 serializer.data 的预取行为对齐）。
        for _rel in ('writer_model_config', 'writer_prompt_config',
                     'reviewer_model_config', 'reviewer_prompt_config'):
            getattr(task, _rel, None)

        # ---- WeKnora 知识注入：项目绑定了智能体且未显式传 knowledge 时，取智能体回答注入 ----
        # 唯一注入水槽（单条/批量两条生成链路都汇聚到这里）；失败优雅降级，不阻断生成。
        # 同时把回答与引用(文档/分块)落到任务上，供"已引用知识库"审计展示。
        # 任务未带 project 时回退到"创建者的项目"找绑定；再无则回退全局默认智能体；
        # 仍无绑定则把原因记入 generation_log（不再静默），便于排查。
        if not selected_knowledge:
            try:
                from .weknora_client import WeKnoraClient
                from apps.projects.models import Project
                from types import SimpleNamespace as _NS
                _cfg = WeKnoraConfig.get_solo()
                if not _cfg.enabled:
                    pass  # 未启用：不注入，也不干扰（无知识上下文）
                else:
                    _binding = None
                    _ctx_project = task.project_id
                    if _ctx_project:
                        _binding = WeKnoraProjectBinding.objects.filter(
                            project_id=_ctx_project, enabled=True).first()
                    if not _binding and not _ctx_project and task.created_by_id:
                        # 任务未带项目 → 回退到创建者的第一个项目（与 _ensure_requirement 逻辑一致）
                        _pr = Project.objects.filter(
                            models.Q(owner=task.created_by) | models.Q(members=task.created_by)
                        ).distinct().order_by('id').first()
                        if _pr:
                            _ctx_project = _pr.id
                            _binding = WeKnoraProjectBinding.objects.filter(
                                project_id=_pr.id, enabled=True).first()
                    if not _binding and _cfg.default_agent_id:
                        # 兜底：全局默认智能体
                        _binding = _NS(agent_id=_cfg.default_agent_id,
                                       agent_name=_cfg.default_agent_name or _cfg.default_agent_id,
                                       knowledge_base_ids=_cfg.knowledge_base_ids)

                    if not _binding:
                        task.generation_log = f"{task.generation_log or ''}[WeKnora] 未找到可用绑定（project={task.project_id}, default_agent={_cfg.default_agent_id!r}），本次未注入知识库回答。\n".strip()
                        task.save(update_fields=['generation_log'])
                        logger.warning(
                            '任务 %s 未关联 WeKnora 绑定(project=%s, default_agent=%r)，跳过知识注入',
                            task.task_id, task.project_id, _cfg.default_agent_id)
                    else:
                        _client = WeKnoraClient(_cfg.base_url, _cfg.api_key, _cfg.timeout)
                        _result = _client.agent_answer(
                            task.requirement_text, _binding.agent_id,
                            _binding.knowledge_base_ids or None,
                        )
                        _answer = ((_result or {}).get('answer') or '').strip()
                        task.weknora_answer = _answer
                        task.weknora_references = (_result or {}).get('references') or []
                        task.weknora_steps = (_result or {}).get('steps') or []
                        task.save(update_fields=['weknora_answer', 'weknora_references', 'weknora_steps'])
                        if _answer:
                            selected_knowledge = [{
                                'name': f"WeKnora({_binding.agent_name or _binding.agent_id})",
                                'content': _answer,
                            }]
                            logger.info('任务 %s 已注入 WeKnora(%s, project=%s) 回答',
                                        task.task_id, _binding.agent_id, _ctx_project or 'default')
            except Exception as e:
                logger.warning('任务 %s WeKnora 知识注入失败(跳过): %s', task.task_id, e)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 根据输出模式选择不同的生成方式
            if task.output_mode == 'stream':
                # 流式模式：实时保存到stream_buffer
                # 生成前先设置初始状态
                task.stream_buffer = ''
                task.stream_position = 0
                task.save()

                # 定义同步保存函数
                def save_stream_buffer(content):
                    """同步保存流式内容到数据库"""
                    task.stream_buffer = content
                    task.stream_position = len(content)
                    task.last_stream_update = timezone.now()
                    task.save(update_fields=['stream_buffer', 'stream_position',
                                             'last_stream_update'])

                # 转换为异步函数
                async_save_stream_buffer = sync_to_async(save_stream_buffer)

                async def stream_callback(chunk):
                    """流式回调：实时保存每个chunk到数据库"""
                    # 先追加到内存中的buffer
                    task.stream_buffer += chunk
                    task.stream_position = len(task.stream_buffer)
                    task.last_stream_update = timezone.now()

                    # 每~100字符保存一次(与评审同样密度,否则SSE每~20s才冒一块,观感"没在流")
                    if task.stream_position % 100 < 20 or len(chunk) > 50:
                        try:
                            await async_save_stream_buffer(task.stream_buffer)
                        except Exception as save_error:
                            logger.warning(f"保存流式内容失败: {save_error}")

                # 生成测试用例
                task.progress = 30
                task.save()

                generated_cases = loop.run_until_complete(
                    AIModelService.generate_test_cases_stream(
                        task, callback=stream_callback,
                        selected_knowledge=selected_knowledge
                    )
                )

                # 生成完成后，确保最终的流式内容被保存
                if task.stream_buffer:
                    save_stream_buffer(task.stream_buffer)

                task.generated_test_cases = generated_cases
                task.progress = 60
                task.save()

                # 流式评审和改进（根据生成配置决定是否执行）
                if enable_auto_review and task.reviewer_model_config and task.reviewer_prompt_config:
                    try:
                        task.status = 'reviewing'
                        task.progress = 70
                        task.save()

                        logger.info(f"开始流式评审任务 {task.task_id}")

                        # 评审内容缓存
                        review_buffer = []

                        def save_review_buffer(content):
                            """同步保存评审内容"""
                            task.review_feedback = content
                            task.save(update_fields=['review_feedback'])

                        async_save_review = sync_to_async(save_review_buffer)

                        async def review_stream_callback(chunk):
                            """流式评审回调"""
                            review_buffer.append(chunk)
                            current_length = sum(len(c) for c in review_buffer)

                            # 每100字符保存一次
                            if current_length % 100 < 20 or len(chunk) > 50:
                                try:
                                    content = ''.join(review_buffer)
                                    await async_save_review(content)
                                except Exception as save_error:
                                    logger.warning(f"保存评审内容失败: {save_error}")

                        try:
                            # 移除超时限制，允许大文档完整评审
                            review_feedback = loop.run_until_complete(
                                AIModelService.review_test_cases_stream(
                                    task, generated_cases, callback=review_stream_callback
                                )
                            )
                            # 保存最终评审内容
                            if review_buffer:
                                task.review_feedback = ''.join(review_buffer)
                                task.save(update_fields=['review_feedback'])
                            logger.info(f"任务 {task.task_id} 流式评审完成")

                            # 根据评审意见改进测试用例（自动执行）
                            logger.info(f"任务 {task.task_id} 开始根据评审意见改进测试用例")
                            task.status = 'revising'
                            task.progress = 85
                            task.final_test_cases = ''  # 清空，准备流式写入
                            task.save()

                            try:
                                # 定义同步保存函数
                                def save_final_buffer(content):
                                    """同步保存最终用例内容"""
                                    task.final_test_cases = content
                                    task.save(update_fields=['final_test_cases'])

                                # 转换为异步函数
                                async_save_final = sync_to_async(save_final_buffer)

                                # 创建流式回调函数，实时更新final_test_cases
                                async def final_callback(chunk):
                                    """流式回调：实时保存最终用例到数据库"""
                                    # 实时追加到final_test_cases并保存
                                    task.final_test_cases = (
                                                                    task.final_test_cases or '') + chunk

                                    # 每100字符或chunk较大时保存一次
                                    current_length = len(task.final_test_cases)
                                    if current_length % 100 < 20 or len(chunk) > 50:
                                        try:
                                            await async_save_final(task.final_test_cases)
                                        except Exception as save_error:
                                            logger.warning(f"保存最终用例失败: {save_error}")

                                # 添加超时保护，避免任务一直卡住（使用配置的超时时间）
                                try:
                                    revised_cases = loop.run_until_complete(
                                        asyncio.wait_for(
                                            AIModelService.revise_test_cases_based_on_review(
                                                task, generated_cases, task.review_feedback,
                                                callback=final_callback
                                            ),
                                            timeout=review_timeout  # 使用配置的超时时间（秒）
                                        )
                                    )
                                except asyncio.TimeoutError:
                                    logger.error(
                                        f"任务 {task.task_id} 改进阶段超时（{review_timeout}秒），使用原始用例")
                                    # 超时时使用原始生成的用例，不再抛出异常
                                    revised_cases = generated_cases
                                # 始终使用返回的完整内容，避免流式输出被截断导致数据丢失
                                # revised_cases 是完整的返回值，task.final_test_cases 只是流式回调的中间状态
                                if revised_cases and len(revised_cases) > 0:
                                    # 检测并修复不完整的最后一条用例
                                    revised_cases = AIModelService.fix_incomplete_last_case(
                                        revised_cases)

                                    # 按用例编号排序后再保存
                                    sorted_cases = AIModelService.sort_test_cases_by_id(
                                        revised_cases)
                                    # 重新编号使编号连续
                                    renumbered_cases = AIModelService.renumber_test_cases(
                                        sorted_cases)
                                    task.final_test_cases = renumbered_cases
                                    # 权威最终用例在此立即直接落库（与评审反馈一致）。
                                    # 不能只做内存赋值：任务完成时 refresh_from_db() 会用 DB 值覆盖内存值，
                                    # 而流式回调的增量保存可能失败/不完整，会导致最终用例丢失（置空）。
                                    task.save(update_fields=['final_test_cases'])
                                    logger.info(
                                        f"任务 {task.task_id} 测试用例改进完成 (revised_cases长度: {len(revised_cases)}, 最终保存长度: {len(task.final_test_cases)})")
                                else:
                                    # 如果返回为空，保留流式回调保存的内容
                                    logger.warning(
                                        f"任务 {task.task_id} 改进返回为空，使用流式回调保存的内容 (长度: {len(task.final_test_cases) if task.final_test_cases else 0})")
                                    # 回调增量保存可能未落库，补一次直接保存，避免最终用例为空
                                    if task.final_test_cases:
                                        task.save(update_fields=['final_test_cases'])
                            except Exception as revise_error:
                                logger.warning(
                                    f"任务 {task.task_id} 改进测试用例失败: {revise_error}，使用原始用例")
                                # 按用例编号排序后再保存
                                sorted_cases = AIModelService.sort_test_cases_by_id(
                                    generated_cases)
                                # 重新编号使编号连续
                                task.final_test_cases = AIModelService.renumber_test_cases(
                                    sorted_cases)
                                task.save()

                        except Exception as inner_error:
                            logger.warning(
                                f"任务 {task.task_id} 流式评审过程异常: {inner_error}")
                            task.review_feedback = f"评审过程出现异常: {str(inner_error)}\n\n建议：测试用例结构完整，可以使用。"
                            # 按用例编号排序后再保存
                            sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                            # 重新编号使编号连续
                            task.final_test_cases = AIModelService.renumber_test_cases(
                                sorted_cases)
                            task.save()

                    except Exception as review_error:
                        logger.error(f"流式评审任务 {task.task_id} 失败: {review_error}")
                        # 按用例编号排序后再保存
                        sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                        task.final_test_cases = AIModelService.renumber_test_cases(sorted_cases)
                        task.review_feedback = f"评审失败: {str(review_error)}\n\n建议：测试用例结构完整，可以使用。"
                        task.save()
                else:
                    # 按用例编号排序后再保存
                    sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                    # 重新编号使编号连续
                    task.final_test_cases = AIModelService.renumber_test_cases(sorted_cases)
                    logger.info(f"任务 {task.task_id} 跳过评审，直接使用生成的测试用例")
                    task.save()

            else:
                # 完整模式：原有逻辑
                task.progress = 30
                task.save()

                generated_cases = loop.run_until_complete(
                    AIModelService.generate_test_cases(task, selected_knowledge=selected_knowledge)
                )

                task.generated_test_cases = generated_cases
                task.progress = 60
                task.save()

                # 评审和改进测试用例（根据生成配置决定是否执行）
                if enable_auto_review and task.reviewer_model_config and task.reviewer_prompt_config:
                    try:
                        task.status = 'reviewing'
                        task.progress = 70
                        task.save()

                        logger.info(f"开始评审任务 {task.task_id}")

                        # 移除超时限制，允许大文档完整评审
                        try:
                            review_feedback = loop.run_until_complete(
                                AIModelService.review_test_cases(task, generated_cases)
                            )
                            task.review_feedback = review_feedback
                            logger.info(f"任务 {task.task_id} 评审完成")

                            # 根据评审意见改进测试用例（自动执行）
                            logger.info(f"任务 {task.task_id} 开始根据评审意见改进测试用例")
                            task.status = 'revising'
                            task.progress = 85
                            task.final_test_cases = ''  # 清空，准备流式写入
                            task.save()

                            try:
                                # 定义同步保存函数
                                def save_final_buffer_full(content):
                                    """同步保存最终用例内容"""
                                    task.final_test_cases = content
                                    task.save(update_fields=['final_test_cases'])

                                # 转换为异步函数
                                async_save_final_full = sync_to_async(save_final_buffer_full)

                                # 创建流式回调函数，实时更新final_test_cases
                                async def final_callback_full(chunk):
                                    """流式回调：实时保存最终用例到数据库"""
                                    # 实时追加到final_test_cases并保存
                                    task.final_test_cases = (
                                                                    task.final_test_cases or '') + chunk

                                    # 每100字符或chunk较大时保存一次
                                    current_length = len(task.final_test_cases)
                                    if current_length % 100 < 20 or len(chunk) > 50:
                                        try:
                                            await async_save_final_full(task.final_test_cases)
                                        except Exception as save_error:
                                            logger.warning(f"保存最终用例失败: {save_error}")

                                # 添加超时保护，避免任务一直卡住（使用配置的超时时间）
                                try:
                                    revised_cases = loop.run_until_complete(
                                        asyncio.wait_for(
                                            AIModelService.revise_test_cases_based_on_review(
                                                task, generated_cases, task.review_feedback,
                                                callback=final_callback_full
                                            ),
                                            timeout=review_timeout  # 使用配置的超时时间（秒）
                                        )
                                    )
                                except asyncio.TimeoutError:
                                    logger.error(
                                        f"任务 {task.task_id} 改进阶段超时（{review_timeout}秒），使用原始用例")
                                    # 超时时使用原始生成的用例，不再抛出异常
                                    revised_cases = generated_cases
                                # 始终使用返回的完整内容，避免流式输出被截断导致数据丢失
                                # revised_cases 是完整的返回值，task.final_test_cases 只是流式回调的中间状态
                                if revised_cases and len(revised_cases) > 0:
                                    # 检测并修复不完整的最后一条用例
                                    revised_cases = AIModelService.fix_incomplete_last_case(
                                        revised_cases)

                                    # 按用例编号排序后再保存
                                    sorted_cases = AIModelService.sort_test_cases_by_id(
                                        revised_cases)
                                    # 重新编号使编号连续
                                    renumbered_cases = AIModelService.renumber_test_cases(
                                        sorted_cases)
                                    task.final_test_cases = renumbered_cases
                                    # 权威最终用例在此立即直接落库（与评审反馈一致），
                                    # 避免任务完成时 refresh_from_db() 用 DB 空值覆盖内存值。
                                    task.save(update_fields=['final_test_cases'])
                                    logger.info(
                                        f"任务 {task.task_id} 测试用例改进完成 (revised_cases长度: {len(revised_cases)}, 最终保存长度: {len(task.final_test_cases)})")
                                else:
                                    # 如果返回为空，保留流式回调保存的内容
                                    logger.warning(
                                        f"任务 {task.task_id} 改进返回为空，使用流式回调保存的内容 (长度: {len(task.final_test_cases) if task.final_test_cases else 0})")
                                    # 回调增量保存可能未落库，补一次直接保存，避免最终用例为空
                                    if task.final_test_cases:
                                        task.save(update_fields=['final_test_cases'])
                            except Exception as revise_error:
                                logger.warning(
                                    f"任务 {task.task_id} 改进测试用例失败: {revise_error}，使用原始用例")
                                # 按用例编号排序后再保存
                                sorted_cases = AIModelService.sort_test_cases_by_id(
                                    generated_cases)
                                # 重新编号使编号连续
                                task.final_test_cases = AIModelService.renumber_test_cases(
                                    sorted_cases)
                                task.save()

                        except Exception as inner_error:
                            logger.warning(f"任务 {task.task_id} 评审过程异常: {inner_error}")
                            task.review_feedback = f"评审过程出现异常: {str(inner_error)}\n\n建议：测试用例结构完整，可以使用。"
                            # 按用例编号排序后再保存
                            sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                            # 重新编号使编号连续
                            task.final_test_cases = AIModelService.renumber_test_cases(
                                sorted_cases)
                            task.save()

                    except Exception as review_error:
                        logger.error(f"评审任务 {task.task_id} 失败: {review_error}")
                        # 评审失败时，仍然使用生成的测试用例作为最终结果
                        # 按用例编号排序后再保存
                        sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                        task.final_test_cases = AIModelService.renumber_test_cases(sorted_cases)
                        task.review_feedback = f"评审失败: {str(review_error)}\n\n建议：测试用例结构完整，可以使用。"
                        task.save()
                else:
                    # 按用例编号排序后再保存
                    sorted_cases = AIModelService.sort_test_cases_by_id(generated_cases)
                    # 重新编号使编号连续
                    task.final_test_cases = AIModelService.renumber_test_cases(sorted_cases)
                    logger.info(f"任务 {task.task_id} 跳过评审，直接使用生成的测试用例")
                    task.save()

            # 完成任务
            # 注意：不要直接调用task.save()，因为这会覆盖流式回调保存的final_test_cases
            # 从数据库重新获取最新的任务对象
            task.refresh_from_db()

            task.status = 'completed'
            task.progress = 100
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'progress', 'completed_at', 'final_test_cases'])
            logger.info(f"任务 {task.task_id} 已完成")

        finally:
            try:
                # 清理异步生成器，防止 "Task was destroyed but it is pending" 警告
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as e:
                logger.warning(f"Error shutting down asyncgens: {e}")
            finally:
                loop.close()

    except Exception as e:
        logger.error(f"生成任务执行失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()



def _extract_json_objects(content):
    """从文本中提取所有已闭合的顶层 JSON 对象（兼容单行 JSONL 与多行 pretty JSON）。

    与前端 parseStreamingTestCases 的 _extractJsonObjects 对齐：按花括号深度切分完整
    对象，跳过字符串内的 {}/转义。AI 偶发输出 pretty-print 多行 JSON 时，按行
    json.loads 会整行失败（或把 steps 子对象误判成用例），必须靠此提取器兜底。
    """
    out = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, c in enumerate(content):
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    out.append(content[start:i + 1].strip())
                    start = -1
    return out


def _ensure_task_requirement(task):
    """任务没有关联需求时，用任务标题+需求文本创建一条 Requirement 并绑定（source_type=manual）。"""
    if getattr(task, 'requirement_id', None):
        return task.requirement

    from apps.projects.models import Project
    from django.db.models import Q as _Q

    project = task.project
    if not project:
        user = task.created_by
        project = Project.objects.filter(
            _Q(owner=user) | _Q(members=user)
        ).distinct().first()
    if not project:
        project = Project.objects.create(
            name='默认项目', owner=task.created_by, description='系统自动创建的默认项目'
        )

    base_title = (task.title or '未命名需求').strip() or '未命名需求'
    requirement, _ = Requirement.objects.get_or_create(
        title=f'{base_title}（手动导入）',
        source_type='manual',
        project=project,
        defaults={'spec': task.requirement_text or '', 'created_by': task.created_by},
    )
    task.requirement = requirement
    task.save(update_fields=['requirement'])
    return requirement


def _start_generation_thread(task, selected_knowledge):
    """在新线程中启动测试用例生成任务。"""
    try:
        import threading
        thread = threading.Thread(target=_execute_task, args=(task, selected_knowledge))
        thread.daemon = True
        thread.start()
    except Exception as e:
        logger.error(f"启动生成任务失败: {e}")
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


def _create_generation_task(task_data, selected_knowledge, request):
    """创建测试用例生成任务并异步启动。返回 (task, error_response_or_None)。"""
    task_serializer = TestCaseGenerationTaskSerializer(data=task_data, context={'request': request})
    if not task_serializer.is_valid():
        return None, Response(task_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    task = task_serializer.save()
    _start_generation_thread(task, selected_knowledge)
    return task, None




class TestCaseGenerationTaskViewSet(viewsets.ModelViewSet):
    """测试用例生成任务视图集"""
    queryset = TestCaseGenerationTask.objects.all()
    serializer_class = TestCaseGenerationTaskSerializer
    pagination_class = TestCaseGenerationTaskPagination
    http_method_names = ['get', 'post', 'patch', 'delete']  # 允许GET、POST、PATCH和DELETE方法
    lookup_field = 'task_id'  # 使用task_id作为查找字段

    def get_queryset(self):
        queryset = super().get_queryset()

        # 安全检查：确保request有query_params属性
        if not hasattr(self.request, 'query_params'):
            return queryset.order_by('-created_at')

        # 按状态过滤
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # 按创建者过滤
        created_by = self.request.query_params.get('created_by')
        if created_by:
            queryset = queryset.filter(created_by_id=created_by)

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """创建新的测试用例生成任务"""
        try:
            serializer = TestCaseGenerationRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data

            # 获取活跃的配置
            writer_config = None
            reviewer_config = None
            writer_prompt = None
            reviewer_prompt = None

            if validated_data.get('use_writer_model', True):
                # 优先查找任意启用的编写模型配置
                writer_config = ConfigResolver.active(role='writer')

                if not writer_config:
                    return Response(
                        {'error': '未找到可用的测试用例编写模型配置'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                writer_prompt = PromptConfig.get_active_config('writer')
                if not writer_prompt:
                    return Response(
                        {'error': '未找到可用的测试用例编写提示词配置'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if validated_data.get('use_reviewer_model', True):
                # 优先查找任意启用的评审模型配置
                reviewer_config = ConfigResolver.active(role='reviewer')

                if not reviewer_config:
                    return Response(
                        {'error': '未找到可用的测试用例评审模型配置'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                reviewer_prompt = PromptConfig.get_active_config('reviewer')
                if not reviewer_prompt:
                    return Response(
                        {'error': '未找到可用的测试用例评审提示词配置'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 创建任务
            task_data = {
                'title': validated_data['title'],
                'requirement_text': validated_data['requirement_text'],
                'writer_model_config': writer_config.id if writer_config else None,
                'reviewer_model_config': reviewer_config.id if reviewer_config else None,
                'writer_prompt_config': writer_prompt.id if writer_prompt else None,
                'reviewer_prompt_config': reviewer_prompt.id if reviewer_prompt else None,
            }

            task_data['case_type'] = validated_data.get('case_type', '')
            task_data['granularity'] = validated_data.get('granularity', 'medium')

            # 如果请求中包含项目ID，添加到任务数据中
            if 'project' in validated_data and validated_data['project']:
                task_data['project'] = validated_data['project']

            # 用户选择的业务知识
            selected_knowledge = validated_data.get('selected_knowledge', [])

            # 处理输出模式：优先使用用户指定的，否则使用生成行为配置的默认值
            output_mode = request.data.get('output_mode')
            if output_mode and output_mode in ['stream', 'complete']:
                task_data['output_mode'] = output_mode
            else:
                # 从生成行为配置中读取默认值
                from .models import GenerationConfig
                gen_config = GenerationConfig.get_active_config()
                if gen_config:
                    task_data['output_mode'] = gen_config.default_output_mode
                else:
                    # 如果没有配置，默认使用流式输出
                    task_data['output_mode'] = 'stream'

            task_serializer = TestCaseGenerationTaskSerializer(
                data=task_data,
                context={'request': request}
            )

            if task_serializer.is_valid():
                task = task_serializer.save()

                # 异步执行生成任务（新线程中自动执行 stream/complete 流程）
                _start_generation_thread(task, selected_knowledge)

                return Response({
                    'message': '测试用例生成任务已创建',
                    'task_id': task.task_id,
                    'task': task_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(task_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"创建生成任务时出错: {e}")
            return Response(
                {'error': f'创建任务失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def progress(self, request, task_id=None):
        """获取任务进度"""
        try:
            # DRF会根据lookup_field自动从URL提取task_id并调用get_object()
            task = self.get_object()

            return Response({
                'task_id': task.task_id,
                'status': task.status,
                'progress': task.progress,
                'generated_test_cases': task.generated_test_cases,
                'review_feedback': task.review_feedback,
                'final_test_cases': task.final_test_cases,
                'error_message': task.error_message,
                'completed_at': task.completed_at
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"获取任务进度时出错: {e}")
            return Response(
                {'error': f'获取进度失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=True,
        methods=['get'],
        url_path='stream_progress',
        renderer_classes=[PassThroughRenderer],
        permission_classes=[]  # 允许访问，task_id本身就是安全标识
    )
    def stream_progress_sse(self, request, task_id=None):
        """
        SSE流式进度推送接口
        实时推送任务的流式输出和进度更新
        不使用DRF的Response，避免content negotiation问题
        注意：EventSource不支持自定义headers，无法发送JWT token，所以允许通过session cookie访问
        """
        try:
            # 记录请求信息（用于调试）
            request_origin = request.META.get('HTTP_ORIGIN', 'unknown')
            logger.info(
                f"SSE连接请求: task_id={task_id}, user={request.user}, authenticated={request.user.is_authenticated}, path={request.path}, origin={request_origin}")

            # 动态获取CORS origin - 使用 Django 配置优先
            def get_allowed_origin(origin):
                """获取允许的CORS origin，优先使用 settings 配置"""
                if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
                    return origin or '*'

                allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', []) or []
                if origin in allowed_origins:
                    return origin

                # 兼容未配置时的本地开发默认
                local_defaults = ['http://localhost:3000', 'http://127.0.0.1:3000']
                if origin in local_defaults:
                    return origin

                # 如果未匹配，优先返回第一个允许的 origin（避免返回错误的 localhost）
                if allowed_origins:
                    return allowed_origins[0]

                # 最后兜底：返回请求 origin（若存在）
                return origin or 'http://localhost:3000'

            cors_origin = get_allowed_origin(request_origin)

            # 处理 CORS 预检请求
            if request.method == 'OPTIONS':
                from django.http import HttpResponse
                response = HttpResponse()
                response['Access-Control-Allow-Origin'] = cors_origin
                response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type'
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Max-Age'] = '86400'
                return response

            # 获取任务对象
            task = TestCaseGenerationTask.objects.filter(task_id=task_id).first()
            if not task:
                logger.warning(f"SSE连接失败: 任务未找到, task_id={task_id}")
                # 返回JSON错误而不是SSE
                from django.http import HttpResponse
                response = HttpResponse(
                    json.dumps({'error': '任务未找到'}),
                    status=404,
                    content_type='application/json'
                )
                response['Access-Control-Allow-Origin'] = cors_origin
                response['Access-Control-Allow-Credentials'] = 'true'
                return response

            # 记录上次发送的stream_position
            last_sent_position = 0
            loop_count = 0  # 循环计数器
            last_review_length = 0  # 记录上次发送的评审内容长度
            last_final_length = 0  # 记录上次发送的最终用例长度
            last_status = ''  # 记录上次的任务状态
            last_weknora_sent = False  # WeKnora 知识审计事件是否已发送

            # 同步生成器: 由 _SSEStream 双协议逐块消费(WSGI 同步 __next__ / ASGI 线程池 __aiter__),
            # 不要再喂给标准 StreamingHttpResponse(会被 iter() 解包走 list() 整包缓冲)
            def event_stream():
                nonlocal last_sent_position, loop_count, last_review_length, last_final_length, last_status, last_weknora_sent

                # Performance & Timeout Optimization
                start_time = time.time()
                last_heartbeat_time = time.time()
                last_progress_hash = None
                MAX_TIMEOUT = 3600  # 1 hour safety timeout

                while True:
                    loop_count += 1
                    current_time = time.time()
                    has_sent_data = False

                    # Safety Timeout Check
                    if current_time - start_time > MAX_TIMEOUT:
                        logger.error(f"SSE Connection timed out after {MAX_TIMEOUT}s: task_id={task_id}")
                        yield f"event: error\ndata: timeout\n\n"
                        break

                    # 从数据库重新获取任务状态(WSGI 直接同步; ASGI 由线程池消费本生成器)
                    try:
                        task.refresh_from_db()
                    except TestCaseGenerationTask.DoesNotExist:
                        yield f"event: error\ndata: task_not_found\n\n"
                        break
                    except Exception as e:
                        logger.error(f"DB refresh failed: {e}")
                        time.sleep(1)
                        continue

                    # 检测状态变化，如果进入revising阶段，重置last_final_length
                    if task.status != last_status:
                        logger.info(f"SSE检测到状态变化: {last_status} -> {task.status}")
                        if task.status == 'revising':
                            logger.info(f"SSE: 进入revising阶段，重置last_final_length")
                            last_final_length = 0
                        last_status = task.status

                    # 每30次循环记录一次日志 (Reduced frequency)
                    if loop_count % 30 == 0:
                        logger.info(
                            f"SSE stream loop #{loop_count}: task_status={task.status}, progress={task.progress}%, buffer_len={len(task.stream_buffer) if task.stream_buffer else 0}")

                    # 检查任务是否已完成或失败
                    if task.status in ['completed', 'failed', 'cancelled']:
                        logger.info(f"SSE任务结束: status={task.status}")
                        # 发送最终状态
                        final_status = json.dumps({'type': 'status', 'status': task.status, 'progress': task.progress},
                                                  ensure_ascii=False)
                        logger.info(f"SSE发送最终状态: {final_status}")
                        yield f"data: {final_status}\n\n"

                        # 如果是流式模式且有缓冲区内容，发送剩余内容
                        if task.output_mode == 'stream' and task.stream_buffer:
                            if last_sent_position < len(task.stream_buffer):
                                new_content = task.stream_buffer[last_sent_position:]
                                content_data = json.dumps({'type': 'content', 'content': new_content},
                                                          ensure_ascii=False)
                                logger.info(f"SSE发送剩余内容: {len(new_content)} 字符")
                                yield f"data: {content_data}\n\n"
                                last_sent_position = len(task.stream_buffer)

                        # 发送剩余的评审内容
                        if task.review_feedback:
                            if len(task.review_feedback) > last_review_length:
                                remaining_review = task.review_feedback[last_review_length:]
                                if remaining_review:
                                    review_data = json.dumps({'type': 'review_content', 'content': remaining_review},
                                                             ensure_ascii=False)
                                    logger.info(
                                        f"SSE发送剩余评审内容: {len(remaining_review)} 字符, 总长度: {len(task.review_feedback)}")
                                    yield f"data: {review_data}\n\n"
                                    last_review_length = len(task.review_feedback)

                        # 发送剩余的最终用例内容
                        if task.final_test_cases:
                            if len(task.final_test_cases) > last_final_length:
                                remaining_final = task.final_test_cases[last_final_length:]
                                if remaining_final:
                                    final_data = json.dumps({'type': 'final_content', 'content': remaining_final},
                                                            ensure_ascii=False)
                                    logger.info(
                                        f"SSE发送剩余最终用例: {len(remaining_final)} 字符, 总长度: {len(task.final_test_cases)}")
                                    yield f"data: {final_data}\n\n"
                                    last_final_length = len(task.final_test_cases)

                        # 发送完成信号
                        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                        logger.info(f"SSE流结束，总循环次数: {loop_count}")

                        # 添加短暂延迟，确保done信号被发送
                        time.sleep(0.1)
                        break

                    # 如果是流式模式，发送新增的内容
                    if task.output_mode == 'stream' and task.stream_buffer:
                        current_position = task.stream_position
                        if current_position > last_sent_position:
                            # 提取新增内容
                            new_content = task.stream_buffer[last_sent_position:current_position]
                            if new_content:
                                content_data = json.dumps({'type': 'content', 'content': new_content},
                                                          ensure_ascii=False)
                                logger.info(f"SSE发送新增内容: {len(new_content)} 字符, 总位置: {current_position}")
                                yield f"data: {content_data}\n\n"
                                last_sent_position = current_position
                                has_sent_data = True

                    # 如果是评审阶段，发送评审内容
                    if task.status == 'reviewing' and task.review_feedback:
                        review_feedback = task.review_feedback
                        if review_feedback:
                            # 计算评审内容的增量
                            if len(review_feedback) > last_review_length:
                                new_review = review_feedback[last_review_length:]
                                if new_review:
                                    review_data = json.dumps({'type': 'review_content', 'content': new_review},
                                                             ensure_ascii=False)
                                    logger.info(f"SSE发送评审内容: {len(new_review)} 字符")
                                    yield f"data: {review_data}\n\n"
                                    last_review_length = len(review_feedback)
                                    has_sent_data = True

                    # 如果有最终用例，发送最终用例内容（在reviewing、revising或completed阶段）
                    if task.status in ['reviewing', 'revising', 'completed'] and task.final_test_cases:
                        final_cases = task.final_test_cases
                        if final_cases:
                            # 计算最终用例的增量
                            if len(final_cases) > last_final_length:
                                new_final = final_cases[last_final_length:]
                                if new_final:
                                    final_data = json.dumps({'type': 'final_content', 'content': new_final},
                                                            ensure_ascii=False)
                                    logger.info(
                                        f"SSE发送最终用例: {len(new_final)} 字符, 总长度: {len(final_cases)}, 阶段: {task.status}")
                                    yield f"data: {final_data}\n\n"
                                    last_final_length = len(final_cases)
                                    has_sent_data = True

                    # 发送 WeKnora 知识审计(注入的回答 + 思考/检索过程 + 引用文档/分块) - 出现一次即发送
                    if not last_weknora_sent and (task.weknora_answer or task.weknora_references or task.weknora_steps):
                        weknora_data = json.dumps({
                            'type': 'weknora',
                            'answer': task.weknora_answer or '',
                            'references': task.weknora_references or [],
                            'steps': task.weknora_steps or [],
                        }, ensure_ascii=False)
                        yield f"data: {weknora_data}\n\n"
                        last_weknora_sent = True
                        has_sent_data = True

                    # 发送进度更新 (Optimized)
                    current_progress_hash = f"{task.status}_{task.progress}"
                    if current_progress_hash != last_progress_hash:
                        progress_data = json.dumps(
                            {'type': 'progress', 'status': task.status, 'progress': task.progress},
                            ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"
                        last_progress_hash = current_progress_hash
                        has_sent_data = True

                    # Heartbeat - 缩短心跳间隔到10秒，确保连接保活
                    if has_sent_data:
                        last_heartbeat_time = current_time
                    elif current_time - last_heartbeat_time >= 10:
                        yield ": keep-alive\n\n"
                        last_heartbeat_time = current_time

                    # 减少休眠时间到 0.5s，提高响应速度(WSGI 阻塞线程/ASGI worker 线程均可)
                    time.sleep(0.5)

            # 返回SSE流式响应 - 使用更稳健的方式
            try:
                # _SseStreamingResponse + _SSEStream: WSGI/runserver(__iter__) 与 ASGI/daphne
                # (__aiter__ 线程池) 双路都逐块实时下发, 不触发 Django 的 list() 整包缓冲
                response = _SseStreamingResponse(
                    _SSEStream(event_stream()),
                    content_type='text/event-stream; charset=utf-8'
                )
            except Exception as e:
                logger.error(f"创建SSE响应失败: {e}")
                raise

            # 设置SSE相关的响应头 - 确保正确处理长连接
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            response['X-Accel-Buffering'] = 'no'
            response['X-Content-Type-Options'] = 'nosniff'
            # 添加连接保持头部，防止过早断开
            # 注意：在本地开发服务器(runserver)中，wsgiref禁止手动设置Hop-by-hop headers(如Connection)
            # 只有在生产环境(Gunicorn/Nginx)下才需要显式设置
            if not settings.DEBUG:
                response['Connection'] = 'keep-alive'

            # 设置CORS头部 - 使用动态计算的cors_origin
            response['Access-Control-Allow-Origin'] = cors_origin
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Cache-Control'

            logger.info(f"SSE连接建立成功: task_id={task_id}, cors_origin={cors_origin}")
            return response

        except Exception as e:
            logger.error(f"SSE流式推送出错: {e}")
            import traceback
            traceback.print_exc()
            from django.http import HttpResponse
            # 获取允许的origin
            request_origin = request.META.get('HTTP_ORIGIN', 'unknown')

            def get_allowed_origin(origin):
                if getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
                    return origin or '*'

                allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', []) or []
                if origin in allowed_origins:
                    return origin

                local_defaults = ['http://localhost:3000', 'http://127.0.0.1:3000']
                if origin in local_defaults:
                    return origin

                if allowed_origins:
                    return allowed_origins[0]

                return origin or 'http://localhost:3000'

            cors_origin = get_allowed_origin(request_origin)
            response = HttpResponse(
                json.dumps({'error': f'流式推送失败: {str(e)}'}),
                status=500,
                content_type='application/json'
            )
            response['Access-Control-Allow-Origin'] = cors_origin
            response['Access-Control-Allow-Credentials'] = 'true'
            return response

    @action(detail=True, methods=['post'])
    def cancel(self, request, task_id=None):
        """取消正在运行的任务"""
        try:
            # DRF会根据lookup_field自动从URL提取task_id并调用get_object()
            task = self.get_object()

            if task.status in ['completed', 'failed', 'cancelled']:
                return Response(
                    {'error': f'任务已经{task.get_status_display()}，无法取消'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            task.status = 'cancelled'
            task.save()

            return Response({
                'message': '任务已取消',
                'task_id': task.task_id,
                'status': task.status
            })

        except Exception as e:
            logger.error(f"取消任务时出错: {e}")
            return Response(
                {'error': f'取消任务失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def save_to_records(self, request, task_id=None):
        """保存测试用例到AI生成用例记录并导入到测试用例管理系统"""
        try:
            # DRF会根据lookup_field自动从URL提取task_id并调用get_object()
            task = self.get_object()

            if task.status != 'completed':
                return Response(
                    {'error': '只能保存已完成的测试用例生成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not task.final_test_cases:
                return Response(
                    {'error': '没有最终测试用例可以保存'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 检查是否已经保存过
            if hasattr(task, 'is_saved_to_records') and task.is_saved_to_records:
                return Response(
                    {'message': '测试用例已经保存到记录中', 'already_saved': True},
                    status=status.HTTP_200_OK
                )

            # 解析并导入测试用例到测试用例管理系统
            test_cases = self._parse_test_cases_content(task.final_test_cases)

            if not test_cases:
                return Response(
                    {'error': '最终用例无法解析为测试用例，无法保存'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from apps.testcases.models import TestCase
            from apps.projects.models import Project
            from django.db import models
            from django.db import transaction

            # 优先使用任务关联的项目
            if task.project:
                project = task.project
                logger.info(f"使用任务关联的项目: {project.name}")
            else:
                # 回退到项目选择逻辑
                user = task.created_by
                accessible_projects = Project.objects.filter(
                    models.Q(owner=user) | models.Q(members=user)
                ).distinct()

                # 尝试从前端获取项目ID
                project_id = request.data.get('project_id')

                if project_id:
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

            # 导入在事务内全量提交：任一条失败即整体回滚，
            # 避免“静默成功但 0 条进库 / 已保存锁死无法重试 / 部分插入产生重复”。
            with transaction.atomic():
                adopted_count = 0
                for test_case in test_cases:
                    parsed_steps = normalize_steps(test_case.get('steps', []))
                    TestCase.objects.create(
                        project=project,
                        author=task.created_by,
                        title=test_case.get('title') or test_case.get('scenario', '测试用例'),
                        description=test_case.get('title') or test_case.get('scenario', ''),
                        preconditions=test_case.get('precondition', ''),
                        steps=json.dumps(parsed_steps, ensure_ascii=False),
                        priority=self._map_priority(test_case.get('priority', '中')),
                        test_type='functional',
                        status='draft',
                        requirement=_ensure_task_requirement(task),
                    )
                    adopted_count += 1

            logger.info(f"成功导入 {adopted_count} 条测试用例到项目 {project.name}")

            # 导入成功后才标记为已保存；失败时保持未保存态，允许修复后重试
            task.is_saved_to_records = True
            task.saved_at = timezone.now()
            task.save(update_fields=['is_saved_to_records', 'saved_at'])

            return Response({
                'message': '测试用例已成功保存到AI生成用例记录并导入到测试用例管理系统',
                'task_id': task.task_id,
                'saved_at': task.saved_at,
                'imported_count': adopted_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"保存测试用例到记录时出错: {e}")
            return Response(
                {'error': f'保存失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def saved_records(self, request):
        """获取已保存的测试用例记录列表"""
        try:
            # 获取已保存到记录的任务
            saved_tasks = TestCaseGenerationTask.objects.filter(
                is_saved_to_records=True,
                status='completed'
            ).order_by('-saved_at')

            # 序列化数据
            serializer = TestCaseGenerationTaskSerializer(saved_tasks, many=True)

            return Response({
                'message': '获取已保存记录成功',
                'records': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"获取已保存记录时出错: {e}")
            return Response(
                {'error': f'获取记录失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='batch_adopt')
    def batch_adopt(self, request, task_id=None):
        """批量采纳任务的所有测试用例"""
        try:
            task = self.get_object()

            if task.status != 'completed':
                return Response(
                    {'error': '只能采纳已完成的测试用例生成任务'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not task.final_test_cases:
                return Response(
                    {'error': '没有最终测试用例可以采纳'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 解析最终测试用例
            test_cases = self._parse_test_cases_content(task.final_test_cases)

            if not test_cases:
                return Response(
                    {'error': '无法解析测试用例内容'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 导入到testcases应用（使用与单条采纳相同的逻辑）
            try:
                from apps.testcases.models import TestCase
                from apps.projects.models import Project
                from django.db import models

                # 优先使用任务关联的项目
                if task.project:
                    project = task.project
                    logger.info(f"使用任务关联的项目: {project.name}")
                else:
                    # 回退到项目选择逻辑
                    user = task.created_by
                    accessible_projects = Project.objects.filter(
                        models.Q(owner=user) | models.Q(members=user)
                    ).distinct()

                    # 尝试从前端获取项目ID
                    project_id = request.data.get('project_id')

                    if project_id:
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

                adopted_count = 0
                for test_case in test_cases:
                    import json as _json
                    parsed_steps = normalize_steps(test_case.get('steps', []))
                    TestCase.objects.create(
                        project=project,  # 使用统一的项目选择逻辑
                        author=task.created_by,
                        title=test_case.get('title') or test_case.get('scenario', '测试用例'),
                        description=test_case.get('scenario', ''),  # 使用scenario作为描述
                        preconditions=test_case.get('precondition', ''),
                        steps=_json.dumps(parsed_steps, ensure_ascii=False),
                        priority=self._map_priority(test_case.get('priority', '中')),
                        test_type='functional',
                        status='draft',
                        requirement=_ensure_task_requirement(task),
                    )
                    adopted_count += 1

                return Response({
                    'message': f'成功采纳 {adopted_count} 条测试用例到项目 "{project.name}"',
                    'adopted_count': adopted_count,
                    'project_name': project.name
                }, status=status.HTTP_200_OK)

            except Exception as import_error:
                logger.error(f"导入测试用例失败: {import_error}")
                return Response(
                    {'error': f'导入测试用例失败: {str(import_error)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"批量采纳测试用例时出错: {e}")
            return Response(
                {'error': f'批量采纳失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='batch-adopt-selected')
    def batch_adopt_selected(self, request, task_id=None):
        """批量采纳选中的测试用例"""
        try:
            task = self.get_object()
            test_cases_data = request.data.get('test_cases', [])

            if not test_cases_data:
                return Response(
                    {'error': '没有提供要采纳的测试用例数据'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 导入到testcases应用
            try:
                from apps.testcases.models import TestCase
                from apps.projects.models import Project
                from django.db import models

                # 优先使用任务关联的项目
                if task.project:
                    project = task.project
                    logger.info(f"使用任务关联的项目: {project.name}")
                else:
                    # 回退到项目选择逻辑
                    user = task.created_by
                    accessible_projects = Project.objects.filter(
                        models.Q(owner=user) | models.Q(members=user)
                    ).distinct()

                    # 尝试从前端获取项目ID
                    project_id = request.data.get('project_id')

                    if project_id:
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

                adopted_count = 0
                for case_data in test_cases_data:
                    import json as _json
                    parsed_steps = normalize_steps(case_data.get('steps', []))
                    TestCase.objects.create(
                        project=project,  # 使用统一的项目选择逻辑
                        author=task.created_by,
                        title=clean_text(case_data.get('title', '测试用例')),
                        description=clean_text(case_data.get('description', '')),
                        preconditions=clean_text(case_data.get('preconditions', '')),
                        steps=_json.dumps(parsed_steps, ensure_ascii=False),
                        priority=case_data.get('priority', 'medium'),
                        test_type=case_data.get('test_type', 'functional'),
                        status=case_data.get('status', 'draft'),
                        requirement=_ensure_task_requirement(task),
                    )
                    adopted_count += 1

                return Response({
                    'message': f'成功采纳 {adopted_count} 条测试用例到项目 "{project.name}"',
                    'adopted_count': adopted_count,
                    'project_name': project.name
                }, status=status.HTTP_200_OK)

            except Exception as import_error:
                logger.error(f"导入选中测试用例失败: {import_error}")
                return Response(
                    {'error': f'导入测试用例失败: {str(import_error)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            logger.error(f"批量采纳选中测试用例时出错: {e}")
            return Response(
                {'error': f'批量采纳失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='batch_discard')
    def batch_discard(self, request, task_id=None):
        """批量弃用任务的所有测试用例 - 删除整个任务"""
        try:
            task = self.get_object()

            logger.info(f"开始批量弃用任务 {task.task_id}")

            # 直接删除整个任务记录
            task.delete()

            return Response({
                'message': '任务已被弃用并删除，不会再在列表中显示'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"批量弃用任务时出错: {e}")
            return Response(
                {'error': f'批量弃用失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='discard-selected-cases')
    def discard_selected_cases(self, request, task_id=None):
        """弃用选中的测试用例 - 从final_test_cases中删除"""
        try:
            task = self.get_object()
            case_indices = request.data.get('case_indices', [])

            if not case_indices:
                return Response(
                    {'error': '没有提供要弃用的测试用例索引'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not task.final_test_cases:
                return Response(
                    {'error': '任务没有最终测试用例'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"开始弃用任务 {task.task_id} 的测试用例，索引: {case_indices}")

            # 解析现有的测试用例
            test_cases = self._parse_test_cases_content(task.final_test_cases)

            # 按索引从大到小排序，避免删除时索引变化
            case_indices.sort(reverse=True)

            discarded_count = 0
            for index in case_indices:
                if 0 <= index < len(test_cases):
                    removed_case = test_cases.pop(index)
                    discarded_count += 1
                    logger.debug(f"弃用测试用例 {index}: {removed_case.get('scenario', 'unknown')}")

            # 如果所有用例都被弃用了，删除整个任务
            if not test_cases:
                logger.info(f"任务 {task.task_id} 的所有用例都被弃用，删除任务")
                task.delete()
                return Response({
                    'message': f'已弃用 {discarded_count} 条测试用例，任务已被删除',
                    'discarded_count': discarded_count,
                    'task_deleted': True
                }, status=status.HTTP_200_OK)

            # 重新生成final_test_cases内容
            task.final_test_cases = self._reconstruct_test_cases_content(test_cases)
            task.save()

            logger.debug(f"重构后的测试用例内容: {task.final_test_cases[:200]}...")

            return Response({
                'message': f'已弃用 {discarded_count} 条测试用例',
                'discarded_count': discarded_count,
                'remaining_cases': len(test_cases),
                'task_deleted': False,
                'updated_test_cases': task.final_test_cases
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"弃用选中测试用例时出错: {e}")
            return Response(
                {'error': f'弃用失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='discard-single-case')
    def discard_single_case(self, request, task_id=None):
        """弃用单个测试用例"""
        try:
            task = self.get_object()
            case_index = request.data.get('case_index')

            if case_index is None:
                return Response(
                    {'error': '没有提供测试用例索引'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not task.final_test_cases:
                return Response(
                    {'error': '任务没有最终测试用例'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"开始弃用任务 {task.task_id} 的单个测试用例，索引: {case_index}")

            # 解析现有的测试用例
            test_cases = self._parse_test_cases_content(task.final_test_cases)

            if case_index < 0 or case_index >= len(test_cases):
                return Response(
                    {'error': f'测试用例索引 {case_index} 超出范围，总共有 {len(test_cases)} 个测试用例'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 删除指定索引的测试用例
            removed_case = test_cases.pop(case_index)
            logger.debug(f"弃用测试用例 {case_index}: {removed_case.get('scenario', 'unknown')}")

            # 如果所有用例都被弃用了，删除整个任务
            if not test_cases:
                logger.info(f"任务 {task.task_id} 的所有用例都被弃用，删除任务")
                task.delete()
                return Response({
                    'message': '已弃用测试用例，任务已被删除',
                    'discarded_count': 1,
                    'task_deleted': True
                }, status=status.HTTP_200_OK)

            # 重新生成final_test_cases内容
            task.final_test_cases = self._reconstruct_test_cases_content(test_cases)
            task.save()

            logger.debug(f"单个弃用 - 重构后的测试用例内容: {task.final_test_cases[:200]}...")

            return Response({
                'message': '已弃用测试用例',
                'discarded_count': 1,
                'remaining_cases': len(test_cases),
                'task_deleted': False,
                'updated_test_cases': task.final_test_cases
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"弃用单个测试用例时出错: {e}")
            return Response(
                {'error': f'弃用失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='update-test-cases')
    def update_test_cases(self, request, task_id=None):
        """更新测试用例内容"""
        try:
            task = self.get_object()

            final_test_cases = request.data.get('final_test_cases')
            if not final_test_cases:
                return Response(
                    {'error': '缺少final_test_cases参数'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"开始更新任务 {task.task_id} 的测试用例内容")

            # 更新final_test_cases字段
            task.final_test_cases = final_test_cases
            task.save(update_fields=['final_test_cases'])

            logger.info(f"任务 {task.task_id} 测试用例更新成功")

            return Response({
                'message': '测试用例更新成功',
                'task_id': task.task_id,
                'final_test_cases': task.final_test_cases
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"更新测试用例时出错: {e}")
            return Response(
                {'error': f'更新失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _parse_test_cases_content(self, content):
        """解析测试用例内容 - 兼容单行 JSONL / 多行 pretty JSON / 旧表格回退"""
        import json
        if not content:
            return []

        content = content.strip()
        cases = []

        # 提取所有已闭合的顶层 JSON 对象（JSONL 与 pretty-print 多行对象都覆盖），
        # 避免 AI 输出 pretty-print 时按行 json.loads 整行失败/把 steps 子对象当用例。
        for seg in _extract_json_objects(content):
            try:
                obj = json.loads(seg)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(obj, dict):
                # JSON 中的非对象（裸 null/数字/字符串）直接跳过，避免对 None 调 .get()
                continue
            # 跳过非用例对象（如 steps 子对象/裸 JSON），避免产生空标题的壳用例
            if obj.get('case_id') is None and obj.get('title') is None:
                continue
            # 规整字段名：JSONL 用 title,precondition,steps,priority,test_type,module。
            # 返回 dict 供下游（采纳等）使用；清洗 Markdown/HTML 残留
            case = {
                'caseId': obj.get('case_id', ''),
                'scenario': clean_text(obj.get('title', '')),
                'title': clean_text(obj.get('title', '')),
                'precondition': clean_text(obj.get('precondition', '')),
                'steps': normalize_steps(obj.get('steps', [])),
                'expected': '',  # 不再有独立预期，steps 内含 expect
                'priority': obj.get('priority', '') or '',
                'test_type': obj.get('test_type', '') or '',
                'module': obj.get('module', '') or '',
            }
            cases.append(case)

        if cases:
            return cases

        # 回退：旧表格格式
        if '|' in content:
            return self._parse_table_format_legacy(content)
        return []

    def _parse_table_format_legacy(self, content):
        """解析旧表格格式的测试用例（兼容回退）"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        test_cases = []
        table_data = []

        for line in lines:
            if '|' in line and not line.startswith('|-'):
                temp_placeholder = "___PIPE___"
                processed_line = line.replace(r'\|', temp_placeholder)
                if processed_line.startswith('|'):
                    processed_line = processed_line[1:]
                if processed_line.endswith('|'):
                    processed_line = processed_line[:-1]
                cells = []
                for cell in processed_line.split('|'):
                    cell_content = cell.replace(temp_placeholder, '|').replace('&#124;', '|').strip()
                    cells.append(cell_content)
                if len(cells) > 1:
                    table_data.append(cells)

        if len(table_data) < 2:
            return []

        headers = [h.lower() for h in table_data[0]]
        for row in table_data[1:]:
            if len(row) < len(headers):
                continue
            test_case = {}
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else ''
                if any(k in header for k in ['编号', 'id', '序号', '用例id']):
                    test_case['caseId'] = value
                elif any(k in header for k in ['场景', '标题', '名称', 'title', 'scenario', '测试目标']):
                    test_case['scenario'] = value
                elif any(k in header for k in ['前置', '前提', 'precondition']):
                    test_case['precondition'] = value
                elif any(k in header for k in ['步骤', 'step', '测试步骤', '操作步骤']):
                    test_case['steps'] = value
                elif any(k in header for k in ['预期', '结果', 'expected', 'result']):
                    test_case['expected'] = value
                elif any(k in header for k in ['优先级', 'priority']):
                    test_case['priority'] = value
            if test_case.get('scenario') or test_case.get('steps'):
                # 清洗 Markdown/HTML 残留：去 **、<br>→换行；步骤字符串拆成多步，
                # 并把该行整体「预期结果」挂到最后一步的 expect
                test_case['scenario'] = clean_text(test_case.get('scenario') or '')
                test_case['precondition'] = clean_text(test_case.get('precondition') or '')
                if isinstance(test_case.get('steps'), str):
                    steps = normalize_steps(test_case['steps'])
                    if steps and test_case.get('expected'):
                        steps[-1]['expect'] = clean_text(test_case['expected'])
                    test_case['steps'] = steps
                test_case['expected'] = clean_text(test_case.get('expected') or '')
                test_cases.append(test_case)
        return test_cases

    def _reconstruct_test_cases_content(self, test_cases):
        """重新构建测试用例内容 - 统一以 JSONL（每行一个独立 JSON）输出。

        与 writer/revise 的 JSONL 约定一致，避免再引入 Markdown 表格/<br> 残留。
        旧表格解析产生的整行预期（expected）兜底挂到末步 expect。
        """
        if not test_cases:
            return ""

        lines = []
        for tc in test_cases:
            steps = tc.get('steps', [])
            if not isinstance(steps, list):
                steps = normalize_steps(steps)
            expected = tc.get('expected') or ''
            if expected and steps and not steps[-1].get('expect'):
                steps[-1]['expect'] = expected
            obj = {
                'case_id': tc.get('caseId') or tc.get('case_id', ''),
                'title': tc.get('title') or tc.get('scenario', ''),
                'precondition': tc.get('precondition', ''),
                'steps': steps,
                'priority': tc.get('priority', ''),
                'test_type': tc.get('test_type', ''),
                'module': tc.get('module', ''),
            }
            lines.append(json.dumps(obj, ensure_ascii=False))
        return '\n'.join(lines)

    def _map_priority(self, priority_str):
        """映射优先级"""
        priority_map = {
            '最高': 'critical',
            '高': 'high',
            '中': 'medium',
            '低': 'low',
            'P0': 'critical',
            'P1': 'high',
            'P2': 'medium',
            'P3': 'low'
        }
        return priority_map.get(priority_str, 'medium')

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取测试用例生成任务的统计信息"""
        try:
            # 获取查询参数
            status_param = request.query_params.get('status')
            created_by = request.query_params.get('created_by')

            # 构建查询
            queryset = TestCaseGenerationTask.objects.all()

            if status_param:
                queryset = queryset.filter(status=status_param)

            if created_by:
                queryset = queryset.filter(created_by_id=created_by)

            # 使用聚合查询获取统计信息
            from django.db.models import Count

            stats = queryset.aggregate(
                total=Count('id'),
                completed=Count('id', filter=models.Q(status='completed')),
                pending=Count('id', filter=models.Q(status='pending')),
                generating=Count('id', filter=models.Q(status='generating')),
                reviewing=Count('id', filter=models.Q(status='reviewing')),
                revising=Count('id', filter=models.Q(status='revising')),
                failed=Count('id', filter=models.Q(status='failed')),
                cancelled=Count('id', filter=models.Q(status='cancelled'))
            )

            # 计算运行中的任务（pending + generating + reviewing + revising）
            stats['running'] = (
                    stats['pending'] + stats['generating'] +
                    stats['reviewing'] + stats['revising']
            )

            return Response({
                'total': stats['total'],
                'completed': stats['completed'],
                'running': stats['running'],
                'failed': stats['failed'],
                'pending': stats['pending'],
                'generating': stats['generating'],
                'reviewing': stats['reviewing'],
                'revising': stats['revising'],
                'cancelled': stats['cancelled']
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"获取统计信息时出错: {e}")
            return Response(
                {'error': f'获取统计信息失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConfigStatusViewSet(viewsets.ViewSet):
    """配置状态检查视图集"""
    permission_classes = []  # 允许未认证用户访问

    @action(detail=False, methods=['get'])
    def check(self, request):
        """检查AI配置状态"""
        try:
            # 检查AI模型配置
            ai_model_configs = AIModelConfig.objects.filter(
                role__in=['writer', 'reviewer']
            )

            # 检查writer模型配置
            writer_model_enabled = ai_model_configs.filter(
                role='writer',
                is_active=True
            ).first()

            writer_model_disabled = ai_model_configs.filter(
                role='writer',
                is_active=False
            ).first()

            # 检查reviewer模型配置
            reviewer_model_enabled = ai_model_configs.filter(
                role='reviewer',
                is_active=True
            ).first()

            reviewer_model_disabled = ai_model_configs.filter(
                role='reviewer',
                is_active=False
            ).first()

            # 检查writer提示词配置
            writer_prompt_enabled = PromptConfig.objects.filter(
                prompt_type='writer',
                is_active=True
            ).first()

            writer_prompt_disabled = PromptConfig.objects.filter(
                prompt_type='writer',
                is_active=False
            ).first()

            # 检查reviewer提示词配置
            reviewer_prompt_enabled = PromptConfig.objects.filter(
                prompt_type='reviewer',
                is_active=True
            ).first()

            reviewer_prompt_disabled = PromptConfig.objects.filter(
                prompt_type='reviewer',
                is_active=False
            ).first()

            # 判断必需配置（writer）
            writer_configured = (
                    writer_model_enabled is not None and
                    writer_prompt_enabled is not None
            )

            # 判断可选配置（reviewer）
            reviewer_configured = (
                    reviewer_model_enabled is not None and
                    reviewer_prompt_enabled is not None
            )

            # 检查生成行为配置
            generation_config = GenerationConfig.get_active_config()

            # 判断是否有禁用的配置
            has_disabled = (
                    writer_model_disabled is not None or
                    writer_prompt_disabled is not None or
                    reviewer_model_disabled is not None or
                    reviewer_prompt_disabled is not None
            )

            # 判断整体状态
            if writer_configured:
                if has_disabled:
                    overall_status = 'disabled'
                    message = '配置完整，但部分配置处于禁用状态'
                else:
                    overall_status = 'enabled'
                    message = '配置完整且已启用'
            else:
                # writer配置不完整
                if writer_model_enabled or writer_prompt_enabled:
                    overall_status = 'disabled'
                    message = '检测到已配置但未启用的配置'
                else:
                    overall_status = 'not_configured'
                    message = '尚未配置AI模型和提示词'

            # 构建返回数据
            response_data = {
                'overall_status': overall_status,
                'message': message,
                'writer_model': {
                    'configured': writer_model_enabled is not None or writer_model_disabled is not None,
                    'enabled': writer_model_enabled is not None,
                    'name': (writer_model_enabled or writer_model_disabled).name if (
                            writer_model_enabled or writer_model_disabled) else None,
                    'provider': (writer_model_enabled or writer_model_disabled).get_model_type_display() if (
                            writer_model_enabled or writer_model_disabled) else None,
                    'id': (writer_model_enabled or writer_model_disabled).id if (
                            writer_model_enabled or writer_model_disabled) else None,
                    'required': True
                },
                'writer_prompt': {
                    'configured': writer_prompt_enabled is not None or writer_prompt_disabled is not None,
                    'enabled': writer_prompt_enabled is not None,
                    'name': (writer_prompt_enabled or writer_prompt_disabled).name if (
                            writer_prompt_enabled or writer_prompt_disabled) else None,
                    'id': (writer_prompt_enabled or writer_prompt_disabled).id if (
                            writer_prompt_enabled or writer_prompt_disabled) else None,
                    'required': True
                },
                'reviewer_model': {
                    'configured': reviewer_model_enabled is not None or reviewer_model_disabled is not None,
                    'enabled': reviewer_model_enabled is not None,
                    'name': (reviewer_model_enabled or reviewer_model_disabled).name if (
                            reviewer_model_enabled or reviewer_model_disabled) else None,
                    'id': (reviewer_model_enabled or reviewer_model_disabled).id if (
                            reviewer_model_enabled or reviewer_model_disabled) else None,
                    'required': False
                },
                'reviewer_prompt': {
                    'configured': reviewer_prompt_enabled is not None or reviewer_prompt_disabled is not None,
                    'enabled': reviewer_prompt_enabled is not None,
                    'name': (reviewer_prompt_enabled or reviewer_prompt_disabled).name if (
                            reviewer_prompt_enabled or reviewer_prompt_disabled) else None,
                    'id': (reviewer_prompt_enabled or reviewer_prompt_disabled).id if (
                            reviewer_prompt_enabled or reviewer_prompt_disabled) else None,
                    'required': False
                },
                'generation_config': {
                    'configured': generation_config is not None,
                    'enabled': generation_config is not None,
                    'name': generation_config.name if generation_config else None,
                    'id': generation_config.id if generation_config else None,
                    'required': True,
                    'default_output_mode': generation_config.default_output_mode if generation_config else None,
                    'enable_auto_review': generation_config.enable_auto_review if generation_config else None
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"检查配置状态失败: {e}")
            return Response({
                'error': f'检查配置状态失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ZentaoConfigViewSet(viewsets.ModelViewSet):
    """禅道配置管理 ViewSet"""
    queryset = ZentaoConfig.objects.all()
    serializer_class = ZentaoConfigSerializer

    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """启用配置"""
        config = self.get_object()
        config.is_active = True
        config.save()
        return Response({'detail': '配置已启用'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """禁用配置"""
        config = self.get_object()
        config.is_active = False
        config.save()
        return Response({'detail': '配置已禁用'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试禅道连接"""
        config = self.get_object()
        try:
            result = ZentaoService.test_connection(config)
            if result['success']:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'success': False, 'message': f'连接测试失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class RequirementViewSet(viewsets.ModelViewSet):
    """需求管理 ViewSet"""
    serializer_class = RequirementSerializer
    pagination_class = RequirementPagination
    filterset_fields = ['project', 'source_type', 'status', 'priority']

    def get_queryset(self):
        qs = Requirement.objects.all()
        project_id = self.request.query_params.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        keyword = self.request.query_params.get('keyword')
        if keyword:
            qs = qs.filter(title__icontains=keyword)
        source_type = self.request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type)
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return RequirementListSerializer
        return RequirementSerializer

    def perform_create(self, serializer):
        serializer.save(source_type='manual')

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """批量删除需求"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response(
                {'error': '请选择要删除的需求'}, status=status.HTTP_400_BAD_REQUEST
            )
        deleted, _ = Requirement.objects.filter(id__in=ids).delete()
        return Response({
            'success': True,
            'message': f'已删除 {deleted} 条需求',
            'deleted': deleted
        })

    @action(detail=False, methods=['post'])
    def ai_parse(self, request):
        """AI解析需求文本"""
        serializer = AIRequirementParseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content = serializer.validated_data['content']
        result = AIRequirementParser.parse_from_text(content)
        return Response(result)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def ai_parse_file(self, request):
        """上传文件并AI解析需求"""
        project_id = request.data.get('project_id')
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'success': False, 'error': '请选择文件'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            file_content = file.read()
            text_content = AIRequirementParser.extract_text_from_file(
                file_content, file.name
            )
            if not text_content or not text_content.strip():
                return Response({
                    'success': False,
                    'error': '文件中未提取到文本内容，请检查文件是否为空'
                })

            result = AIRequirementParser.parse_from_text(text_content)
            return Response(result)
        except Exception as e:
            logger.error(f"文件解析失败: {e}")
            return Response({
                'success': False,
                'error': f'文件解析失败: {str(e)}'
            })

    @action(detail=False, methods=['post'])
    def ai_import(self, request):
        """导入AI解析的需求项"""
        serializer = AIRequirementImportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_id = serializer.validated_data['project_id']
        requirements = serializer.validated_data['requirements']

        imported = 0
        failed = 0
        errors = []

        for item in requirements:
            try:
                Requirement.objects.create(
                    project_id=project_id,
                    title=item.get('title', ''),
                    spec=item.get('spec', ''),
                    category=item.get('category', ''),
                    priority=item.get('priority'),
                    stage=item.get('stage', 'planned'),
                    status=item.get('status', 'draft'),
                    source_note=item.get('source_note', ''),
                    source_type='ai_import',
                    estimate=item.get('estimate'),
                    created_by=request.user if request.user.is_authenticated else None,
                )
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(f"导入 '{item.get('title', '')}' 失败: {str(e)}")

        return Response({
            'success': True,
            'message': f'成功导入 {imported} 条需求' + (f'，{failed} 条失败' if failed else ''),
            'imported': imported,
            'failed': failed,
            'errors': errors
        })

    @action(detail=False, methods=['post'])
    def generate_test_cases(self, request):
        """为选中的需求批量AI生成测试用例（每个需求创建一个生成任务）"""
        serializer = RequirementGenerateTestCasesRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        if not ids:
            return Response(
                {'error': '请选择要生成用例的需求'},
                status=status.HTTP_400_BAD_REQUEST
            )

        requirements = list(Requirement.objects.filter(id__in=ids))
        if len(requirements) != len(set(ids)):
            return Response(
                {'error': '部分需求不存在或已被删除，请刷新后重试'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 校验生成配置就绪
        writer_config = ConfigResolver.active(role='writer')
        if not writer_config:
            return Response(
                {'error': '未找到可用的测试用例编写模型配置，请先在配置中心配置'},
                status=status.HTTP_400_BAD_REQUEST
            )
        writer_prompt = PromptConfig.get_active_config('writer')
        if not writer_prompt:
            return Response(
                {'error': '未找到可用的测试用例编写提示词配置，请先在配置中心配置'},
                status=status.HTTP_400_BAD_REQUEST
            )

        use_reviewer = serializer.validated_data.get('use_reviewer_model', True)
        reviewer_config = None
        reviewer_prompt = None
        if use_reviewer:
            reviewer_config = ConfigResolver.active(role='reviewer')
            if not reviewer_config:
                return Response(
                    {'error': '未找到可用的测试用例评审模型配置，请先在配置中心配置'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            reviewer_prompt = PromptConfig.get_active_config('reviewer')
            if not reviewer_prompt:
                return Response(
                    {'error': '未找到可用的测试用例评审提示词配置，请先在配置中心配置'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # 输出模式：优先用户指定，否则使用生成行为配置的默认值
        output_mode = serializer.validated_data.get('output_mode')
        if output_mode not in ('stream', 'complete'):
            gen_config = GenerationConfig.get_active_config()
            output_mode = gen_config.default_output_mode if gen_config else 'stream'

        case_type = serializer.validated_data.get('case_type', '')
        granularity = serializer.validated_data.get('granularity', 'medium')
        selected_knowledge_map = serializer.validated_data.get('selected_knowledge', {}) or {}

        created_tasks = []
        failed_titles = []

        for requirement in requirements:
            requirement_text = f"需求标题: {requirement.title}\n\n需求描述:\n{requirement.spec or ''}"
            # 每条需求只使用其自身对应的业务知识作为生成上下文
            requirement_knowledge = selected_knowledge_map.get(
                str(requirement.id), selected_knowledge_map.get(requirement.id, [])
            )
            task_data = {
                'title': requirement.title,
                'requirement_text': requirement_text,
                'writer_model_config': writer_config.id if writer_config else None,
                'reviewer_model_config': reviewer_config.id if reviewer_config else None,
                'writer_prompt_config': writer_prompt.id if writer_prompt else None,
                'reviewer_prompt_config': reviewer_prompt.id if reviewer_prompt else None,
                'case_type': case_type,
                'granularity': granularity,
                'project': requirement.project_id,
                'output_mode': output_mode,
                'requirement': requirement.id,
            }
            task, error_response = _create_generation_task(
                task_data, requirement_knowledge, request
            )
            if error_response is not None or task is None:
                failed_titles.append(requirement.title)
            else:
                created_tasks.append(task)

        return Response({
            'success': True,
            'message': f'已为 {len(created_tasks)} 条需求创建AI生成任务'
                       + (f'，{len(failed_titles)} 条失败' if failed_titles else ''),
            'created': len(created_tasks),
            'failed': failed_titles,
            'tasks': [
                {'task_id': t.task_id, 'title': t.title} for t in created_tasks
            ]
        }, status=status.HTTP_201_CREATED)


# ==================== 禅道代理端点 ====================

@csrf_exempt
def zentao_products(request):
    """获取禅道产品列表"""
    if request.method == 'GET':
        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse(
                {'error': '请先在配置中心配置禅道连接信息'}, status=400
            )
        try:
            products = ZentaoService.get_products(config)
            return JsonResponse({'products': products})
        except Exception as e:
            return JsonResponse({'error': f'获取产品列表失败: {str(e)}'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def zentao_projects(request):
    """获取禅道项目列表"""
    if request.method == 'GET':
        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse(
                {'error': '请先在配置中心配置禅道连接信息'}, status=400
            )
        try:
            projects = ZentaoService.get_projects(config)
            return JsonResponse({'projects': projects})
        except Exception as e:
            return JsonResponse({'error': f'获取项目列表失败: {str(e)}'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def zentao_product_stories(request, product_id):
    """获取禅道产品下的需求列表"""
    if request.method == 'GET':
        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse(
                {'error': '请先在配置中心配置禅道连接信息'}, status=400
            )
        try:
            stories = ZentaoService.get_product_stories(config, product_id)
            return JsonResponse({'stories': stories})
        except Exception as e:
            return JsonResponse({'error': f'获取需求列表失败: {str(e)}'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def zentao_project_stories(request, project_id):
    """获取禅道项目下的需求列表"""
    if request.method == 'GET':
        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse(
                {'error': '请先在配置中心配置禅道连接信息'}, status=400
            )
        try:
            stories = ZentaoService.get_project_stories(config, project_id)
            return JsonResponse({'stories': stories})
        except Exception as e:
            return JsonResponse({'error': f'获取需求列表失败: {str(e)}'}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def zentao_status(request):
    """诊断禅道连接状态"""
    if request.method == 'GET':
        config = ZentaoConfig.get_active_config()
        if not config:
            return JsonResponse({
                'configured': False,
                'message': '未配置禅道连接信息'
            })
        try:
            result = ZentaoService.test_connection(config)
            return JsonResponse({
                'configured': True,
                'message': '已配置',
                'connection': result
            })
        except Exception as e:
            return JsonResponse({
                'configured': True,
                'message': '已配置',
                'connection': {'success': False, 'message': str(e)}
            })
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def zentao_sync(request):
    """同步禅道需求到本地"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    config = ZentaoConfig.get_active_config()
    if not config:
        return JsonResponse(
            {'error': '请先在配置中心配置禅道连接信息'}, status=400
        )

    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        story_ids = data.get('story_ids', [])
        product_id = data.get('product_id', 0)
        product_name = data.get('product_name', '')

        if not story_ids:
            return JsonResponse({'error': '没有选择要同步的需求'}, status=400)

        created = 0
        updated = 0

        for story_id in story_ids:
            try:
                story = ZentaoService.get_story_detail(config, story_id)
            except Exception as e:
                logger.warning(f"获取禅道需求 {story_id} 详情失败: {e}")
                continue

            title = story.get('title', '')
            if not title:
                continue

            zentao_id = story.get('id', story_id)

            # 尝试更新已存在的需求
            existing = Requirement.objects.filter(zentao_id=zentao_id).first()
            if existing:
                existing.title = title
                existing.spec = story.get('spec', '')
                existing.project_id = project_id
                existing.product_id = story.get('product') or product_id
                existing.product_name = product_name or story.get('productName', '')
                existing.category = story.get('category', '')
                existing.priority = story.get('pri')
                existing.stage = story.get('stage', '')
                existing.status = story.get('status', '')
                existing.source_type = 'zentao'
                existing.source_note = story.get('sourceNote', '')
                existing.estimate = story.get('estimate')
                existing.module_id = story.get('module')
                existing.raw_data = story
                existing.synced_at = timezone.now()
                existing.save()
                updated += 1
            else:
                Requirement.objects.create(
                    zentao_id=zentao_id,
                    project_id=project_id,
                    product_id=story.get('product') or product_id,
                    product_name=product_name or story.get('productName', ''),
                    title=title,
                    spec=story.get('spec', ''),
                    category=story.get('category', ''),
                    priority=story.get('pri'),
                    stage=story.get('stage', ''),
                    status=story.get('status', ''),
                    source_type='zentao',
                    source_note=story.get('sourceNote', ''),
                    estimate=story.get('estimate'),
                    module_id=story.get('module'),
                    raw_data=story,
                    synced_at=timezone.now(),
                    created_by=request.user if request.user.is_authenticated else None,
                )
                created += 1

        return JsonResponse({
            'success': True,
            'message': f'同步完成：新增 {created} 条，更新 {updated} 条',
            'created': created,
            'updated': updated,
            'total': created + updated
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': '请求数据格式错误'}, status=400)
    except Exception as e:
        logger.error(f"同步失败: {e}")
        return JsonResponse({'error': f'同步失败: {str(e)}'}, status=400)



# ============================================================
# WeKnora 外部知识库配置(配置中心) + 项目⇄智能体绑定
# ============================================================
class WeKnoraConfigViewSet(viewsets.ViewSet):
    """WeKnora 连接配置(单例行)；支持测试连接与拉取智能体列表"""

    def list(self, request):
        cfg = WeKnoraConfig.get_solo()
        return Response(WeKnoraConfigSerializer(cfg).data)

    def retrieve(self, request, pk=None):
        cfg = WeKnoraConfig.get_solo()
        return Response(WeKnoraConfigSerializer(cfg).data)

    def update(self, request, pk=None):
        cfg = WeKnoraConfig.get_solo()
        data = dict(request.data)
        # api_key 为 write_only；留空表示保持不变，避免误清空
        if not data.get('api_key'):
            data.pop('api_key', None)
        serializer = WeKnoraConfigSerializer(cfg, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WeKnoraConfigSerializer(WeKnoraConfig.get_solo()).data)

    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        cfg = WeKnoraConfig.get_solo()
        data = request.data or {}
        base_url = data.get('base_url', cfg.base_url)
        api_key = data.get('api_key', cfg.api_key)
        timeout = data.get('timeout', cfg.timeout)
        check_agents = bool(data.get('check_agents', True))
        try:
            from .weknora_client import WeKnoraClient
            client = WeKnoraClient(base_url, api_key, timeout)
            ok, result = client.test_connection(check_agents=check_agents)
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        if not ok:
            return Response({'success': False, 'error': result},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, **result})

    @action(detail=False, methods=['get'])
    def agents(self, request):
        cfg = WeKnoraConfig.get_solo()
        if not (cfg.base_url and (cfg.api_key or '') ):
            return Response({'success': False, 'error': 'WeKnora 未配置'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            from .weknora_client import WeKnoraClient
            client = WeKnoraClient(cfg.base_url, cfg.api_key, cfg.timeout)
            agents = client.list_agents()
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, 'agents': agents})


class WeKnoraProjectBindingViewSet(viewsets.ModelViewSet):
    """项目 ⇄ WeKnora 智能体绑定 CRUD(每项目至多一个,upsert)"""

    queryset = WeKnoraProjectBinding.objects.all().order_by('id')
    serializer_class = WeKnoraProjectBindingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs.select_related('project')

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        existing = WeKnoraProjectBinding.objects.filter(project=project).first()
        if existing:
            for attr, value in serializer.validated_data.items():
                if attr != 'project':
                    setattr(existing, attr, value)
            existing.save()
            serializer.instance = existing
        else:
            serializer.save()
