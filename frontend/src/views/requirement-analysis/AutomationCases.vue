<template>
  <div class="page-container page-container--full automation-cases">
    <PageHeader :title="t('automation.casesTitle')" :desc="t('automation.casesDesc')">
      <template #actions>
        <el-button type="primary" :disabled="!selectedCases.length" @click="openExecute(selectedCases)">
          {{ t('automation.batchExecute') }} ({{ selectedCases.length }})
        </el-button>
        <el-button :disabled="!failedSelectedIds.length" @click="batchRetryConvert">
          {{ t('automation.batchRetry') }} ({{ failedSelectedIds.length }})
        </el-button>
      </template>
    </PageHeader>

    <div class="card-container">
      <div class="filter-bar">
        <el-select v-model="filters.project" clearable style="width: 200px"
          :placeholder="t('automation.project')" @change="onProjectChange">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.requirement" clearable style="width: 240px"
          :placeholder="t('automation.requirement')" :disabled="!filters.project" @change="loadCases">
          <el-option v-for="r in requirements" :key="r.id" :label="r.title" :value="r.id" />
        </el-select>
        <el-select v-model="filters.convertStatus" clearable style="width: 150px"
          :placeholder="t('automation.convertStatus')">
          <el-option :label="t('automation.processing')" value="processing" />
          <el-option :label="t('automation.done')" value="done" />
          <el-option :label="t('automation.failed')" value="failed" />
        </el-select>
        <el-input v-model="filters.search" clearable style="width: 220px"
          :placeholder="t('automation.searchTitle')" @keyup.enter="reload" />
        <el-button type="primary" @click="reload">{{ t('automation.search') }}</el-button>
      </div>

      <div class="table-container">
        <el-table :data="cases" v-loading="loading" height="100%"
          @selection-change="selectedCases = $event">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="title" :label="t('automation.casesTitle')" min-width="220" show-overflow-tooltip />
          <el-table-column prop="project_name" :label="t('automation.project')" width="140" show-overflow-tooltip />
          <el-table-column prop="requirement_title" :label="t('automation.requirement')" width="180" show-overflow-tooltip />
          <el-table-column :label="t('automation.source')" width="110">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ sourceLabel(row.source_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('automation.convertStatus')" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="convertTagType(row.convert_status)">
                {{ convertLabel(row.convert_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('automation.lastExecution')" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.last_execution" size="small" :type="execTagType(row.last_execution.status)">
                {{ execLabel(row.last_execution.status) }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('automation.records')" width="240" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">{{ t('automation.editSteps') }}</el-button>
              <el-button link type="success" @click="openExecute([row])">{{ t('automation.execute') }}</el-button>
              <el-button link @click="openRecords(row)">{{ t('automation.records') }}</el-button>
              <el-button link type="danger" @click="removeCase(row)">{{ t('automation.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="pagination-container">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
          layout="total, prev, pager, next" @current-change="loadCases" />
      </div>
    </div>

    <!-- 编辑步骤 -->
    <el-dialog v-model="showEdit" :title="t('automation.editSteps')" width="820px">
      <el-form ref="editFormRef" label-width="90px">
        <el-form-item :label="t('automation.casesTitle')">
          <el-input v-model="editing.title" />
        </el-form-item>
        <el-form-item :label="t('automation.precondition')">
          <el-input v-model="editing.precondition" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="editing.steps.length" label=" ">
          <div class="step-header">
            <span class="action-input">{{ t('automation.actionLabel') }}</span>
            <span class="verify-input">{{ t('automation.verifyLabel') }}</span>
            <span class="col-op"></span>
          </div>
        </el-form-item>
        <el-form-item v-for="(s, idx) in editing.steps" :key="idx"
          :label="`${idx + 1}.`">
          <div class="step-row">
            <el-input v-model="s.action" type="textarea" :rows="1"
              class="action-input" :placeholder="t('automation.actionLabel')"
              @input="syncStepHeights" />
            <el-input v-model="s.verify" type="textarea" :rows="1"
              :placeholder="t('automation.verifyLabel')" class="verify-input"
              @input="syncStepHeights" />
            <el-button link type="danger" class="del-btn"
              @click="editing.steps.splice(idx, 1)">✕</el-button>
          </div>
        </el-form-item>
        <el-form-item label=" ">
          <el-button link type="primary" @click="editing.steps.push({ action: '', verify: '' })">
            {{ t('automation.addStep') }}
          </el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">{{ t('automation.cancel') }}</el-button>
        <el-button type="primary" :loading="savingEdit" @click="saveEdit">{{ t('automation.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 执行 -->
    <el-dialog v-model="showExecute" :title="t('automation.execute')" width="480px">
      <el-select v-model="executeEnvId" style="width: 100%">
        <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
      </el-select>
      <div v-if="!environments.length" class="env-empty">{{ t('automation.noEnvironment') }}</div>
      <template #footer>
        <el-button @click="showExecute = false">{{ t('automation.cancel') }}</el-button>
        <el-button type="primary" :disabled="!executeEnvId" :loading="executing" @click="submitExecute">
          {{ t('automation.startExecute') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 执行记录抽屉 -->
    <el-drawer v-model="showRecords" :title="t('automation.records')" size="60%">
      <el-table :data="records" v-loading="recordsLoading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('automation.execStatus')" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="execTagType(row.status)">{{ execLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="environment_name" :label="t('automation.environment')" width="140" />
        <el-table-column prop="error" :label="t('automation.errorInfo')" show-overflow-tooltip />
        <el-table-column prop="started_at" :label="t('automation.lastExecution')" width="170" />
        <el-table-column :label="t('automation.executionLog')" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewLog(row)">{{ t('automation.records') }}</el-button>
          </template>
        </el-table-column>
        <el-table-column :label="t('automation.actions')" width="80">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeRecord(row)">{{ t('automation.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 日志对话框：结构化时间线 + 原始日志切换 -->
    <el-dialog v-model="showLog" :title="t('automation.executionLog')" width="820px">
      <div v-if="currentDetail.length" class="log-toolbar">
        <el-radio-group v-model="logViewMode" size="small">
          <el-radio-button value="timeline">{{ t('automation.timelineView') }}</el-radio-button>
          <el-radio-button value="raw">{{ t('automation.rawLogView') }}</el-radio-button>
        </el-radio-group>
      </div>
      <el-timeline v-if="logViewMode === 'timeline' && currentDetail.length" class="step-timeline">
        <el-timeline-item v-for="step in currentDetail" :key="step.index"
          :type="step.error ? 'danger' : 'success'"
          :timestamp="stepTimestamp(step)">
          <div class="step-card">
            <div class="step-actions">
              <span v-for="(a, i) in step.actions" :key="i" class="step-action">{{ a }}</span>
              <span v-if="!step.actions.length" class="step-action muted">-</span>
            </div>
            <div v-if="step.url" class="step-url">{{ step.title ? `${step.title} · ` : '' }}{{ step.url }}</div>
            <div v-if="step.thinking || step.evaluation || step.next_goal" class="step-thinking">
              {{ step.thinking || step.evaluation || step.next_goal }}
            </div>
            <div v-if="step.result" class="step-result">{{ step.result }}</div>
            <div v-if="step.error" class="step-error">{{ step.error }}</div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <pre v-else class="log-view">{{ currentLog }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import api from '@/utils/api'
import {
  getAutomationCases,
  updateAutomationCase,
  deleteAutomationCase,
  retryAutomationConvert,
  executeAutomationCase,
  batchExecuteAutomationCases,
  getAutomationEnvironments,
  getAutomationExecutions,
  deleteAutomationExecution,
  getAutomationSession,
} from '@/api/requirement-analysis'

const { t } = useI18n()

const projects = ref([])
const requirements = ref([])
const environments = ref([])
const cases = ref([])
const selectedCases = ref([])
const loading = ref(false)
const filters = ref({ project: null, requirement: null, convertStatus: null, search: '' })
const page = ref(1)
const pageSize = 20
const total = ref(0)
let pollTimer = null

const failedSelectedIds = computed(() =>
  selectedCases.value.filter(c => c.convert_status === 'failed').map(c => c.id))

const loadProjects = async () => {
  const { data } = await api.get('/projects/')
  projects.value = data.results || data
}

const loadRequirements = async () => {
  if (!filters.value.project) { requirements.value = []; return }
  const { data } = await api.get('/requirement-analysis/requirements-manage/',
    { params: { project: filters.value.project } })
  requirements.value = data.results || data
}

const loadEnvironments = async () => {
  if (!filters.value.project) { environments.value = []; return }
  const { data } = await getAutomationEnvironments({ project: filters.value.project })
  environments.value = data.results || data
}

const loadCases = async () => {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filters.value.project) params.project = filters.value.project
    if (filters.value.requirement) params.requirement = filters.value.requirement
    if (filters.value.convertStatus) params.convert_status = filters.value.convertStatus
    if (filters.value.search) params.search = filters.value.search
    const { data } = await getAutomationCases(params)
    cases.value = data.results || data
    total.value = data.count || cases.value.length
  } finally {
    loading.value = false
  }
}

const reload = () => { page.value = 1; loadCases() }

const onProjectChange = async () => {
  filters.value.requirement = null
  await Promise.all([loadRequirements(), loadEnvironments()])
  reload()
}

// ---------- 编辑 ----------
const showEdit = ref(false)
const savingEdit = ref(false)
const editing = ref({ id: null, title: '', precondition: '', steps: [] })

const openEdit = (row) => {
  editing.value = {
    id: row.id,
    title: row.title,
    precondition: row.precondition,
    steps: (row.steps || []).map(s => ({ action: s.action, verify: s.verify })),
  }
  showEdit.value = true
  syncStepHeights()
}

// 同一行「操作步骤 / 预期结果」两个输入框高度取较大者，保持等高
const editFormRef = ref(null)
const syncStepHeights = () => {
  nextTick(() => {
    const root = editFormRef.value?.$el
    if (!root) return
    root.querySelectorAll('.step-row').forEach(row => {
      const areas = row.querySelectorAll('textarea')
      if (areas.length < 2) return
      areas.forEach(t => { t.style.height = 'auto' })
      const h = Math.max(...Array.from(areas).map(t => t.scrollHeight))
      areas.forEach(t => { t.style.height = `${h}px` })
    })
  })
}

const saveEdit = async () => {
  savingEdit.value = true
  try {
    await updateAutomationCase(editing.value.id, {
      title: editing.value.title,
      precondition: editing.value.precondition,
      steps: editing.value.steps,
    })
    ElMessage.success(t('automation.save') + ' ✓')
    showEdit.value = false
    await loadCases()
  } finally {
    savingEdit.value = false
  }
}

// ---------- 执行 ----------
const showExecute = ref(false)
const executing = ref(false)
const executeEnvId = ref(null)
const executeTargets = ref([])

const openExecute = (rows) => {
  executeTargets.value = rows
  executeEnvId.value = environments.value[0]?.id || null
  showExecute.value = true
}

const submitExecute = async () => {
  executing.value = true
  try {
    let sessionId
    if (executeTargets.value.length === 1) {
      const { data } = await executeAutomationCase(executeTargets.value[0].id,
        { environment_id: executeEnvId.value })
      sessionId = data.session_id
    } else {
      const { data } = await batchExecuteAutomationCases({
        ids: executeTargets.value.map(c => c.id), environment_id: executeEnvId.value })
      sessionId = data.session_id
    }
    showExecute.value = false
    ElMessage.success(t('automation.sessionProgress') + ' #' + sessionId)
    startPolling(sessionId)
  } finally {
    executing.value = false
  }
}

const startPolling = (sessionId) => {
  stopPolling()
  pollTimer = setInterval(async () => {
    const { data } = await getAutomationSession(sessionId)
    if (['done', 'failed'].includes(data.status)) {
      stopPolling()
      await loadCases()
      ElMessage({
        type: data.status === 'done' ? 'success' : 'error',
        message: data.status === 'done'
          ? t('automation.execCompleted') : (data.error || t('automation.failed')),
      })
    }
  }, 3000)
}
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onBeforeUnmount(stopPolling)

// ---------- 记录 ----------
const showRecords = ref(false)
const records = ref([])
const recordsLoading = ref(false)
const currentRecordCase = ref(null)
const showLog = ref(false)
const currentLog = ref('')
const currentDetail = ref([])
const logViewMode = ref('timeline')

const openRecords = async (row) => {
  showRecords.value = true
  currentRecordCase.value = row
  recordsLoading.value = true
  try {
    const { data } = await getAutomationExecutions({ case: row.id })
    records.value = data.results || data
  } finally {
    recordsLoading.value = false
  }
}

const removeRecord = async (row) => {
  try {
    await ElMessageBox.confirm(t('automation.deleteExecConfirm'), t('automation.delete'), {
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteAutomationExecution(row.id)
  ElMessage.success(t('automation.saveSuccess'))
  if (currentRecordCase.value) await openRecords(currentRecordCase.value)
  await loadCases()
}

const viewLog = (row) => {
  currentLog.value = row.log || row.error || '-'
  currentDetail.value = Array.isArray(row.result_detail) ? row.result_detail : []
  logViewMode.value = currentDetail.value.length ? 'timeline' : 'raw'
  showLog.value = true
}
const stepTimestamp = (step) => {
  const duration = step.duration != null ? ` · ${Number(step.duration).toFixed(1)}s` : ''
  return `${t('automation.stepLabel')} ${step.index}${duration}`
}

// ---------- 其他 ----------
const batchRetryConvert = async () => {
  for (const id of failedSelectedIds.value) {
    await retryAutomationConvert(id)
  }
  ElMessage.success(t('automation.processing'))
  await loadCases()
}

const removeCase = async (row) => {
  await ElMessageBox.confirm(t('automation.deleteConfirm'), { type: 'warning' })
  await deleteAutomationCase(row.id)
  await loadCases()
}

const sourceLabel = (v) => ({ generated: t('automation.sourceAI'), testcase: t('automation.sourceManual'), inline: t('automation.sourceInline') }[v] || v)
const convertLabel = (v) => ({ processing: t('automation.processing'), done: t('automation.done'), failed: t('automation.failed') }[v] || v)
const convertTagType = (v) => ({ processing: 'warning', done: 'success', failed: 'danger' }[v] || 'info')
const execLabel = (v) => ({ pending: t('automation.pending'), running: t('automation.running'), success: t('automation.success'), failed: t('automation.failed'), stopped: t('automation.stopped') }[v] || v)
const execTagType = (v) => ({ pending: 'info', running: 'warning', success: 'success', failed: 'danger', stopped: 'info' }[v] || 'info')

onMounted(async () => {
  await loadProjects()
  if (projects.value.length) {
    filters.value.project = projects.value[0].id
    await Promise.all([loadRequirements(), loadEnvironments()])
  }
  await loadCases()
})
</script>

<style scoped>
.step-header { display: flex; gap: 8px; width: 100%; font-size: 12px; color: var(--el-text-color-secondary); }
.step-header .action-input,
.step-row .action-input { flex: 1; }
.step-header .verify-input,
.step-row .verify-input { flex: 1; }
.step-header .col-op { width: 21px; }
.step-row { display: flex; gap: 8px; width: 100%; align-items: flex-start; }
.step-row textarea { resize: none; }
.step-row .del-btn { margin-top: 4px; width: 21px; }
.log-view { max-height: 480px; overflow: auto; white-space: pre-wrap; margin: 0; }
.env-empty { color: var(--el-color-warning); margin-top: 8px; font-size: 13px; }
.log-toolbar { margin-bottom: 14px; }
.step-timeline { max-height: 520px; overflow: auto; padding-left: 4px; }
.step-card { display: flex; flex-direction: column; gap: 4px; }
.step-action {
  display: inline-block;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 1px 8px;
  margin-right: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px;
}
.step-action.muted { color: var(--el-text-color-placeholder); }
.step-url { font-size: 12px; color: var(--el-text-color-secondary); word-break: break-all; }
.step-thinking { font-size: 12.5px; color: var(--el-text-color-secondary); }
.step-result { font-size: 12.5px; color: var(--el-text-color-regular); white-space: pre-wrap; }
.step-error { font-size: 12.5px; color: var(--el-color-danger); white-space: pre-wrap; }
</style>
