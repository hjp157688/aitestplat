<template>
  <div class="page-container automation-environments">
    <PageHeader :title="t('automation.envsTitle')" :desc="t('automation.envsDesc')">
      <template #actions>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>{{ t('automation.createEnv') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="card-container">
      <div class="filter-bar">
        <el-select v-model="selectedProject" style="width: 240px"
          :placeholder="t('automation.project')" @change="loadEnvironments">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
      <div class="table-container">
        <el-table :data="environments" v-loading="loading">
          <el-table-column prop="name" :label="t('automation.envName')" min-width="160" />
          <el-table-column prop="base_url" :label="t('automation.baseUrl')" min-width="200" show-overflow-tooltip />
          <el-table-column prop="cdp_url" :label="t('automation.cdpUrl')" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.cdp_url || '-' }}</template>
          </el-table-column>
          <el-table-column prop="login_url" :label="t('automation.loginUrl')" min-width="200" show-overflow-tooltip />
          <el-table-column prop="username" :label="t('automation.username')" width="140" />
          <el-table-column :label="t('automation.password')" width="110">
            <template #default="{ row }">{{ row.has_password ? '••••••' : '-' }}</template>
          </el-table-column>
          <el-table-column :label="t('automation.variables')" width="90">
            <template #default="{ row }">{{ (row.variables || []).length }}</template>
          </el-table-column>
          <el-table-column :label="t('automation.active')" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.is_active" @change="toggleActive(row, $event)" />
            </template>
          </el-table-column>
          <el-table-column :label="t('automation.records')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">{{ t('automation.edit') }}</el-button>
              <el-button link type="danger" @click="removeEnv(row)">{{ t('automation.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <el-dialog v-model="showDialog" :title="editingId ? t('automation.envName') : t('automation.createEnv')" width="720px">
      <el-form :model="form" label-width="110px">
        <el-form-item :label="t('automation.envName')" required>
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item :label="t('automation.baseUrl')">
          <el-input v-model="form.base_url" placeholder="https://demo.example.com" />
        </el-form-item>
        <el-form-item :label="t('automation.cdpUrl')">
          <el-input v-model="form.cdp_url" :placeholder="t('automation.cdpUrlPlaceholder')" clearable />
        </el-form-item>
        <el-form-item :label="t('automation.loginUrl')">
          <el-input v-model="form.login_url" :placeholder="t('automation.notRequired')" />
        </el-form-item>
        <el-form-item :label="t('automation.username')">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item :label="t('automation.password')">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="form.has_password ? t('automation.passwordKeep') : ''" />
        </el-form-item>
        <el-form-item :label="t('automation.variables')">
          <div class="var-editor">
            <div v-for="(v, idx) in form.variables" :key="idx" class="var-row">
              <el-input v-model="v.key" :placeholder="t('automation.varKey')" style="width: 180px" />
              <el-input v-model="v.value" :placeholder="t('automation.varValue')" style="flex: 1" />
              <el-input v-model="v.description" :placeholder="t('automation.varDesc')" style="width: 160px" />
              <el-button link type="danger" @click="form.variables.splice(idx, 1)">{{ t('automation.delete') }}</el-button>
            </div>
            <el-button link type="primary" @click="form.variables.push({ key: '', value: '', description: '' })">
              {{ t('automation.addVar') }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item :label="t('automation.active')">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item :label="t('automation.enableScreenshot')">
          <div class="screenshot-switch">
            <el-switch v-model="form.enable_screenshot" />
            <span class="screenshot-hint">{{ t('automation.enableScreenshotHint') }}</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">{{ t('automation.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('automation.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import api from '@/utils/api'
import {
  getAutomationEnvironments,
  createAutomationEnvironment,
  updateAutomationEnvironment,
  deleteAutomationEnvironment,
} from '@/api/requirement-analysis'

const { t } = useI18n()
const projects = ref([])
const selectedProject = ref(null)
const environments = ref([])
const loading = ref(false)
const showDialog = ref(false)
const saving = ref(false)
const editingId = ref(null)
const emptyForm = () => ({
  name: '', base_url: '', cdp_url: '', login_url: '', username: '', password: '',
  variables: [], is_active: true, enable_screenshot: true,
})
const form = ref(emptyForm())

const loadProjects = async () => {
  const { data } = await api.get('/projects/')
  projects.value = data.results || data
  if (projects.value.length && !selectedProject.value) {
    selectedProject.value = projects.value[0].id
    await loadEnvironments()
  }
}

const loadEnvironments = async () => {
  if (!selectedProject.value) return
  loading.value = true
  try {
    const { data } = await getAutomationEnvironments({ project: selectedProject.value })
    environments.value = data.results || data
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.value = emptyForm()
  showDialog.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.value = {
    ...row,
    password: '',
    variables: (row.variables || []).map(v => ({ ...v })),
    enable_screenshot: row.enable_screenshot !== false,
  }
  showDialog.value = true
}

const save = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning(t('automation.envName'))
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value, project: selectedProject.value }
    if (!payload.password) delete payload.password  // 留空不改密码
    if (editingId.value) {
      await updateAutomationEnvironment(editingId.value, payload)
    } else {
      await createAutomationEnvironment(payload)
    }
    ElMessage.success(t('automation.save') + ' ✓')
    showDialog.value = false
    await loadEnvironments()
  } finally {
    saving.value = false
  }
}

const toggleActive = async (row, value) => {
  await updateAutomationEnvironment(row.id, { is_active: value })
  row.is_active = value
}

const removeEnv = async (row) => {
  await ElMessageBox.confirm(t('automation.deleteEnvConfirm'), { type: 'warning' })
  await deleteAutomationEnvironment(row.id)
  ElMessage.success(t('automation.saveSuccess'))
  await loadEnvironments()
}

onMounted(loadProjects)
</script>

<style scoped>
.var-editor { width: 100%; }
.var-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
.screenshot-switch { display: flex; align-items: center; gap: 10px; }
.screenshot-hint { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
