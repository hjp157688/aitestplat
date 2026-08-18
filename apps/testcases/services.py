from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from apps.users.models import User
from apps.versions.models import Version

from .models import TestCase, TestCaseImportRecord


TEMPLATE_VERSION = 'v2'
TEMPLATE_SHEET_NAME = '用例导入模板'
INSTRUCTION_SHEET_NAME = '填写说明'


@dataclass
class ImportSummary:
    total_rows: int
    success_count: int
    failed_count: int
    skip_count: int
    failure_details: List[dict]


class TestCaseImportTemplateService:
    # 规范格式 = 六列，与「导出 Excel」保持一致，预期结果内联在操作步骤中（n. 操作 | 预期: 结果）
    HEADERS = [
        '用例标题*',
        '前置条件',
        '操作步骤*',
        '优先级',
        '测试类型',
        '关联版本',
    ]

    SAMPLE_ROW = [
        '用户登录成功校验',
        '用户已注册且账号状态正常',
        '1. 打开登录页 | 预期: 页面正常显示登录页\n2. 输入正确用户名和密码 | 预期: 输入无报错\n3. 点击登录按钮 | 预期: 跳转到首页，显示登录成功信息',
        '高',
        '功能测试',
        'V1.0,V1.1',
    ]

    INSTRUCTIONS = [
        ['模板版本', TEMPLATE_VERSION],
        ['说明', '请勿修改表头名称，按模板字段填写并上传'],
        ['默认处理', '模板中未提供的字段将使用系统默认值：描述为空、状态=draft(草稿)、标签=[]、指派人为空'],
        ['用例标题*', '必填，测试用例标题，建议唯一且明确'],
        ['前置条件', '可选'],
        ['操作步骤*', '必填，支持多行文本；每行一步，预期结果内联在同一行末尾：n. 操作内容 | 预期: 期望结果'],
        ['优先级', '可选，支持中文或英文：低/中/高/紧急 或 low/medium/high/critical；默认 medium(中)'],
        ['测试类型', '可选，支持中文或英文：功能测试/集成测试/API测试/UI测试/性能测试/安全测试 或 functional/integration/api/ui/performance/security；默认 functional(功能测试)'],
        ['中英文示例', '优先级示例：高 或 high；测试类型示例：功能测试 或 functional'],
        ['关联版本', '可选，填写当前项目下的版本名称，多个版本用英文逗号分隔'],
        ['关联项目', '上传时由页面选择，不需要在 Excel 中填写'],
    ]

    @classmethod
    def build_template(cls) -> BytesIO:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = TEMPLATE_SHEET_NAME
        worksheet.append(cls.HEADERS)
        worksheet.append(cls.SAMPLE_ROW)

        header_fill = PatternFill(fill_type='solid', fgColor='D9EAF7')
        required_fill = PatternFill(fill_type='solid', fgColor='FDE2E2')
        header_font = Font(bold=True)

        for index, header in enumerate(cls.HEADERS, start=1):
            cell = worksheet.cell(row=1, column=index)
            cell.font = header_font
            cell.fill = required_fill if header.endswith('*') else header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        for row in worksheet.iter_rows(min_row=2, max_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical='top', wrap_text=True)

        column_widths = [24, 24, 40, 14, 18, 22]
        for idx, width in enumerate(column_widths, start=1):
            worksheet.column_dimensions[chr(64 + idx)].width = width

        instruction_sheet = workbook.create_sheet(INSTRUCTION_SHEET_NAME)
        for row in cls.INSTRUCTIONS:
            instruction_sheet.append(row)
        instruction_sheet.column_dimensions['A'].width = 22
        instruction_sheet.column_dimensions['B'].width = 80
        for row in instruction_sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical='top', wrap_text=True)
        for cell in instruction_sheet[1]:
            cell.font = header_font
            cell.fill = header_fill

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return output


class TestCaseExcelImportService:
    PRIORITY_MAP = {
        'low': 'low', '低': 'low',
        'medium': 'medium', '中': 'medium',
        'high': 'high', '高': 'high',
        'critical': 'critical', '紧急': 'critical',
    }
    STATUS_MAP = {
        'draft': 'draft', '草稿': 'draft',
        'active': 'active', '激活': 'active',
        'deprecated': 'deprecated', '废弃': 'deprecated',
    }
    TEST_TYPE_MAP = {
        'functional': 'functional', '功能测试': 'functional',
        'integration': 'integration', '集成测试': 'integration',
        'api': 'api', 'API测试': 'api', 'api测试': 'api',
        'ui': 'ui', 'UI测试': 'ui', 'ui测试': 'ui',
        'performance': 'performance', '性能测试': 'performance',
        'security': 'security', '安全测试': 'security',
    }

    # 表头识别为「模糊匹配」：先去 *、去空白、小写再比对，中/英变体均可。
    # 不要求表头与模板完全一致、不要求顺序，只有必填列（REQUIRED_FIELDS）必须出现在同一工作表内。
    HEADER_ALIASES = {
        '标题': 'title', '用例标题': 'title', 'title': 'title',
        '前置条件': 'preconditions', '前置': 'preconditions',
        'preconditions': 'preconditions', 'precondition': 'preconditions',
        '操作步骤': 'steps', '步骤': 'steps', 'steps': 'steps',
        '优先级': 'priority', '优先': 'priority', 'priority': 'priority',
        '测试类型': 'test_type', '类型': 'test_type', 'testtype': 'test_type',
        '关联版本': 'versions', '版本': 'versions',
        'versions': 'versions', 'version': 'versions',
    }
    REQUIRED_FIELDS = ('title', 'steps')
    MAX_HEADER_SCAN_ROWS = 10

    # 「无版本」占位文案（导出/人工填写的 noVersion 值）视为空，不当作版本名校验
    NO_VERSION_PLACEHOLDERS = {
        '未关联版本', '不关联版本', '无', '无版本',
        'no version', 'none', 'n/a', 'na', '-',
    }

    @classmethod
    def import_record(cls, record: TestCaseImportRecord) -> ImportSummary:
        workbook = load_workbook(record.import_file.path)
        worksheet, header_row_idx, field_to_col = cls._locate_sheet(workbook)

        rows = list(worksheet.iter_rows(min_row=header_row_idx + 2, values_only=True))
        effective_rows = [row for row in rows if any(cls._normalize_text(value) for value in row)]
        total_rows = len(effective_rows)
        success_count = 0
        failed_count = 0
        skip_count = 0
        failure_details: List[dict] = []

        version_map = {
            version.name: version
            for version in Version.objects.filter(projects=record.project).distinct()
        }

        for index, row in enumerate(effective_rows, start=header_row_idx + 2):
            row_values = list(row)
            row_data = {
                field: cls._normalize_text(row_values[col] if col < len(row_values) else '')
                for field, col in field_to_col.items()
            }

            error_messages = cls._validate_row(row_data, version_map)
            if error_messages:
                failed_count += 1
                failure_details.append({
                    'row_number': index,
                    'title': row_data.get('title', ''),
                    'errors': error_messages,
                })
                continue

            version_names = cls._split_csv(row_data.get('versions'))

            with transaction.atomic():
                steps_json = cls._parse_steps_cell(row_data['steps'])
                testcase = TestCase.objects.create(
                    project=record.project,
                    title=row_data['title'],
                    description='',
                    preconditions=row_data.get('preconditions', ''),
                    steps=json.dumps(steps_json, ensure_ascii=False),
                    priority=cls.PRIORITY_MAP.get(row_data.get('priority', '').lower(), 'medium'),
                    status='draft',
                    test_type=cls.TEST_TYPE_MAP.get(row_data.get('test_type', '').lower(), 'functional'),
                    tags=[],
                    author=record.created_by,
                    assignee=None,
                )
                if version_names:
                    testcase.versions.set([version_map[name].id for name in version_names])

            success_count += 1
            record.progress = int(success_count / total_rows * 100) if total_rows else 100
            record.success_count = success_count
            record.failed_count = failed_count
            record.total_rows = total_rows
            record.save(update_fields=['progress', 'success_count', 'failed_count', 'total_rows', 'updated_at'])

        return ImportSummary(
            total_rows=total_rows,
            success_count=success_count,
            failed_count=failed_count,
            skip_count=skip_count,
            failure_details=failure_details,
        )

    @staticmethod
    def _match_header(value) -> Optional[str]:
        """表头单元格 -> 字段名（模糊：去掉 */空白并小写后精确比对），无法识别返回 None"""
        text = TestCaseExcelImportService._normalize_header(value)
        if not text:
            return None
        return TestCaseExcelImportService.HEADER_ALIASES.get(text)

    @classmethod
    def _find_header(cls, worksheet) -> Optional[tuple]:
        """在前若干行里找包含必填列（标题/步骤）的表头行。
        返回 (0-based 表头行号, {field: 0-based 列号})；找不到返回 None。"""
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=1, max_row=cls.MAX_HEADER_SCAN_ROWS)):
            field_to_col = {}
            for col, cell in enumerate(row):
                field = cls._match_header(cell.value)
                if field is not None and field not in field_to_col:
                    field_to_col[field] = col
            if all(field in field_to_col for field in cls.REQUIRED_FIELDS):
                return row_idx, field_to_col
        return None

    @classmethod
    def _locate_sheet(cls, workbook) -> tuple:
        """任选一个含必填列的工作表（优先模板名工作表），不要求工作表名称一致。"""
        sheets = list(workbook.worksheets)
        ordered = (
            [ws for ws in sheets if ws.title == TEMPLATE_SHEET_NAME]
            + [ws for ws in sheets if ws.title != TEMPLATE_SHEET_NAME]
        )
        for ws in ordered:
            found = cls._find_header(ws)
            if found is not None:
                return ws, found[0], found[1]
        raise ValueError('Excel 中未找到包含必填列（用例标题/操作步骤）的工作表')

    @classmethod
    def build_failure_report(cls, record: TestCaseImportRecord) -> Optional[ContentFile]:
        if not record.failure_details:
            return None

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = '失败明细'
        worksheet.append(['行号', '标题', '失败原因'])
        for item in record.failure_details:
            worksheet.append([
                item.get('row_number'),
                item.get('title', ''),
                '；'.join(item.get('errors', [])),
            ])

        for column in ('A', 'B', 'C'):
            worksheet.column_dimensions[column].width = 20 if column != 'C' else 80

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return ContentFile(output.read(), name=f'{record.import_no}_failed_rows.xlsx')

    @classmethod
    def generate_import_no(cls) -> str:
        return f'IMP_{timezone.now().strftime("%Y%m%d%H%M%S")}_{uuid.uuid4().hex[:6].upper()}'

    @classmethod
    def _validate_row(cls, row_data: Dict[str, str], version_map: Dict[str, Version]) -> List[str]:
        errors = []
        if not row_data.get('title'):
            errors.append('标题不能为空')
        if not row_data.get('steps'):
            errors.append('操作步骤不能为空')

        priority = row_data.get('priority', '')
        if priority and priority.lower() not in cls.PRIORITY_MAP and priority not in cls.PRIORITY_MAP:
            errors.append(f'优先级无效: {priority}')

        test_type = row_data.get('test_type', '')
        if test_type and test_type.lower() not in cls.TEST_TYPE_MAP and test_type not in cls.TEST_TYPE_MAP:
            errors.append(f'测试类型无效: {test_type}')

        version_names = cls._split_csv(row_data.get('versions'))
        invalid_versions = [name for name in version_names if name not in version_map]
        if invalid_versions:
            errors.append(f'版本不存在: {", ".join(invalid_versions)}')

        return errors

    @staticmethod
    def _get_assignee(username: str) -> Optional[User]:
        if not username:
            return None
        return User.objects.filter(username=username).first()

    @staticmethod
    def _parse_steps_cell(cell_value: str) -> List[dict]:
        """把Excel单元格文本解析为[{desc, expect}]"""
        if not cell_value:
            return []
        steps = []
        for line in str(cell_value).split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^\d+\.\s*(.*?)\s*\|\s*预期:\s*(.*)$', line)
            if m:
                steps.append({'desc': m.group(1).strip(), 'expect': m.group(2).strip()})
            else:
                steps.append({'desc': re.sub(r'^\d+[\.\)、]\s*', '', line), 'expect': ''})
        return steps

    @staticmethod
    def _split_csv(text: str) -> List[str]:
        if not text:
            return []
        result = []
        for item in str(text).split(','):
            item = item.strip()
            if not item:
                continue
            if item.lower() in TestCaseExcelImportService.NO_VERSION_PLACEHOLDERS:
                continue
            result.append(item)
        return result

    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ''
        return str(value).strip()

    @staticmethod
    def _normalize_header(value) -> str:
        text = TestCaseExcelImportService._normalize_text(value)
        if not text:
            return ''
        text = text.replace('\ufeff', '').replace('\u200b', '')
        # 去掉必填标记 * 并转小写，便于模糊匹配（标题/标题*/Title 均命中 title）
        text = text.replace('*', '').lower()
        return re.sub(r'\s+', '', text)


def execute_import_record(record_id: int, celery_task_id: str = '') -> dict:
    """执行一次用例 Excel 导入并回写记录状态。

    Celery 任务体（tasks.import_testcases_from_excel）与「Redis/Celery 不可用时的
    请求内同步降级」共用同一实现，避免两条路径逻辑分叉。失败时仍抛异常（调用方视
    场景决定是否吞掉），record.status/error_message 已同步为失败状态。
    """
    record = TestCaseImportRecord.objects.get(id=record_id)
    record.status = 'importing'
    record.progress = 5
    if celery_task_id:
        record.celery_task_id = celery_task_id
    record.error_message = ''
    record.save(update_fields=['status', 'progress', 'celery_task_id', 'error_message', 'updated_at'])

    try:
        summary = TestCaseExcelImportService.import_record(record)
        record.refresh_from_db()
        record.total_rows = summary.total_rows
        record.success_count = summary.success_count
        record.failed_count = summary.failed_count
        record.skip_count = summary.skip_count
        record.failure_details = summary.failure_details
        record.progress = 100
        record.completed_at = timezone.now()

        if summary.failed_count > 0 and summary.success_count > 0:
            record.status = 'partial_success'
        elif summary.failed_count > 0:
            record.status = 'failed'
        else:
            record.status = 'completed'

        failure_report = TestCaseExcelImportService.build_failure_report(record)
        if failure_report:
            record.failure_report_file.save(failure_report.name, failure_report, save=False)

        record.save()
        return {
            'record_id': record.id,
            'status': record.status,
            'success_count': record.success_count,
            'failed_count': record.failed_count,
        }
    except Exception as exc:
        record.status = 'failed'
        record.progress = 100
        record.error_message = str(exc)
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'progress', 'error_message', 'completed_at', 'updated_at'])
        raise
