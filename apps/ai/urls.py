# -*- coding: utf-8 -*-
"""AI 网关路由。"""

from rest_framework.routers import DefaultRouter

from .views import AiCallRecordViewSet

router = DefaultRouter()
router.register(r'ai-call-records', AiCallRecordViewSet)

urlpatterns = router.urls
