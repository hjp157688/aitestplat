<template>
  <el-dialog
    :model-value="modelValue"
    :title="mode === 'create'
      ? $t('apiTesting.interface.batchActions.createSuite')
      : $t('apiTesting.interface.batchActions.addToExistingSuite')"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="val => $emit('update:modelValue', val)"
  >
    <div class="create-suite-dialog">
      <el-radio-group v-model="mode" style="margin-bottom: 16px;">
        <el-radio value="create">{{ $t('apiTesting.interface.batchActions.createSuite') }}</el-radio>
        <el-radio value="add">{{ $t('apiTesting.interface.batchActions.addToExistingSuite') }}</el-radio>
      </el-radio-group>

      <el-form v-if="mode === 'create'" label-width="80px">
        <el-form-item :label="$t('apiTesting.automation.createTestSuite')" required>
          <el-input v-model="suiteName" :placeholder="$t('apiTesting.interface.batchActions.suiteNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.interface.batchActions.description')">
          <el-input v-model="description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="$t('apiTesting.interface.batchActions.environment')">
          <el-select v-model="environmentId" clearable :placeholder="$t('apiTesting.interface.batchActions.selectEnvironment')" style="width: 100%;">
            <el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-form v-else label-width="80px">
        <el-form-item :label="$t('apiTesting.automation.testSuite')" required>
          <el-select v-model="targetSuiteId" :placeholder="$t('apiTesting.interface.batchActions.selectSuite')" style="width: 100%;">
            <el-option v-for="suite in suites" :key="suite.id" :label="suite.name" :value="suite.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <div class="suite-tip">{{ $t('apiTesting.interface.batchActions.willAdd', { count: requestIds.length }) }}</div>
    </div>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ $t('apiTesting.common.cancel') }}</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">{{ $t('apiTesting.common.confirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getTestSuites,
  getEnvironments,
  createTestSuiteFromRequests,
  addRequestsToTestSuite,
} from '@/api/api-testing'

const props = defineProps({
  modelValue: Boolean,
  projectId: { type: Number, default: null },
  requestIds: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'created', 'added'])

const mode = ref('create')
const suiteName = ref('')
const description = ref('')
const environmentId = ref(null)
const targetSuiteId = ref(null)
const suites = ref([])
const environments = ref([])
const submitting = ref(false)

watch(() => props.modelValue, (val) => {
  if (!val) return
  mode.value = 'create'
  suiteName.value = ''
  description.value = ''
  environmentId.value = null
  targetSuiteId.value = null
  loadSuites()
  loadEnvironments()
})

const loadSuites = async () => {
  try {
    const { data } = await getTestSuites({ project: props.projectId, page_size: 100 })
    suites.value = data.results || data || []
  } catch (e) { /* ignore */ }
}

const loadEnvironments = async () => {
  try {
    const { data } = await getEnvironments({})
    const all = data.results || data || []
    environments.value = all.filter((env) =>
      env.scope === 'GLOBAL' ||
      (env.scope === 'LOCAL' && env.project === props.projectId)
    )
  } catch (e) { /* ignore */ }
}

const submit = async () => {
  if (mode.value === 'create') {
    if (!suiteName.value.trim()) {
      ElMessage.warning('请输入套件名称')
      return
    }
    submitting.value = true
    try {
      await createTestSuiteFromRequests({
        project_id: props.projectId,
        name: suiteName.value.trim(),
        description: description.value,
        environment_id: environmentId.value || null,
        request_ids: props.requestIds,
      })
      ElMessage.success('套件创建成功')
      emit('update:modelValue', false)
      emit('created')
    } catch (e) {
      ElMessage.error('套件操作失败')
    } finally {
      submitting.value = false
    }
  } else {
    if (!targetSuiteId.value) {
      ElMessage.warning('请选择目标套件')
      return
    }
    submitting.value = true
    try {
      await addRequestsToTestSuite(targetSuiteId.value, {
        request_ids: props.requestIds,
      })
      ElMessage.success('已加入套件')
      emit('update:modelValue', false)
      emit('added')
    } catch (e) {
      ElMessage.error('套件操作失败')
    } finally {
      submitting.value = false
    }
  }
}
</script>

<style scoped>
.create-suite-dialog {
  padding-top: 4px;
}
.suite-tip {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>