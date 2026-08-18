<template>
  <div class="generation-config">
    <PageHeader :title="$t('generationConfig.title')" />

    <div class="main-content">
      <!-- 配置列表 -->
      <div class="configs-section">
        <div class="section-header">
          <h2>{{ $t('generationConfig.configList') }}</h2>
          <button class="add-config-btn" @click="openAddModal">
            {{ $t('generationConfig.addConfig') }}
          </button>
        </div>

        <div class="configs-grid">
          <div v-for="config in configs" :key="config.id" class="config-card">
            <div class="config-header">
              <div class="config-title">
                <h3>{{ config.name }}</h3>
                <div class="config-badges">
                  <span class="status-badge" :class="{ active: config.is_active }">
                    {{ config.is_active ? $t('generationConfig.enabled') : $t('generationConfig.disabled') }}
                  </span>
                  <span class="mode-badge">
                    {{ config.default_output_mode === 'stream' ? $t('generationConfig.streamMode') : $t('generationConfig.completeMode') }}
                  </span>
                </div>
              </div>
              <div class="config-actions">
                <button v-if="!config.is_active" class="enable-btn" @click="enableConfig(config.id)">
                  {{ $t('generationConfig.enable') }}
                </button>
                <button class="edit-btn" @click="editConfig(config)">{{ $t('generationConfig.edit') }}</button>
                <button class="delete-btn" @click="deleteConfig(config.id)">{{ $t('generationConfig.delete') }}</button>
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

        <div v-if="configs.length === 0" class="empty-state">
          <el-icon class="empty-icon"><Setting /></el-icon>
          <h3>{{ $t('generationConfig.emptyTitle') }}</h3>
          <p>{{ $t('generationConfig.emptyDescription') }}</p>
          <button class="add-first-config-btn" @click="openAddModal">
            {{ $t('generationConfig.addFirstConfig') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 添加/编辑配置弹窗 -->
    <div v-if="showAddModal || showEditModal" class="config-modal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ isEditing ? $t('generationConfig.editTitle') : $t('generationConfig.addTitle') }}{{ $t('generationConfig.formTitle') }}</h3>
          <button class="close-btn" @click="closeModals">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveConfig">
            <div class="form-section">
              <h4>{{ $t('generationConfig.basicInfo') }}</h4>
              <div class="form-group">
                <label>{{ $t('generationConfig.configName') }} <span class="required">*</span></label>
                <input
                  v-model="configForm.name"
                  type="text"
                  class="form-input"
                  :placeholder="$t('generationConfig.configNamePlaceholder')"
                  required>
              </div>

              <div class="form-group">
                <label class="checkbox-label">
                  <input v-model="configForm.is_active" type="checkbox">
                  <span class="checkmark"></span>
                  {{ $t('generationConfig.enableThisConfig') }}
                </label>
                <div class="checkbox-hint">
                  {{ $t('generationConfig.enableHint') }}
                </div>
              </div>
            </div>

            <div class="form-section">
              <h4>{{ $t('generationConfig.outputModeSettings') }}</h4>
              <div class="form-group">
                <label>{{ $t('generationConfig.defaultOutputMode') }} <span class="required">*</span></label>
                <select v-model="configForm.default_output_mode" class="form-select" required>
                  <option value="stream">{{ $t('generationConfig.realtimeStream') }}</option>
                  <option value="complete">{{ $t('generationConfig.completeOutput') }}</option>
                </select>
                <div class="field-hint">
                  {{ $t('generationConfig.outputModeHint') }}
                </div>
              </div>
            </div>

            <div class="form-section">
              <h4>{{ $t('generationConfig.automationSettings') }}</h4>
              <div class="form-group">
                <label class="checkbox-label">
                  <input v-model="configForm.enable_auto_review" type="checkbox">
                  <span class="checkmark"></span>
                  {{ $t('generationConfig.enableAutoReview') }}
                </label>
                <div class="checkbox-hint">
                  {{ $t('generationConfig.autoReviewHint') }}
                </div>
              </div>
            </div>

            <div class="form-section">
              <h4>{{ $t('generationConfig.timeoutSettingsLabel') }}</h4>
              <div class="form-group">
                <label>{{ $t('generationConfig.reviewTimeoutLabel') }}</label>
                <input
                  v-model.number="configForm.review_timeout"
                  type="number"
                  class="form-input"
                  min="10"
                  max="3600">
                <div class="field-hint">{{ $t('generationConfig.timeoutHint') }}</div>
              </div>
            </div>

            <div class="modal-actions">
              <button type="button" class="cancel-btn" @click="closeModals">{{ $t('generationConfig.cancel') }}</button>
              <button
                type="submit"
                class="confirm-btn"
                :disabled="isSaving">
                <span v-if="isSaving">{{ $t('generationConfig.saving') }}</span>
                <span v-else>{{ $t('generationConfig.saveConfig') }}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { getGenerationConfigs, createGenerationConfig, updateGenerationConfig, deleteGenerationConfig } from '@/api/requirement-analysis'
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'
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
        is_active: true
      }
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
      try {
        console.log('Loading generation configs...')
        const response = await getGenerationConfigs()
        console.log('Generation configs API response:', response.data)

        // 处理分页API响应格式
        if (response.data && response.data.results && Array.isArray(response.data.results)) {
          this.configs = response.data.results
        } else if (response.data && Array.isArray(response.data)) {
          this.configs = response.data
        } else {
          console.warn('Unexpected API response format:', response.data)
          this.configs = []
        }

        console.log('Final configs count:', this.configs.length)
      } catch (error) {
        console.error('Failed to load config:', error)
        this.configs = []

        if (error.response?.status === 401) {
          ElMessage.error(this.t('generationConfig.pleaseLogin'))
        } else {
          ElMessage.error(this.t('generationConfig.loadFailed') + ': ' + (error.response?.data?.error || error.message))
        }
      }
    },

    resetForm() {
      this.configForm = {
        name: this.t('generationConfig.defaultConfigName'),
        default_output_mode: 'stream',
        enable_auto_review: true,
        review_timeout: 1500,
        is_active: true
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

    async enableConfig(configId) {
      try {
        await api.post(`/requirement-analysis/generation-config/${configId}/enable/`)
        ElMessage.success(this.t('generationConfig.enableSuccess'))
        this.loadConfigs()
      } catch (error) {
        console.error('Failed to enable config:', error)
        ElMessage.error(this.t('generationConfig.enableFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    async deleteConfig(configId) {
      if (!confirm(this.t('generationConfig.deleteConfirm'))) {
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
.generation-config {
  padding: 28px var(--aitest-space-6);
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-6);
  flex-wrap: wrap;
  gap: var(--aitest-space-4);
}

.section-header h2 {
  color: var(--aitest-text-1);
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
}

.add-config-btn {
  background: var(--aitest-primary);
  color: #FFFFFF;
  border: none;
  padding: var(--aitest-space-3) 22px;
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s;
}

.add-config-btn:hover { background: var(--aitest-primary-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); }

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(600px, 1fr));
  gap: var(--aitest-space-5);
}

.config-card {
  background: var(--aitest-surface);
  border-radius: 14px;
  padding: var(--aitest-space-6);
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: transform 0.2s, box-shadow 0.2s;
}

.config-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--aitest-space-5);
  padding-bottom: var(--aitest-space-4);
  border-bottom: 1px solid var(--aitest-surface-subtle);
}

.config-title h3 {
  color: var(--aitest-text-1);
  margin: 0 0 var(--aitest-space-3) 0;
  font-size: 1.15rem;
  font-weight: 700;
}

.config-badges {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
}

.status-badge, .mode-badge {
  padding: 3px var(--aitest-space-3);
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 600;
}

.status-badge { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.status-badge.active { background: var(--aitest-success-bg); color: var(--aitest-success); }
.mode-badge { background: var(--aitest-info-bg); color: var(--aitest-primary); }

.config-actions {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
}

.enable-btn, .edit-btn, .delete-btn {
  padding: var(--aitest-space-2) var(--aitest-space-3);
  border: none;
  border-radius: var(--aitest-radius);
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.15s;
}

.enable-btn { background: var(--aitest-success); color: #FFFFFF; }
.enable-btn:hover { background: #047857; }
.edit-btn { background: var(--aitest-warning); color: #FFFFFF; }
.edit-btn:hover { background: var(--aitest-warning); }
.delete-btn { background: var(--aitest-danger); color: #FFFFFF; }
.delete-btn:hover { background: #B91C1C; }

.config-details { margin-top: var(--aitest-space-4); }

.detail-section {
  margin-bottom: var(--aitest-space-4);
  padding: var(--aitest-space-3);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius-lg);
}

.detail-section h4 {
  margin: 0 0 var(--aitest-space-3) 0;
  color: var(--aitest-text-1);
  font-size: 0.9rem;
  font-weight: 600;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--aitest-space-2) 0;
  font-size: 0.85rem;
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
  font-size: 0.78rem;
  color: var(--aitest-text-3);
  font-weight: 500;
}

.meta-item span {
  color: var(--aitest-text-2);
  font-size: 0.85rem;
}

.empty-state {
  text-align: center;
  padding: 80px var(--aitest-space-5);
  color: var(--aitest-text-2);
}

.empty-icon { font-size: 4rem; margin-bottom: var(--aitest-space-5); }

.empty-state h3 {
  color: var(--aitest-text-1);
  margin-bottom: var(--aitest-space-3);
}

.add-first-config-btn {
  background: var(--aitest-primary);
  color: #FFFFFF;
  border: none;
  padding: var(--aitest-space-4) 28px;
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  margin-top: var(--aitest-space-5);
  transition: all 0.2s;
}

.add-first-config-btn:hover { background: var(--aitest-primary-hover); box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); }

.config-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--aitest-surface);
  border-radius: 14px;
  padding: 0;
  max-width: 700px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 25px 50px rgba(0,0,0,0.12);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--aitest-space-5) var(--aitest-space-6);
  border-bottom: 1px solid var(--aitest-border);
}

.modal-header h3 {
  margin: 0;
  color: var(--aitest-text-1);
  font-weight: 700;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--aitest-text-3);
  padding: var(--aitest-space-1) var(--aitest-space-2);
  border-radius: var(--aitest-radius);
  transition: all 0.15s;
}

.close-btn:hover { color: var(--aitest-text-1); background: var(--aitest-surface-subtle); }

.modal-body { padding: var(--aitest-space-6); }

.form-section {
  margin-bottom: 22px;
  padding: var(--aitest-space-5);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius-lg);
}

.form-section h4 {
  margin: 0 0 var(--aitest-space-4) 0;
  color: var(--aitest-text-1);
  font-size: 1rem;
  font-weight: 600;
}

.form-group { margin-bottom: var(--aitest-space-4); }

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--aitest-space-4);
}

.form-group label {
  display: block;
  margin-bottom: var(--aitest-space-2);
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: 0.85rem;
}

.form-input, .form-select {
  width: 100%;
  padding: var(--aitest-space-3) var(--aitest-space-3);
  border: 1.5px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  font-size: 0.9rem;
  color: var(--aitest-text-1);
  background: var(--aitest-surface);
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus, .form-select:focus {
  outline: none;
  border-color: var(--aitest-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.field-hint {
  margin-top: var(--aitest-space-1);
  font-size: 0.78rem;
  color: var(--aitest-text-3);
  font-style: italic;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-3);
  cursor: pointer;
  user-select: none;
}

.checkbox-label input[type="checkbox"] { width: auto; accent-color: var(--aitest-primary); }

.checkbox-hint {
  margin-top: var(--aitest-space-1);
  font-size: 0.78rem;
  color: var(--aitest-text-3);
  font-style: italic;
}

.required { color: var(--aitest-danger); }

.modal-actions {
  display: flex;
  gap: var(--aitest-space-3);
  justify-content: flex-end;
  margin-top: var(--aitest-space-6);
}

.cancel-btn {
  background: var(--aitest-surface-subtle);
  color: var(--aitest-text-2);
  border: 1.5px solid var(--aitest-border);
  padding: var(--aitest-space-3) var(--aitest-space-5);
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.cancel-btn:hover { background: var(--aitest-surface-subtle); }

.confirm-btn {
  background: var(--aitest-primary);
  color: #FFFFFF;
  border: none;
  padding: var(--aitest-space-3) var(--aitest-space-5);
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.confirm-btn:hover:not(:disabled) { background: var(--aitest-primary-hover); }
.confirm-btn:disabled { background: var(--aitest-border-strong); cursor: not-allowed; }

@media (max-width: 768px) {
  .configs-grid { grid-template-columns: 1fr; }
  .config-header { flex-direction: column; gap: var(--aitest-space-4); align-items: flex-start; }
  .form-row { grid-template-columns: 1fr; }
  .detail-item { flex-direction: column; align-items: flex-start; gap: var(--aitest-space-1); }
}
</style>
