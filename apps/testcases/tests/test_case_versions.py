"""用例版本历史（TestCaseVersion）测试

- 创建用例自动产生 v1 快照（覆盖 API 创建/禅道导入/AI 补充等一切创建路径）
- 手动编辑产生下一版本（source=manual_edit），无内容变化不产生版本
- 版本号按用例独立自增
- 快照记录来源/备注/操作人
"""
import json
from unittest import mock

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.testcases.services import snapshot_case_version

User = get_user_model()


def make_case(user, **overrides):
    from apps.testcases.models import TestCase as TestCaseModel

    data = dict(
        project=Project.objects.create(name='p', owner=user),
        author=user,
        title='登录用例',
        description='desc',
        preconditions='已注册',
        steps='1. 打开登录页',
        priority='medium',
        test_type='functional',
        tags=['smoke'],
    )
    data.update(overrides)
    return TestCaseModel.objects.create(**data)


class CreateSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u1', password='x')

    def test_create_case_makes_v1_snapshot(self):
        """创建用例后自动存在 v1 快照，内容与用例一致"""
        tc = make_case(self.user)
        versions = tc.version_history.all()
        self.assertEqual(versions.count(), 1)
        v1 = versions[0]
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.source, 'created')
        self.assertEqual(v1.title, tc.title)
        self.assertEqual(v1.steps, tc.steps)
        self.assertEqual(v1.preconditions, tc.preconditions)
        self.assertEqual(v1.tags, ['smoke'])

    def test_version_counter_independent_per_case(self):
        """两条用例各自从 v1 开始，互不串号"""
        tc1 = make_case(self.user)
        tc2 = make_case(self.user, title='第二条用例')
        self.assertEqual(tc1.version_history.get().version, 1)
        self.assertEqual(tc2.version_history.get().version, 1)
        self.assertEqual(tc1.version_history.count(), 1)
        self.assertEqual(tc2.version_history.count(), 1)


class SnapshotServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u2', password='x')

    def test_snapshot_increments_and_stores_source_note_user(self):
        tc = make_case(self.user)
        tc.title = '登录用例-改'
        tc.save()
        v2 = snapshot_case_version(tc, source='manual_edit', note='补充异常场景', created_by=self.user)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.source, 'manual_edit')
        self.assertEqual(v2.note, '补充异常场景')
        self.assertEqual(v2.created_by, self.user)
        self.assertEqual(v2.title, '登录用例-改')

    def test_snapshot_captures_current_steps(self):
        tc = make_case(self.user)
        tc.steps = '1. 打开登录页\n2. 输入密码'
        v = snapshot_case_version(tc, source='ai_modified')
        self.assertEqual(v.steps, '1. 打开登录页\n2. 输入密码')

    def test_concurrent_snapshots_increment_monotonically(self):
        tc = make_case(self.user)
        for i in range(3):
            tc.title = f'标题{i}'
            snapshot_case_version(tc, source='ai_modified', note=f'第{i}轮')
        versions = list(tc.version_history.order_by('version').values_list('version', flat=True))
        self.assertEqual(versions, [1, 2, 3, 4])


class ManualEditVersionTests(TestCase):
    """手动编辑路径：PATCH 内容字段产生新版本，无内容变化不产生"""

    def setUp(self):
        self.user = User.objects.create_user('u3', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.tc = make_case(self.user)

    def test_patch_content_creates_manual_edit_version(self):
        resp = self.client.patch(
            f'/api/testcases/{self.tc.id}/',
            {'title': '登录用例（AI改）', 'steps': '1. 打开登录页 2. 登录'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        versions = self.tc.version_history.order_by('version')
        self.assertEqual(versions.count(), 2)
        v2 = versions.last()
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.source, 'manual_edit')
        self.assertEqual(v2.title, '登录用例（AI改）')
        self.assertEqual(v2.created_by, self.user)

    def test_patch_version_ids_only_keeps_v1(self):
        """只改发布版本关联（非内容字段）不产生新版本"""
        resp = self.client.patch(f'/api/testcases/{self.tc.id}/', {'version_ids': []}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tc.version_history.count(), 1, '内容未变不应新增版本')


class VersionApiTests(TestCase):
    """版本时间线与回退 API"""

    def setUp(self):
        self.user = User.objects.create_user('u4', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.tc = make_case(self.user)

    def _patch(self, data):
        return self.client.patch(f'/api/testcases/{self.tc.id}/', data, format='json')

    def test_versions_list_returns_ordered_snapshots(self):
        self._patch({'title': '第二版'})
        self._patch({'title': '第三版'})
        resp = self.client.get(f'/api/testcases/{self.tc.id}/versions/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        versions = body['results'] if isinstance(body, dict) and 'results' in body else body
        self.assertEqual([v['version'] for v in versions], [1, 2, 3])
        self.assertEqual(versions[0]['source'], 'created')
        self.assertEqual(versions[1]['source'], 'manual_edit')
        self.assertEqual(versions[1]['title'], '第二版')

    def test_restore_to_older_version_appends_restore_version(self):
        self._patch({'title': '改坏了'})
        resp = self.client.post(
            f'/api/testcases/{self.tc.id}/versions/1/restore/', {'note': '改坏了，回退'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.tc.refresh_from_db()
        self.assertEqual(self.tc.title, '登录用例')  # 回到 v1 内容
        versions = list(self.tc.version_history.order_by('version'))
        self.assertEqual(len(versions), 3)
        v3 = versions[-1]
        self.assertEqual(v3.source, 'restore')
        self.assertEqual(v3.title, '登录用例')  # 新版本内容=回退目标内容
        self.assertEqual(v3.note, '改坏了，回退')
        self.assertEqual(v3.version, 3)

    def test_restore_current_version_rejected(self):
        resp = self.client.post(f'/api/testcases/{self.tc.id}/versions/1/restore/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.tc.version_history.count(), 1)

    def test_restore_nonexistent_version_404(self):
        resp = self.client.post(f'/api/testcases/{self.tc.id}/versions/99/restore/', {}, format='json')
        self.assertEqual(resp.status_code, 404)


class LegacyCaseLazyInitTests(TestCase):
    """存量老用例没有版本记录：首次修改/查询历史时应补录 v1（初版内容），保证可对比"""

    def setUp(self):
        self.user = User.objects.create_user('legacy', password='x')
        self.tc = make_case(self.user)
        # 模拟功能上线前创建的老用例：删掉创建信号落的 v1
        self.tc.version_history.all().delete()

    def test_manual_edit_backfills_baseline_before_change(self):
        """老用例手动编辑：先补 v1（编辑前内容），再落 v2（manual_edit）"""
        original_title = self.tc.title
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        resp = self.client.patch(f'/api/testcases/{self.tc.id}/', {'title': '改过的标题'}, format='json')
        self.assertEqual(resp.status_code, 200)
        versions = list(self.tc.version_history.order_by('version'))
        self.assertEqual([v.version for v in versions], [1, 2])
        self.assertEqual(versions[0].source, 'created')
        self.assertEqual(versions[0].title, original_title)  # v1 = 编辑前内容
        self.assertEqual(versions[1].source, 'manual_edit')
        self.assertEqual(versions[1].title, '改过的标题')

    def test_versions_list_backfills_v1_for_untouched_case(self):
        """查历史时懒初始化：老用例没版本则补一条 v1"""
        original_title = self.tc.title
        resp = self.client_api().get(f'/api/testcases/{self.tc.id}/versions/')
        self.assertEqual(resp.status_code, 200)
        versions = resp.json()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]['version'], 1)
        self.assertEqual(versions[0]['title'], original_title)

    def client_api(self):
        client = APIClient()
        client.force_authenticate(self.user)
        return client

    def test_ai_modify_backfills_baseline(self):
        """AI 修改老用例：初版内容先落 v1，修改结果落 v2（ai_modified）"""
        from apps.testcases.models import TestCaseAiTask
        from unittest import mock

        original_title = self.tc.title
        task = TestCaseAiTask.objects.create(
            task_id='legacy1', mode='modify', note='n',
            case_ids=[self.tc.id], created_by=self.user,
        )
        output = json.dumps([{
            '编号': self.tc.id, 'title': 'AI改的标题', 'precondition': '前置',
            'steps': [{'desc': 's', 'expect': 'e'}], 'priority': 'P1',
        }], ensure_ascii=False)
        with mock.patch('apps.testcases.ai_tasks.AIClient.chat_sync', return_value={'choices': [{'message': {'content': output}}]}), \
             mock.patch('apps.testcases.ai_tasks.ConfigResolver') as mock_resolver:
            mock_resolver.active.return_value = object()
            from apps.testcases.ai_tasks import run_ai_task
            run_ai_task(task)

        versions = list(self.tc.version_history.order_by('version'))
        self.assertEqual([v.version for v in versions], [1, 2])
        self.assertEqual(versions[0].source, 'created')
        self.assertEqual(versions[0].title, original_title)
        self.assertEqual(versions[1].source, 'ai_modified')
        self.assertEqual(versions[1].title, 'AI改的标题')


class VersionDeleteTests(TestCase):
    """历史版本删除：最新版不可删、编号不重排"""

    def setUp(self):
        self.user = User.objects.create_user('vdel', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.tc = make_case(self.user)
        self.client.patch(f'/api/testcases/{self.tc.id}/', {'title': '第二版'}, format='json')
        self.client.patch(f'/api/testcases/{self.tc.id}/', {'title': '第三版'}, format='json')

    def test_delete_middle_version_succeeds_without_renumber(self):
        resp = self.client.delete(f'/api/testcases/{self.tc.id}/versions/2/')
        self.assertEqual(resp.status_code, 200)
        versions = list(self.tc.version_history.order_by('version').values_list('version', flat=True))
        self.assertEqual(versions, [1, 3], '编号不应重排')

    def test_delete_latest_version_rejected(self):
        resp = self.client.delete(f'/api/testcases/{self.tc.id}/versions/3/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.tc.version_history.count(), 3)

    def test_delete_single_version_rejected(self):
        """唯一版本即最新版，同样不可删"""
        tc2 = make_case(self.user, title='单版本用例')
        resp = self.client.delete(f'/api/testcases/{tc2.id}/versions/1/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(tc2.version_history.count(), 1)

    def test_delete_nonexistent_version_404(self):
        resp = self.client.delete(f'/api/testcases/{self.tc.id}/versions/99/')
        self.assertEqual(resp.status_code, 404)
