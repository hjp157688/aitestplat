<template>
  <div class="page-container">
    <PageHeader :title="$t('testcase.detail')">
      <template #actions>
        <el-button @click="backToList">{{ $t('common.back') }}</el-button>
        <el-button type="primary" @click="editTestCase">{{ $t('common.edit') }}</el-button>
      </template>
    </PageHeader>

    <div class="card-container" v-if="testcase">
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="$t('testcase.caseTitle')" :span="2">{{ testcase.title }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.priority')">
          <el-tag size="small" :type="priorityType(testcase.priority)">{{ getPriorityText(testcase.priority) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.testType')">{{ getTypeText(testcase.test_type) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.project')">{{ testcase.project?.name || $t('testcase.noProject') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.relatedVersions')" :span="2">
          <div v-if="testcase.versions && testcase.versions.length > 0" class="version-tags">
            <el-tag
              v-for="version in testcase.versions"
              :key="version.id"
              size="small"
              :type="version.is_baseline ? 'warning' : 'info'"
              class="version-tag"
            >
              {{ version.name }}
            </el-tag>
          </div>
          <span v-else class="no-version">{{ $t('testcase.noVersion') }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.author')">{{ testcase.author?.username }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.createdAt')" :span="2">{{ formatDate(testcase.created_at) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.caseDescription')" :span="2">{{ testcase.description || $t('testcase.noDescription') }}</el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.preconditions')" :span="2">
          <div v-html="testcase.preconditions || $t('testcase.none')"></div>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('testcase.steps')" :span="2">
          <div v-if="parsedSteps.length" class="steps-display">
            <div v-for="(step, idx) in parsedSteps" :key="idx" class="step-item">
              <span class="step-num">{{ idx + 1 }}.</span>
              <div class="step-body">
                <div class="step-desc">{{ step.desc }}</div>
                <div v-if="step.expect" class="step-expect">{{ $t('testcase.expectPrefix') }}: {{ step.expect }}</div>
              </div>
            </div>
          </div>
          <span v-else>{{ $t('testcase.none') }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const testcase = ref(null)

// 解析结构化步骤 [{desc, expect}]
const parsedSteps = computed(() => {
  if (!testcase.value?.steps) return []
  try {
    const arr = JSON.parse(testcase.value.steps)
    return Array.isArray(arr) ? arr : []
  } catch (e) {
    return [{ desc: testcase.value.steps, expect: '' }]
  }
})

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    testcase.value = response.data
  } catch (error) {
    ElMessage.error(t('testcase.fetchDetailFailed'))
  }
}

const backToList = () => {
  router.push('/ai-generation/testcases')
}

const editTestCase = () => {
  router.push(`/ai-generation/testcases/${route.params.id}/edit`)
}

const getPriorityText = (priority) => {
  const textMap = {
    low: t('testcase.low'),
    medium: t('testcase.medium'),
    high: t('testcase.high'),
    critical: t('testcase.critical')
  }
  return textMap[priority] || priority
}

// 优先级 → el-tag type（低=成功色 / 中=警告色 / 高、紧急=危险色）
const priorityType = (priority) => {
  const map = { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }
  return map[priority] || 'info'
}

const getTypeText = (type) => {
  const textMap = {
    functional: t('testcase.functional'),
    integration: t('testcase.integration'),
    api: t('testcase.api'),
    ui: t('testcase.ui'),
    performance: t('testcase.performance'),
    security: t('testcase.security')
  }
  return textMap[type] || '-'
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchTestCase()
})
</script>

<style lang="scss" scoped>
.steps-display {
  width: 100%;

  .step-item {
    display: flex;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px dashed var(--aitest-border);

    &:last-child {
      border-bottom: none;
    }

    .step-num {
      flex-shrink: 0;
      color: var(--aitest-text-2);
      font-weight: 600;
    }

    .step-body {
      flex: 1;

      .step-expect {
        color: var(--aitest-text-2);
        margin-top: 2px;
      }
    }
  }
}

.version-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--aitest-space-2);

  .version-tag {
    margin: 0;
  }
}

.no-version {
  color: var(--aitest-text-3);
  font-size: var(--aitest-font-size-sm);
  font-style: italic;
}

.steps-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: var(--aitest-text-1);
  font-family: inherit;
}
</style>