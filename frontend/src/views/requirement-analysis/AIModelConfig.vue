<template>
  <div class="page-container ai-model-config">
    <PageHeader :title="$t('configuration.aiModel.title')" />

    <div class="main-content">
      <!-- 配置列表 -->
      <div class="configs-section">
        <div class="section-header">
          <h2>{{ $t('configuration.aiModel.configList') }}</h2>
          <el-button type="primary" @click="openAddModal">
            {{ $t('configuration.aiModel.addConfig') }}
          </el-button>
        </div>

        <div v-loading="isLoadingConfigs" class="configs-grid">
          <template v-for="config in configs" :key="config?.id || 'unknown'">
            <div v-if="config && config.id" class="config-card">
              <div class="config-header">
                <div class="config-title">
                  <h3>{{ config.name || $t('configuration.common.unnamed') }}</h3>
                  <div class="config-badges">
                    <span class="model-badge" :class="config.model_type">
                      {{ $t('configuration.aiModel.modelTypes.' + config.model_type) }}
                    </span>
                    <span class="role-badge" :class="config.role">
                      {{ $t('configuration.aiModel.roles.' + config.role) }}
                    </span>
                    <span class="status-badge" :class="{ active: config.is_active }">
                      <span class="status-tag__dot"></span>
                      {{ config.is_active ? $t('configuration.common.enabled') : $t('configuration.common.disabled') }}
                    </span>
                  </div>
                </div>
                <div class="config-actions">
                  <el-switch
                    v-model="config.is_active"
                    @change="toggleActive(config)"
                    :active-text="$t('configuration.common.enabled')"
                    :inactive-text="$t('configuration.common.disabled')"
                    :loading="config.toggling"
                  />
                  <el-button size="small" @click="testConnection(config)" :loading="testingConfigId === config.id">
                    {{ $t('configuration.aiModel.testConnection') }}
                  </el-button>
                  <el-button size="small" @click="editConfig(config)">{{ $t('configuration.common.edit') }}</el-button>
                  <el-button size="small" type="danger" plain @click="deleteConfig(config.id)">{{ $t('configuration.common.delete') }}</el-button>
                </div>
              </div>

              <div class="config-details">
              <div class="detail-item">
                <label>{{ $t('configuration.aiModel.baseUrl') }}:</label>
                <span>{{ config.base_url }}</span>
              </div>
              <div class="detail-item">
                <label>{{ $t('configuration.aiModel.modelName') }}:</label>
                <span>{{ config.model_name }}</span>
              </div>
              <div class="detail-item">
                <label>{{ $t('configuration.aiModel.maxTokens') }}:</label>
                <span>{{ config.max_tokens || $t('configuration.aiModel.unlimited') }}</span>
              </div>
              <div class="detail-item">
                <label>{{ $t('configuration.aiModel.temperature') }}:</label>
                <span>{{ config.temperature }}</span>
              </div>
              <div class="detail-item">
                <label>{{ $t('configuration.aiModel.topP') }}:</label>
                <span>{{ config.top_p }}</span>
              </div>
              <div class="detail-item">
                <label>{{ $t('configuration.common.createdAt') }}:</label>
                <span>{{ formatDateTime(config.created_at) }}</span>
              </div>
              </div>
            </div>
          </template>
        </div>

        <div v-if="!isLoadingConfigs && configs.length === 0" class="empty-state">
          <div class="empty-icon"><el-icon><Setting /></el-icon></div>
          <div class="empty-title">{{ $t('configuration.aiModel.emptyTitle') }}</div>
          <div class="empty-hint">{{ $t('configuration.aiModel.emptyDescription') }}</div>
          <div class="empty-state__actions">
            <el-button type="primary" @click="openAddModal">
              {{ $t('configuration.aiModel.addFirstConfig') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑配置弹窗 -->
    <el-dialog
      :model-value="shouldShowModal"
      @close="closeModals"
      :title="isEditing ? $t('configuration.aiModel.editConfig') : $t('configuration.aiModel.addConfigTitle')"
      width="640px">
      <form @submit.prevent="saveConfig">
        <div class="form-group">
          <label>{{ $t('configuration.aiModel.configName') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.name"
            :placeholder="$t('configuration.aiModel.configNamePlaceholder')"
            required />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>{{ $t('configuration.aiModel.modelType') }} <span class="required">*</span></label>
            <el-select
              v-model="configForm.model_type"
              style="width: 100%"
              required
              @change="onModelTypeChange(configForm.model_type)">
              <el-option :label="$t('configuration.aiModel.selectModelType')" value="" disabled />
              <el-option v-for="type in modelTypes" :key="type" :label="$t('configuration.aiModel.modelTypes.' + type)" :value="type" />
            </el-select>
          </div>

          <div class="form-group">
            <label>{{ $t('configuration.aiModel.role') }} <span class="required">*</span></label>
            <el-select
              v-model="configForm.role"
              style="width: 100%"
              required>
              <el-option :label="$t('configuration.aiModel.selectRole')" value="" disabled />
              <el-option v-for="role in roles" :key="role" :label="$t('configuration.aiModel.roles.' + role)" :value="role" />
            </el-select>
          </div>
        </div>

        <div class="form-group">
          <label>{{ $t('configuration.aiModel.apiKey') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.api_key"
            type="password"
            show-password
            :placeholder="isEditing ? $t('configuration.aiModel.apiKeyPlaceholderEdit') : $t('configuration.aiModel.apiKeyPlaceholder')"
            :required="!isEditing" />
          <small v-if="isEditing && configForm.api_key && configForm.api_key.includes('*')" class="form-hint">
            {{ $t('configuration.aiModel.apiKeyMaskHint') }}
          </small>
        </div>

        <div class="form-group">
          <label>{{ $t('configuration.aiModel.baseUrl') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.base_url"
            :placeholder="$t('configuration.aiModel.baseUrlPlaceholder')"
            required />
          <small class="form-hint">
            {{ $t('configuration.aiModel.baseUrlHint') }}
          </small>
        </div>

        <div v-if="configForm.model_type === 'azure_openai'" class="form-group">
          <label>{{ $t('configuration.aiModel.azureApiVersion') }}</label>
          <el-input
            v-model="configForm.provider_extra.api_version"
            :placeholder="$t('configuration.aiModel.azureApiVersionPlaceholder')" />
          <small class="form-hint">
            {{ $t('configuration.aiModel.azureApiVersionHint') }}
          </small>
        </div>

        <div class="form-group">
          <label>{{ $t('configuration.aiModel.modelName') }} <span class="required">*</span></label>
          <el-input
            v-model="configForm.model_name"
            :placeholder="$t('configuration.aiModel.modelNamePlaceholder')"
            required>
            <template #append>
              <el-button :loading="isFetchingModels" @click="fetchAvailableModelsInModal">
                {{ isFetchingModels ? $t('configuration.aiModel.fetchingModels') : $t('configuration.aiModel.fetchModels') }}
              </el-button>
            </template>
          </el-input>
          <small class="form-hint">
            {{ $t('configuration.aiModel.modelNameHint') }}
          </small>
          <div v-if="availableModels.length > 0" class="model-list-selector">
            <div class="model-list-header">
              <label>{{ $t('configuration.aiModel.availableModels') }}</label>
              <el-button link type="primary" size="small" @click="showAvailableModelsPanel = !showAvailableModelsPanel">
                {{ showAvailableModelsPanel ? $t('configuration.aiModel.hideModelList') : $t('configuration.aiModel.showModelList') }}
              </el-button>
            </div>
            <small class="form-hint">
              {{ $t('configuration.aiModel.availableModelsHint', { count: filteredAvailableModels.length, total: availableModels.length }) }}
            </small>
            <div v-show="showAvailableModelsPanel" class="model-list-panel">
              <button
                v-for="model in filteredAvailableModels"
                :key="model"
                type="button"
                class="model-list-item"
                :class="{ active: configForm.model_name === model }"
                @click="selectModelFromList(model)">
                {{ model }}
              </button>
              <div v-if="filteredAvailableModels.length === 0" class="model-list-empty">
                {{ $t('configuration.aiModel.noFilteredModels') }}
              </div>
            </div>
          </div>
        </div>

        <div class="form-row form-row-3">
          <div class="form-group">
            <label>{{ $t('configuration.aiModel.maxTokens') }}</label>
            <el-input-number
              v-model="configForm.max_tokens"
              :min="0"
              controls-position="right"
              :placeholder="$t('configuration.aiModel.maxTokensHint')"
              style="width: 100%" />
          </div>

          <div class="form-group">
            <label>{{ $t('configuration.aiModel.temperature') }}</label>
            <el-input-number
              v-model="configForm.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              controls-position="right"
              style="width: 100%" />
          </div>

          <div class="form-group">
            <label>{{ $t('configuration.aiModel.topP') }}</label>
            <el-input-number
              v-model="configForm.top_p"
              :min="0"
              :max="1"
              :step="0.1"
              controls-position="right"
              style="width: 100%" />
          </div>
        </div>

        <div class="form-group">
          <el-checkbox v-model="configForm.is_active">
            {{ $t('configuration.aiModel.enableConfig') }}
          </el-checkbox>
        </div>
      </form>
      <template #footer>
        <el-button @click="closeModals">{{ $t('configuration.common.cancel') }}</el-button>
        <el-button :loading="isTestingInModal" @click="testConnectionInModal">
          {{ $t('configuration.aiModel.testConnection') }}
        </el-button>
        <el-button type="primary" :loading="isSaving" @click="saveConfig">
          {{ $t('configuration.aiModel.saveConfig') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 连接测试结果弹窗 -->
    <el-dialog
      v-model="showTestResult"
      :title="$t('configuration.aiModel.testResult')"
      width="560px">
      <div class="test-result" :class="{ success: testResult.success, error: !testResult.success }">
        <div class="result-icon">
          <el-icon v-if="testResult.success" :size="48" color="var(--aitest-success)"><CircleCheck /></el-icon>
          <el-icon v-else :size="48" color="var(--aitest-danger)"><CircleClose /></el-icon>
        </div>
        <div class="result-content">
          <h4>{{ testResult.success ? $t('configuration.aiModel.connectionSuccess') : $t('configuration.aiModel.connectionFailed') }}</h4>
          <p>{{ testResult.message }}</p>
          <div v-if="testResult.response" class="api-response">
            <label>{{ $t('configuration.aiModel.aiResponse') }}:</label>
            <p>{{ testResult.response }}</p>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'AIModelConfig',
  components: { PageHeader },
  setup() {
    const { t } = useI18n()
    return { t }
  },
  data() {
    return {
      configs: [], // 确保初始化为空数组
      isLoadingConfigs: false,
      showAddModal: false,
      showEditModal: false,
      showTestResult: false,
      isEditing: false,
      isSaving: false,
      isTestingInModal: false,
      isFetchingModels: false,
      isTestingConnection: false,
      testingConfigId: null,
      editingConfigId: null,
      availableModels: [],
      showAvailableModelsPanel: false,
      // 模型类型/角色选项（与后端 apps/ai/providers.py 保持一致）
      modelTypes: [
        'deepseek', 'qwen', 'siliconflow', 'zhipu', 'xiaomi', 'xiaomi_coding_plan',
        'openai', 'azure_openai', 'anthropic', 'google_gemini', 'other'
      ],
      roles: [
        'writer', 'reviewer', 'browser_use_text', 'api_testcase_generator'
      ],
      configForm: {
        name: '',
        model_type: '',
        role: '',
        api_key: '',
        base_url: '',
        model_name: '',
        max_tokens: 4096,
        temperature: 0.7,
        top_p: 0.9,
        is_active: true,
        provider_extra: {}
      },
      // 模型类型与API Base URL的映射关系（与后端 apps.ai.providers 保持一致）
      modelBaseUrlMap: {
        deepseek: 'https://api.deepseek.com',
        qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        siliconflow: 'https://api.siliconflow.cn/v1',
        zhipu: 'https://open.bigmodel.cn/api/paas/v4',
        xiaomi: 'https://api.xiaomimimo.com/v1',
        xiaomi_coding_plan: 'https://token-plan-cn.xiaomimimo.com/v1',
        openai: 'https://api.openai.com/v1',
        azure_openai: '',
        anthropic: 'https://api.anthropic.com/v1',
        google_gemini: 'https://generativelanguage.googleapis.com/v1beta/openai',
        other: ''
      },
      testResult: {
        success: false,
        message: '',
        response: ''
      }
    }
  },

  computed: {
    shouldShowModal() {
      return this.showAddModal || this.showEditModal
    },
    filteredAvailableModels() {
      const keyword = (this.configForm.model_name || '').trim().toLowerCase()
      if (!keyword) {
        return this.availableModels
      }
      return this.availableModels.filter(model => model.toLowerCase().includes(keyword))
    }
  },

  watch: {
    shouldShowModal(newVal, oldVal) {
      console.log('Modal visibility changed:', newVal, 'was:', oldVal)
    }
  },

  mounted() {
    // 确保组件初始状态正确
    this.initializeComponent()

    this.loadConfigs()
  },

  methods: {
    // 当模型类型改变时自动填充API Base URL
    onModelTypeChange(modelType) {
      this.availableModels = []
      this.showAvailableModelsPanel = false

      // 根据选择的模型类型自动填充base_url
      if (Object.prototype.hasOwnProperty.call(this.modelBaseUrlMap, modelType)) {
        this.configForm.base_url = this.modelBaseUrlMap[modelType]
      }
    },

    initializeComponent() {
      // 强制重置所有状态
      this.showAddModal = false
      this.showEditModal = false
      this.showTestResult = false
      this.isEditing = false
      this.isSaving = false
      this.isTestingInModal = false
      this.isFetchingModels = false
      this.isTestingConnection = false
      this.testingConfigId = null
      this.editingConfigId = null
      this.availableModels = []
      this.showAvailableModelsPanel = false
    },
    async loadConfigs() {
      this.isLoadingConfigs = true
      try {
        const response = await api.get('/requirement-analysis/ai-models/')

        // 处理分页API响应格式 {count: 1, next: null, previous: null, results: [...]}
        if (response.data && response.data.results && Array.isArray(response.data.results)) {
          this.configs = response.data.results
            .filter(config => config && config.id)
            .map(config => ({ ...config, toggling: false }))
        } else if (response.data && Array.isArray(response.data)) {
          // 直接数组格式的fallback
          this.configs = response.data
            .filter(config => config && config.id)
            .map(config => ({ ...config, toggling: false }))
        } else {
          console.warn('Unexpected API response format:', response.data)
          this.configs = []
        }
      } catch (error) {
        console.error('Failed to load configs:', error)
        this.configs = [] // 确保configs始终是数组

        if (error.response?.status === 401) {
          ElMessage.error(this.t('configuration.aiModel.messages.pleaseLogin'))
        } else {
          ElMessage.error(this.t('configuration.aiModel.messages.loadFailedDetail', { error: error.response?.data?.error || error.message }))
        }
      } finally {
        this.isLoadingConfigs = false
      }
    },

    openAddModal() {
      this.resetForm()
      this.isEditing = false
      this.showAddModal = true
    },

    resetForm() {
      // 使用Object.assign确保响应式
      Object.assign(this.configForm, {
        name: '',
        model_type: '',
        role: '',
        api_key: '',
        base_url: '',
        model_name: '',
        max_tokens: 4096,
        temperature: 0.7,
        top_p: 0.9,
        is_active: true,
        provider_extra: {}
      })
      this.availableModels = []
      this.showAvailableModelsPanel = false
    },

    editConfig(config) {
      this.isEditing = true
      this.editingConfigId = config.id
      this.configForm = {
        name: config.name,
        model_type: config.model_type,
        role: config.role,
        api_key: config.api_key_masked || '', // 显示掩码版本的API Key
        base_url: config.base_url,
        model_name: config.model_name,
        max_tokens: config.max_tokens,
        temperature: config.temperature,
        top_p: config.top_p,
        is_active: config.is_active,
        provider_extra: config.provider_extra || {}
      }
      this.availableModels = []
      this.showAvailableModelsPanel = false
      this.showEditModal = true
    },

    selectModelFromList(modelName) {
      this.configForm.model_name = modelName
    },

    async fetchAvailableModelsInModal() {
      if (!this.configForm.model_type) {
        ElMessage.warning(this.t('configuration.aiModel.messages.selectProviderFirst'))
        return
      }

      if (!this.configForm.api_key) {
        ElMessage.warning(this.t('configuration.aiModel.messages.enterApiKey'))
        return
      }

      if (!this.configForm.base_url) {
        ElMessage.warning(this.t('configuration.aiModel.messages.enterBaseUrl'))
        return
      }

      this.isFetchingModels = true

      try {
        let response

        if (this.isEditing && this.configForm.api_key.includes('*') && this.editingConfigId) {
          response = await api.get(
            `/requirement-analysis/ai-models/${this.editingConfigId}/available_models/`,
            { timeout: 90000 }
          )
        } else {
          response = await api.post(
            '/requirement-analysis/ai-models/available_models/',
            {
              name: this.configForm.name,
              model_type: this.configForm.model_type,
              role: this.configForm.role || 'writer',
              api_key: this.configForm.api_key,
              base_url: this.configForm.base_url,
              model_name: this.configForm.model_name || 'temp-model',
              max_tokens: this.configForm.max_tokens || null,
              temperature: this.configForm.temperature,
              top_p: this.configForm.top_p
            },
            { timeout: 90000 }
          )
        }

        this.availableModels = Array.isArray(response.data?.models) ? response.data.models : []

        if (this.availableModels.length === 0) {
          this.showAvailableModelsPanel = false
          ElMessage.warning(this.t('configuration.aiModel.messages.noModelsFound'))
          return
        }

        this.showAvailableModelsPanel = true
        ElMessage.success(this.t('configuration.aiModel.messages.fetchModelsSuccess', { count: this.availableModels.length }))
      } catch (error) {
        console.error('Failed to fetch available models:', error)
        this.availableModels = []
        this.showAvailableModelsPanel = false
        ElMessage.error(
          error.response?.data?.message ||
          error.response?.data?.error ||
          this.t('configuration.aiModel.messages.fetchModelsFailed', { error: error.message })
        )
      } finally {
        this.isFetchingModels = false
      }
    },

    async saveConfig() {
      // 验证必填字段
      const requiredFields = [
        { name: 'name', value: this.configForm.name },
        { name: 'model_type', value: this.configForm.model_type },
        { name: 'role', value: this.configForm.role },
        { name: 'api_key', value: this.configForm.api_key },
        { name: 'base_url', value: this.configForm.base_url },
        { name: 'model_name', value: this.configForm.model_name }
      ]

      const emptyFields = requiredFields.filter(field => !field.value || field.value.trim() === '')

      if (emptyFields.length > 0) {
        ElMessage.error(this.t('configuration.aiModel.messages.fillRequired', { fields: emptyFields.map(f => f.name).join(', ') }))
        return
      }

      // 检查唯一约束冲突（仅在创建新配置且is_active为true时）
      if (!this.isEditing && this.configForm.is_active) {
        const existingConfig = this.configs.find(config =>
          config.model_type === this.configForm.model_type &&
          config.role === this.configForm.role &&
          config.is_active === true
        )

        if (existingConfig) {
          ElMessage.error(this.t('configuration.aiModel.messages.duplicateConfig', { name: existingConfig.name }))
          return
        }
      }

      this.isSaving = true

      // max_tokens 留空 = 不限制（后端不向服务端传 max_tokens，由模型输出上限决定）
      const payload = { ...this.configForm, max_tokens: this.configForm.max_tokens || null }

      try {
        if (this.isEditing) {
          // 编辑时，如果API Key是掩码格式或为空，则不更新它
          const updateData = { ...payload }
          if (!updateData.api_key || updateData.api_key.includes('*')) {
            delete updateData.api_key
          }

          await api.patch(`/requirement-analysis/ai-models/${this.editingConfigId}/`, updateData)
          ElMessage.success(this.t('configuration.aiModel.messages.updateSuccess'))
        } else {
          await api.post('/requirement-analysis/ai-models/', payload)
          ElMessage.success(this.t('configuration.aiModel.messages.saveSuccess'))
        }

        this.closeModals()

        // 等待模态框关闭后再刷新数据
        await this.$nextTick()
        await this.loadConfigs()
      } catch (error) {
        console.error('Failed to save config:', error)
        console.error('Error response:', error.response?.data)

        if (error.response?.data) {
          const errors = error.response.data
          let errorMessage = this.t('configuration.aiModel.messages.saveFailed') + ': '

          // 处理唯一约束错误
          if (errors.non_field_errors) {
            const uniqueConstraintError = errors.non_field_errors.find(err =>
              err.includes('唯一集合') || err.includes('unique')
            )
            if (uniqueConstraintError) {
              errorMessage = this.t('configuration.aiModel.messages.conflictError')
            } else {
              errorMessage += errors.non_field_errors.join(', ')
            }
          } else {
            // 处理字段特定错误
            Object.keys(errors).forEach(field => {
              if (Array.isArray(errors[field])) {
                errorMessage += `${field}: ${errors[field].join(', ')}; `
              } else {
                errorMessage += `${field}: ${errors[field]}; `
              }
            })
          }

          ElMessage.error(errorMessage)
        } else {
          ElMessage.error(this.t('configuration.aiModel.messages.saveFailedDetail', { error: error.message }))
        }
      } finally {
        this.isSaving = false
      }
    },

    async deleteConfig(configId) {
      try {
        await ElMessageBox.confirm(
          this.t('configuration.aiModel.messages.deleteConfirm'),
          this.t('configuration.aiModel.messages.deleteTitle'),
          {
            confirmButtonText: this.t('configuration.common.confirm'),
            cancelButtonText: this.t('configuration.common.cancel'),
            type: 'warning'
          }
        )
      } catch {
        return
      }

      try {
        await api.delete(`/requirement-analysis/ai-models/${configId}/`)
        ElMessage.success(this.t('configuration.aiModel.messages.deleteSuccess'))
        this.loadConfigs()
      } catch (error) {
        console.error('Failed to delete config:', error)
        ElMessage.error(this.t('configuration.aiModel.messages.deleteFailedDetail', { error: error.response?.data?.error || error.message }))
      }
    },

    async toggleActive(config) {
      if (config.is_active) {
        const activeConfigs = this.configs.filter(c => c.id !== config.id && c.role === config.role && c.is_active)
        if (activeConfigs.length > 0) {
          const activeConfigNames = activeConfigs.map(c => c.name).join(', ')
          try {
            await ElMessageBox.confirm(
              this.t('configuration.aiModel.messages.toggleConfirm', { name: config.name, configs: activeConfigNames }),
              this.t('configuration.common.confirm'),
              {
                confirmButtonText: this.t('configuration.common.confirm'),
                cancelButtonText: this.t('configuration.common.cancel'),
                type: 'warning'
              }
            )
          } catch {
            config.is_active = false
            return
          }
        }
      }

      config.toggling = true

      try {
        await api.patch(`/requirement-analysis/ai-models/${config.id}/`, {
          is_active: config.is_active
        })

        ElMessage.success(
          this.t('configuration.aiModel.messages.toggleSuccess', {
            status: config.is_active ? this.t('configuration.common.enabled') : this.t('configuration.common.disabled')
          })
        )
        await this.loadConfigs()
      } catch (error) {
        console.error('Failed to toggle active status:', error)
        ElMessage.error(
          `${this.t('configuration.aiModel.messages.toggleFailed')}: ${error.response?.data?.error || error.message}`
        )
        config.is_active = !config.is_active
      } finally {
        config.toggling = false
      }
    },

    async testConnection(config) {
      this.isTestingConnection = true
      this.testingConfigId = config.id

      try {
        const response = await api.post(`/requirement-analysis/ai-models/${config.id}/test_connection/`)
        this.testResult = response.data
        this.showTestResult = true
      } catch (error) {
        console.error('Failed to test connection:', error)
        this.testResult = {
          success: false,
          message: error.response?.data?.message || error.message,
          response: ''
        }
        this.showTestResult = true
      } finally {
        this.isTestingConnection = false
        this.testingConfigId = null
      }
    },

    async testConnectionInModal() {
      if (!this.configForm.api_key) {
        ElMessage.warning(this.t('configuration.aiModel.messages.enterApiKey'))
        return
      }

      if (!this.configForm.model_type || !this.configForm.model_name) {
        ElMessage.warning(this.t('configuration.aiModel.messages.selectProviderModel'))
        return
      }

      if (!this.configForm.base_url) {
        ElMessage.warning(this.t('configuration.aiModel.messages.fillRequired', { fields: 'base_url' }))
        return
      }

      this.isTestingInModal = true

      try {
        let response

        // 编辑态且沿用原有 API Key 时，直接测试已保存配置
        if (this.isEditing && this.configForm.api_key.includes('*') && this.editingConfigId) {
          response = await api.post(
            `/requirement-analysis/ai-models/${this.editingConfigId}/test_connection/`,
            {},
            { timeout: 90000 }
          )
        } else {
          response = await api.post(
            '/requirement-analysis/ai-models/test_connection/',
            {
              name: this.configForm.name,
              model_type: this.configForm.model_type,
              role: this.configForm.role || 'writer',
              api_key: this.configForm.api_key,
              base_url: this.configForm.base_url,
              model_name: this.configForm.model_name,
              max_tokens: this.configForm.max_tokens || null,
              temperature: this.configForm.temperature,
              top_p: this.configForm.top_p
            },
            { timeout: 90000 }
          )
        }

        this.testResult = {
          success: response.data?.success ?? true,
          message: response.data?.message || this.t('configuration.aiModel.connectionSuccessMsg'),
          response: response.data?.response || ''
        }
        this.showTestResult = true
      } catch (error) {
        console.error('Failed to test connection in modal:', error)
        this.testResult = {
          success: false,
          message: error.response?.data?.message || error.response?.data?.error || error.message,
          response: ''
        }
        this.showTestResult = true
      } finally {
        this.isTestingInModal = false
      }
    },

    closeModals() {
      this.showAddModal = false
      this.showEditModal = false
      this.isEditing = false
      this.editingConfigId = null
      this.resetForm()
    },

    closeTestResult() {
      this.showTestResult = false
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
}

.section-header h2 {
  color: var(--aitest-text-1);
  margin: 0;
  font-size: var(--aitest-font-size-lg);
  font-weight: 600;
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
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
  gap: var(--aitest-space-3);
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

/* 厂商/角色徽章：胶囊外观 + token 语义色（不足处引用 tokens.scss 的 vendor 色对） */
.model-badge, .role-badge, .status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: var(--aitest-radius-full);
  font-size: var(--aitest-font-size-xs);
  font-weight: 600;
}

.model-badge.deepseek { background: var(--aitest-info-bg); color: var(--aitest-info); }
.model-badge.qwen { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.model-badge.siliconflow { background: var(--aitest-vendor-cyan-bg); color: var(--aitest-vendor-cyan); }
.model-badge.zhipu { background: var(--aitest-vendor-blue-bg); color: var(--aitest-vendor-blue); }
.model-badge.other { background: var(--aitest-neutral-bg); color: var(--aitest-neutral); }
.model-badge.xiaomi { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.model-badge.xiaomi_coding_plan { background: var(--aitest-vendor-orange-bg); color: var(--aitest-vendor-orange); }
.model-badge.azure_openai { background: var(--aitest-vendor-sky-bg); color: var(--aitest-vendor-sky); }
.model-badge.openai { background: var(--aitest-success-bg); color: var(--aitest-success); }
.model-badge.anthropic { background: var(--aitest-vendor-orange-bg); color: var(--aitest-vendor-orange); }
.model-badge.google_gemini { background: var(--aitest-vendor-blue-bg); color: var(--aitest-vendor-blue); }

.role-badge.writer { background: var(--aitest-success-bg); color: var(--aitest-success); }
.role-badge.reviewer { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.role-badge.tokenizer { background: var(--aitest-vendor-sky-bg); color: var(--aitest-vendor-sky); }
.role-badge.browser_use_text { background: var(--aitest-neutral-bg); color: var(--aitest-neutral); }
.role-badge.embedding { background: var(--aitest-vendor-pink-bg); color: var(--aitest-vendor-pink); }
.role-badge.api_testcase_generator { background: var(--aitest-info-bg); color: var(--aitest-info); }

.status-badge { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.status-badge.active { background: var(--aitest-success-bg); color: var(--aitest-success); }

.config-actions {
  display: flex;
  gap: var(--aitest-space-2);
  flex-wrap: wrap;
  align-items: center;
}

.config-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--aitest-space-3);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-1);
}

.detail-item label {
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-3);
  font-weight: 500;
}

.detail-item span {
  color: var(--aitest-text-1);
  font-size: var(--aitest-font-size-base);
  word-break: break-all;
}

/* 弹窗表单 */
.form-group {
  margin-bottom: var(--aitest-space-4);
}

.form-group label {
  display: block;
  margin-bottom: var(--aitest-space-2);
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--aitest-space-4);
}

.form-row-3 {
  grid-template-columns: 1fr 1fr 1fr;
}

.required { color: var(--aitest-danger); }

.form-hint {
  display: block;
  margin-top: var(--aitest-space-1);
  color: var(--aitest-text-3);
  font-size: var(--aitest-font-size-xs);
  font-style: italic;
}

.model-list-selector { margin-top: var(--aitest-space-3); }

.model-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--aitest-space-3);
}

.model-list-panel {
  margin-top: var(--aitest-space-3);
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius);
  background: var(--aitest-surface);
  padding: var(--aitest-space-2);
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-2);
}

.model-list-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--aitest-border);
  background: var(--aitest-surface);
  color: var(--aitest-text-2);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-2) var(--aitest-space-3);
  cursor: pointer;
  transition: all 0.15s;
  word-break: break-all;
  font-size: var(--aitest-font-size-sm);
  font-family: var(--aitest-font-mono);
}

.model-list-item:hover {
  border-color: var(--aitest-primary);
  background: var(--aitest-canvas);
}

.model-list-item.active {
  border-color: var(--aitest-primary);
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary-hover);
}

.model-list-empty {
  color: var(--aitest-text-3);
  padding: var(--aitest-space-2) var(--aitest-space-1);
  font-size: var(--aitest-font-size-sm);
}

/* 连接测试结果 */
.test-result {
  display: flex;
  gap: var(--aitest-space-5);
  align-items: flex-start;
}

.result-icon { flex-shrink: 0; }

.result-content h4 {
  margin: 0 0 var(--aitest-space-3) 0;
  color: var(--aitest-text-1);
}

.test-result.success .result-content h4 { color: var(--aitest-success); }
.test-result.error .result-content h4 { color: var(--aitest-danger); }

.api-response {
  margin-top: var(--aitest-space-4);
  padding: var(--aitest-space-4);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
  border-left: 3px solid var(--aitest-primary);
}

.api-response label {
  display: block;
  font-weight: 600;
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-2);
  font-size: var(--aitest-font-size-sm);
}

.api-response p {
  margin: 0;
  color: var(--aitest-text-2);
  line-height: var(--aitest-line-height-normal);
}

@media (max-width: 768px) {
  .configs-grid { grid-template-columns: 1fr; }
  .config-header { flex-direction: column; gap: var(--aitest-space-4); align-items: flex-start; }
  .config-details { grid-template-columns: 1fr; }
  .form-row, .form-row-3 { grid-template-columns: 1fr; }
}
</style>
