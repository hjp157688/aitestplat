<template>
  <div class="weknora-config page-container">
    <PageHeader :title="$t('configuration.weknora.title')" :desc="$t('configuration.weknora.desc')" />

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <template v-else>
      <!-- 连接配置 -->
      <div class="card-container section-card">
        <div class="section-header">
          <div class="section-title">
            <el-icon><Connection /></el-icon>
            <span>{{ $t('configuration.weknora.connectionSection') }}</span>
          </div>
          <span class="status-tag" :class="cfg.enabled ? 'active' : 'inactive'">
            <span class="status-tag__dot"></span>
            {{ cfg.enabled ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}
          </span>
        </div>

        <el-form :model="cfg" label-width="150px" label-position="right">
          <el-form-item :label="$t('configuration.weknora.baseUrl')">
            <el-input v-model="cfg.base_url" placeholder="http://localhost:8080" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="cfg.api_key"
              type="password"
              show-password
              :placeholder="$t('configuration.weknora.apiKeyPlaceholder')"
            />
          </el-form-item>
          <el-form-item :label="$t('configuration.weknora.timeout')">
            <el-input-number v-model="cfg.timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item :label="$t('configuration.common.isActive')">
            <el-switch v-model="cfg.enabled" />
          </el-form-item>
          <el-form-item>
            <div class="form-actions">
              <el-button type="primary" @click="saveConnection" :loading="saving">
                {{ $t('configuration.weknora.saveConfig') }}
              </el-button>
              <el-button @click="testConnection" :loading="testing">
                {{ $t('configuration.weknora.testConnection') }}
              </el-button>
              <el-button @click="loadAgents" :loading="loadingAgents" :disabled="!cfg.base_url || !cfg.api_key">
                {{ $t('configuration.weknora.loadAgents') }}
              </el-button>
            </div>
          </el-form-item>
        </el-form>

        <div v-if="agents.length > 0" class="agents-block">
          <div class="agents-title">{{ $t('configuration.weknora.agentsTitle', { count: agents.length }) }}</div>
          <div v-for="a in agents" :key="a.id" class="agent-chip">
            <span>{{ a.name }}</span>
            <code>{{ a.id }}</code>
            <el-tag v-if="a.is_builtin" size="small" type="info">{{ $t('configuration.weknora.builtin') }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 项目绑定 -->
      <div class="card-container">
        <div class="section-header">
          <div class="section-title">
            <el-icon><Coin /></el-icon>
            <span>{{ $t('configuration.weknora.bindingSection') }}</span>
          </div>
          <el-button type="primary" size="small" @click="openBindingDialog(null)">
            <el-icon><Plus /></el-icon>
            {{ $t('configuration.weknora.addBinding') }}
          </el-button>
        </div>

        <el-table :data="bindings" v-loading="bindingsLoading" :empty-text="$t('configuration.weknora.noBindings')">
          <el-table-column :label="$t('configuration.weknora.colProject')" prop="project_name" min-width="140" />
          <el-table-column :label="$t('configuration.weknora.colAgent')" min-width="160">
            <template #default="{ row }">
              {{ row.agent_name || row.agent_id }}
              <code v-if="row.agent_id" class="agent-id">{{ row.agent_id }}</code>
            </template>
          </el-table-column>
          <el-table-column :label="$t('configuration.weknora.colKb')" prop="knowledge_base_ids" min-width="160">
            <template #default="{ row }">
              <span v-if="row.knowledge_base_ids && row.knowledge_base_ids.length">
                {{ row.knowledge_base_ids.join(', ') }}
              </span>
              <span v-else class="muted">{{ $t('configuration.weknora.kbDefault') }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('configuration.weknora.colStatus')" width="100">
            <template #default="{ row }">
              <span class="status-tag" :class="row.enabled ? 'active' : 'inactive'">
                <span class="status-tag__dot"></span>
                {{ row.enabled ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('configuration.weknora.colActions')" width="140">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="openBindingDialog(row)">{{ $t('configuration.common.edit') }}</el-button>
              <el-button size="small" type="danger" link @click="deleteBinding(row)">{{ $t('configuration.common.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 绑定弹窗 -->
    <el-dialog
      v-model="bindingDialogVisible"
      :title="editingBinding ? $t('configuration.weknora.bindingEditTitle') : $t('configuration.weknora.bindingAddTitle')"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form :model="bindingForm" label-width="120px" label-position="right">
        <el-form-item :label="$t('configuration.weknora.colProject')" required>
          <el-select v-model="bindingForm.project" filterable :placeholder="$t('configuration.weknora.selectProject')" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('configuration.weknora.agentLabel')" required>
          <el-select v-model="bindingForm.agent_id" filterable :placeholder="$t('configuration.weknora.selectAgent')" style="width: 100%">
            <el-option
              v-for="a in agents"
              :key="a.id"
              :label="`${a.name} (${a.id})`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('configuration.weknora.colKb')">
          <el-input
            v-model="bindingForm.knowledge_base_ids_input"
            :placeholder="$t('configuration.weknora.kbPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="$t('configuration.common.isActive')">
          <el-switch v-model="bindingForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="bindingDialogVisible = false">{{ $t('configuration.common.cancel') }}</el-button>
          <el-button type="primary" @click="saveBinding" :loading="savingBinding">{{ $t('configuration.common.save') }}</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Coin, Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'
import {
  getWeKnoraConfig,
  updateWeKnoraConfig,
  testWeKnoraConnection,
  listWeKnoraAgents,
  listWeKnoraBindings,
  saveWeKnoraBinding,
  deleteWeKnoraBinding
} from '@/api/requirement'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const loadingAgents = ref(false)

const cfg = reactive({
  id: null,
  base_url: 'http://localhost:8080',
  api_key: '',
  timeout: 30,
  enabled: false
})

const agents = ref([])
const projects = ref([])
const bindings = ref([])
const bindingsLoading = ref(false)

const bindingDialogVisible = ref(false)
const editingBinding = ref(null)
const savingBinding = ref(false)
const bindingForm = reactive({
  project: null,
  agent_id: '',
  knowledge_base_ids_input: '',
  enabled: true
})

async function loadAll() {
  loading.value = true
  try {
    const res = await getWeKnoraConfig()
    const d = res.data || {}
    Object.assign(cfg, d)
    if (!d.api_key && d.api_key !== undefined) cfg.api_key = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.error || t('configuration.weknora.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  const res = await api.get('/projects/')
  projects.value = res.data?.results || res.data || []
}

async function loadBindings() {
  bindingsLoading.value = true
  try {
    const res = await listWeKnoraBindings()
    bindings.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.error || t('configuration.weknora.loadBindingsFailed'))
  } finally {
    bindingsLoading.value = false
  }
}

async function loadAgents() {
  loadingAgents.value = true
  try {
    const res = await listWeKnoraAgents()
    if (res.data?.success) {
      agents.value = res.data.agents || []
      ElMessage.success(t('configuration.weknora.agentsLoaded', { count: agents.value.length }))
      if (agents.value.length === 0) ElMessage.warning(t('configuration.weknora.agentsEmpty'))
    } else {
      ElMessage.error(res.data?.error || res.data?.message || t('configuration.weknora.agentsFailed'))
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.response?.data?.message || t('configuration.weknora.agentsFailed'))
  } finally {
    loadingAgents.value = false
  }
}

async function saveConnection() {
  if (!cfg.base_url) {
    ElMessage.warning(t('configuration.weknora.urlRequired'))
    return
  }
  saving.value = true
  try {
    await updateWeKnoraConfig({
      base_url: cfg.base_url,
      api_key: cfg.api_key,
      timeout: cfg.timeout,
      enabled: cfg.enabled
    })
    ElMessage.success(t('configuration.weknora.saveSuccess'))
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || t('configuration.weknora.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  if (!cfg.base_url) {
    ElMessage.warning(t('configuration.weknora.urlRequired'))
    return
  }
  testing.value = true
  try {
    const res = await testWeKnoraConnection({
      base_url: cfg.base_url,
      api_key: cfg.api_key,
      timeout: cfg.timeout,
      check_agents: true
    })
    if (res.data?.success) {
      ElMessage.success(t('configuration.weknora.testSuccess'))
      if (res.data.agents?.length) {
        agents.value = res.data.agents
        ElMessage.info(t('configuration.weknora.agentsInfo', { count: res.data.agents.length }))
      }
    } else {
      ElMessage.error(res.data?.error || res.data?.message || t('configuration.weknora.testFailed'))
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.response?.data?.message || t('configuration.weknora.testError'))
  } finally {
    testing.value = false
  }
}

function openBindingDialog(binding) {
  editingBinding.value = binding
  if (binding) {
    bindingForm.project = binding.project
    bindingForm.agent_id = binding.agent_id
    bindingForm.knowledge_base_ids_input = (binding.knowledge_base_ids || []).join(', ')
    bindingForm.enabled = !!binding.enabled
  } else {
    bindingForm.project = null
    bindingForm.agent_id = ''
    bindingForm.knowledge_base_ids_input = ''
    bindingForm.enabled = true
  }
  if (agents.value.length === 0) {
    loadAgents()
  }
  bindingDialogVisible.value = true
}

async function saveBinding() {
  if (!bindingForm.project) {
    ElMessage.warning(t('configuration.weknora.projectRequired'))
    return
  }
  if (!bindingForm.agent_id) {
    ElMessage.warning(t('configuration.weknora.agentRequired'))
    return
  }
  const bindingData = {
    project: bindingForm.project,
    agent_id: bindingForm.agent_id,
    enabled: bindingForm.enabled
  }
  const kbInput = bindingForm.knowledge_base_ids_input.trim()
  if (kbInput) {
    bindingData.knowledge_base_ids = kbInput.split(',').map((s) => s.trim()).filter(Boolean)
  }
  savingBinding.value = true
  try {
    await saveWeKnoraBinding(bindingData)
    ElMessage.success(editingBinding.value ? t('configuration.weknora.bindingUpdated') : t('configuration.weknora.bindingCreated'))
    bindingDialogVisible.value = false
    await loadBindings()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || t('configuration.weknora.saveFailed'))
  } finally {
    savingBinding.value = false
  }
}

async function deleteBinding(binding) {
  try {
    await ElMessageBox.confirm(
      t('configuration.weknora.deleteConfirm', { name: binding.project_name }),
      t('configuration.weknora.deleteConfirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('configuration.common.delete'),
        cancelButtonText: t('configuration.common.cancel')
      }
    )
    await deleteWeKnoraBinding(binding.id)
    ElMessage.success(t('configuration.weknora.deleted'))
    await loadBindings()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || t('configuration.weknora.deleteFailed'))
    }
  }
}

onMounted(async () => {
  await loadAll()
  await loadProjects()
  await loadBindings()
})
</script>

<style scoped>
/* 页面骨架：page-container + PageHeader + card-container 分区；留白由全局 .page-container 提供，根容器不私写 max-width */
.loading-container {
  padding: var(--aitest-space-10);
}

.section-card {
  margin-bottom: var(--aitest-space-4);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--aitest-space-4);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  font-weight: 600;
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-1);
}

.form-actions {
  display: flex;
  gap: var(--aitest-space-3);
}

.agents-block {
  margin-top: var(--aitest-space-4);
  padding-top: var(--aitest-space-4);
  border-top: 1px solid var(--aitest-border);
}

.agents-title {
  font-weight: 600;
  margin-bottom: var(--aitest-space-2);
  font-size: var(--aitest-font-size-base);
  color: var(--aitest-text-2);
}

.agent-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--aitest-space-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-1) var(--aitest-space-3);
  margin: 0 var(--aitest-space-2) var(--aitest-space-2) 0;
}

.agent-chip code,
.agent-id {
  color: var(--aitest-text-3);
  font-size: var(--aitest-font-size-sm);
}

.muted {
  color: var(--aitest-text-3);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--aitest-space-3);
}
</style>
