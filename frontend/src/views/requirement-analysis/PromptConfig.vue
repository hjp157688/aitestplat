<template>
  <div class="prompt-config">
    <PageHeader :title="$t('promptConfig.title')" />

    <div class="main-content">
      <!-- 配置列表 -->
      <div class="configs-section">
        <div class="section-header">
          <h2>{{ $t('promptConfig.configListTitle') }}</h2>
          <div class="header-actions">
            <button class="load-defaults-btn" @click="loadDefaultPrompts">
              {{ $t('promptConfig.loadDefaults') }}
            </button>
            <button class="add-config-btn" @click="openAddModal">
              {{ $t('promptConfig.addConfig') }}
            </button>
          </div>
        </div>

        <div class="configs-grid">
          <div v-for="config in configs" :key="config.id" class="config-card">
            <div class="config-header">
              <div class="config-title">
                <h3>{{ config.name }}</h3>
                <div class="config-badges">
                  <span class="type-badge" :class="config.prompt_type">
                    {{ getPromptTypeLabel(config.prompt_type) }}
                  </span>
                  <span class="status-badge" :class="{ active: config.is_active }">
                    {{ config.is_active ? $t('promptConfig.enabled') : $t('promptConfig.disabled') }}
                  </span>
                </div>
              </div>
              <div class="config-actions">
                <button class="preview-btn" @click="previewPrompt(config)">{{ $t('promptConfig.preview') }}</button>
                <button class="edit-btn" @click="editConfig(config)">{{ $t('promptConfig.edit') }}</button>
                <button class="delete-btn" @click="deleteConfig(config.id)">{{ $t('promptConfig.delete') }}</button>
              </div>
            </div>

            <div class="config-details">
              <div class="prompt-preview">
                <label>{{ $t('promptConfig.contentPreview') }}</label>
                <div class="content-preview">
                  {{ truncateContent(config.content, 200) }}
                </div>
              </div>
              <div class="config-meta">
                <div class="meta-item">
                  <label>{{ $t('promptConfig.createdAt') }}</label>
                  <span>{{ formatDateTime(config.created_at) }}</span>
                </div>
                <div class="meta-item">
                  <label>{{ $t('promptConfig.updatedAt') }}</label>
                  <span>{{ formatDateTime(config.updated_at) }}</span>
                </div>
                <div class="meta-item">
                  <label>{{ $t('promptConfig.createdBy') }}</label>
                  <span>{{ config.created_by_name || $t('promptConfig.unknown') }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="configs.length === 0" class="empty-state">
          <el-icon class="empty-icon"><EditPen /></el-icon>
          <h3>{{ $t('promptConfig.noConfigs') }}</h3>
          <p>{{ $t('promptConfig.emptyHint') }}</p>
          <div class="empty-actions">
            <button class="add-first-config-btn" @click="openAddModal">
              {{ $t('promptConfig.addFirstConfig') }}
            </button>
            <button class="load-defaults-first-btn" @click="loadDefaultPrompts">
              {{ $t('promptConfig.loadDefaults') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑配置弹窗 -->
    <div v-if="showAddModal || showEditModal" class="config-modal">
      <div class="modal-content large" @click.stop>
        <div class="modal-header">
          <h3>{{ isEditing ? $t('promptConfig.editConfig') : $t('promptConfig.addConfig') }}</h3>
          <button class="close-btn" @click="closeModals">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveConfig">
            <div class="form-group">
              <label>{{ $t('promptConfig.configName') }} <span class="required">*</span></label>
              <input
                v-model="configForm.name"
                type="text"
                class="form-input"
                :placeholder="$t('promptConfig.configNamePlaceholder')"
                required>
            </div>

            <div class="form-group">
              <label>{{ $t('promptConfig.promptType') }} <span class="required">*</span></label>
              <select v-model="configForm.prompt_type" class="form-select" required>
                <option value="">{{ $t('promptConfig.selectPromptType') }}</option>
                <option value="writer">{{ $t('promptConfig.writerPrompt') }}</option>
                <option value="reviewer">{{ $t('promptConfig.reviewerPrompt') }}</option>
                <option value="api_testcase_generator">{{ $t('promptConfig.apiTestCaseGenerator') }}</option>
              </select>
            </div>

            <div class="form-group">
              <label>{{ $t('promptConfig.promptContent') }} <span class="required">*</span></label>
              <div class="textarea-container">
                <textarea
                  v-model="configForm.content"
                  class="form-textarea large"
                  rows="20"
                  :placeholder="$t('promptConfig.contentPlaceholder')"
                  required></textarea>
                <div class="char-count">{{ $t('promptConfig.charCount', { count: configForm.content.length }) }}</div>
              </div>
              <div class="textarea-tips">
                <p><strong>{{ $t('promptConfig.writingTipsTitle') }}</strong></p>
                <ul>
                  <li>{{ $t('promptConfig.tip1') }}</li>
                  <li>{{ $t('promptConfig.tip2') }}</li>
                  <li>{{ $t('promptConfig.tip3') }}</li>
                  <li>{{ $t('promptConfig.tip4') }}</li>
                </ul>
              </div>
            </div>

            <div class="form-group">
              <label class="checkbox-label">
                <input
                  v-model="configForm.is_active"
                  type="checkbox">
                <span class="checkmark"></span>
                {{ $t('promptConfig.enableConfig') }}
              </label>
              <div class="checkbox-hint">
                {{ $t('promptConfig.enableHint') }}
              </div>
            </div>

            <div class="modal-actions">
              <button type="button" class="cancel-btn" @click="closeModals">{{ $t('promptConfig.cancel') }}</button>
              <button
                type="submit"
                class="confirm-btn"
                :disabled="isSaving">
                <span v-if="isSaving">{{ $t('promptConfig.saving') }}</span>
                <span v-else>{{ $t('promptConfig.saveConfig') }}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <div v-if="showPreviewModal" class="preview-modal" @click="closePreview">
      <div class="modal-content large" @click.stop>
        <div class="modal-header">
          <h3>{{ $t('promptConfig.previewTitle', { name: previewConfig.name }) }}</h3>
          <button class="close-btn" @click="closePreview">×</button>
        </div>
        <div class="modal-body">
          <div class="preview-content">
            <div class="preview-meta">
              <div class="meta-item">
                <label>{{ $t('promptConfig.type') }}</label>
                <span class="type-badge" :class="previewConfig.prompt_type">
                  {{ getPromptTypeLabel(previewConfig.prompt_type) }}
                </span>
              </div>
              <div class="meta-item">
                <label>{{ $t('promptConfig.status') }}</label>
                <span class="status-badge" :class="{ active: previewConfig.is_active }">
                  {{ previewConfig.is_active ? $t('promptConfig.enabled') : $t('promptConfig.disabled') }}
                </span>
              </div>
            </div>
            <div class="content-display">
              <label>{{ $t('promptConfig.promptContent') }}</label>
              <div class="content-text">{{ previewConfig.content }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 默认提示词预览弹窗 -->
    <div v-if="showDefaultsModal" class="defaults-modal" @click="closeDefaultsModal">
      <div class="modal-content large" @click.stop>
        <div class="modal-header">
          <h3>{{ $t('promptConfig.defaultPromptsPreview') }}</h3>
          <button class="close-btn" @click="closeDefaultsModal">×</button>
        </div>
        <div class="modal-body">
          <div class="defaults-content">
            <div class="tabs">
              <button
                class="tab-btn"
                :class="{ active: activeTab === 'writer' }"
                @click="activeTab = 'writer'">
                {{ $t('promptConfig.writerTab') }}
              </button>
              <button
                class="tab-btn"
                :class="{ active: activeTab === 'reviewer' }"
                @click="activeTab = 'reviewer'">
                {{ $t('promptConfig.reviewerTab') }}
              </button>
              <button
                class="tab-btn"
                :class="{ active: activeTab === 'api_testcase_generator' }"
                @click="activeTab = 'api_testcase_generator'">
                {{ $t('promptConfig.apiTestCaseGeneratorTab') }}
              </button>
            </div>

            <div class="tab-content">
              <div class="content-display">
                <div class="content-text">{{ defaultPrompts[activeTab] || $t('promptConfig.noContent') }}</div>
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button class="cancel-btn" @click="closeDefaultsModal">{{ $t('promptConfig.cancel') }}</button>
            <button
              class="confirm-btn"
              @click="confirmLoadDefaults"
              :disabled="isLoadingDefaults">
              <span v-if="isLoadingDefaults">{{ $t('promptConfig.loading') }}</span>
              <span v-else>{{ $t('promptConfig.confirmLoad') }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import { EditPen } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'PromptConfig',
  components: { PageHeader },
  data() {
    return {
      configs: [],
      showAddModal: false,
      showEditModal: false,
      showPreviewModal: false,
      showDefaultsModal: false,
      isEditing: false,
      isSaving: false,
      isLoadingDefaults: false,
      editingConfigId: null,
      previewConfig: {},
      defaultPrompts: {
        writer: '',
        reviewer: '',
        api_testcase_generator: ''
      },
      activeTab: 'writer',
      configForm: {
        name: '',
        prompt_type: '',
        content: '',
        is_active: true
      }
    }
  },

  mounted() {
    this.loadConfigs()
  },

  methods: {
    getPromptTypeLabel(promptType) {
      const labels = {
        writer: this.$t('promptConfig.writerPrompt'),
        reviewer: this.$t('promptConfig.reviewerPrompt'),
        api_testcase_generator: this.$t('promptConfig.apiTestCaseGenerator')
      }
      return labels[promptType] || promptType
    },

    getExistingPromptConfig(promptType, excludeId = null) {
      return this.configs.find(config => config.prompt_type === promptType && config.id !== excludeId)
    },

    getMissingPromptTypes() {
      return ['writer', 'reviewer', 'api_testcase_generator'].filter(type => !this.getExistingPromptConfig(type))
    },

    formatApiError(error, fallbackText) {
      const data = error?.response?.data
      if (!data) {
        return error?.message || fallbackText
      }

      if (typeof data.error === 'string') {
        return data.error
      }

      if (Array.isArray(data.error) && data.error.length > 0) {
        return data.error.join(', ')
      }

      if (Array.isArray(data.prompt_type) && data.prompt_type.length > 0) {
        return data.prompt_type.join(', ')
      }

      if (typeof data.prompt_type === 'string') {
        return data.prompt_type
      }

      return Object.keys(data)
        .map(key => Array.isArray(data[key]) ? data[key].join(', ') : data[key])
        .join('; ') || fallbackText
    },

    openAddModal() {
      console.log('openAddModal clicked')
      this.resetForm()
      this.isEditing = false
      this.showAddModal = true
      console.log('showAddModal set to:', this.showAddModal)
    },

    async loadConfigs() {
      try {
        console.log('Loading prompt configs...')
        // 统一从需求分析提示词接口加载三类配置（writer/reviewer/api_testcase_generator）
        const response = await api.get('/requirement-analysis/prompts/')
        console.log('Prompts API response:', response.data)

        let configs = []
        if (response.data && response.data.results && Array.isArray(response.data.results)) {
          configs = response.data.results
        } else if (response.data && Array.isArray(response.data)) {
          configs = response.data
        }

        this.configs = configs
        console.log('Final configs count:', this.configs.length)
      } catch (error) {
        console.error(this.$t('promptConfig.loadConfigsFailed'), error)
        this.configs = []
        if (error.response?.status === 401) {
          ElMessage.error(this.$t('promptConfig.pleaseLogin'))
        } else {
          ElMessage.error(this.$t('promptConfig.loadConfigsFailed') + ': ' + (error.response?.data?.error || error.message))
        }
      }
    },

    async loadDefaultPrompts() {
      console.log('loadDefaultPrompts clicked')
      const missingTypes = this.getMissingPromptTypes()

      if (missingTypes.length === 0) {
        const allTypes = ['writer', 'reviewer', 'api_testcase_generator'].map(type => this.getPromptTypeLabel(type))
        ElMessage.warning(this.$t('promptConfig.promptExists', { types: allTypes.join('、') }))
        return
      }

      try {
        // 统一从需求分析 load_defaults 加载三类默认提示词（writer/reviewer/api_testcase_generator）
        const response = await api.get('/requirement-analysis/prompts/load_defaults/')
        console.log('Default prompts response:', response.data)
        this.defaultPrompts = response.data.defaults || {}

        this.showDefaultsModal = true
        console.log('showDefaultsModal set to:', this.showDefaultsModal)
      } catch (error) {
        console.error(this.$t('promptConfig.loadDefaultsFailed'), error)
        ElMessage.error(this.$t('promptConfig.loadDefaultsFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    async confirmLoadDefaults() {
      this.isLoadingDefaults = true

      try {
        const missingTypes = this.getMissingPromptTypes()

        if (missingTypes.length === 0) {
          const allTypes = ['writer', 'reviewer', 'api_testcase_generator'].map(type => this.getPromptTypeLabel(type))
          ElMessage.warning(this.$t('promptConfig.promptExists', { types: allTypes.join('、') }))
          return
        }

        // 创建编写提示词配置
        if (missingTypes.includes('writer') && this.defaultPrompts.writer) {
          await api.post('/requirement-analysis/prompts/', {
            name: this.$t('promptConfig.defaultWriterName'),
            prompt_type: 'writer',
            content: this.defaultPrompts.writer,
            is_active: true
          })
        }

        // 创建评审提示词配置
        if (missingTypes.includes('reviewer') && this.defaultPrompts.reviewer) {
          await api.post('/requirement-analysis/prompts/', {
            name: this.$t('promptConfig.defaultReviewerName'),
            prompt_type: 'reviewer',
            content: this.defaultPrompts.reviewer,
            is_active: true
          })
        }

        // 创建接口测试用例生成提示词配置（统一写到同一张 PromptConfig 表）
        if (missingTypes.includes('api_testcase_generator') && this.defaultPrompts.api_testcase_generator) {
          await api.post('/requirement-analysis/prompts/', {
            name: this.$t('promptConfig.defaultApiTestCaseName'),
            prompt_type: 'api_testcase_generator',
            content: this.defaultPrompts.api_testcase_generator,
            is_active: true
          })
        }

        ElMessage.success(this.$t('promptConfig.defaultsLoadSuccess'))
        this.closeDefaultsModal()
        this.loadConfigs()
      } catch (error) {
        console.error(this.$t('promptConfig.loadDefaultsFailed'), error)
        ElMessage.error(this.$t('promptConfig.loadFailed') + ': ' + this.formatApiError(error, this.$t('promptConfig.loadFailed')))
      } finally{
        this.isLoadingDefaults = false
      }
    },

    resetForm() {
      this.configForm = {
        name: '',
        prompt_type: '',
        content: '',
        is_active: true
      }
    },

    editConfig(config) {
      this.isEditing = true
      this.editingConfigId = config.id
      this.configForm = {
        name: config.name,
        prompt_type: config.prompt_type,
        content: config.content,
        is_active: config.is_active
      }
      this.showEditModal = true
    },

    previewPrompt(config) {
      this.previewConfig = config
      this.showPreviewModal = true
    },

    async saveConfig() {
      this.isSaving = true

      try {
        const existingConfig = this.getExistingPromptConfig(
          this.configForm.prompt_type,
          this.isEditing ? this.editingConfigId : null
        )

        if (existingConfig) {
          ElMessage.warning(
            this.$t('promptConfig.promptTypeExists', {
              type: this.getPromptTypeLabel(this.configForm.prompt_type)
            })
          )
          return
        }

        // 提示词配置统一存于同一个接口（writer/reviewer/api_testcase_generator）
        const baseUrl = '/requirement-analysis/prompts'

        if (this.isEditing) {
          await api.patch(`${baseUrl}/${this.editingConfigId}/`, this.configForm)
          ElMessage.success(this.$t('promptConfig.updateSuccess'))
        } else {
          await api.post(`${baseUrl}/`, this.configForm)
          ElMessage.success(this.$t('promptConfig.addSuccess'))
        }

        this.closeModals()
        this.loadConfigs()
      } catch (error) {
        console.error(this.$t('promptConfig.saveConfigFailed'), error)
        ElMessage.error(this.$t('promptConfig.saveFailed') + ': ' + this.formatApiError(error, this.$t('promptConfig.saveFailed')))
      } finally {
        this.isSaving = false
      }
    },

    async deleteConfig(configId) {
      if (!confirm(this.$t('promptConfig.deleteConfirm'))) {
        return
      }

      try {
        // 提示词配置统一存于同一个接口
        const baseUrl = '/requirement-analysis/prompts'

        await api.delete(`${baseUrl}/${configId}/`)
        ElMessage.success(this.$t('promptConfig.deleteSuccess'))
        this.loadConfigs()
      } catch (error) {
        console.error(this.$t('promptConfig.deleteConfigFailed'), error)
        ElMessage.error(this.$t('promptConfig.deleteFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    closeModals() {
      this.showAddModal = false
      this.showEditModal = false
      this.isEditing = false
      this.editingConfigId = null
      this.resetForm()
    },

    closePreview() {
      this.showPreviewModal = false
      this.previewConfig = {}
    },

    closeDefaultsModal() {
      this.showDefaultsModal = false
      this.defaultPrompts = { writer: '', reviewer: '', api_testcase_generator: '' }
      this.activeTab = 'writer'
    },

    truncateContent(content, maxLength) {
      if (!content) return ''
      if (content.length <= maxLength) return content
      return content.substring(0, maxLength) + '...'
    },

    formatDateTime(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN', {
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
.prompt-config {
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

.header-actions {
  display: flex;
  gap: var(--aitest-space-3);
}

.load-defaults-btn {
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

.load-defaults-btn:hover { background: #6D28D9; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25); }

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
  grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
  gap: var(--aitest-space-5);
}

.config-card {
  background: var(--aitest-surface);
  border-radius: 14px;
  padding: var(--aitest-space-6);
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
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

.type-badge, .status-badge {
  padding: 3px var(--aitest-space-3);
  border-radius: 20px;
  font-size: 0.72rem;
  font-weight: 600;
}

.type-badge.writer { background: var(--aitest-success-bg); color: var(--aitest-success); }
.type-badge.reviewer { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.type-badge.api_testcase_generator { background: var(--aitest-info-bg); color: var(--aitest-primary); }

.status-badge { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.status-badge.active { background: var(--aitest-success-bg); color: var(--aitest-success); }

.config-actions {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
}

.preview-btn, .edit-btn, .delete-btn {
  padding: var(--aitest-space-2) var(--aitest-space-3);
  border: none;
  border-radius: var(--aitest-radius);
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.15s;
}

.preview-btn { background: var(--aitest-primary); color: #FFFFFF; }
.preview-btn:hover { background: var(--aitest-primary-hover); }
.edit-btn { background: var(--aitest-warning); color: #FFFFFF; }
.edit-btn:hover { background: var(--aitest-warning); }
.delete-btn { background: var(--aitest-danger); color: #FFFFFF; }
.delete-btn:hover { background: #B91C1C; }

.config-details { margin-top: var(--aitest-space-4); }

.prompt-preview { margin-bottom: var(--aitest-space-4); }

.prompt-preview label {
  font-size: 0.8rem;
  color: var(--aitest-text-3);
  font-weight: 500;
  display: block;
  margin-bottom: var(--aitest-space-2);
}

.content-preview {
  background: var(--aitest-canvas);
  padding: var(--aitest-space-3);
  border-radius: var(--aitest-radius-lg);
  color: var(--aitest-text-2);
  font-size: 0.85rem;
  line-height: 1.5;
  border-left: 3px solid var(--aitest-primary);
}

.config-meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--aitest-space-3);
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

.empty-actions {
  display: flex;
  gap: var(--aitest-space-4);
  justify-content: center;
  margin-top: var(--aitest-space-5);
  flex-wrap: wrap;
}

.add-first-config-btn, .load-defaults-first-btn {
  border: none;
  padding: var(--aitest-space-4) 28px;
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  transition: all 0.2s;
}

.add-first-config-btn { background: var(--aitest-primary); color: #FFFFFF; }
.add-first-config-btn:hover { background: var(--aitest-primary-hover); box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); }
.load-defaults-first-btn { background: var(--aitest-primary); color: #FFFFFF; }
.load-defaults-first-btn:hover { background: #6D28D9; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25); }

.config-modal, .preview-modal, .defaults-modal {
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
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 25px 50px rgba(0,0,0,0.12);
}

.modal-content.large { max-width: 900px; }

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

.form-group { margin-bottom: var(--aitest-space-5); }

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

.textarea-container { position: relative; }

.form-textarea {
  width: 100%;
  padding: var(--aitest-space-3);
  border: 1.5px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  font-size: 0.9rem;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  resize: vertical;
  min-height: 200px;
  color: var(--aitest-text-2);
  background: var(--aitest-surface);
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-textarea.large { min-height: 400px; }

.form-textarea:focus {
  outline: none;
  border-color: var(--aitest-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.char-count {
  text-align: right;
  font-size: 0.75rem;
  color: var(--aitest-text-3);
  margin-top: var(--aitest-space-1);
}

.textarea-tips {
  margin-top: var(--aitest-space-3);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius-lg);
  border-left: 3px solid var(--aitest-primary);
}

.textarea-tips p {
  margin: 0 0 var(--aitest-space-3) 0;
  color: var(--aitest-text-2);
  font-weight: 600;
  font-size: 0.85rem;
}

.textarea-tips ul { margin: 0; padding-left: var(--aitest-space-5); }

.textarea-tips li {
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-1);
  line-height: 1.4;
  font-size: 0.82rem;
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
  font-size: 0.8rem;
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

.preview-content, .defaults-content { margin-bottom: var(--aitest-space-5); }

.preview-meta {
  display: flex;
  gap: var(--aitest-space-5);
  margin-bottom: var(--aitest-space-5);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius-lg);
}

.preview-meta .meta-item {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
}

.content-display { margin-bottom: var(--aitest-space-5); }

.content-display label {
  font-weight: 600;
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-3);
  display: block;
  font-size: 0.85rem;
}

.content-text {
  background: var(--aitest-canvas);
  padding: var(--aitest-space-5);
  border-radius: var(--aitest-radius-lg);
  color: var(--aitest-text-2);
  line-height: 1.6;
  white-space: pre-wrap;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.85rem;
  border-left: 3px solid var(--aitest-primary);
  max-height: 400px;
  overflow-y: auto;
}

.tabs {
  display: flex;
  gap: 2px;
  margin-bottom: var(--aitest-space-5);
  border-bottom: 1.5px solid var(--aitest-border);
}

.tab-btn {
  background: none;
  border: none;
  padding: var(--aitest-space-3) var(--aitest-space-5);
  cursor: pointer;
  color: var(--aitest-text-2);
  font-size: 0.9rem;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn.active {
  color: var(--aitest-primary);
  border-bottom-color: var(--aitest-primary);
  background: var(--aitest-canvas);
}

.tab-btn:hover { background: var(--aitest-canvas); }

@media (max-width: 768px) {
  .configs-grid { grid-template-columns: 1fr; }
  .config-header { flex-direction: column; gap: var(--aitest-space-4); align-items: flex-start; }
  .header-actions { flex-direction: column; width: 100%; }
  .empty-actions { flex-direction: column; align-items: center; }
  .preview-meta { flex-direction: column; gap: var(--aitest-space-3); }
}
</style>
