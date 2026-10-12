<template>
  <div class="weknora-config page-container">
    <PageHeader title="WeKnora 知识库配置" />

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else class="card-container">
      <!-- 连接配置 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div class="section-header">
            <el-icon><Connection /></el-icon>
            <span>WeKnora 连接配置</span>
            <el-tag :type="cfg.enabled ? 'success' : 'info'" size="small">
              {{ cfg.enabled ? '已启用' : '未启用' }}
            </el-tag>
          </div>
        </template>

        <el-form :model="cfg" label-width="150px" label-position="right">
          <el-form-item label="服务地址">
            <el-input v-model="cfg.base_url" placeholder="http://localhost:8080" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="cfg.api_key"
              type="password"
              show-password
              placeholder="WeKnora 账户 API Key"
            />
          </el-form-item>
          <el-form-item label="超时(秒)">
            <el-input-number v-model="cfg.timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item label="是否启用">
            <el-switch v-model="cfg.enabled" />
          </el-form-item>
          <el-form-item>
            <div class="form-actions">
              <el-button type="primary" @click="saveConnection" :loading="saving">
                保存配置
              </el-button>
              <el-button @click="testConnection" :loading="testing">
                测试连接
              </el-button>
              <el-button @click="loadAgents" :loading="loadingAgents" :disabled="!cfg.base_url || !cfg.api_key">
                获取智能体列表
              </el-button>
            </div>
          </el-form-item>
        </el-form>

        <div v-if="agents.length > 0" class="agents-block">
          <div class="agents-title">可用智能体（{{ agents.length }}）：</div>
          <div v-for="a in agents" :key="a.id" class="agent-chip">
            <span>{{ a.name }}</span>
            <code>{{ a.id }}</code>
            <el-tag v-if="a.is_builtin" size="small" type="info">内置</el-tag>
          </div>
        </div>
      </el-card>

      <!-- 项目绑定 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div class="section-header">
            <el-icon><Coin /></el-icon>
            <span>项目 ⇄ 智能体绑定</span>
            <el-button type="primary" size="small" @click="openBindingDialog(null)">
              <el-icon><Plus /></el-icon>
              新增绑定
            </el-button>
          </div>
        </template>

        <el-table :data="bindings" v-loading="bindingsLoading" empty-text="暂无项目绑定">
          <el-table-column label="项目" prop="project_name" min-width="140" />
          <el-table-column label="智能体" min-width="160">
            <template #default="{ row }">
              {{ row.agent_name || row.agent_id }}
              <code v-if="row.agent_id" class="agent-id">{{ row.agent_id }}</code>
            </template>
          </el-table-column>
          <el-table-column label="知识库ID" prop="knowledge_base_ids" min-width="160">
            <template #default="{ row }">
              <span v-if="row.knowledge_base_ids && row.knowledge_base_ids.length">
                {{ row.knowledge_base_ids.join(', ') }}
              </span>
              <span v-else class="muted">默认</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                {{ row.enabled ? '已启用' : '已停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="openBindingDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" link @click="deleteBinding(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 绑定弹窗 -->
    <el-dialog
      v-model="bindingDialogVisible"
      :title="editingBinding ? '编辑项目绑定' : '新增项目绑定'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form :model="bindingForm" label-width="120px" label-position="right">
        <el-form-item label="项目" required>
          <el-select v-model="bindingForm.project" filterable placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="WeKnora 智能体" required>
          <el-select v-model="bindingForm.agent_id" filterable placeholder="选择智能体" style="width: 100%">
            <el-option
              v-for="a in agents"
              :key="a.id"
              :label="`${a.name} (${a.id})`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="知识库ID">
          <el-input
            v-model="bindingForm.knowledge_base_ids_input"
            placeholder="可留空(使用智能体默认知识库)；多个用逗号分隔"
          />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="bindingForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="bindingDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveBinding" :loading="savingBinding">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
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
    ElMessage.error(e.response?.data?.error || '加载配置失败')
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
    ElMessage.error(e.response?.data?.error || '加载绑定失败')
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
      ElMessage.success(`已获取 ${agents.value.length} 个智能体`)
      if (agents.value.length === 0) ElMessage.warning('未获取到智能体')
    } else {
      ElMessage.error(res.data?.error || res.data?.message || '获取智能体失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.response?.data?.message || '获取智能体失败')
  } finally {
    loadingAgents.value = false
  }
}

async function saveConnection() {
  if (!cfg.base_url) {
    ElMessage.warning('请填写服务地址')
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
    ElMessage.success('配置已保存')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  if (!cfg.base_url) {
    ElMessage.warning('请先填写服务地址')
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
      ElMessage.success('连接成功')
      if (res.data.agents?.length) {
        agents.value = res.data.agents
        ElMessage.info(`共 ${res.data.agents.length} 个智能体`)
      }
    } else {
      ElMessage.error(res.data?.error || res.data?.message || '连接失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.response?.data?.message || '连接测试失败')
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
    ElMessage.warning('请选择项目')
    return
  }
  if (!bindingForm.agent_id) {
    ElMessage.warning('请选择智能体')
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
    ElMessage.success(editingBinding.value ? '绑定已更新' : '绑定已创建')
    bindingDialogVisible.value = false
    await loadBindings()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    savingBinding.value = false
  }
}

async function deleteBinding(binding) {
  try {
    await ElMessageBox.confirm(`确定删除项目「${binding.project_name}」的绑定吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteWeKnoraBinding(binding.id)
    ElMessage.success('已删除')
    await loadBindings()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
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
/* 非表格配置页：主体包进 card-container，普通滚动；页面留白由全局 .page-container 提供 */
.weknora-config {
  max-width: 1100px;
  margin: 0 auto;
}
.loading-container {
  padding: var(--aitest-space-10);
}
.section-card {
  margin-bottom: var(--aitest-space-5);
}
.section-card:last-child {
  margin-bottom: 0;
}
.section-header {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  font-weight: 600;
}
.form-actions {
  display: flex;
  gap: var(--aitest-space-3);
}
.agents-block {
  margin-top: var(--aitest-space-4);
}
.agents-title {
  font-weight: 600;
  margin-bottom: var(--aitest-space-2);
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
