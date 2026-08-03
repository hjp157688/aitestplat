<template>
  <el-dialog
    v-model="visible"
    :title="$t('apiTesting.generateTestCases.title')"
    width="1000px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="generate-testcases-dialog">
      <!-- Step 1: 配置生成 -->
      <div v-if="!generationStarted" class="config-section">
        <div class="selected-requests">
          <h4>{{ $t('apiTesting.generateTestCases.selectedRequests') }} ({{ selectedRequests.length }})</h4>
          <el-table :data="selectedRequests" max-height="200" style="width: 100%">
            <el-table-column prop="name" :label="$t('apiTesting.importOpenApi.summary')" />
            <el-table-column :label="$t('apiTesting.importOpenApi.method')" width="80">
              <template #default="{ row }">
                <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="url" :label="'URL'" min-width="250" show-overflow-tooltip />
          </el-table>
        </div>

        <div class="gen-options">
          <div class="option-item">
            <span class="label">{{ $t('apiTesting.generateTestCases.aiConfig') }}:</span>
            <el-select v-model="aiConfigId" :placeholder="$t('apiTesting.generateTestCases.selectAiConfig')" style="width: 300px;">
              <el-option
                v-for="c in aiConfigs"
                :key="c.id"
                :label="`${c.name} (${c.model_name})`"
                :value="c.id"
              />
            </el-select>
          </div>
          <div class="option-item">
            <span class="label">{{ $t('apiTesting.generateTestCases.scenarios') }}:</span>
            <el-checkbox-group v-model="scenarios">
              <el-checkbox value="positive" label="positive">{{ $t('apiTesting.generateTestCases.positive') }}</el-checkbox>
              <el-checkbox value="negative" label="negative">{{ $t('apiTesting.generateTestCases.negative') }}</el-checkbox>
              <el-checkbox value="boundary" label="boundary">{{ $t('apiTesting.generateTestCases.boundary') }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
      </div>

      <!-- Step 2: 生成进度 -->
      <div v-if="generationStarted && generating" class="progress-section">
        <el-alert :title="$t('apiTesting.generateTestCases.generating')" type="info" :closable="false" show-icon />
        <el-progress :percentage="progress" :status="progress === 100 ? 'success' : ''" style="margin-top: 16px;" />
        <p class="progress-text">{{ progressText }}</p>
      </div>

      <!-- Step 3: 生成结果 -->
      <div v-if="generationCompleted" class="result-section">
        <el-alert
          :title="`${$t('apiTesting.generateTestCases.completed')} - ${$t('apiTesting.generateTestCases.totalCases', { count: totalCaseCount })}`"
          type="success"
          :closable="false"
          show-icon
        />

        <div class="result-toolbar">
          <el-checkbox v-model="selectAllCases" @change="handleSelectAllCases">{{ $t('apiTesting.generateTestCases.selectAll') }}</el-checkbox>
          <el-button size="small" @click="expandAll">{{ $t('apiTesting.generateTestCases.expandAll') }}</el-button>
          <el-button size="small" @click="collapseAll">{{ $t('apiTesting.generateTestCases.collapseAll') }}</el-button>
        </div>

        <el-collapse v-model="activeGroups" class="result-groups">
          <el-collapse-item
            v-for="group in caseGroups"
            :key="group.requestId"
            :name="String(group.requestId)"
          >
            <template #title>
              <div class="group-title">
                <el-tag :type="methodTagType(group.method)" size="small">{{ group.method }}</el-tag>
                <span class="group-name">{{ group.requestName }}</span>
                <span class="group-url">{{ group.url }}</span>
                <el-tag size="small" type="info">{{ group.cases.length }} {{ $t('apiTesting.generateTestCases.cases') }}</el-tag>
              </div>
            </template>

            <div class="case-list">
              <div
                v-for="(testCase, index) in group.cases"
                :key="index"
                class="case-card"
                :class="{ selected: selectedCases[group.requestId]?.includes(index) }"
              >
                <div class="case-header">
                  <el-checkbox
                    :model-value="selectedCases[group.requestId]?.includes(index)"
                    @change="(val) => toggleCase(group.requestId, index, val)"
                  >
                    <span class="case-name">{{ testCase.name }}</span>
                  </el-checkbox>
                  <div class="case-actions">
                    <el-button size="small" text @click="toggleCaseDetail(group.requestId, index)">
                      {{ expandedCases[`${group.requestId}_${index}`] ? $t('apiTesting.generateTestCases.collapseAll') : $t('apiTesting.generateTestCases.expandAll') }}
                    </el-button>
                    <el-button size="small" text type="danger" @click="removeCase(group.requestId, index)">
                      {{ $t('apiTesting.common.delete') }}
                    </el-button>
                  </div>
                </div>

                <div v-if="expandedCases[`${group.requestId}_${index}`]" class="case-detail">
                  <div class="detail-section">
                    <h5>{{ $t('apiTesting.generateTestCases.requestBody') }}</h5>
                    <el-input
                      :model-value="formatBody(testCase.body_override)"
                      type="textarea"
                      :rows="4"
                      readonly
                    />
                  </div>
                  <div class="detail-section">
                    <h5>{{ $t('apiTesting.generateTestCases.assertions') }} ({{ testCase.assertions?.length || 0 }})</h5>
                    <div v-for="(assertion, ai) in testCase.assertions" :key="ai" class="assertion-item">
                      <el-tag size="small" type="success">✓</el-tag>
                      <span>{{ formatAssertion(assertion) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div class="save-section">
          <div class="save-options">
            <el-input
              v-model="suiteName"
              :placeholder="$t('apiTesting.generateTestCases.suiteNamePlaceholder')"
              style="width: 300px;"
            />
          </div>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="generationError" class="error-section">
        <el-alert :title="$t('apiTesting.generateTestCases.error')" :description="generationError" type="error" show-icon />
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">{{ $t('apiTesting.common.cancel') }}</el-button>
      <el-button
        v-if="!generationStarted"
        type="primary"
        @click="startGeneration"
        :loading="generating"
        :disabled="!canGenerate"
      >
        {{ $t('apiTesting.generateTestCases.generate') }}
      </el-button>
      <el-button
        v-if="generationCompleted"
        type="primary"
        @click="saveCases"
        :loading="saving"
        :disabled="saving"
      >
        {{ $t('apiTesting.generateTestCases.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const props = defineProps({
  modelValue: Boolean,
  selectedRequests: { type: Array, default: () => [] },
  projectId: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// 生成配置
const aiConfigs = ref([])
const aiConfigId = ref(null)
const scenarios = ref(['positive', 'negative', 'boundary'])
const generating = ref(false)
const generationStarted = ref(false)
const generationCompleted = ref(false)
const generationError = ref('')
const progress = ref(0)
const progressText = ref('')
const taskId = ref('')
let pollingTimer = null

// 生成结果
const caseGroups = ref([])
const activeGroups = ref([])
const selectedCases = ref({})
const expandedCases = ref({})
const selectAllCases = ref(true)
const suiteName = ref('')
const saving = ref(false)

const canGenerate = computed(() => {
  return props.selectedRequests.length > 0
})

const totalCaseCount = computed(() => {
  let count = 0
  caseGroups.value.forEach(g => { count += g.cases.length })
  return count
})

function methodTagType(method) {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}

function formatBody(body) {
  if (!body) return ''
  if (typeof body === 'string') return body
  return JSON.stringify(body, null, 2)
}

function formatAssertion(assertion) {
  if (!assertion) return ''
  if (assertion.type === 'status_code') {
    return `${assertion.type} ${assertion.operator} ${assertion.expected}`
  }
  return `${assertion.type} ${assertion.operator} ${assertion.path || ''} ${assertion.expected || ''}`
}

async function loadAiConfigs() {
  try {
    const res = await api.get('/requirement-analysis/ai-models/', {
      params: { role: 'api_testcase_generator', is_active: true },
    })
    aiConfigs.value = res.data?.results || res.data || []
    if (aiConfigs.value.length > 0) {
      aiConfigId.value = aiConfigs.value[0].id
    }
  } catch (e) {
    console.error('Failed to load AI configs:', e)
  }
}

async function startGeneration() {
  generationStarted.value = true
  generating.value = true
  progress.value = 0
  progressText.value = '正在初始化...'
  generationError.value = ''

  try {
    const res = await api.post('/api-testing/requests/generate-testcases/', {
      request_ids: props.selectedRequests.map(r => r.id),
      ai_config_id: aiConfigId.value,
    })
    taskId.value = res.data.task_id
    startPolling()
  } catch (e) {
    generating.value = false
    generationError.value = e.response?.data?.error || e.message
  }
}

function startPolling() {
  pollingTimer = setInterval(async () => {
    try {
      const res = await api.get('/api-testing/requests/generation-progress/', {
        params: { task_id: taskId.value },
      })

      const data = res.data
      progress.value = data.progress || 0
      progressText.value = `进度: ${progress.value}%`

      if (data.status === 'completed') {
        clearInterval(pollingTimer)
        generating.value = false
        generationCompleted.value = true
        processResult(data.result)
      } else if (data.status === 'failed') {
        clearInterval(pollingTimer)
        generating.value = false
        generationError.value = data.error || '生成失败'
      }
    } catch (e) {
      // 继续轮询
    }
  }, 2000)
}

function processResult(result) {
  if (!result || !result.test_cases) {
    caseGroups.value = []
    return
  }

  const groups = []
  for (const [requestId, cases] of Object.entries(result.test_cases)) {
    const request = props.selectedRequests.find(r => String(r.id) === String(requestId))
    if (request) {
      groups.push({
        requestId: Number(requestId),
        requestName: request.name,
        method: request.method,
        url: request.url,
        cases: Array.isArray(cases) ? cases : [],
      })
      // 默认全选
      selectedCases.value[requestId] = Array.from({ length: (Array.isArray(cases) ? cases : []).length }, (_, i) => i)
    }
  }

  caseGroups.value = groups
  activeGroups.value = groups.map(g => String(g.requestId))
}

function handleSelectAllCases(val) {
  if (val) {
    caseGroups.value.forEach(g => {
      selectedCases.value[g.requestId] = Array.from({ length: g.cases.length }, (_, i) => i)
    })
  } else {
    selectedCases.value = {}
  }
}

function toggleCase(requestId, index, val) {
  if (!selectedCases.value[requestId]) {
    selectedCases.value[requestId] = []
  }
  if (val) {
    if (!selectedCases.value[requestId].includes(index)) {
      selectedCases.value[requestId].push(index)
    }
  } else {
    selectedCases.value[requestId] = selectedCases.value[requestId].filter(i => i !== index)
  }
}

function toggleCaseDetail(requestId, index) {
  const key = `${requestId}_${index}`
  expandedCases.value[key] = !expandedCases.value[key]
}

function removeCase(requestId, index) {
  const group = caseGroups.value.find(g => g.requestId === requestId)
  if (group) {
    group.cases.splice(index, 1)
    if (selectedCases.value[requestId]) {
      selectedCases.value[requestId] = selectedCases.value[requestId]
        .filter(i => i !== index)
        .map(i => i > index ? i - 1 : i)
    }
  }
}

function expandAll() {
  activeGroups.value = caseGroups.value.map(g => String(g.requestId))
  caseGroups.value.forEach(g => {
    g.cases.forEach((_, i) => {
      expandedCases.value[`${g.requestId}_${i}`] = true
    })
  })
}

function collapseAll() {
  activeGroups.value = []
  expandedCases.value = {}
}

async function saveCases() {
  saving.value = true
  try {
    const cases = []
    for (const group of caseGroups.value) {
      for (const index of (selectedCases.value[group.requestId] || [])) {
        cases.push({
          request_id: group.requestId,
          ...group.cases[index],
        })
      }
    }

    await api.post('/api-testing/requests/save-testcases/', {
      task_id: taskId.value,
      cases,
      suite_name: suiteName.value || null,
      collection_id: null,
      project_id: props.projectId,
    })

    ElMessage.success(`成功保存 ${cases.length} 条测试用例`)
    emit('saved')
    handleClose()
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    saving.value = false
  }
}

function handleClose() {
  visible.value = false
  resetState()
}

function resetState() {
  generationStarted.value = false
  generationCompleted.value = false
  generationError.value = ''
  generating.value = false
  progress.value = 0
  caseGroups.value = []
  selectedCases.value = {}
  expandedCases.value = {}
  selectAllCases.value = true
  suiteName.value = ''
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

watch(visible, (val) => {
  if (val) {
    loadAiConfigs()
    resetState()
  }
})

onBeforeUnmount(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
  }
})
</script>

<style scoped>
.generate-testcases-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selected-requests h4 {
  margin: 0 0 8px 0;
}

.gen-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.option-item .label {
  font-weight: 500;
  white-space: nowrap;
}

.progress-section {
  text-align: center;
  padding: 20px;
}

.progress-text {
  color: var(--el-text-color-secondary);
  margin-top: 8px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.group-name {
  font-weight: 500;
}

.group-url {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}

.case-card {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 8px 12px;
}

.case-card.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.case-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.case-name {
  font-weight: 500;
}

.case-actions {
  display: flex;
  gap: 4px;
}

.case-detail {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.detail-section {
  margin-bottom: 8px;
}

.detail-section h5 {
  margin: 0 0 4px 0;
}

.assertion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.save-section {
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.save-options {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>