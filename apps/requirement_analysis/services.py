import os
import json
import time
import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    from PyPDF2 import PdfReader
except ImportError:
    from PyPDF2 import PdfFileReader as PdfReader
    
try:
    import docx
except ImportError:
    docx = None
from django.conf import settings
from django.core.files.storage import default_storage

from .models import RequirementDocument, RequirementAnalysis, Requirement, GeneratedTestCase, AnalysisTask, create_requirement_from_br_data

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理服务"""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """从PDF文件提取文本"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"PDF文本提取失败: {e}")
            return f"PDF文本提取失败: {str(e)}"
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """从Word文档提取文本"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Word文档文本提取失败: {e}")
            return f"Word文档文本提取失败: {str(e)}"
    
    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """从文本文件提取文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as file:
                    return file.read().strip()
            except Exception as e:
                logger.error(f"文本文件读取失败: {e}")
                return f"文本文件读取失败: {str(e)}"
        except Exception as e:
            logger.error(f"文本文件读取失败: {e}")
            return f"文本文件读取失败: {str(e)}"
    
    @staticmethod
    def extract_text_from_xlsx(file_path: str) -> str:
        """从Excel文件提取文本"""
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True, data_only=True)
            text_parts = []
            for sheet in wb.worksheets:
                text_parts.append(f"【Sheet: {sheet.title}】")
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                    if cells:
                        text_parts.append("\t".join(cells))
            wb.close()
            return "\n".join(text_parts).strip()
        except Exception as e:
            logger.error(f"Excel文件文本提取失败: {e}")
            return f"Excel文件文本提取失败: {str(e)}"

    @classmethod
    def extract_text(cls, document) -> str:
        """根据文档类型提取文本

        兼容两种模型：
        - RequirementDocument：使用 document_type 字段（pdf/docx/txt/md）
        - KnowledgeDocument：使用 file_type 字段（pdf/docx/md/xlsx/txt）
        """
        file_path = document.file.path

        doc_type = getattr(document, 'file_type', '') or getattr(document, 'document_type', '') or ''

        if doc_type == 'pdf':
            return cls.extract_text_from_pdf(file_path)
        elif doc_type == 'docx':
            return cls.extract_text_from_docx(file_path)
        elif doc_type == 'xlsx':
            return cls.extract_text_from_xlsx(file_path)
        elif doc_type in ('txt', 'md'):
            return cls.extract_text_from_txt(file_path)
        else:
            return "不支持的文档类型"


class AIService:
    """AI服务类 - 模拟大模型调用"""
    
    @staticmethod
    async def analyze_requirements(text: str, document_title: str = "") -> Dict[str, Any]:
        """
        先进的需求分析 - 使用新的智能分析引擎
        
        Args:
            text: 需求文档文本内容
            document_title: 文档标题
            
        Returns:
            Dict包含分析报告、结构化需求等信息
        """
        try:
            # 直接导入并使用先进分析器
            from apps.requirement_analysis.advanced_analyzer import advanced_analyzer
            
            logger.info(f"使用先进分析器分析需求，文档标题: {document_title}")
            
            # 使用先进分析器进行分析
            result = await advanced_analyzer.analyze_requirements_advanced(text, document_title)
            
            # 转换为原系统期望的格式
            analysis_report = result.get("analysis_report", "")
            structured_requirements = result.get("structured_requirements", {})
            requirements_list = structured_requirements.get("requirements", [])
            
            # 计算分析时间（模拟）
            import time
            analysis_time = time.time() % 10 + 2  # 2-12秒之间的模拟时间
            
            logger.info(f"先进需求分析完成，识别需求{len(requirements_list)}个")
            
            return {
                "analysis_report": analysis_report,
                "requirements": requirements_list,
                "requirements_count": len(requirements_list),
                "analysis_time": analysis_time,
                "quality_assessment": result.get("quality_assessment", {}),
                "risk_analysis": result.get("risk_analysis", {})
            }
            
        except Exception as e:
            logger.error(f"先进需求分析失败: {e}")
            logger.info("使用备用分析方法")
            # fallback到原来的分析逻辑
            return await AIService._fallback_analyze_requirements(text, document_title)
    
    @staticmethod
    async def _fallback_analyze_requirements(text: str, document_title: str = "") -> Dict[str, Any]:
        """备用需求分析方法"""
        # 模拟AI分析过程
        await asyncio.sleep(2)
        
        # 这里应该调用真实的大模型API
        # 现在返回改进的模拟数据
        analysis_report = f"""
# 需求分析报告

## 文档概述
基于提供的需求文档"{document_title}"，共识别出以下主要需求模块和功能点。

## 主要功能模块
1. 用户管理模块
2. 数据处理模块  
3. 报告生成模块
4. 系统配置模块

## 详细需求分析
基于文档内容分析，识别出以下具体需求：

### 功能需求
- 用户认证和权限管理
- 数据录入和维护功能
- 业务流程处理
- 报表和统计功能

### 非功能需求
- 系统性能要求：响应时间 < 3秒
- 安全性要求：数据加密存储
- 可用性要求：99.5%系统可用率
- 兼容性要求：支持主流浏览器

## 风险评估
- 技术实现风险：中等
- 进度风险：低
- 资源风险：低

## 建议
建议采用敏捷开发模式，分阶段实施各功能模块。

分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # 生成基础的结构化需求
        requirements = [
            {
                "requirement_id": "REQ-001",
                "requirement_name": "用户认证管理", 
                "requirement_type": "functional",
                "parent_requirement": None,
                "module": "用户管理",
                "requirement_level": "high",
                "reviewer": "admin",
                "estimated_hours": 16,
                "description": "作为一名系统用户，我希望通过用户名和密码登录系统，这样可以确保系统安全性并获得个性化服务。",
                "acceptance_criteria": "用户能够使用有效凭证成功登录系统，无效凭证登录失败，系统记录登录日志。"
            },
            {
                "requirement_id": "REQ-002",
                "requirement_name": "数据管理功能",
                "requirement_type": "functional", 
                "parent_requirement": None,
                "module": "数据管理",
                "requirement_level": "high",
                "reviewer": "admin",
                "estimated_hours": 24,
                "description": "作为一名数据操作员，我希望能够对系统数据进行增删改查操作，这样可以有效管理业务信息。",
                "acceptance_criteria": "数据操作功能正常，数据完整性得到保证，操作权限控制有效。"
            },
            {
                "requirement_id": "REQ-003",
                "requirement_name": "报表统计功能",
                "requirement_type": "functional",
                "parent_requirement": None,
                "module": "报表管理",
                "requirement_level": "medium", 
                "reviewer": "admin",
                "estimated_hours": 20,
                "description": "作为一名管理人员，我希望能够生成各类业务报表和统计图表，这样可以直观了解业务数据和趋势。",
                "acceptance_criteria": "系统能够生成多种格式的报表，数据准确，支持导出功能。"
            }
        ]
        
        return {
            "analysis_report": analysis_report,
            "requirements": requirements,
            "requirements_count": len(requirements)
        }
    
    @staticmethod
    async def generate_test_cases(requirement: Requirement, test_level: str, test_priority: str, count: int) -> List[Dict[str, Any]]:
        """生成测试用例 - 大模型A"""
        # 模拟AI生成过程
        await asyncio.sleep(1)
        
        # 生成唯一case_id的辅助函数
        def generate_unique_case_id(req, base_index):
            """生成唯一的测试用例ID"""
            base_case_id = f"TC-{req.requirement_id}-{base_index:03d}"
            case_id = base_case_id
            counter = 1
            
            # 检查是否已存在，如果存在则添加后缀
            from .models import GeneratedTestCase
            while GeneratedTestCase.objects.filter(requirement=req, case_id=case_id).exists():
                case_id = f"{base_case_id}_{counter}"
                counter += 1
            
            return case_id
        
        # 获取该需求现有测试用例的数量，作为起始索引
        from .models import GeneratedTestCase
        existing_count = GeneratedTestCase.objects.filter(requirement=requirement).count()
        
        # 根据需求生成测试用例
        test_cases = []
        for i in range(count):
            case_id = generate_unique_case_id(requirement, existing_count + i + 1)
            
            # 根据需求类型生成不同的测试用例
            if "登录" in requirement.title:
                test_cases.append({
                    "case_id": case_id,
                    "title": f"验证用户使用有效凭证登录系统的认证流程和权限获取",
                    "priority": test_priority,
                    "precondition": "系统正常运行，测试用户账号已创建",
                    "test_steps": "1. 打开登录页面\n2. 输入有效的用户名和密码\n3. 点击登录按钮\n4. 检查登录结果和页面跳转",
                    "expected_result": "用户成功登录系统，跳转到主页面，显示用户信息和相应权限功能"
                })
            elif "数据" in requirement.title:
                test_cases.append({
                    "case_id": case_id,
                    "title": f"测试数据录入功能在各种输入场景下的验证机制和保存结果",
                    "priority": test_priority,
                    "precondition": "系统正常运行，用户已登录具备数据操作权限",
                    "test_steps": "1. 进入数据录入页面\n2. 填写必填字段信息\n3. 提交数据\n4. 验证数据保存结果",
                    "expected_result": "数据成功保存到数据库，页面显示保存成功提示，可以查询到新录入的数据"
                })
            elif "报告" in requirement.title:
                test_cases.append({
                    "case_id": case_id,
                    "title": f"验证报告生成功能在不同格式和数据量下的处理能力和输出质量",
                    "priority": test_priority, 
                    "precondition": "系统正常运行，存在可用于生成报告的数据",
                    "test_steps": "1. 进入报告生成页面\n2. 选择报告类型和参数\n3. 点击生成报告\n4. 检查生成的报告内容和格式",
                    "expected_result": "报告成功生成，内容准确完整，格式符合要求，可以正常下载"
                })
            else:
                test_cases.append({
                    "case_id": case_id,
                    "title": f"验证{requirement.title}功能的基本操作流程和预期结果",
                    "priority": test_priority,
                    "precondition": "系统正常运行，用户已登录",
                    "test_steps": f"1. 访问{requirement.title}功能\n2. 执行主要操作步骤\n3. 验证操作结果",
                    "expected_result": f"{requirement.title}功能正常工作，操作结果符合预期"
                })
        
        return test_cases
    
    @staticmethod
    async def review_test_cases(test_cases: List[GeneratedTestCase], review_criteria: str) -> Dict[str, Any]:
        """评审测试用例 - 大模型B"""
        # 模拟AI评审过程
        await asyncio.sleep(1.5)
        
        reviewed_cases = []
        for test_case in test_cases:
            # 模拟评审逻辑
            review_score = 85  # 模拟评分
            
            review_comments = f"""
评审意见:
1. 测试用例标题清晰明确，能够准确描述测试目的
2. 测试步骤详细具体，具有良好的可执行性
3. 预期结果明确，便于验证
4. 建议补充异常场景的测试覆盖

评审分数: {review_score}/100
评审状态: 通过
"""
            
            reviewed_cases.append({
                "test_case_id": test_case.id,
                "review_score": review_score,
                "review_comments": review_comments.strip(),
                "status": "reviewed" if review_score >= 80 else "rejected"
            })
        
        return {
            "reviewed_cases": reviewed_cases,
            "overall_score": sum(case["review_score"] for case in reviewed_cases) / len(reviewed_cases),
            "pass_rate": len([case for case in reviewed_cases if case["status"] == "reviewed"]) / len(reviewed_cases) * 100
        }


class RequirementAnalysisService:
    """需求分析服务"""
    
    @classmethod
    def create_analysis_task(cls, document: RequirementDocument, task_type: str) -> AnalysisTask:
        """创建分析任务"""
        task_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
        
        task = AnalysisTask.objects.create(
            task_id=task_id,
            task_type=task_type,
            document=document,
            status='pending'
        )
        
        return task
    
    @classmethod
    async def process_document_analysis(cls, document: RequirementDocument) -> RequirementAnalysis:
        """处理文档分析"""
        # 创建分析任务
        task = cls.create_analysis_task(document, 'requirement_analysis')
        
        try:
            # 更新任务状态
            task.status = 'running'
            task.started_at = datetime.now()
            task.progress = 10
            task.save()
            
            # 提取文档文本
            if not document.extracted_text:
                document.extracted_text = DocumentProcessor.extract_text(document)
                document.save()
            
            task.progress = 30
            task.save()
            
            # 调用AI分析
            start_time = time.time()
            analysis_result = await AIService.analyze_requirements(
                document.extracted_text, 
                document.title
            )
            analysis_time = time.time() - start_time
            
            task.progress = 70
            task.save()
            
            # 创建分析记录
            analysis = RequirementAnalysis.objects.create(
                document=document,
                analysis_report=analysis_result['analysis_report'],
                requirements_count=analysis_result['requirements_count'],
                analysis_time=analysis_time
            )
            
            # 保存需求数据
            for req_data in analysis_result['requirements']:
                create_requirement_from_br_data(analysis, req_data)
            
            # 更新文档状态
            document.status = 'analyzed'
            document.save()
            
            # 完成任务
            task.status = 'completed'
            task.completed_at = datetime.now()
            task.progress = 100
            task.result = analysis_result
            task.save()
            
            return analysis
            
        except Exception as e:
            logger.error(f"文档分析失败: {e}")
            
            # 更新任务状态
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = datetime.now()
            task.save()
            
            # 更新文档状态
            document.status = 'failed'
            document.save()
            
            raise e
    
    @classmethod
    async def generate_test_cases_for_requirements(cls, requirement_ids: List[int], test_level: str, test_priority: str, test_case_count: int) -> List[GeneratedTestCase]:
        """为需求生成测试用例"""
        generated_cases = []
        
        for req_id in requirement_ids:
            try:
                requirement = Requirement.objects.get(id=req_id)
                
                # 调用AI生成测试用例
                test_cases_data = await AIService.generate_test_cases(
                    requirement, test_level, test_priority, test_case_count
                )
                
                # 保存生成的测试用例
                for case_data in test_cases_data:
                    test_case = GeneratedTestCase.objects.create(
                        requirement=requirement,
                        case_id=case_data['case_id'],
                        title=case_data['title'],
                        priority=case_data['priority'],
                        precondition=case_data['precondition'],
                        test_steps=case_data['test_steps'],
                        expected_result=case_data['expected_result'],
                        generated_by_ai='AI-A'
                    )
                    generated_cases.append(test_case)
                    
            except Requirement.DoesNotExist:
                logger.error(f"需求ID {req_id} 不存在")
                continue
            except Exception as e:
                logger.error(f"为需求 {req_id} 生成测试用例失败: {e}")
                continue
        
        return generated_cases
    
    @classmethod
    async def review_test_cases(cls, test_case_ids: List[int], review_criteria: str) -> Dict[str, Any]:
        """评审测试用例"""
        test_cases = GeneratedTestCase.objects.filter(id__in=test_case_ids)
        
        # 调用AI评审
        review_result = await AIService.review_test_cases(list(test_cases), review_criteria)
        
        # 更新测试用例状态
        for case_review in review_result['reviewed_cases']:
            try:
                test_case = GeneratedTestCase.objects.get(id=case_review['test_case_id'])
                test_case.status = case_review['status']
                test_case.review_comments = case_review['review_comments']
                test_case.reviewed_by_ai = 'AI-B'
                test_case.save()
            except GeneratedTestCase.DoesNotExist:
                logger.error(f"测试用例ID {case_review['test_case_id']} 不存在")
                continue

        return review_result


import requests
import warnings

from django.utils import timezone

# 禅道常部署于内网且使用自签名证书，屏蔽 urllib3 的 InsecureRequestWarning 噪音
warnings.filterwarnings(
    'ignore',
    message='.*Unverified HTTPS request.*',
    category=requests.packages.urllib3.exceptions.InsecureRequestWarning,
)


class ZentaoService:
    """禅道 API 集成服务"""

    @staticmethod
    def _get_token(config) -> str:
        """获取禅道API Token"""
        url = config.zentao_url.rstrip('/') + '/api.php/v1/tokens'

        try:
            resp = requests.post(
                url,
                json={'account': config.zentao_account, 'password': config.zentao_password},
                headers={'Accept': 'application/json'},
                verify=False,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                token = data.get('token', '')
                if not token:
                    raise Exception(f"返回数据中无token字段，响应: {resp.text[:200]}")
                return token
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except requests.exceptions.SSLError:
            raise Exception(
                f"HTTPS 连接被中断 ({url})，可能是 VPN/代理/防火墙拦截了请求；"
                f"请关闭 VPN 或检查网络环境后重试"
            )
        except requests.Timeout:
            raise Exception(f"连接禅道超时 ({url})")
        except requests.ConnectionError:
            raise Exception(f"无法连接到禅道服务器 ({config.zentao_url})，请检查地址是否正确")
        except Exception as e:
            if 'token' not in str(e).lower():
                raise Exception(f"获取Token异常: {str(e)}")
            raise

    @staticmethod
    def _call_api(config, endpoint: str, method: str = 'GET', json_body=None) -> dict:
        """调用禅道API"""
        token = ZentaoService._get_token(config)
        url = config.zentao_url.rstrip('/') + endpoint
        headers = {'Token': token}

        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, verify=False, timeout=30)
            elif method == 'POST':
                resp = requests.post(url, headers=headers, json=json_body or {}, verify=False, timeout=30)
            elif method == 'PUT':
                resp = requests.put(url, headers=headers, json=json_body or {}, verify=False, timeout=30)
            else:
                raise Exception(f"不支持的method: {method}")

            if resp.status_code in (200, 201):
                data = resp.json()
                if isinstance(data, dict) and data.get('error'):
                    raise Exception(f"禅道API返回错误: {data.get('error')}")
                return data
            else:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except requests.exceptions.SSLError:
            raise Exception(
                f"HTTPS 连接被中断 ({endpoint})，可能是 VPN/代理/防火墙拦截了请求；"
                f"请关闭 VPN 或检查网络环境后重试"
            )
        except requests.Timeout:
            raise Exception(f"调用禅道API超时 ({endpoint})")
        except Exception as e:
            if 'HTTP' in str(e) or '禅道' in str(e):
                raise
            raise Exception(f"调用禅道API异常 ({endpoint}): {str(e)}")

    @staticmethod
    def get_products(config) -> list:
        """获取禅道产品列表"""
        data = ZentaoService._call_api(config, '/api.php/v1/products?page=1&limit=100000')
        return data.get('products', [])

    @staticmethod
    def get_projects(config) -> list:
        """获取禅道项目列表"""
        data = ZentaoService._call_api(config, '/api.php/v1/projects?page=1&limit=100000')
        return data.get('projects', [])

    @staticmethod
    def get_product_stories(config, product_id: int) -> list:
        """获取产品下的需求列表"""
        data = ZentaoService._call_api(
            config, f'/api.php/v1/products/{product_id}/stories?page=1&limit=10000'
        )
        return data.get('stories', [])

    @staticmethod
    def get_project_stories(config, project_id: int) -> list:
        """获取项目下的需求列表"""
        data = ZentaoService._call_api(
            config, f'/api.php/v1/projects/{project_id}/stories?page=1&limit=10000'
        )
        return data.get('stories', [])

    @staticmethod
    def get_story_detail(config, story_id: int) -> dict:
        """获取单个需求的完整详情"""
        return ZentaoService._call_api(config, f'/api.php/v1/stories/{story_id}')

    # ==================== 测试用例读写 ====================

    @staticmethod
    def get_story_testcases(config, story_id: int) -> list:
        """获取需求(story)下的测试用例列表"""
        data = ZentaoService._call_api(
            config, f'/api.php/v1/stories/{story_id}/cases?page=1&limit=10000'
        )
        # 禅道返回键名可能是 cases 或 testcases
        return data.get('cases') or data.get('testcases') or []

    @staticmethod
    def get_testcase_detail(config, case_id: int) -> dict:
        """获取单个测试用例详情"""
        return ZentaoService._call_api(config, f'/api.php/v1/testcases/{case_id}')

    @staticmethod
    def create_testcase(config, product_id: int, case_data: dict) -> dict:
        """创建禅道测试用例"""
        return ZentaoService._call_api(
            config, f'/api.php/v1/products/{product_id}/testcases',
            method='POST', json_body=case_data,
        )

    @staticmethod
    def update_testcase(config, case_id: int, case_data: dict) -> dict:
        """更新禅道测试用例"""
        return ZentaoService._call_api(
            config, f'/api.php/v1/testcases/{case_id}',
            method='PUT', json_body=case_data,
        )

    # ==================== 字段映射 ====================

    PRIORITY_TO_ZENTAO = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
    PRIORITY_FROM_ZENTAO = {1: 'critical', 2: 'high', 3: 'medium', 4: 'low'}
    TYPE_TO_ZENTAO = {
        'functional': 'feature', 'integration': 'interface', 'api': 'interface',
        'ui': 'feature', 'performance': 'performance', 'security': 'security',
    }
    TYPE_FROM_ZENTAO = {
        'feature': 'functional', 'interface': 'api', 'performance': 'performance',
        'security': 'security', 'config': 'functional', 'install': 'functional',
        'unit': 'functional', 'other': 'functional',
    }

    @staticmethod
    def map_priority_to_zentao(priority):
        return ZentaoService.PRIORITY_TO_ZENTAO.get(priority, 3)

    @staticmethod
    def map_priority_from_zentao(pri):
        return ZentaoService.PRIORITY_FROM_ZENTAO.get(pri, 'medium')

    @staticmethod
    def map_type_to_zentao(test_type):
        return ZentaoService.TYPE_TO_ZENTAO.get(test_type, 'feature')

    @staticmethod
    def map_type_from_zentao(zentao_type):
        return ZentaoService.TYPE_FROM_ZENTAO.get(zentao_type, 'functional')

    @staticmethod
    def steps_to_zentao(steps_json):
        """本地 steps JSON 文本 -> 禅道 steps 数组 [{desc, expect}]"""
        import json
        try:
            steps = json.loads(steps_json) if steps_json else []
        except (ValueError, TypeError):
            return []
        return [{'desc': s.get('desc', ''), 'expect': s.get('expect', '')}
                for s in steps if isinstance(s, dict)]

    @staticmethod
    def steps_from_zentao(zentao_steps):
        """禅道 steps 数组 -> 本地 steps JSON 文本"""
        import json
        if not isinstance(zentao_steps, list):
            return '[]'
        return json.dumps(
            [{'desc': s.get('desc', ''), 'expect': s.get('expect', '')}
             for s in zentao_steps if isinstance(s, dict)],
            ensure_ascii=False,
        )

    @staticmethod
    def test_connection(config) -> dict:
        """测试禅道连接"""
        try:
            token = ZentaoService._get_token(config)
            return {'success': True, 'token': token[:8] + '...', 'message': '连接成功'}
        except Exception as e:
            return {'success': False, 'message': str(e)}


class AIRequirementParser:
    """AI需求解析服务"""

    PARSE_PROMPT = """你是一个专业的需求分析专家。请从以下文档内容中提取所有需求项，每个需求项格式如下：

{
  "requirements": [
    {
      "title": "需求标题（必填）",
      "spec": "需求描述",
      "category": "分类：feature(功能)/interface(接口)/performance(性能)/safe(安全)/experience(体验)/improve(改进)/other(其他)",
      "priority": "优先级：1(最高)至5(最低)",
      "stage": "阶段：wait(未开始)/planned(已计划)/projected(已立项)/developing(研发中)/developed(研发完毕)/testing(测试中)/tested(测试完毕)/verified(已验收)/released(已发布)",
      "status": "状态：draft(草稿)/active(激活)/closed(已关闭)/changed(已变更)",
      "source_note": "来源备注（可选）",
      "estimate": "预计工时（数字，可选）"
    }
  ]
}

请确保：
1. 返回完整的JSON数组格式
2. 每个需求项的title是必填的
3. 尽可能多地从文档中提取需求信息
4. 如果文档内容不清晰，合理推断并补充

文档内容：
{content}"""

    @staticmethod
    def parse_from_text(content: str) -> Dict[str, Any]:
        """使用AI解析文本中的需求项"""
        from .models import AIModelService
        from apps.ai.resolver import ConfigResolver
        from apps.ai.prompt_registry import get_prompt_content_raw
        from apps.ai import observability

        # 获取活跃的编写模型配置（model_type=None 表示任意提供商，统一走 resolver）
        writer_config = ConfigResolver.active(role='writer')
        if not writer_config:
            return {
                'success': False,
                'requirements': [],
                'error': '未找到活跃的AI模型配置，请先在配置中心配置AI模型'
            }

        # 提示词从注册表取（未 seed 时回退代码默认）
        prompt_template = get_prompt_content_raw(
            'requirement_parse', default=AIRequirementParser.PARSE_PROMPT)
        prompt = prompt_template.replace('{content}', content)
        messages = [
            {'role': 'system', 'content': '你是一个需求分析专家，请严格按照JSON格式输出。'},
            {'role': 'user', 'content': prompt}
        ]

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            token = observability.set_scenario('requirement_parse')
            try:
                response = loop.run_until_complete(
                    AIModelService.call_openai_compatible_api(writer_config, messages, max_tokens=4096)
                )
            finally:
                observability.reset_scenario(token)
            loop.close()

            response_text = response['choices'][0]['message']['content']
            # 清理响应文本
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]

            result = json.loads(response_text)
            requirements = result.get('requirements', []) if isinstance(result, dict) else result

            return {
                'success': True,
                'requirements': requirements,
                'raw_response': response_text
            }
        except json.JSONDecodeError as e:
            logger.error(f"AI解析结果JSON解析失败: {e}, 原始响应: {response_text}")
            return {
                'success': False,
                'requirements': [],
                'raw_response': response_text,
                'error': f'AI返回结果解析失败: {str(e)}'
            }
        except Exception as e:
            logger.error(f"AI需求解析失败: {e}")
            return {
                'success': False,
                'requirements': [],
                'error': f'AI解析失败: {str(e)}'
            }

    @staticmethod
    def extract_text_from_file(file_content: bytes, filename: str) -> str:
        """从上传的文件中提取文本内容"""
        filename_lower = filename.lower()

        if filename_lower.endswith('.txt') or filename_lower.endswith('.md'):
            return file_content.decode('utf-8', errors='ignore')

        if filename_lower.endswith('.pdf'):
            try:
                import io
                reader = PdfReader(io.BytesIO(file_content))
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return '\n\n'.join(text_parts)
            except Exception as e:
                logger.error(f"PDF解析失败: {e}")
                raise Exception(f"PDF文件解析失败: {str(e)}")

        if filename_lower.endswith('.docx'):
            try:
                import io
                doc = docx.Document(io.BytesIO(file_content))
                text_parts = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text.strip())
                return '\n\n'.join(text_parts)
            except Exception as e:
                logger.error(f"Word解析失败: {e}")
                raise Exception(f"Word文件解析失败: {str(e)}")

        if filename_lower.endswith('.xlsx'):
            try:
                import io
                from openpyxl import load_workbook
                wb = load_workbook(io.BytesIO(file_content), data_only=True)
                text_parts = []
                for sheet_name in wb.sheetnames:
                    ws = wb[sheet_name]
                    sheet_lines = [f"【工作表: {sheet_name}】"]
                    for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                                              max_col=ws.max_column, values_only=True):
                        row_values = [str(cell) if cell is not None else '' for cell in row]
                        row_text = ' | '.join(row_values).strip()
                        if row_text:
                            sheet_lines.append(row_text)
                    if len(sheet_lines) > 1:
                        text_parts.append('\n'.join(sheet_lines))
                wb.close()
                return '\n\n'.join(text_parts)
            except Exception as e:
                logger.error(f"Excel解析失败: {e}")
                raise Exception(f"Excel文件解析失败: {str(e)}")

        if filename_lower.endswith('.xls'):
            raise Exception('不支持旧版 .xls 格式，请将文件另存为 .xlsx 格式后再上传')

        # 尝试作为文本文件读取
        try:
            return file_content.decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            raise Exception(f'不支持的文件格式: {filename}。支持的文件类型: txt, md, pdf, docx, xlsx')