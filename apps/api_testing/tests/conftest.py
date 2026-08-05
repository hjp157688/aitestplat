# -*- coding: utf-8 -*-
"""pytest 配置：为 api_testing 测试初始化 Django app registry"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()