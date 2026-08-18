from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RequirementDocumentViewSet,
    RequirementAnalysisViewSet,
    GeneratedTestCaseViewSet,
    AnalysisTaskViewSet,
    AIModelConfigViewSet,
    PromptConfigViewSet,
    GenerationConfigViewSet,
    TestCaseGenerationTaskViewSet,
    ConfigStatusViewSet,
    ZentaoConfigViewSet,
    RequirementViewSet,
    KnowledgeDocumentViewSet,
    KnowledgeEntryViewSet,
    KnowledgeRetrieveViewSet,
    upload_and_analyze,
    analyze_text,
    zentao_products,
    zentao_projects,
    zentao_product_stories,
    zentao_project_stories,
    zentao_status,
    zentao_sync,
)

# 创建DRF路由器
router = DefaultRouter()
router.register(r'documents', RequirementDocumentViewSet, basename='requirementdocument')
router.register(r'analyses', RequirementAnalysisViewSet, basename='requirementanalysis')
router.register(r'test-cases', GeneratedTestCaseViewSet, basename='generatedtestcase')
router.register(r'tasks', AnalysisTaskViewSet, basename='analysistask')
router.register(r'ai-models', AIModelConfigViewSet, basename='aimodelconfig')
router.register(r'prompts', PromptConfigViewSet, basename='promptconfig')
router.register(r'generation-config', GenerationConfigViewSet, basename='generationconfig')
router.register(r'testcase-generation', TestCaseGenerationTaskViewSet, basename='testcasegenerationtask')
router.register(r'config', ConfigStatusViewSet, basename='configstatus')
router.register(r'zentao-config', ZentaoConfigViewSet, basename='zentaoconfig')
router.register(r'requirements-manage', RequirementViewSet, basename='requirementmanage')
router.register(r'knowledge-documents', KnowledgeDocumentViewSet, basename='knowledgedocument')
router.register(r'knowledge-entries', KnowledgeEntryViewSet, basename='knowledgeentry')
router.register(r'knowledge', KnowledgeRetrieveViewSet, basename='knowledgeretrieve')

app_name = 'requirement_analysis'

urlpatterns = [
    # DRF路由
    path('', include(router.urls)),

    # 特殊API端点
    path('upload-and-analyze/', upload_and_analyze, name='upload-and-analyze'),
    path('analyze-text/', analyze_text, name='analyze-text'),

    # 禅道代理端点
    path('zentao/products/', zentao_products, name='zentao-products'),
    path('zentao/projects/', zentao_projects, name='zentao-projects'),
    path('zentao/products/<int:product_id>/stories/', zentao_product_stories, name='zentao-product-stories'),
    path('zentao/projects/<int:project_id>/stories/', zentao_project_stories, name='zentao-project-stories'),
    path('zentao/status/', zentao_status, name='zentao-status'),
    path('zentao/sync/', zentao_sync, name='zentao-sync'),
]