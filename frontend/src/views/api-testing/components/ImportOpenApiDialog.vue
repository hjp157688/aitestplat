<template>
  <el-dialog
    v-model="visible"
    :title="$t('apiTesting.importOpenApi.title')"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="import-openapi-dialog">
      <!-- Step 1: 上传/粘贴文档 -->
      <div class="upload-section">
        <el-tabs v-model="inputMethod" type="border-card">
          <el-tab-pane :label="$t('apiTesting.importOpenApi.uploadFile')" name="file">
            <el-upload
              ref="uploadRef"
              class="upload-area"
              drag
              action="#"
              :auto-upload="false"
              :limit="1"
              :accept="'.json,.yaml,.yml'"
              :show-file-list="false"
              :on-change="handleFileChange"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-text">
                <p>{{ $t('apiTesting.importOpenApi.dragOrClick') }}</p>
                <p class="upload-hint">.json / .yaml / .yml</p>
              </div>
            </el-upload>
            <div v-if="uploadedFile" class="file-info">
              <el-icon><Document /></el-icon>
              <span>{{ uploadedFile.name }}</span>
              <span class="file-size">({{ formatFileSize(uploadedFile.size) }})</span>
              <el-button type="danger" size="small" text @click="clearFile">{{ $t('apiTesting.common.remove') }}</el-button>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="$t('apiTesting.importOpenApi.pasteText')" name="paste">
            <el-input
              v-model="pasteContent"
              type="textarea"
              :rows="12"
              :placeholder="$t('apiTesting.importOpenApi.pastePlaceholder')"
            />
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 项目选择 -->
      <div class="project-select">
        <span class="label">{{ $t('apiTesting.importOpenApi.targetProject') }}:</span>
        <el-select v-model="projectId" :placeholder="$t('apiTesting.importOpenApi.selectProject')" style="width: 300px;">
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
      </div>

      <!-- 解析结果 -->
      <div v-if="parseResult" class="parse-result">
        <el-alert
          :title="`${$t('apiTesting.importOpenApi.parseSuccess')} - ${parseResult.title} (${parseResult.spec_version})`"
          type="success"
          :closable="false"
          show-icon
        >
          <template #default>
            <div>{{ parseResult.endpoint_count }} {{ $t('apiTesting.importOpenApi.endpoints') }}</div>
            <div v-if="parseResult.base_url">Base URL: {{ parseResult.base_url }}</div>
          </template>
        </el-alert>

        <!-- 按 Tag 分组预览 -->
        <div v-if="parseResult.groups && parseResult.groups.length > 1" class="group-preview">
          <div class="table-header">
            <el-checkbox v-model="selectAll" @change="handleSelectAll">{{ $t('apiTesting.importOpenApi.selectAll') }}</el-checkbox>
          </div>
          <div v-for="group in parseResult.groups" :key="group.tag" class="tag-group">
            <div class="tag-header">
              <el-icon><Folder /></el-icon>
              <span class="tag-name">{{ group.tag }}</span>
              <span class="tag-count">({{ group.endpoints.length }})</span>
            </div>
            <el-table
              :data="group.endpoints"
              size="small"
              @selection-change="(rows) => handleGroupSelectionChange(group.tag, rows)"
              :ref="(el) => { if (el) groupTableRefs[group.tag] = el }"
            >
              <el-table-column type="selection" width="40" />
              <el-table-column :label="$t('apiTesting.importOpenApi.method')" width="75">
                <template #default="{ row }">
                  <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="path" :label="$t('apiTesting.importOpenApi.path')" min-width="180" />
              <el-table-column prop="summary" :label="$t('apiTesting.importOpenApi.summary')" min-width="150" show-overflow-tooltip />
              <el-table-column :label="$t('apiTesting.importOpenApi.info')" min-width="120">
                <template #default="{ row }">
                  <div class="endpoint-info">
                    <span v-if="row.parameters && row.parameters.filter(p => p.in === 'query').length > 0" class="info-tag">
                      Query
                    </span>
                    <span v-if="row.parameters && row.parameters.filter(p => p.in === 'path').length > 0" class="info-tag">
                      Path
                    </span>
                    <span v-if="row.request_body" class="info-tag body-tag">
                      Body: {{ row.request_body.content_type?.includes('json') ? 'JSON' : row.request_body.content_type }}
                    </span>
                    <span v-if="row._auth_headers && row._auth_headers.length > 0" class="info-tag auth-tag">
                      Auth: {{ row._auth_headers[0].description }}
                    </span>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 无分组时显示平铺表格 -->
        <div v-else class="endpoint-table">
          <div class="table-header">
            <el-checkbox v-model="selectAll" @change="handleSelectAll">{{ $t('apiTesting.importOpenApi.selectAll') }}</el-checkbox>
          </div>
          <el-table
            :data="filteredEndpoints"
            max-height="300"
            @selection-change="handleSelectionChange"
            ref="endpointTableRef"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column :label="$t('apiTesting.importOpenApi.method')" width="80">
              <template #default="{ row }">
                <el-tag :type="methodTagType(row.method)" size="small">{{ row.method }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="path" :label="$t('apiTesting.importOpenApi.path')" min-width="200" />
            <el-table-column prop="summary" :label="$t('apiTesting.importOpenApi.summary')" min-width="200" show-overflow-tooltip />
            <el-table-column :label="$t('apiTesting.importOpenApi.info')" min-width="120">
              <template #default="{ row }">
                <div class="endpoint-info">
                  <span v-if="row.parameters && row.parameters.filter(p => p.in === 'query').length > 0" class="info-tag">
                    Query
                  </span>
                  <span v-if="row.parameters && row.parameters.filter(p => p.in === 'path').length > 0" class="info-tag">
                    Path
                  </span>
                  <span v-if="row.request_body" class="info-tag body-tag">
                    Body: {{ row.request_body.content_type?.includes('json') ? 'JSON' : row.request_body.content_type }}
                  </span>
                  <span v-if="row._auth_headers && row._auth_headers.length > 0" class="info-tag auth-tag">
                    Auth: {{ row._auth_headers[0].description }}
                  </span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 导入配置 -->
      <div v-if="parseResult" class="import-config">
        <div class="config-item">
          <span class="label">Base URL:</span>
          <el-input v-model="baseUrl" placeholder="https://api.example.com" style="width: 400px;" />
        </div>
        <div class="config-item" v-if="parseResult.groups && parseResult.groups.length > 1">
          <el-checkbox v-model="byTag">{{ $t('apiTesting.importOpenApi.byTag') }}</el-checkbox>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">{{ $t('apiTesting.common.cancel') }}</el-button>
      <el-button
        v-if="!parseResult"
        type="primary"
        @click="parseDocument"
        :loading="parsing"
        :disabled="!canParse"
      >
        {{ $t('apiTesting.importOpenApi.parse') }}
      </el-button>
      <el-button
        v-else
        type="primary"
        @click="importToCollection"
        :loading="importing"
        :disabled="!canImport"
      >
        {{ $t('apiTesting.importOpenApi.import') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Folder } from '@element-plus/icons-vue'
import api from '@/utils/api'

const props = defineProps({
  modelValue: Boolean,
  projects: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'imported'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const inputMethod = ref('file')
const uploadedFile = ref(null)
const pasteContent = ref('')
const projectId = ref(null)
const baseUrl = ref('')
const parsing = ref(false)
const importing = ref(false)
const parseResult = ref(null)
const selectAll = ref(true)
const selectedEndpoints = ref([])
const groupTableRefs = ref({})
const byTag = ref(true)
const tagFilter = ref(null)

const canParse = computed(() => {
  if (inputMethod.value === 'file') return uploadedFile.value && projectId.value
  return pasteContent.value.trim() && projectId.value
})

const canImport = computed(() => {
  return projectId.value && selectedEndpoints.value.length > 0
})

const filteredEndpoints = computed(() => {
  if (!parseResult.value) return []
  if (!tagFilter.value) return parseResult.value.endpoints
  return parseResult.value.endpoints.filter(ep => ep.tags.includes(tagFilter.value))
})

function handleFileChange(file) {
  uploadedFile.value = file.raw
}

function clearFile() {
  uploadedFile.value = null
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function methodTagType(method) {
  const map = { GET: 'success', POST: 'primary', PUT: 'warning', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}

function handleSelectAll(val) {
  if (val && parseResult.value) {
    selectedEndpoints.value = [...filteredEndpoints.value]
  } else {
    selectedEndpoints.value = []
  }
}

function handleSelectionChange(rows) {
  selectedEndpoints.value = rows
}

function handleGroupSelectionChange(tag, rows) {
  // 更新 selectedEndpoints，替换该 tag 组的旧选择
  selectedEndpoints.value = selectedEndpoints.value.filter(
    ep => !ep.tags || !ep.tags.includes(tag)
  )
  selectedEndpoints.value = [...selectedEndpoints.value, ...rows]
}

function filterByTag(tag) {
  tagFilter.value = tagFilter.value === tag ? null : tag
}

async function parseDocument() {
  parsing.value = true
  try {
    let formData = new FormData()

    if (inputMethod.value === 'file') {
      formData.append('title', uploadedFile.value.name)
      formData.append('file', uploadedFile.value)
      formData.append('project', projectId.value)
    } else {
      // 粘贴模式：创建临时文件上传
      const blob = new Blob([pasteContent.value], { type: 'application/octet-stream' })
      const ext = pasteContent.value.trim().startsWith('{') ? 'json' : 'yaml'
      formData.append('title', `api-doc.${ext}`)
      formData.append('file', blob, `api-doc.${ext}`)
      formData.append('project', projectId.value)
    }

    const uploadRes = await api.post('/api-testing/api-docs/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    const docId = uploadRes.data.id
    const parseRes = await api.post(`/api-testing/api-docs/${docId}/parse/`)
    parseResult.value = parseRes.data
    parseResult.value._docId = docId

    // 自动填充 Base URL
    if (parseResult.value.base_url && !baseUrl.value) {
      baseUrl.value = parseResult.value.base_url
    }

    // 默认全选
    selectedEndpoints.value = [...parseResult.value.endpoints]
    ElMessage.success('解析成功')
  } catch (e) {
    ElMessage.error('解析失败: ' + (e.response?.data?.error || e.message))
  } finally {
    parsing.value = false
  }
}

async function importToCollection() {
  importing.value = true
  try {
    // 只导入选中的端点
    const docId = parseResult.value._docId
    await api.post(`/api-testing/api-docs/${docId}/import/`, {
      project_id: projectId.value,
      base_url: baseUrl.value,
      by_tag: byTag.value,
    })

    ElMessage.success(`成功导入 ${selectedEndpoints.value.length} 个接口`)
    emit('imported')
    handleClose()
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.error || e.message))
  } finally {
    importing.value = false
  }
}

function handleClose() {
  visible.value = false
  uploadedFile.value = null
  pasteContent.value = ''
  parseResult.value = null
  tagFilter.value = null
  selectAll.value = true
  byTag.value = true
  selectedEndpoints.value = []
}

watch(tagFilter, () => {
  // 标签筛选变化时重置全选
  selectAll.value = true
  selectedEndpoints.value = [...filteredEndpoints.value]
})
</script>

<style scoped>
.import-openapi-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-area {
  width: 100%;
}

.upload-icon {
  font-size: 48px;
  color: var(--el-color-primary);
}

.upload-text p {
  margin: 4px 0;
}

.upload-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  margin-top: 8px;
}

.file-size {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.project-select {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-select .label,
.import-config .label {
  font-weight: 500;
  white-space: nowrap;
}

.parse-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.table-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.import-config {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-preview {
  max-height: 400px;
  overflow-y: auto;
}

.tag-group {
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
}

.tag-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--el-fill-color-light);
  font-weight: 500;
  font-size: 13px;
}

.tag-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.endpoint-info { display: flex; flex-wrap: wrap; gap: 4px; }
.info-tag {
  font-size: 11px; padding: 1px 6px; border-radius: 3px;
  background: var(--el-fill-color-light); color: var(--el-text-color-secondary);
}
.body-tag { background: #ecf5ff; color: #409eff; }
.auth-tag { background: #fef0f0; color: #f56c6c; }
</style>