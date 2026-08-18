"""导入/导出 Excel 回归测试

导入规则（宽松）：
- 只需包含必填列：用例标题 / 操作步骤（模糊匹配，含中/英变体、带不带 *、顺序随意）；
- 工作表名称不要求为「用例导入模板」，任意含必填列的工作表均可；
- 表头可在前若干行内识别（首行为装饰标题也可）；
- 其余可选列按表头识别填充，多余列忽略，预期结果内联在操作步骤（n. 操作 | 预期: 结果）。
同时约束：官方模板本身必须可导入、前端「导出 Excel」产物必须可导回。
"""
import json
from io import BytesIO
from unittest import mock
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.testcases.models import TestCase as TestCaseModel, TestCaseImportRecord
from apps.testcases.services import (
    TestCaseExcelImportService,
    TestCaseImportTemplateService,
)
from apps.versions.models import Version

User = get_user_model()

CANONICAL_HEADERS = ['用例标题*', '前置条件', '操作步骤*', '优先级', '测试类型', '关联版本']
SHEET_NAME = '用例导入模板'


class TestCaseImportExportFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('importer', password='x')
        self.project = Project.objects.create(name='p', owner=self.user)
        self.v10 = Version.objects.create(name='V1.0', created_by=self.user)
        self.v10.projects.add(self.project)
        self.v11 = Version.objects.create(name='V1.1', created_by=self.user)
        self.v11.projects.add(self.project)

    @staticmethod
    def _record_from_workbook(record, path):
        record.import_file = ContentFile(path.getvalue(), name='x.xlsx')
        record.save()

    def _import_workbook(self, workbook) -> 'TestCaseImportRecord':
        buf = BytesIO()
        workbook.save(buf)
        record = TestCaseImportRecord.objects.create(
            import_no='IMP_TEST_' + str(uuid4().hex[:6]).upper(),
            project=self.project,
            status='pending',
            created_by=self.user,
        )
        self._record_from_workbook(record, buf)
        return TestCaseExcelImportService.import_record(record)

    def test_official_template_is_importable(self):
        """官方下发的模板必须能通过表头校验（此前含 预期结果* 会直接报「表头不匹配」）"""
        summary = self._import_workbook(
            load_workbook(TestCaseImportTemplateService.build_template())
        )
        # 不抛异常即通过；模板自带示例行作为真实数据参与导入
        self.assertEqual(summary.total_rows, 1)
        self.assertEqual(summary.failed_count, 0)

    def test_template_headers_recognizable(self):
        """模板 HEADERS 每一列都应能被导入器识别为字段"""
        fields = [
            TestCaseExcelImportService._match_header(h)
            for h in TestCaseImportTemplateService.HEADERS
        ]
        self.assertEqual(len(fields), len(TestCaseImportTemplateService.HEADERS))
        self.assertTrue(all(fields))
        self.assertEqual(set(fields), set(TestCaseExcelImportService.REQUIRED_FIELDS + ('preconditions', 'priority', 'test_type', 'versions')))

    def test_export_layout_roundtrips(self):
        """模拟前端「导出 Excel」产物（模板六列 + 工作表名）可直接导回，字段完整"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS)
        ws.append([
            '用户登录成功校验',
            '用户已注册且账号状态正常',
            '1. 打开登录页 | 预期: 页面正常显示登录页\n2. 输入正确用户名和密码 | 预期: 输入无报错\n3. 点击登录按钮 | 预期: 跳转到首页',
            '高',
            '功能测试',
            'V1.0,V1.1',
        ])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (1, 1, 0))

        tc = TestCaseModel.objects.get(project=self.project, title='用户登录成功校验')
        self.assertEqual(json.loads(tc.steps), [
            {'desc': '打开登录页', 'expect': '页面正常显示登录页'},
            {'desc': '输入正确用户名和密码', 'expect': '输入无报错'},
            {'desc': '点击登录按钮', 'expect': '跳转到首页'},
        ])
        self.assertEqual(tc.priority, 'high')
        self.assertEqual(tc.test_type, 'functional')
        self.assertEqual(
            sorted(v.name for v in tc.versions.all()), ['V1.0', 'V1.1']
        )
        self.assertEqual(tc.preconditions, '用户已注册且账号状态正常')

    def test_export_layout_with_extra_cols_roundtrips(self):
        """六列按序 + 附加信息列（编号/项目/作者/创建时间）也能导入，附加列被忽略"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS + ['测试用例编号', '关联项目', '作者', '创建时间'])
        ws.append([
            '登录成功校验', '账号状态正常',
            '1. 打开登录页 | 预期: 显示登录页',
            '中', 'API测试', 'V1.0',
            'TC001', '项目A', 'admin', '2026-08-13 10:00',
        ])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (1, 1, 0))
        tc = TestCaseModel.objects.get(project=self.project, title='登录成功校验')
        self.assertEqual(json.loads(tc.steps)[0]['expect'], '显示登录页')
        self.assertEqual(tc.priority, 'medium')
        self.assertEqual(tc.test_type, 'api')
        self.assertEqual(list(tc.versions.all()), [self.v10])

    def test_loose_headers_and_sheet_name_accepted(self):
        """表头不必精确、顺序可乱、工作表名不要求一致，只需包含必填列"""
        wb = Workbook()
        ws = wb.active
        ws.title = '随便一个表名'
        # 乱序 + 不带必填标记 *（覆盖 _normalize_header 去 * 逻辑）
        ws.append(['优先级', '步骤', '标题', '测试类型'])
        ws.append(['紧急', '1. 登录 | 预期: 成功', '登录校验', 'UI测试'])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (1, 1, 0))
        tc = TestCaseModel.objects.get(project=self.project, title='登录校验')
        self.assertEqual(tc.priority, 'critical')
        self.assertEqual(tc.test_type, 'ui')
        self.assertEqual(json.loads(tc.steps)[0]['expect'], '成功')

    def test_english_headers_accepted(self):
        """英文表头（Title/Steps/...）也能识别导入"""
        wb = Workbook()
        ws = wb.active
        ws.title = 'Sheet1'
        ws.append(['Title', 'Preconditions', 'Steps', 'Priority', 'Test Type', 'Versions'])
        ws.append(['EN Case', 'ready', '1. click | 预期: done', 'high', 'API测试', 'V1.0'])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (1, 1, 0))
        tc = TestCaseModel.objects.get(project=self.project, title='EN Case')
        self.assertEqual(tc.preconditions, 'ready')
        self.assertEqual(tc.priority, 'high')
        self.assertEqual(tc.test_type, 'api')
        self.assertEqual(list(tc.versions.all()), [self.v10])

    def test_header_not_in_first_row(self):
        """表头不在第一行（首行为标题装饰行）也能识别"""
        wb = Workbook()
        ws = wb.active
        ws.title = '用例清单'
        ws.append(['测试用例清单'])
        ws.append(['用例标题*', '前置条件', '操作步骤*', '优先级', '测试类型', '关联版本'])
        ws.append(['装饰行下的用例', '', '1. 操作 | 预期: 结果', '高', '功能测试', 'V1.0'])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (1, 1, 0))
        self.assertTrue(TestCaseModel.objects.filter(project=self.project, title='装饰行下的用例').exists())

    def test_missing_required_columns_rejected(self):
        """缺少必填列（标题 或 步骤）应被拒绝并给出明确提示"""

        def make(headers):
            wb = Workbook()
            ws = wb.active
            ws.title = SHEET_NAME
            ws.append(headers)
            return wb

        with self.assertRaises(ValueError) as ctx:
            self._import_workbook(make(['前置条件', '操作步骤*', '优先级', '测试类型', '关联版本']))
        self.assertIn('用例标题', str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            self._import_workbook(make(['用例标题*', '前置条件', '优先级', '测试类型', '关联版本']))
        self.assertIn('操作步骤', str(ctx.exception))

    def test_no_version_placeholder_ignored(self):
        """版本列为「无版本」占位文案（未关联版本/No version）时视为空，不再报版本不存在"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS)
        ws.append(['无版本用例', '', '1. 操作 | 预期: 完成', '高', '功能测试', '未关联版本'])
        ws.append(['无版本英文', '', '1. 操作 | 预期: 完成', '高', '功能测试', 'No version'])
        ws.append(['混合版本', '', '1. 操作 | 预期: 完成', '高', '功能测试', 'V1.0,未关联版本'])

        summary = self._import_workbook(wb)
        self.assertEqual((summary.total_rows, summary.success_count, summary.failed_count), (3, 3, 0))
        nover = TestCaseModel.objects.get(project=self.project, title='无版本用例')
        self.assertEqual(list(nover.versions.all()), [])
        enver = TestCaseModel.objects.get(project=self.project, title='无版本英文')
        self.assertEqual(list(enver.versions.all()), [])
        mixed = TestCaseModel.objects.get(project=self.project, title='混合版本')
        self.assertEqual(list(mixed.versions.all()), [self.v10])

    def test_invalid_row_reported_not_crash(self):
        """坏行（缺标题/缺步骤）应进入失败明细而不是让整个导入崩溃"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS)
        ws.append(['', '', '', '高', '功能测试', ''])
        ws.append(['只有标题无步骤', '', '', '', '功能测试', ''])
        ws.append(['合法用例', '', '1. 点按钮 | 预期: 有反应', '低', 'UI测试', 'V1.0'])

        summary = self._import_workbook(wb)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.failed_count, 2)
        self.assertEqual(len(summary.failure_details), 2)

    def test_sync_fallback_when_celery_unavailable(self):
        """Redis/Celery 不可用时，导入降级为请求内同步执行：接口 201 且记录立即完成"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS)
        ws.append(['同步降级用例', '', '1. 操作 | 预期: 完成', '高', '功能测试', 'V1.0'])
        buf = BytesIO()
        wb.save(buf)

        client = APIClient()
        client.force_authenticate(self.user)
        with mock.patch(
            'apps.testcases.views.import_testcases_from_excel.delay',
            side_effect=Exception('Error 61 connecting to 127.0.0.1:6379'),
        ):
            resp = client.post(
                '/api/testcases/import-records/',
                {'project_id': self.project.id, 'file': SimpleUploadedFile('cases.xlsx', buf.getvalue())},
                format='multipart',
            )

        self.assertEqual(resp.status_code, 201)
        record = TestCaseImportRecord.objects.get(id=resp.json()['id'])
        self.assertEqual(record.status, 'completed')
        self.assertEqual(record.success_count, 1)
        self.assertTrue(TestCaseModel.objects.filter(project=self.project, title='同步降级用例').exists())

    def test_async_delay_success_stores_task_id(self):
        """Celery 可用（delay 正常返回）时，异步提交并记录 celery_task_id"""
        wb = Workbook()
        ws = wb.active
        ws.title = SHEET_NAME
        ws.append(CANONICAL_HEADERS)
        buf = BytesIO()
        wb.save(buf)

        client = APIClient()
        client.force_authenticate(self.user)
        with mock.patch(
            'apps.testcases.views.import_testcases_from_excel.delay',
            return_value=mock.MagicMock(id='async-task-001'),
        ) as m_delay:
            resp = client.post(
                '/api/testcases/import-records/',
                {'project_id': self.project.id, 'file': SimpleUploadedFile('cases.xlsx', buf.getvalue())},
                format='multipart',
            )

        self.assertEqual(resp.status_code, 201)
        m_delay.assert_called_once()
        record = TestCaseImportRecord.objects.get(id=resp.json()['id'])
        self.assertEqual(record.celery_task_id, 'async-task-001')
