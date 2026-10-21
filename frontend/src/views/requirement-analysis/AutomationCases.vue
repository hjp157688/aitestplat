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
      <el-form label-width="90px">
        <el-form-item :label="t('automation.casesTitle')">
          <el-input v-model="editing.title" />
        </el-form-item>
        <el-form-item :label="t('automation.precondition')">
          <el-input v-model="editing.precondition" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-for="(s, idx) in editing.steps" :key="idx"
          :label="`${idx + 1}.`">
          <div class="step-row">
            <el-input v-model="s.action" type="textarea" :autosize="{ minRows: 1 }"
              :placeholder="t('automation.actionLabel')" />
            <el-input v-model="s.verify" :placeholder="t('automation.verifyLabel')" style="width: 240px" />
            <el-button link type="danger" @click="editing.steps.splice(idx, 1)">✕</el-button>
          </div>
        </el-form-item>
        <el-button link type="primary" @click="editing.steps.push({ action: '', verify: '' })">
          {{ t('automation.addStep') }}
        </el-button>
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
        <el-table-column :label="t('automation.convertStatus')" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="execTagType(row.status)">{{ execLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="environment_name" :label="t('automation.environment')" width="140" />
        <el-table-column prop="error" :label="t('automation.loginFailed')" show-overflow-tooltip />
        <el-table-column prop="started_at" :label="t('automation.lastExecution')" width="170" />
        <el-table-column :label="t('automation.executionLog')" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewLog(row)">{{ t('automation.records') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 日志对话框 -->
    <el-dialog v-model="showLog" :title="t('automation.executionLog')" width="720px">
      <pre class="log-view">{{ currentLog }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
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
const showLog = ref(false)
const currentLog = ref('')

const openRecords = async (row) => {
  showRecords.value = true
  recordsLoading.value = true
  try {
    const { data } = await getAutomationExecutions({ case: row.id })
    records.value = data.results || data
  } finally {
    recordsLoading.value = false
  }
}

const viewLog = (row) => { currentLog.value = row.log || row.error || '-'; showLog.value = true }

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
.step-row { display: flex; gap: 8px; width: 100%; }
.log-view { max-height: 480px; overflow: auto; white-space: pre-wrap; margin: 0; }
.env-empty { color: var(--el-color-warning); margin-top: 8px; font-size: 13px; }
</style>
