<template>
  <div class="page-container">
    <PageHeader :title="$t('testcase.detail')">
      <template #actions>
        <el-button @click="backToList">{{ $t('common.back') }}</el-button>
        <el-button type="primary" @click="editTestCase">{{ $t('common.edit') }}</el-button>
      </template>
    </PageHeader>

    <div class="card-container" v-if="testcase">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('testcase.caseTitle')" :span="2">{{ testcase.title }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.priority')">
          <el-tag size="small" :type="priorityType(testcase.priority)">{{ getPriorityText(testcase.priority) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.testType')">{{ getTypeText(testcase.test_type) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.project')">{{ testcase.project?.name || $t('testcase.noProject') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.relatedVersions')" :span="2">
          <div v-if="testcase.versions && testcase.versions.length > 0" class="version-tags">
            <el-tag
              v-for="version in testcase.versions"
              :key="version.id"
              size="small"
              :type="version.is_baseline ? 'warning' : 'info'"
              class="version-tag"
            >
              {{ version.name }}
            </el-tag>
          </div>
          <span v-else class="no-version">{{ $t('testcase.noVersion') }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.author')">{{ testcase.author?.username }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.createdAt')" :span="2">{{ formatDate(testcase.created_at) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.caseDescription')" :span="2">{{ testcase.description || $t('testcase.noDescription') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.preconditions')" :span="2">
          <div v-html="testcase.preconditions || $t('testcase.none')"></div>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.steps')" :span="2">
          <div v-if="parsedSteps.length" class="steps-display">
            <div v-for="(step, idx) in parsedSteps" :key="idx" class="step-item">
              <span class="step-num">{{ idx + 1 }}.</span>
              <div class="step-body">
                <div class="step-desc">{{ step.desc }}</div>
                <div v-if="step.expect" class="step-expect">{{ $t('testcase.expectPrefix') }}: {{ step.expect }}</div>
              </div>
            </div>
          </div>
          <span v-else>{{ $t('testcase.none') }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 历史版本（用例级变更链：创建/手动编辑/AI修改/禅道同步/回退） -->
      <div class="version-history-section">
        <div class="version-history-header">
          <h3 class="section-title">{{ $t('testcase.versionHistory') }}</h3>
          <div class="version-history-actions">
            <el-button
              size="small"
              :disabled="checkedVersions.length !== 2"
              @click="showVersionDiff">
              {{ $t('testcase.versionCompare') }}
            </el-button>
          </div>
        </div>

        <el-empty v-if="!caseVersions.length && !versionsLoading" :description="$t('testcase.versionEmpty')" :image-size="60" />
        <el-table
          v-else
          v-loading="versionsLoading"
          :data="caseVersions"
          size="small"
          @selection-change="onVersionSelectionChange">
          <el-table-column type="selection" width="42" />
          <el-table-column prop="version" :label="'v'" width="70" align="center">
            <template #default="scope">
              <el-tag
                size="small"
                :type="scope.row.version === currentVersion ? 'success' : 'info'">
                v{{ scope.row.version }}{{ scope.row.version === currentVersion ? ` (${$t('testcase.versionCurrent')})` : '' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="source_display" :label="$t('testcase.status')" width="110" align="center" />
          <el-table-column prop="note" :label="$t('testcase.versionNoteLabel')">
            <template #default="scope">{{ scope.row.note || $t('testcase.versionNoNote') }}</template>
          </el-table-column>
          <el-table-column prop="created_by_name" :label="$t('testcase.author')" width="120" />
          <el-table-column prop="created_at" :label="$t('testcase.createdAt')" width="150">
            <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
          </el-table-column>
          <el-table-column :label="$t('project.actions')" width="150" align="center">
            <template #default="scope">
              <el-button
                link
                type="primary"
                size="small"
                :disabled="scope.row.version === currentVersion"
                @click="restoreVersion(scope.row)">
                {{ $t('testcase.versionRestore') }}
              </el-button>
              <el-button
                link
                type="danger"
                size="small"
                :disabled="scope.row.version === currentVersion"
                @click="deleteVersion(scope.row)">
                {{ $t('common.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 版本对比：仅展示有差异的字段，左右为两版内容 -->
        <div v-if="diffVisible" class="version-diff">
          <div class="version-diff-title">
            {{ $t('testcase.versionDiffTitle', { a: diffPair[0].version, b: diffPair[1].version }) }}
            ·
            {{ $t('testcase.versionChangedFields', { count: diffFields.length }) }}
          </div>
          <el-empty
            v-if="!diffFields.length"
            :description="$t('testcase.versionNoDiff')"
            :image-size="48" />
          <div v-else class="diff-list">
            <div v-for="field in diffFields" :key="field.key" class="diff-item">
              <div class="diff-field">{{ field.label }}</div>
              <div class="diff-versions">
                <div class="diff-side">
                  <div class="diff-side-tag">v{{ diffPair[0].version }}</div>
                  <pre class="diff-content">{{ field.before }}</pre>
                </div>
                <div class="diff-side">
                  <div class="diff-side-label">v{{ diffPair[1].version }}</div>
                  <pre class="diff-content">{{ field.after }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { getTestCaseVersions, restoreTestCaseVersion, deleteTestCaseVersion } from '@/api/requirement'
import dayjs from 'dayjs'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const testcase = ref(null)

// ==================== 用例版本历史 ====================
const caseVersions = ref([])
const versionsLoading = ref(false)
const checkedVersions = ref([]) // 勾选待对比的两个版本
const currentVersion = ref(1) // 用例当前内容对应的最新版本号
const diffVisible = ref(false)
const diffPair = ref([])

const VERSION_SOURCE_KEYS = {
  created: 'versionSourceCreated',
  manual_edit: 'versionSourceManualEdit',
  ai_modified: 'versionSourceAiModified',
  ai_supplemented: 'versionSourceAiSupplemented',
  zentao_sync: 'versionSourceZentaoSync',
  restore: 'versionSourceRestore'
}

const fetchVersions = async () => {
  versionsLoading.value = true
  try {
    const res = await getTestCaseVersions(route.params.id)
    caseVersions.value = res.data || []
    currentVersion.value = caseVersions.value.length
      ? Math.max(...caseVersions.value.map(v => v.version))
      : 1
  } catch (error) {
    caseVersions.value = []
  } finally {
    versionsLoading.value = false
  }
}

const onVersionSelectionChange = (selection) => {
  checkedVersions.value = selection
}

// 字段展示标签 + 展示值（steps 解析成可读文本）
const versionFieldMeta = [
  { key: 'title', labelKey: 'testcase.caseTitle', plain: true },
  { key: 'priority', labelKey: 'testcase.priority' },
  { key: 'test_type', labelKey: 'testcase.testType' },
  { key: 'preconditions', labelKey: 'testcase.preconditions' },
  { key: 'steps', labelKey: 'testcase.steps' },
  { key: 'description', labelKey: 'testcase.caseDescription' }
]

const versionFieldText = (row, key) => {
  if (key === 'steps') {
    try {
      const arr = JSON.parse(row.steps)
      if (Array.isArray(arr)) {
        return arr
          .map((s, i) => `${i + 1}. ${s.desc || ''}${s.expect ? ` → ${s.expect}` : ''}`)
          .join('\n')
      }
    } catch (e) {
      return row.steps || '-'
    }
  }
  if (key === 'priority') return getPriorityText(row.priority)
  if (key === 'test_type') return getTypeText(row.test_type)
  return row[key] || '-'
}

const diffFields = computed(() => {
  if (checkedVersions.value.length !== 2) return []
  const [a, b] = checkedVersions.value
  return versionFieldMeta
    .map(meta => ({
      key: meta.key,
      label: t(meta.labelKey),
      before: versionFieldText(a, meta.key),
      after: versionFieldText(b, meta.key)
    }))
    .filter(f => f.before !== f.after)
})

const showVersionDiff = () => {
  const [a, b] = checkedVersions.value
  diffPair.value = a.version < b.version ? [a, b] : [b, a]
  diffVisible.value = true
}

const restoreVersion = async (row) => {
  try {
    await ElMessageBox.confirm(
      t('testcase.versionRestoreConfirm', { version: row.version }),
      t('testcase.versionHistory'),
      { type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    await restoreTestCaseVersion(route.params.id, row.version, '')
    ElMessage.success(t('testcase.versionRestoreSuccess', { version: row.version }))
    await Promise.all([fetchTestCase(), fetchVersions()])
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('testcase.aiTaskFailed'))
  }
}

const deleteVersion = async (row) => {
  try {
    await ElMessageBox.confirm(
      t('testcase.versionDeleteConfirm', { version: row.version }),
      t('testcase.versionHistory'),
      { type: 'warning' }
    )
  } catch (e) {
    return
  }
  try {
    await deleteTestCaseVersion(route.params.id, row.version)
    ElMessage.success(t('testcase.versionDeleteSuccess', { version: row.version }))
    // 对比勾选里若包含被删版本则清空，避免悬空引用
    if (checkedVersions.value.some(v => v.version === row.version)) {
      checkedVersions.value = []
      diffVisible.value = false
    }
    await fetchVersions()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('testcase.aiTaskFailed'))
  }
}

// 解析结构化步骤 [{desc, expect}]
const parsedSteps = computed(() => {
  if (!testcase.value?.steps) return []
  try {
    const arr = JSON.parse(testcase.value.steps)
    return Array.isArray(arr) ? arr : []
  } catch (e) {
    return [{ desc: testcase.value.steps, expect: '' }]
  }
})

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    testcase.value = response.data
  } catch (error) {
    ElMessage.error(t('testcase.fetchDetailFailed'))
  }
}

const backToList = () => {
  router.push('/ai-generation/testcases')
}

const editTestCase = () => {
  router.push(`/ai-generation/testcases/${route.params.id}/edit`)
}

const getPriorityText = (priority) => {
  const textMap = {
    low: t('testcase.low'),
    medium: t('testcase.medium'),
    high: t('testcase.high'),
    critical: t('testcase.critical')
  }
  return textMap[priority] || priority
}

// 优先级 → el-tag type（低=成功色 / 中=警告色 / 高、紧急=危险色）
const priorityType = (priority) => {
  const map = { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[priority] || 'info'
}

const getTypeText = (type) => {
  const textMap = {
    functional: t('testcase.functional'),
    integration: t('testcase.integration'),
    api: t('testcase.api'),
    ui: t('testcase.ui'),
    performance: t('testcase.performance'),
    security: t('testcase.security')
  }
  return textMap[type] || '-'
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchTestCase()
  fetchVersions()
})
</script>

<style lang="scss" scoped>
.steps-display {
  width: 100%;

  .step-item {
    display: flex;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px dashed var(--aitest-border);

    &:last-child {
      border-bottom: none;
    }

    .step-num {
      flex-shrink: 0;
      color: var(--aitest-text-2);
      font-weight: 600;
    }

    .step-body {
      flex: 1;

      .step-expect {
        color: var(--aitest-text-2);
        margin-top: 2px;
      }
    }
  }
}

.version-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--aitest-space-2);

  .version-tag {
    margin: 0;
  }
}

.no-version {
  color: var(--aitest-text-3);
  font-size: var(--aitest-font-size-sm);
  font-style: italic;
}

.steps-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--aitest-text-1);
  font-family: inherit;
}

.version-history-section {
  margin-top: 20px;
}

.version-history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--aitest-text-1);
}

.version-diff {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid var(--aitest-line-2, #e4e7ed);
  border-radius: 8px;
  background: var(--aitest-canvas, #f8fafc);
}

.version-diff-title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--aitest-text-2, #475569);
}

.diff-item {
  margin-bottom: 14px;
}

.diff-field {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--aitest-text-1);
}

.diff-versions {
  display: flex;
  gap: 12px;
}

.diff-side {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--aitest-border-1, #e4e7ed);
  border-radius: 6px;
  background: #fff;
}

.diff-side-label {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.diff-content {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--aitest-text-1);
  font-family: inherit;
}
</style>