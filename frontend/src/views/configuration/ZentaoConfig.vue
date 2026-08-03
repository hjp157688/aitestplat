<template>
  <div class="zentao-config">
    <div class="page-header">
      <h1>禅道配置</h1>
      <p>配置禅道系统连接信息，用于同步需求数据</p>
    </div>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else class="configs-grid">
      <div
        v-for="config in configs"
        :key="config.id"
        class="config-card"
        :class="{ active: config.is_active }"
      >
        <div class="card-header">
          <div class="card-title">
            <el-icon><Connection /></el-icon>
            <span>{{ config.name }}</span>
            <el-tag :type="config.is_active ? 'success' : 'info'" size="small">
              {{ config.is_active ? '已启用' : '已禁用' }}
            </el-tag>
          </div>
          <div class="card-actions">
            <el-switch
              :model-value="config.is_active"
              @change="(val) => handleToggleEnable(config, val)"
              :loading="config._toggling"
            />
            <el-button
              size="small"
              type="primary"
              link
              @click="handleTestConnection(config)"
              :loading="config._testing"
            >
              测试连接
            </el-button>
            <el-button
              size="small"
              type="primary"
              link
              @click="openEditDialog(config)"
            >
              编辑
            </el-button>
            <el-button
              size="small"
              type="danger"
              link
              @click="handleDelete(config)"
            >
              删除
            </el-button>
          </div>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">禅道地址：</span>
            <span class="info-value">{{ config.zentao_url }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">登录账号：</span>
            <span class="info-value">{{ config.zentao_account }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">密码：</span>
            <span class="info-value">{{ config.password_masked || '******' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">创建时间：</span>
            <span class="info-value">{{ formatDateTime(config.created_at) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">更新时间：</span>
            <span class="info-value">{{ formatDateTime(config.updated_at) }}</span>
          </div>
        </div>
      </div>

      <div v-if="configs.length === 0" class="empty-state">
        <el-icon :size="48"><Connection /></el-icon>
        <p>暂无禅道配置</p>
        <p class="empty-hint">请添加禅道配置以启用需求同步功能</p>
        <el-button type="primary" @click="openEditDialog(null)">
          添加第一个配置
        </el-button>
      </div>
    </div>

    <div class="add-btn-wrapper" v-if="configs.length > 0">
      <el-button type="primary" @click="openEditDialog(null)">
        <el-icon><Plus /></el-icon>
        添加配置
      </el-button>
    </div>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑禅道配置' : '添加禅道配置'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：默认配置" />
        </el-form-item>
        <el-form-item label="禅道地址" prop="zentao_url">
          <el-input
            v-model="form.zentao_url"
            placeholder="https://zentao.example.com"
          />
        </el-form-item>
        <el-form-item label="登录账号" prop="zentao_account">
          <el-input
            v-model="form.zentao_account"
            placeholder="请输入禅道登录账号"
          />
        </el-form-item>
        <el-form-item label="登录密码" prop="zentao_password">
          <el-input
            v-model="form.zentao_password"
            type="password"
            show-password
            :placeholder="isEditing ? '不修改请保持原值不变' : '请输入禅道登录密码'"
          />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button
            v-if="!isEditing"
            type="warning"
            plain
            @click="handleTestConnectionPreview"
            :loading="testingPreview"
            style="margin-right: auto;"
          >
            测试连接
          </el-button>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">
            保存配置
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Plus } from '@element-plus/icons-vue'
import {
  getZentaoConfigs,
  createZentaoConfig,
  updateZentaoConfig,
  deleteZentaoConfig,
  testZentaoConnection,
  enableZentaoConfig,
  disableZentaoConfig
} from '@/api/requirement'

const configs = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const saving = ref(false)
const testingPreview = ref(false)

const form = reactive({
  name: '默认配置',
  zentao_url: '',
  zentao_account: '',
  zentao_password: '',
  is_active: true
})

const formRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  zentao_url: [{ required: true, message: '请输入禅道地址', trigger: 'blur' }],
  zentao_account: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  zentao_password: [
    {
      validator: (_rule, value, callback) => {
        if (!isEditing.value && !value) {
          callback(new Error('请输入登录密码'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadConfigs() {
  loading.value = true
  try {
    const res = await getZentaoConfigs()
    configs.value = (res.data?.results || res.data || []).map(c => ({
      ...c,
      _toggling: false,
      _testing: false
    }))
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加载配置失败')
  } finally {
    loading.value = false
  }
}

function openEditDialog(config) {
  if (config) {
    isEditing.value = true
    editingId.value = config.id
    form.name = config.name
    form.zentao_url = config.zentao_url
    form.zentao_account = config.zentao_account
    form.zentao_password = ''
    form.is_active = config.is_active
  } else {
    isEditing.value = false
    editingId.value = null
    form.name = '默认配置'
    form.zentao_url = ''
    form.zentao_account = ''
    form.zentao_password = ''
    form.is_active = true
  }
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const data = {
      name: form.name,
      zentao_url: form.zentao_url,
      zentao_account: form.zentao_account,
      is_active: form.is_active
    }
    if (form.zentao_password) {
      data.zentao_password = form.zentao_password
    }
    if (isEditing.value) {
      await updateZentaoConfig(editingId.value, data)
      ElMessage.success('配置更新成功')
    } else {
      await createZentaoConfig(data)
      ElMessage.success('配置添加成功')
    }
    dialogVisible.value = false
    loadConfigs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(config) {
  try {
    await ElMessageBox.confirm('确定要删除此配置吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteZentaoConfig(config.id)
    ElMessage.success('配置删除成功')
    loadConfigs()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '删除失败')
    }
  }
}

async function handleToggleEnable(config, val) {
  config._toggling = true
  try {
    if (val) {
      await enableZentaoConfig(config.id)
    } else {
      await disableZentaoConfig(config.id)
    }
    ElMessage.success(`配置已${val ? '启用' : '禁用'}`)
    loadConfigs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    config._toggling = false
  }
}

async function handleTestConnection(config) {
  config._testing = true
  try {
    const res = await testZentaoConnection(config.id)
    if (res.data?.success) {
      ElMessage.success(`连接成功！Token: ${res.data.token}`)
    } else {
      ElMessage.error(res.data?.message || '连接失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '连接测试失败')
  } finally {
    config._testing = false
  }
}

async function handleTestConnectionPreview() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  testingPreview.value = true
  try {
    const data = {
      name: form.name,
      zentao_url: form.zentao_url,
      zentao_account: form.zentao_account,
      zentao_password: form.zentao_password,
      is_active: true
    }
    const createRes = await createZentaoConfig(data)
    const newId = createRes.data?.id
    if (newId) {
      const testRes = await testZentaoConnection(newId)
      if (testRes.data?.success) {
        ElMessage.success(`连接成功！Token: ${testRes.data.token}`)
      } else {
        ElMessage.error(testRes.data?.message || '连接失败')
      }
      await deleteZentaoConfig(newId)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '连接测试失败')
  } finally {
    testingPreview.value = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.zentao-config {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 1.5rem;
  color: #1a202c;
  margin: 0 0 8px 0;
}

.page-header p {
  color: #64748b;
  margin: 0;
}

.loading-container {
  padding: 40px;
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.config-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
}

.config-card.active {
  border-color: #22c55e;
  box-shadow: 0 2px 12px rgba(34, 197, 94, 0.15);
}

.config-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 1rem;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-row {
  display: flex;
  font-size: 0.9rem;
}

.info-label {
  color: #94a3b8;
  min-width: 80px;
  flex-shrink: 0;
}

.info-value {
  color: #334155;
  word-break: break-all;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
  grid-column: 1 / -1;
}

.empty-state p {
  margin: 12px 0;
}

.empty-hint {
  font-size: 0.9rem;
  margin-bottom: 20px;
}

.add-btn-wrapper {
  margin-top: 20px;
  text-align: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>