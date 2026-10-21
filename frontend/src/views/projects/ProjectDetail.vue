<template>
  <div class="page-container">
    <PageHeader :title="$t('project.projectDetail')">
      <template #actions>
        <el-button type="primary" @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon>
          {{ $t('common.back') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="card-container">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="$t('project.projectInfo')" name="info">
          <div v-if="project">
            <el-descriptions :column="2" border>
              <el-descriptions-item :label="$t('project.projectName')">{{ project.name }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.status')">
                <StatusTag :status="getStatusTag(project.status)" :text="getStatusText(project.status)" />
              </el-descriptions-item>
              <el-descriptions-item :label="$t('project.owner')">{{ project.owner?.username }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.createdAt')">{{ formatDate(project.created_at) }}</el-descriptions-item>
              <el-descriptions-item :label="$t('project.projectDescription')" :span="2">{{ project.description || $t('project.noDescription') }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="$t('project.projectMembers')" name="members">
          <div class="members-section">
            <el-button type="primary" @click="openAddMemberDialog()">{{ $t('project.addMember') }}</el-button>
            <el-table :data="project?.members || []" style="width: 100%">
              <el-table-column prop="user.username" :label="$t('project.username')" />
              <el-table-column prop="user.email" :label="$t('project.email')" />
              <el-table-column prop="role" :label="$t('project.role')" />
              <el-table-column prop="joined_at" :label="$t('project.joinedAt')">
                <template #default="{ row }">
                  {{ formatDate(row.joined_at) }}
                </template>
              </el-table-column>
              <el-table-column :label="$t('project.actions')" width="100">
                <template #default="{ row }">
                  <el-button type="danger" link size="small" @click="removeMember(row)">{{ $t('common.delete') }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="$t('project.environments')" name="environments">
          <div class="environments-section">
            <el-button type="primary" @click="showAddEnvDialog = true">{{ $t('project.addEnvironment') }}</el-button>
            <el-table :data="project?.environments || []" style="width: 100%">
              <el-table-column prop="name" :label="$t('project.environmentName')" />
              <el-table-column prop="base_url" :label="$t('project.baseUrl')" />
              <el-table-column prop="description" :label="$t('project.description')" />
              <el-table-column prop="is_default" :label="$t('project.defaultEnvironment')">
                <template #default="{ row }">
                  <StatusTag v-if="row.is_default" status="success" :text="$t('project.yes')" />
                  <span v-else>{{ $t('project.no') }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="showAddMemberDialog" :title="$t('project.addMember')" width="480px">
      <el-form :model="memberForm" label-width="90px">
        <el-form-item :label="$t('project.username')" required>
          <el-select
            v-model="memberForm.user_id"
            filterable
            :placeholder="$t('project.selectUser')"
            :loading="loadingUsers"
            style="width: 100%">
            <el-option
              v-for="u in userOptions"
              :key="u.id"
              :label="u.username"
              :value="u.id">
              <span>{{ u.username }}</span>
              <span class="user-option-email">{{ u.email }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('project.role')" required>
          <el-select v-model="memberForm.role" style="width: 100%">
            <el-option :label="$t('project.roleOwner')" value="owner" />
            <el-option :label="$t('project.roleAdmin')" value="admin" />
            <el-option :label="$t('project.roleDeveloper')" value="developer" />
            <el-option :label="$t('project.roleTester')" value="tester" />
            <el-option :label="$t('project.roleViewer')" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMemberDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="savingMember" @click="submitAddMember">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 添加环境弹窗 -->
    <el-dialog v-model="showAddEnvDialog" :title="$t('project.addEnvironment')" width="480px">
      <el-form :model="envForm" label-width="90px">
        <el-form-item :label="$t('project.environmentName')" required>
          <el-input v-model="envForm.name" />
        </el-form-item>
        <el-form-item :label="$t('project.baseUrl')" required>
          <el-input v-model="envForm.base_url" placeholder="https://api.example.com" />
        </el-form-item>
        <el-form-item :label="$t('project.description')">
          <el-input v-model="envForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="$t('project.defaultEnvironment')">
          <el-switch v-model="envForm.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddEnvDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="savingEnv" @click="submitAddEnv">{{ $t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import api from '@/utils/api'
import dayjs from 'dayjs'

const route = useRoute()
const { t } = useI18n()
const project = ref(null)
const activeTab = ref('info')
const showAddMemberDialog = ref(false)
const showAddEnvDialog = ref(false)

const userOptions = ref([])
const loadingUsers = ref(false)
const savingMember = ref(false)
const savingEnv = ref(false)
const memberForm = ref({ user_id: null, role: 'developer' })
const envForm = ref({ name: '', base_url: '', description: '', is_default: false })

// 拉取可选用户列表（已选过的成员过滤掉）
const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const response = await api.get('/users/')
    const users = response.data.results || response.data || []
    const existing = new Set((project.value?.members || []).map(m => m.user?.id))
    userOptions.value = users.filter(u => !existing.has(u.id))
  } catch (error) {
    userOptions.value = []
  } finally {
    loadingUsers.value = false
  }
}

const openAddMemberDialog = () => {
  memberForm.value = { user_id: null, role: 'developer' }
  loadUsers()
  showAddMemberDialog.value = true
}

const submitAddMember = async () => {
  if (!memberForm.value.user_id) {
    ElMessage.warning(t('project.selectUser'))
    return
  }
  if (!memberForm.value.role) {
    ElMessage.warning(t('project.roleRequired'))
    return
  }
  savingMember.value = true
  try {
    await api.post(`/projects/${route.params.id}/members/add/`, {
      user_id: memberForm.value.user_id,
      role: memberForm.value.role
    })
    ElMessage.success(t('project.memberAddSuccess'))
    showAddMemberDialog.value = false
    memberForm.value = { user_id: null, role: 'developer' }
    fetchProject()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('project.memberAddFailed'))
  } finally {
    savingMember.value = false
  }
}

const submitAddEnv = async () => {
  if (!envForm.value.name.trim()) {
    ElMessage.warning(t('project.envNameRequired'))
    return
  }
  if (!envForm.value.base_url.trim()) {
    ElMessage.warning(t('project.envUrlRequired'))
    return
  }
  savingEnv.value = true
  try {
    await api.post(`/projects/${route.params.id}/environments/`, {
      ...envForm.value,
      name: envForm.value.name.trim(),
      base_url: envForm.value.base_url.trim()
    })
    ElMessage.success(t('project.envAddSuccess'))
    showAddEnvDialog.value = false
    envForm.value = { name: '', base_url: '', description: '', is_default: false }
    fetchProject()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || t('project.envAddFailed'))
  } finally {
    savingEnv.value = false
  }
}

const fetchProject = async () => {
  try {
    const response = await api.get(`/projects/${route.params.id}/`)
    project.value = response.data
  } catch (error) {
    ElMessage.error(t('project.fetchDetailFailed'))
  }
}

const getStatusTag = (status) => {
  const tagMap = {
    active: 'active',
    paused: 'paused',
    completed: 'completed',
    archived: 'inactive'
  }
  return tagMap[status] || 'inactive'
}

const getStatusText = (status) => {
  const textMap = {
    active: t('project.active'),
    paused: t('project.paused'),
    completed: t('project.completed'),
    archived: t('project.archived')
  }
  return textMap[status] || status
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const removeMember = async (member) => {
  try {
    await api.delete(`/projects/${route.params.id}/members/${member.id}/`)
    ElMessage.success(t('project.memberDeleteSuccess'))
    fetchProject()
  } catch (error) {
    ElMessage.error(t('project.memberDeleteFailed'))
  }
}

onMounted(() => {
  fetchProject()
})
</script>

<style lang="scss" scoped>
.members-section,
.environments-section {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-5);
  padding: var(--aitest-space-5) 0;
}

.user-option-email {
  float: right;
  color: var(--aitest-text-3, #94A3B8);
  font-size: 12px;
}
</style>