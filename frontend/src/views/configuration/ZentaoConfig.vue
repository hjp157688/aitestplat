<template>
  <div class="zentao-config page-container">
    <PageHeader :title="$t('configuration.zentao.title')" :desc="$t('configuration.zentao.desc')">
      <template #actions>
        <el-button type="primary" @click="openEditDialog(null)">
          <el-icon><Plus /></el-icon>
          {{ $t('configuration.zentao.addConfig') }}
        </el-button>
      </template>
    </PageHeader>

    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="configs.length === 0" class="card-container">
      <div class="empty-state">
        <div class="empty-icon"><el-icon><Connection /></el-icon></div>
        <div class="empty-title">{{ $t('configuration.zentao.emptyTitle') }}</div>
        <div class="empty-hint">{{ $t('configuration.zentao.emptyHint') }}</div>
        <div class="empty-state__actions">
          <el-button type="primary" @click="openEditDialog(null)">
            {{ $t('configuration.zentao.addFirstConfig') }}
          </el-button>
        </div>
      </div>
    </div>

    <div v-else class="configs-grid">
      <div
        v-for="config in configs"
        :key="config.id"
        class="config-card"
      >
        <div class="card-header">
          <div class="card-title">
            <el-icon><Connection /></el-icon>
            <span>{{ config.name }}</span>
          </div>
          <span class="status-tag" :class="config.is_active ? 'active' : 'inactive'">
            <span class="status-tag__dot"></span>
            {{ config.is_active ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}
          </span>
        </div>
        <div class="card-actions">
          <el-switch
            :model-value="config.is_active"
            @change="(val) => handleToggleEnable(config, val)"
            :loading="config._toggling"
          />
          <el-button size="small" type="primary" link @click="handleTestConnection(config)" :loading="config._testing">
            {{ $t('configuration.zentao.testConnection') }}
          </el-button>
          <el-button size="small" type="primary" link @click="openEditDialog(config)">
            {{ $t('configuration.common.edit') }}
          </el-button>
          <el-button size="small" type="danger" link @click="handleDelete(config)">
            {{ $t('configuration.common.delete') }}
          </el-button>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">{{ $t('configuration.zentao.fieldUrl') }}</span>
            <span class="info-value">{{ config.zentao_url }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('configuration.zentao.fieldAccount') }}</span>
            <span class="info-value">{{ config.zentao_account }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('configuration.zentao.fieldPassword') }}</span>
            <span class="info-value">{{ config.password_masked || '******' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('configuration.common.createdAt') }}</span>
            <span class="info-value">{{ formatDateTime(config.created_at) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">{{ $t('configuration.common.updatedAt') }}</span>
            <span class="info-value">{{ formatDateTime(config.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? $t('configuration.zentao.dialogEditTitle') : $t('configuration.zentao.dialogAddTitle')"
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
        <el-form-item :label="$t('configuration.zentao.fieldName')" prop="name">
          <el-input v-model="form.name" :placeholder="$t('configuration.zentao.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('configuration.zentao.fieldUrl')" prop="zentao_url">
          <el-input v-model="form.zentao_url" placeholder="https://zentao.example.com" />
        </el-form-item>
        <el-form-item :label="$t('configuration.zentao.fieldAccount')" prop="zentao_account">
          <el-input v-model="form.zentao_account" :placeholder="$t('configuration.zentao.accountPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('configuration.zentao.fieldPassword')" prop="zentao_password">
          <el-input
            v-model="form.zentao_password"
            type="password"
            show-password
            :placeholder="isEditing ? $t('configuration.zentao.passwordKeepPlaceholder') : $t('configuration.zentao.passwordPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="$t('configuration.common.isActive')">
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
            {{ $t('configuration.zentao.testConnection') }}
          </el-button>
          <el-button @click="dialogVisible = false">{{ $t('configuration.common.cancel') }}</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">
            {{ $t('configuration.common.save') }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

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
  name: [{ required: true, message: () => t('configuration.zentao.ruleName'), trigger: 'blur' }],
  zentao_url: [{ required: true, message: () => t('configuration.zentao.ruleUrl'), trigger: 'blur' }],
  zentao_account: [{ required: true, message: () => t('configuration.zentao.ruleAccount'), trigger: 'blur' }],
  zentao_password: [
    {
      validator: (_rule, value, callback) => {
        if (!isEditing.value && !value) {
          callback(new Error(t('configuration.zentao.rulePassword')))
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
    ElMessage.error(e.response?.data?.error || t('configuration.zentao.loadFailed'))
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
      ElMessage.success(t('configuration.zentao.updateSuccess'))
    } else {
      await createZentaoConfig(data)
      ElMessage.success(t('configuration.zentao.addSuccess'))
    }
    dialogVisible.value = false
    loadConfigs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.error || t('configuration.zentao.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(config) {
  try {
    await ElMessageBox.confirm(t('configuration.zentao.deleteConfirm'), t('configuration.zentao.deleteConfirmTitle'), {
      type: 'warning',
      confirmButtonText: t('configuration.common.delete'),
      cancelButtonText: t('configuration.common.cancel')
    })
    await deleteZentaoConfig(config.id)
    ElMessage.success(t('configuration.zentao.deleteSuccess'))
    loadConfigs()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || t('configuration.zentao.deleteFailed'))
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
    ElMessage.success(t('configuration.zentao.toggleSuccess', { state: val ? t('configuration.zentao.stateEnabled') : t('configuration.zentao.stateDisabled') }))
    loadConfigs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('configuration.zentao.operateFailed'))
  } finally {
    config._toggling = false
  }
}

async function handleTestConnection(config) {
  config._testing = true
  try {
    const res = await testZentaoConnection(config.id)
    if (res.data?.success) {
      ElMessage.success(t('configuration.zentao.testSuccess', { token: res.data.token }))
    } else {
      ElMessage.error(res.data?.message || t('configuration.zentao.testFailed'))
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || t('configuration.zentao.testError'))
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
        ElMessage.success(t('configuration.zentao.testSuccess', { token: testRes.data.token }))
      } else {
        ElMessage.error(testRes.data?.message || t('configuration.zentao.testFailed'))
      }
      await deleteZentaoConfig(newId)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || t('configuration.zentao.testError'))
  } finally {
    testingPreview.value = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
/* 页面骨架：page-container + PageHeader + 卡片网格；留白由全局 .page-container 提供，根容器不私写 max-width */

.loading-container {
  padding: var(--aitest-space-10);
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: var(--aitest-space-4);
}

.config-card {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-card-border);
  border-radius: var(--aitest-card-radius);
  padding: var(--aitest-card-padding);
  box-shadow: var(--aitest-card-shadow);
  transition: box-shadow 0.2s;
}

.config-card:hover {
  box-shadow: var(--aitest-shadow-md);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-3);
  padding-bottom: var(--aitest-space-3);
  border-bottom: 1px solid var(--aitest-border);
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  font-weight: 600;
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-1);
  min-width: 0;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-1);
  margin-bottom: var(--aitest-space-3);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-2);
}

.info-row {
  display: flex;
  font-size: var(--aitest-font-size-base);
  line-height: var(--aitest-line-height-normal);
}

.info-label {
  color: var(--aitest-text-3);
  width: 88px;
  flex-shrink: 0;
}

.info-value {
  color: var(--aitest-text-2);
  word-break: break-all;
  min-width: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--aitest-space-3);
}
</style>
