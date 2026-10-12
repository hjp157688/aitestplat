<template>
  <div class="page-container prompt-config">
    <PageHeader :title="$t('promptConfig.title')" />

    <div class="main-content">
      <!-- 配置列表 -->
      <div class="configs-section">
        <div class="section-header">
          <h2>{{ $t('promptConfig.configListTitle') }}</h2>
          <div class="header-actions">
            <el-button @click="loadDefaultPrompts">
              {{ $t('promptConfig.loadDefaults') }}
            </el-button>
            <el-button type="primary" @click="openAddModal">
              {{ $t('promptConfig.addConfig') }}
            </el-button>
          </div>
        </div>

        <div v-loading="isLoadingConfigs" class="configs-grid">
          <div v-for="config in configs" :key="config.id" class="config-card">
            <div class="config-header">
              <div class="config-title">
                <h3>{{ config.name }}</h3>
                <div class="config-badges">
                  <span class="type-badge" :class="config.prompt_type">
                    {{ getPromptTypeLabel(config.prompt_type) }}
                  </span>
                  <span class="status-badge" :class="{ active: config.is_active }">
                    <span class="status-tag__dot"></span>
                    {{ config.is_active ? $t('promptConfig.enabled') : $t('promptConfig.disabled') }}
                  </span>
                </div>
              </div>
              <div class="config-actions">
                <el-button size="small" @click="previewPrompt(config)">{{ $t('promptConfig.preview') }}</el-button>
                <el-button size="small" @click="editConfig(config)">{{ $t('promptConfig.edit') }}</el-button>
                <el-button size="small" type="danger" plain @click="deleteConfig(config.id)">{{ $t('promptConfig.delete') }}</el-button>
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

        <div v-if="!isLoadingConfigs && configs.length === 0" class="empty-state">
          <div class="empty-icon"><el-icon><EditPen /></el-icon></div>
          <div class="empty-title">{{ $t('promptConfig.noConfigs') }}</div>
          <div class="empty-hint">{{ $t('promptConfig.emptyHint') }}</div>
          <div class="empty-state__actions">
            <el-button type="primary" @click="openAddModal">
              {{ $t('promptConfig.addFirstConfig') }}
            </el-button>
            <el-button @click="loadDefaultPrompts">
              {{ $t('promptConfig.loadDefaults') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑配置弹窗 -->
    <el-dialog
      v-model="showAddModal"
      :title="$t('promptConfig.addConfig')"
      width="860px"
      @close="onEditModalClosed">
      <form @submit.prevent="saveConfig">
        <div class="form-group">
          <label>{{ $t('promptConfig.configName') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.name"
            :placeholder="$t('promptConfig.configNamePlaceholder')"
            required />
        </div>

        <div class="form-group">
          <label>{{ $t('promptConfig.promptType') }} <span class="required">*</span></label>
          <el-select v-model="configForm.prompt_type" style="width: 100%" required>
            <el-option :label="$t('promptConfig.selectPromptType')" value="" disabled />
            <el-option :label="$t('promptConfig.writerPrompt')" value="writer" />
            <el-option :label="$t('promptConfig.reviewerPrompt')" value="reviewer" />
            <el-option :label="$t('promptConfig.apiTestCaseGenerator')" value="api_testcase_generator" />
          </el-select>
        </div>

        <div class="form-group">
          <label>{{ $t('promptConfig.promptContent') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.content"
            type="textarea"
            :rows="18"
            :placeholder="$t('promptConfig.contentPlaceholder')"
            required />
          <div class="char-count">{{ $t('promptConfig.charCount', { count: configForm.content.length }) }}</div>
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
          <el-checkbox v-model="configForm.is_active">
            {{ $t('promptConfig.enableConfig') }}
          </el-checkbox>
          <div class="checkbox-hint">
            {{ $t('promptConfig.enableHint') }}
          </div>
        </div>
      </form>
      <template #footer>
        <el-button @click="closeModals">{{ $t('promptConfig.cancel') }}</el-button>
        <el-button type="primary" :loading="isSaving" @click="saveConfig">
          {{ $t('promptConfig.saveConfig') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 预览弹窗 -->
    <el-dialog
      v-model="showPreviewModal"
      :title="$t('promptConfig.previewTitle', { name: previewConfig.name })"
      width="860px"
      @close="closePreview">
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
              <span class="status-tag__dot"></span>
              {{ previewConfig.is_active ? $t('promptConfig.enabled') : $t('promptConfig.disabled') }}
            </span>
          </div>
        </div>
        <div class="content-display">
          <label>{{ $t('promptConfig.promptContent') }}</label>
          <div class="content-text">{{ previewConfig.content }}</div>
        </div>
      </div>
    </el-dialog>

    <!-- 默认提示词预览弹窗 -->
    <el-dialog
      v-model="showDefaultsModal"
      :title="$t('promptConfig.defaultPromptsPreview')"
      width="860px"
      @close="closeDefaultsModal">
      <div class="defaults-content">
        <el-tabs v-model="activeTab">
          <el-tab-pane :label="$t('promptConfig.writerTab')" name="writer" />
          <el-tab-pane :label="$t('promptConfig.reviewerTab')" name="reviewer" />
          <el-tab-pane :label="$t('promptConfig.apiTestCaseGeneratorTab')" name="api_testcase_generator" />
        </el-tabs>

        <div class="tab-content">
          <div class="content-display">
            <div class="content-text">{{ defaultPrompts[activeTab] || $t('promptConfig.noContent') }}</div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeDefaultsModal">{{ $t('promptConfig.cancel') }}</el-button>
        <el-button type="primary" :loading="isLoadingDefaults" @click="confirmLoadDefaults">
          {{ $t('promptConfig.confirmLoad') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'PromptConfig',
  components: { PageHeader },
  data() {
    return {
      configs: [],
      isLoadingConfigs: false,
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
      this.resetForm()
      this.isEditing = false
      this.showAddModal = true
    },

    async loadConfigs() {
      this.isLoadingConfigs = true
      try {
        // 统一从需求分析提示词接口加载三类配置（writer/reviewer/api_testcase_generator）
        const response = await api.get('/requirement-analysis/prompts/')

        let configs = []
        if (response.data && response.data.results && Array.isArray(response.data.results)) {
          configs = response.data.results
        } else if (response.data && Array.isArray(response.data)) {
          configs = response.data
        }

        this.configs = configs
      } catch (error) {
        console.error(this.$t('promptConfig.loadConfigsFailed'), error)
        this.configs = []
        if (error.response?.status === 401) {
          ElMessage.error(this.$t('promptConfig.pleaseLogin'))
        } else {
          ElMessage.error(this.$t('promptConfig.loadConfigsFailed') + ': ' + (error.response?.data?.error || error.message))
        }
      } finally {
        this.isLoadingConfigs = false
      }
    },

    async loadDefaultPrompts() {
      const missingTypes = this.getMissingPromptTypes()

      if (missingTypes.length === 0) {
        const allTypes = ['writer', 'reviewer', 'api_testcase_generator'].map(type => this.getPromptTypeLabel(type))
        ElMessage.warning(this.$t('promptConfig.promptExists', { types: allTypes.join('、') }))
        return
      }

      try {
        // 统一从需求分析 load_defaults 加载三类默认提示词（writer/reviewer/api_testcase_generator）
        const response = await api.get('/requirement-analysis/prompts/load_defaults/')
        this.defaultPrompts = response.data.defaults || {}

        this.showDefaultsModal = true
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
      try {
        await ElMessageBox.confirm(
          this.$t('promptConfig.deleteConfirm'),
          this.$t('promptConfig.delete'),
          {
            confirmButtonText: this.$t('configuration.common.confirm'),
            cancelButtonText: this.$t('promptConfig.cancel'),
            type: 'warning'
          }
        )
      } catch {
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

    // 添加/编辑弹窗关闭后清理（closeModals 之外还需覆盖遮罩点击关闭）
    onEditModalClosed() {
      if (!this.showAddModal && !this.showEditModal) {
        this.isEditing = false
        this.editingConfigId = null
        this.resetForm()
      }
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

.header-actions {
  display: flex;
  gap: var(--aitest-space-2);
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
  gap: var(--aitest-space-4);
  min-height: 120px;
}

.config-card {
  background: var(--aitest-surface);
  border-radius: var(--aitest-card-radius);
  padding: var(--aitest-card-padding);
  border: 1px solid var(--aitest-card-border);
  box-shadow: var(--aitest-card-shadow);
  transition: box-shadow 0.2s ease;
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

/* 类型/状态徽章（胶囊外观 + token 语义色对） */
.type-badge, .status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--aitest-radius-full);
  font-size: var(--aitest-font-size-xs);
  font-weight: 600;
}

.type-badge.writer { background: var(--aitest-success-bg); color: var(--aitest-success); }
.type-badge.reviewer { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.type-badge.api_testcase_generator { background: var(--aitest-info-bg); color: var(--aitest-info); }

.status-badge { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.status-badge.active { background: var(--aitest-success-bg); color: var(--aitest-success); }

.config-actions {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
}

.config-details { margin-top: var(--aitest-space-4); }

.prompt-preview { margin-bottom: var(--aitest-space-4); }

.prompt-preview label {
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-3);
  font-weight: 500;
  display: block;
  margin-bottom: var(--aitest-space-2);
}

.content-preview {
  background: var(--aitest-canvas);
  padding: var(--aitest-space-3);
  border-radius: var(--aitest-radius);
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-base);
  line-height: var(--aitest-line-height-normal);
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
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-3);
  font-weight: 500;
}

.meta-item span {
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
}

/* 弹窗表单 */
.form-group { margin-bottom: var(--aitest-space-4); }

.form-group label {
  display: block;
  margin-bottom: var(--aitest-space-2);
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
}

.char-count {
  text-align: right;
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-3);
  margin-top: var(--aitest-space-1);
}

.textarea-tips {
  margin-top: var(--aitest-space-3);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
  border-left: 3px solid var(--aitest-primary);
}

.textarea-tips p {
  margin: 0 0 var(--aitest-space-3) 0;
  color: var(--aitest-text-2);
  font-weight: 600;
  font-size: var(--aitest-font-size-sm);
}

.textarea-tips ul { margin: 0; padding-left: var(--aitest-space-5); }

.textarea-tips li {
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-1);
  line-height: 1.4;
  font-size: var(--aitest-font-size-base);
}

.checkbox-hint {
  margin-top: var(--aitest-space-1);
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
  font-style: italic;
}

.required { color: var(--aitest-danger); }

/* 预览弹窗 */
.preview-content, .defaults-content { margin-bottom: var(--aitest-space-4); }

.preview-meta {
  display: flex;
  gap: var(--aitest-space-5);
  margin-bottom: var(--aitest-space-4);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
}

.preview-meta .meta-item {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
}

.content-display { margin-bottom: var(--aitest-space-4); }

.content-display label {
  font-weight: 600;
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-3);
  display: block;
  font-size: var(--aitest-font-size-sm);
}

.content-text {
  background: var(--aitest-canvas);
  padding: var(--aitest-space-4);
  border-radius: var(--aitest-radius);
  color: var(--aitest-text-2);
  line-height: var(--aitest-line-height-relaxed);
  white-space: pre-wrap;
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-sm);
  border-left: 3px solid var(--aitest-primary);
  max-height: 400px;
  overflow-y: auto;
}

.tab-content { margin-top: var(--aitest-space-2); }

@media (max-width: 768px) {
  .configs-grid { grid-template-columns: 1fr; }
  .config-header { flex-direction: column; gap: var(--aitest-space-4); align-items: flex-start; }
  .header-actions { flex-direction: column; width: 100%; }
  .preview-meta { flex-direction: column; gap: var(--aitest-space-3); }
}
</style>
