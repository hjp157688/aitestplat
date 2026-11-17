<template>
  <div class="page-container generation-config">
    <PageHeader :title="$t('generationConfig.title')" />

    <div class="main-content">
      <!-- 配置列表 -->
      <div class="configs-section">
        <div class="section-header">
          <h2>{{ $t('generationConfig.configList') }}</h2>
          <el-button type="primary" @click="openAddModal">
            {{ $t('generationConfig.addConfig') }}
          </el-button>
        </div>

        <div v-loading="isLoadingConfigs" class="configs-grid">
          <div v-for="config in configs" :key="config.id" class="config-card">
            <div class="config-header">
              <div class="config-title">
                <h3>{{ config.name }}</h3>
                <div class="config-badges">
                  <span class="status-badge" :class="{ active: config.is_active }">
                    <span class="status-tag__dot"></span>
                    {{ config.is_active ? $t('generationConfig.enabled') : $t('generationConfig.disabled') }}
                  </span>
                  <span class="mode-badge">
                    {{ config.default_output_mode === 'stream' ? $t('generationConfig.streamMode') : $t('generationConfig.completeMode') }}
                  </span>
                </div>
              </div>
              <div class="config-actions">
                <el-switch
                  :model-value="config.is_active"
                  :loading="config._toggling"
                  @change="(val) => toggleActive(config, val)"
                />
                <el-button size="small" @click="editConfig(config)">{{ $t('generationConfig.edit') }}</el-button>
                <el-button size="small" type="danger" plain @click="deleteConfig(config.id)">{{ $t('generationConfig.delete') }}</el-button>
              </div>
            </div>

            <div class="config-details">
              <div class="detail-section">
                <h4>{{ $t('generationConfig.outputMode') }}</h4>
                <div class="detail-item">
                  <label>{{ $t('generationConfig.defaultMode') }}</label>
                  <span>{{ config.default_output_mode === 'stream' ? $t('generationConfig.realtimeStream') : $t('generationConfig.completeOutput') }}</span>
                </div>
              </div>

              <div class="detail-section">
                <h4>{{ $t('generationConfig.automationProcess') }}</h4>
                <div class="detail-item">
                  <label>{{ $t('generationConfig.aiReview') }}</label>
                  <span :class="{ enabled: config.enable_auto_review, disabled: !config.enable_auto_review }">
                    {{ config.enable_auto_review ? $t('generationConfig.enabled') : $t('generationConfig.disabled') }}
                  </span>
                </div>
              </div>

              <div class="detail-section">
                <h4>{{ $t('generationConfig.timeoutSettings') }}</h4>
                <div class="detail-item">
                  <label>{{ $t('generationConfig.reviewTimeout') }}</label>
                  <span>{{ config.review_timeout }} {{ $t('generationConfig.seconds') }}</span>
                </div>
              </div>

              <div class="config-meta">
                <div class="meta-item">
                  <label>{{ $t('generationConfig.createdAt') }}</label>
                  <span>{{ formatDateTime(config.created_at) }}</span>
                </div>
                <div class="meta-item">
                  <label>{{ $t('generationConfig.updatedAt') }}</label>
                  <span>{{ formatDateTime(config.updated_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!isLoadingConfigs && configs.length === 0" class="empty-state">
          <div class="empty-icon"><el-icon><Setting /></el-icon></div>
          <div class="empty-title">{{ $t('generationConfig.emptyTitle') }}</div>
          <div class="empty-hint">{{ $t('generationConfig.emptyDescription') }}</div>
          <div class="empty-state__actions">
            <el-button type="primary" @click="openAddModal">
              {{ $t('generationConfig.addFirstConfig') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑配置弹窗 -->
    <el-dialog
      :model-value="shouldShowModal"
      :title="(isEditing ? $t('generationConfig.editTitle') : $t('generationConfig.addTitle')) + $t('generationConfig.formTitle')"
      width="640px"
      @close="closeModals">
      <form @submit.prevent="saveConfig">
        <div class="form-section">
          <h4>{{ $t('generationConfig.basicInfo') }}</h4>
          <div class="form-group">
            <label>{{ $t('generationConfig.configName') }} <span class="required">*</span></label>
            <el-input
              v-model="configForm.name"
              :placeholder="$t('generationConfig.configNamePlaceholder')"
              required />
          </div>
          <div class="checkbox-hint">
            {{ $t('generationConfig.activateHint') }}
          </div>
        </div>

        <div class="form-section">
          <h4>{{ $t('generationConfig.outputModeSettings') }}</h4>
          <div class="form-group">
            <label>{{ $t('generationConfig.defaultOutputMode') }} <span class="required">*</span></label>
            <el-select v-model="configForm.default_output_mode" style="width: 100%" required>
              <el-option :label="$t('generationConfig.realtimeStream')" value="stream" />
              <el-option :label="$t('generationConfig.completeOutput')" value="complete" />
            </el-select>
            <div class="field-hint">
              {{ $t('generationConfig.outputModeHint') }}
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4>{{ $t('generationConfig.automationSettings') }}</h4>
          <div class="form-group">
            <el-checkbox v-model="configForm.enable_auto_review">
              {{ $t('generationConfig.enableAutoReview') }}
            </el-checkbox>
            <div class="checkbox-hint">
              {{ $t('generationConfig.autoReviewHint') }}
            </div>
          </div>
        </div>

        <div class="form-section">
          <h4>{{ $t('generationConfig.timeoutSettingsLabel') }}</h4>
          <div class="form-group">
            <label>{{ $t('generationConfig.reviewTimeoutLabel') }}</label>
            <el-input-number
              v-model="configForm.review_timeout"
              :min="10"
              :max="3600"
              controls-position="right"
              style="width: 100%" />
            <div class="field-hint">{{ $t('generationConfig.timeoutHint') }}</div>
          </div>
        </div>
      </form>
      <template #footer>
        <el-button @click="closeModals">{{ $t('generationConfig.cancel') }}</el-button>
        <el-button type="primary" :loading="isSaving" @click="saveConfig">
          {{ $t('generationConfig.saveConfig') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { getGenerationConfigs, createGenerationConfig, updateGenerationConfig, deleteGenerationConfig } from '@/api/requirement-analysis'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'GenerationConfigView',
  components: { PageHeader },
  setup() {
    const { t, locale } = useI18n()
    return { t, locale }
  },
  data() {
    return {
      configs: [],
      isLoadingConfigs: false,
      showAddModal: false,
      showEditModal: false,
      isEditing: false,
      isSaving: false,
      editingConfigId: null,
      configForm: {
        name: '',
        default_output_mode: 'stream',
        enable_auto_review: true,
        review_timeout: 1500,
        is_active: false
      }
    }
  },

  computed: {
    shouldShowModal() {
      return this.showAddModal || this.showEditModal
    }
  },

  mounted() {
    this.configForm.name = this.t('generationConfig.defaultConfigName')
    this.loadConfigs()
  },

  methods: {
    openAddModal() {
      this.resetForm()
      this.isEditing = false
      this.showAddModal = true
    },

    async loadConfigs() {
      this.isLoadingConfigs = true
      try {
        const response = await getGenerationConfigs()

        // 处理分页API响应格式
        if (response.data && response.data.results && Array.isArray(response.data.results)) {
          this.configs = response.data.results.map(c => ({ ...c, _toggling: false }))
        } else if (response.data && Array.isArray(response.data)) {
          this.configs = response.data.map(c => ({ ...c, _toggling: false }))
        } else {
          console.warn('Unexpected API response format:', response.data)
          this.configs = []
        }
      } catch (error) {
        console.error('Failed to load config:', error)
        this.configs = []

        if (error.response?.status === 401) {
          ElMessage.error(this.t('generationConfig.pleaseLogin'))
        } else {
          ElMessage.error(this.t('generationConfig.loadFailed') + ': ' + (error.response?.data?.error || error.message))
        }
      } finally {
        this.isLoadingConfigs = false
      }
    },

    resetForm() {
      this.configForm = {
        name: this.t('generationConfig.defaultConfigName'),
        default_output_mode: 'stream',
        enable_auto_review: true,
        review_timeout: 1500,
        is_active: false
      }
    },

    editConfig(config) {
      this.isEditing = true
      this.editingConfigId = config.id
      this.configForm = {
        name: config.name,
        default_output_mode: config.default_output_mode,
        enable_auto_review: config.enable_auto_review,
        review_timeout: config.review_timeout,
        is_active: config.is_active
      }
      this.showEditModal = true
    },

    async saveConfig() {
      this.isSaving = true

      try {
        if (this.isEditing) {
          await updateGenerationConfig(this.editingConfigId, this.configForm)
          ElMessage.success(this.t('generationConfig.updateSuccess'))
        } else {
          await createGenerationConfig(this.configForm)
          ElMessage.success(this.t('generationConfig.saveSuccess'))
        }

        this.closeModals()
        this.loadConfigs()
      } catch (error) {
        console.error('Failed to save config:', error)
        ElMessage.error(this.t('generationConfig.saveFailed') + ': ' + (error.response?.data?.error || error.message))
      } finally {
        this.isSaving = false
      }
    },

    async toggleActive(config, val) {
      config._toggling = true
      try {
        await api.post(`/requirement-analysis/generation-config/${config.id}/${val ? 'enable' : 'disable'}/`)
        ElMessage.success(val ? this.t('generationConfig.enableSuccess') : this.t('generationConfig.disableSuccess'))
        this.loadConfigs()
      } catch (error) {
        console.error('Failed to toggle config:', error)
        ElMessage.error((val ? this.t('generationConfig.enableFailed') : this.t('generationConfig.disableFailed')) + ': ' + (error.response?.data?.error || error.message))
      } finally {
        config._toggling = false
      }
    },

    async deleteConfig(configId) {
      try {
        await ElMessageBox.confirm(
          this.t('generationConfig.deleteConfirm'),
          this.t('generationConfig.delete'),
          {
            confirmButtonText: this.t('configuration.common.confirm'),
            cancelButtonText: this.t('generationConfig.cancel'),
            type: 'warning'
          }
        )
      } catch {
        return
      }

      try {
        await deleteGenerationConfig(configId)
        ElMessage.success(this.t('generationConfig.deleteSuccess'))
        this.loadConfigs()
      } catch (error) {
        console.error('Failed to delete config:', error)
        ElMessage.error(this.t('generationConfig.deleteFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    closeModals() {
      this.showAddModal = false
      this.showEditModal = false
      this.isEditing = false
      this.editingConfigId = null
      this.resetForm()
    },

    formatDateTime(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString(this.locale === 'zh-cn' ? 'zh-CN' : 'en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    }
  }
}
</script>

<style scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-section);
  flex-wrap: wrap;
  gap: var(--aitest-space-4);
}

.section-header h2 {
  color: var(--aitest-text-1);
  margin: 0;
  font-size: var(--aitest-font-size-lg);
  font-weight: 600;
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
  gap: var(--aitest-space-4);
  min-height: 120px;
}

.config-card {
  background: var(--aitest-surface);
  border-radius: var(--aitest-card-radius);
  padding: var(--aitest-card-padding);
  border: 1px solid var(--aitest-card-border);
  box-shadow: var(--aitest-card-shadow);
  transition: box-shadow 0.2s;
}

.config-card:hover {
  box-shadow: var(--aitest-shadow-md);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--aitest-space-4);
  padding-bottom: var(--aitest-space-4);
  border-bottom: 1px solid var(--aitest-border);
}

.config-title h3 {
  color: var(--aitest-text-1);
  margin: 0 0 var(--aitest-space-2) 0;
  font-size: var(--aitest-font-size-md);
  font-weight: 600;
}

.config-badges {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
}

/* 状态/模式徽章（胶囊外观 + token 语义色对） */
.status-badge, .mode-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--aitest-radius-full);
  font-size: var(--aitest-font-size-xs);
  font-weight: 600;
}

.status-badge { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.status-badge.active { background: var(--aitest-success-bg); color: var(--aitest-success); }
.mode-badge { background: var(--aitest-info-bg); color: var(--aitest-info); }

.config-actions {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  flex-shrink: 0;
}

.config-details { margin-top: var(--aitest-space-4); }

.detail-section {
  margin-bottom: var(--aitest-space-3);
  padding: var(--aitest-space-3);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
}

.detail-section h4 {
  margin: 0 0 var(--aitest-space-3) 0;
  color: var(--aitest-text-1);
  font-size: var(--aitest-font-size-base);
  font-weight: 600;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--aitest-space-2) 0;
  font-size: var(--aitest-font-size-base);
}

.detail-item label { color: var(--aitest-text-2); font-weight: 500; }
.detail-item span { color: var(--aitest-text-2); font-weight: 600; }
.detail-item span.enabled { color: var(--aitest-success); }
.detail-item span.disabled { color: var(--aitest-danger); }

.config-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--aitest-space-3);
  margin-top: var(--aitest-space-4);
  padding-top: var(--aitest-space-4);
  border-top: 1px solid var(--aitest-border);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-1);
}

.meta-item label {
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-3);
  font-weight: 500;
}

.meta-item span {
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
}

/* 弹窗表单 */
.form-section {
  margin-bottom: var(--aitest-space-5);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
}

.form-section h4 {
  margin: 0 0 var(--aitest-space-4) 0;
  color: var(--aitest-text-1);
  font-size: var(--aitest-font-size-md);
  font-weight: 600;
}

.form-group { margin-bottom: var(--aitest-space-4); }

.form-group label {
  display: block;
  margin-bottom: var(--aitest-space-2);
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
}

.field-hint {
  margin-top: var(--aitest-space-1);
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
  font-style: italic;
}

.checkbox-hint {
  margin-top: var(--aitest-space-1);
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
  font-style: italic;
}

.required { color: var(--aitest-danger); }

@media (max-width: 768px) {
  .configs-grid { grid-template-columns: 1fr; }
  .config-header { flex-direction: column; gap: var(--aitest-space-4); align-items: flex-start; }
  .detail-item { flex-direction: column; align-items: flex-start; gap: var(--aitest-space-1); }
}
</style>
