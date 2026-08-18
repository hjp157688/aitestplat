<template>
  <div class="page-container">
    <PageHeader :title="$t('reviewTemplate.title')">
      <template #actions>
        <el-button type="primary" @click="createTemplate">
          <el-icon><Plus /></el-icon>
          {{ $t('reviewTemplate.createTemplate') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="filter-bar">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item :label="$t('reviewTemplate.project')">
          <el-select v-model="filters.project" :placeholder="$t('reviewTemplate.selectProject')" clearable @change="fetchTemplates">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <div class="templates-grid">
      <el-card
        v-for="template in templates"
        :key="template.id"
        class="template-card"
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="template-name">{{ template.name }}</span>
            <div class="card-actions">
              <el-button type="primary" link size="small" @click="useTemplate(template)">{{ $t('reviewTemplate.useTemplate') }}</el-button>
              <el-button type="primary" link size="small" @click="editTemplate(template)">{{ $t('reviewTemplate.edit') }}</el-button>
              <el-popconfirm
                :title="$t('reviewTemplate.deleteConfirm')"
                @confirm="deleteTemplate(template.id)"
              >
                <template #reference>
                  <el-button type="danger" link size="small">{{ $t('reviewTemplate.delete') }}</el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </template>

        <div class="template-content">
          <div class="template-info">
            <div class="info-item">
              <span class="info-label">{{ $t('reviewTemplate.projectLabel') }}</span>
              <span class="info-value">
                {{ Array.isArray(template.project)
                    ? template.project.map(p => p.name).join(', ')
                    : (template.project?.name || $t('reviewTemplate.noData')) }}
              </span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('reviewTemplate.creatorLabel') }}</span>
              <span class="info-value">{{ template.creator?.username }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('reviewTemplate.createdAtLabel') }}</span>
              <span class="info-value">{{ formatDate(template.created_at) }}</span>
            </div>
          </div>

          <div class="template-description">
            {{ template.description || $t('reviewTemplate.noDescription') }}
          </div>

          <div class="template-checklist">
            <div class="checklist-title">{{ $t('reviewTemplate.checklistTitle') }}</div>
            <ul v-if="template.checklist?.length">
              <li v-for="(item, index) in template.checklist.slice(0, 3)" :key="index">
                {{ item }}
              </li>
              <li v-if="template.checklist.length > 3" class="more-items">
                {{ $t('reviewTemplate.moreItems', { count: template.checklist.length - 3 }) }}
              </li>
            </ul>
            <div v-else class="empty-checklist">{{ $t('reviewTemplate.noChecklist') }}</div>
          </div>

          <div class="template-reviewers">
            <div class="reviewers-title">{{ $t('reviewTemplate.reviewersTitle') }}</div>
            <div class="reviewers-list">
              <el-tag
                v-for="reviewer in template.default_reviewers"
                :key="reviewer.id"
                size="small"
                class="reviewer-tag"
              >
                {{ reviewer.username }}
              </el-tag>
              <span v-if="!template.default_reviewers?.length" class="empty-reviewers">
                {{ $t('reviewTemplate.noReviewers') }}
              </span>
            </div>
          </div>
        </div>
      </el-card>

      <div v-if="!templates.length && !loading" class="empty-templates">
        <el-empty :description="$t('reviewTemplate.noData')" />
      </div>
    </div>

    <!-- 模板表单对话框 -->
    <el-dialog
      v-model="templateDialogVisible"
      :title="isEdit ? $t('reviewTemplate.editTitle') : $t('reviewTemplate.createTitle')"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="120px">
        <el-row :gutter="24">
          <el-col :span="12">
            <el-form-item :label="$t('reviewTemplate.templateName')" prop="name">
              <el-input v-model="templateForm.name" :placeholder="$t('reviewTemplate.templateNamePlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('reviewTemplate.associatedProject')" prop="project">
              <el-select v-model="templateForm.project" :placeholder="$t('reviewTemplate.selectProject')" @change="onProjectChange">
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item :label="$t('reviewTemplate.templateDescription')">
          <el-input
            v-model="templateForm.description"
            type="textarea"
            :rows="3"
            :placeholder="$t('reviewTemplate.templateDescriptionPlaceholder')"
          />
        </el-form-item>

        <el-form-item :label="$t('reviewTemplate.checklist')">
          <div class="checklist-editor">
            <div
              v-for="(item, index) in templateForm.checklist"
              :key="index"
              class="checklist-item"
            >
              <el-input
                v-model="templateForm.checklist[index]"
                :placeholder="$t('reviewTemplate.checklistItemPlaceholder')"
              />
              <el-button
                type="danger"
                size="small"
                @click="removeChecklistItem(index)"
                :icon="Delete"
              />
            </div>
            <el-button type="primary" size="small" @click="addChecklistItem">
              <el-icon><Plus /></el-icon>
              {{ $t('reviewTemplate.addChecklistItem') }}
            </el-button>
          </div>
        </el-form-item>

        <el-form-item :label="$t('reviewTemplate.defaultReviewers')">
          <el-select
            v-model="templateForm.default_reviewers"
            multiple
            :placeholder="$t('reviewTemplate.selectDefaultReviewers')"
          >
            <el-option
              v-for="user in projectUsers"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="templateDialogVisible = false">{{ $t('reviewTemplate.cancel') }}</el-button>
        <el-button type="primary" @click="saveTemplate" :loading="saving">{{ $t('reviewTemplate.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import api from '@/utils/api'
import dayjs from 'dayjs'
import PageHeader from '@/components/common/PageHeader.vue'

const router = useRouter()
const { t } = useI18n()

const templates = ref([])
const projects = ref([])
const projectUsers = ref([])
const loading = ref(false)
const templateDialogVisible = ref(false)
const templateFormRef = ref()
const saving = ref(false)
const isEdit = ref(false)
const editingTemplateId = ref(null)

const filters = reactive({
  project: ''
})

const templateForm = reactive({
  name: '',
  description: '',
  project: '',
  checklist: [''],
  default_reviewers: []
})

const templateRules = {
  name: [{ required: true, message: t('reviewTemplate.nameRequired'), trigger: 'blur' }],
  project: [{ required: true, message: t('reviewTemplate.projectRequired'), trigger: 'change' }]
}

const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.project) {
      params.project = filters.project
    }

    const response = await api.get('/reviews/review-templates/', { params })
    templates.value = response.data.results || response.data || []
  } catch (error) {
    ElMessage.error(t('reviewTemplate.fetchListFailed'))
  } finally {
    loading.value = false
  }
}

const fetchProjects = async () => {
  try {
    const response = await api.get('/projects/')
    projects.value = response.data.results || response.data || []
  } catch (error) {
    ElMessage.error(t('reviewTemplate.fetchProjectsFailed'))
  }
}

const fetchProjectUsers = async () => {
  try {
    const response = await api.get('/auth/users/')
    projectUsers.value = response.data.results || response.data || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
    ElMessage.error(t('reviewTemplate.fetchUsersFailed'))
    projectUsers.value = []
  }
}

const createTemplate = () => {
  isEdit.value = false
  resetTemplateForm()
  templateDialogVisible.value = true
}

const editTemplate = (template) => {
  isEdit.value = true
  editingTemplateId.value = template.id
  
  templateForm.name = template.name
  templateForm.description = template.description
  // 处理project字段：如果是数组，取第一个ID；如果是单个对象，取其ID
  if (Array.isArray(template.project) && template.project.length > 0) {
    templateForm.project = template.project[0].id
  } else if (template.project && template.project.id) {
    templateForm.project = template.project.id
  } else {
    templateForm.project = ''
  }
  templateForm.checklist = template.checklist.length ? [...template.checklist] : ['']
  templateForm.default_reviewers = template.default_reviewers.map(u => u.id)
  
  // 用户列表已经在页面加载时获取，不需要重新获取
  templateDialogVisible.value = true
}

const useTemplate = (template) => {
  // 使用模板创建评审
  router.push({
    path: '/ai-generation/reviews/create',
    query: { template: template.id }
  })
}

const saveTemplate = async () => {
  if (!templateFormRef.value) return

  try {
    await templateFormRef.value.validate()
    saving.value = true

    const data = {
      ...templateForm,
      checklist: templateForm.checklist.filter(item => item.trim()),
      // 将project转换为数组格式，因为后端期望的是列表
      project: templateForm.project ? [templateForm.project] : []
    }

    if (isEdit.value) {
      await api.put(`/reviews/review-templates/${editingTemplateId.value}/`, data)
      ElMessage.success(t('reviewTemplate.updateSuccess'))
    } else {
      await api.post('/reviews/review-templates/', data)
      ElMessage.success(t('reviewTemplate.createSuccess'))
    }

    templateDialogVisible.value = false
    fetchTemplates()

  } catch (error) {
    console.error('保存模板失败:', error)
    ElMessage.error(isEdit.value ? t('reviewTemplate.updateFailed') : t('reviewTemplate.createFailed'))
  } finally {
    saving.value = false
  }
}

const deleteTemplate = async (id) => {
  try {
    await api.delete(`/reviews/review-templates/${id}/`)
    ElMessage.success(t('reviewTemplate.deleteSuccess'))
    fetchTemplates()
  } catch (error) {
    ElMessage.error(t('reviewTemplate.deleteFailed'))
  }
}

const resetTemplateForm = () => {
  templateForm.name = ''
  templateForm.description = ''
  templateForm.project = ''
  templateForm.checklist = ['']
  templateForm.default_reviewers = []
  editingTemplateId.value = null
}

const addChecklistItem = () => {
  templateForm.checklist.push('')
}

const removeChecklistItem = (index) => {
  if (templateForm.checklist.length > 1) {
    templateForm.checklist.splice(index, 1)
  }
}

const onProjectChange = (projectId) => {
  if (projectId) {
    // 清空默认评审人选择
    templateForm.default_reviewers = []
  }
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}


onMounted(() => {
  fetchTemplates()
  fetchProjects()
  fetchProjectUsers() // 页面加载时就获取所有用户
})
</script>

<style lang="scss" scoped>
.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--aitest-space-3) 0;

  :deep(.el-form-item) {
    margin-right: var(--aitest-space-4);
    margin-bottom: var(--aitest-space-3);
  }

  :deep(.el-select) {
    width: 240px;
  }
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: var(--aitest-space-5);
}

.template-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .template-name {
      font-weight: 600;
      font-size: var(--aitest-font-size-lg);
    }

    .card-actions {
      display: flex;
      gap: var(--aitest-space-2);
    }
  }
}

.template-content {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-4);

  .template-info {
    .info-item {
      display: flex;
      margin-bottom: var(--aitest-space-2);

      .info-label {
        min-width: 80px;
        color: var(--el-text-color-secondary);
        font-size: var(--aitest-font-size-md);
      }

      .info-value {
        color: var(--aitest-text-1);
        font-size: var(--aitest-font-size-md);
        min-width: 0;
      }
    }
  }

  .template-description {
    color: var(--el-text-color-regular);
    line-height: 1.6;
    font-size: var(--aitest-font-size-md);
  }

  .template-checklist {
    .checklist-title {
      font-weight: 500;
      margin-bottom: var(--aitest-space-2);
      color: var(--aitest-text-1);
    }

    ul {
      margin: 0;
      padding-left: var(--aitest-space-5);

      li {
        margin-bottom: var(--aitest-space-1);
        color: var(--el-text-color-regular);
        font-size: var(--aitest-font-size-md);

        &.more-items {
          color: var(--el-text-color-secondary);
          font-style: italic;
        }
      }
    }

    .empty-checklist {
      color: var(--el-text-color-secondary);
      font-size: var(--aitest-font-size-md);
      font-style: italic;
    }
  }

  .template-reviewers {
    .reviewers-title {
      font-weight: 500;
      margin-bottom: var(--aitest-space-2);
      color: var(--aitest-text-1);
    }

    .reviewers-list {
      .reviewer-tag {
        margin-right: var(--aitest-space-2);
        margin-bottom: var(--aitest-space-1);
      }

      .empty-reviewers {
        color: var(--el-text-color-secondary);
        font-size: var(--aitest-font-size-md);
        font-style: italic;
      }
    }
  }
}

.empty-templates {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.checklist-editor {
  .checklist-item {
    display: flex;
    gap: var(--aitest-space-2);
    margin-bottom: var(--aitest-space-2);
    align-items: center;
  }
}
</style>
