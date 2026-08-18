<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('apiTesting.automation.editAssertions')"
    width="680px"
    :close-on-click-modal="false"
    @update:model-value="val => $emit('update:modelValue', val)"
  >
    <div class="assertion-editor-dialog">
      <div class="assertions-header">
        <el-button size="small" type="primary" @click="addAssertion">
          <el-icon><Plus /></el-icon>
          {{ $t('apiTesting.interface.addAssertion') }}
        </el-button>
        <span class="assertion-tip" v-if="suiteRequest && (suiteRequest.request?.name)">
          {{ suiteRequest.request.name }}
        </span>
      </div>

      <div class="assertions-list">
        <div
          v-for="(assertion, index) in localAssertions"
          :key="index"
          class="assertion-item"
        >
          <div class="assertion-row">
            <el-input
              v-model="assertion.name"
              :placeholder="$t('apiTesting.interface.assertionName')"
              size="small"
              class="assertion-name"
            />
            <el-select
              v-model="assertion.type"
              :placeholder="$t('apiTesting.interface.selectAssertionType')"
              size="small"
              class="assertion-type"
              @change="onAssertionTypeChange(assertion)"
            >
              <el-option :label="$t('apiTesting.interface.assertionTypes.statusCode')" value="status_code" />
              <el-option :label="$t('apiTesting.interface.assertionTypes.responseTime')" value="response_time" />
              <el-option :label="$t('apiTesting.interface.assertionTypes.contains')" value="contains" />
              <el-option :label="$t('apiTesting.interface.assertionTypes.jsonPath')" value="json_path" />
              <el-option :label="$t('apiTesting.interface.assertionTypes.header')" value="header" />
              <el-option :label="$t('apiTesting.interface.assertionTypes.equals')" value="equals" />
            </el-select>
            <el-select
              v-if="assertionOperators(assertion.type).length"
              v-model="assertion.operator"
              size="small"
              class="assertion-operator"
            >
              <el-option
                v-for="op in assertionOperators(assertion.type)"
                :key="op"
                :label="assertionOperatorLabel(op)"
                :value="op"
              />
            </el-select>
            <el-button size="small" type="danger" circle @click="removeAssertion(index)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>

          <div class="assertion-params" v-if="assertion.type">
            <el-input-number
              v-if="assertion.type === 'status_code'"
              v-model="assertion.expected"
              :min="100"
              :max="599"
              size="small"
              :placeholder="$t('apiTesting.interface.expectedStatusCode')"
            />
            <el-input-number
              v-else-if="assertion.type === 'response_time'"
              v-model="assertion.expected"
              :min="1"
              size="small"
              :placeholder="$t('apiTesting.interface.maxResponseTime')"
            />
            <el-input
              v-else-if="assertion.type === 'contains'"
              v-model="assertion.expected"
              :placeholder="$t('apiTesting.interface.expectedContains')"
              size="small"
            />
            <div v-else-if="assertion.type === 'json_path'" class="param-row">
              <el-input
                v-model="assertion.json_path"
                :placeholder="$t('apiTesting.interface.jsonPathExample')"
                size="small"
              />
              <el-input
                v-if="!isExistenceOperator(assertion.operator)"
                v-model="assertion.expected"
                :placeholder="$t('apiTesting.interface.expectedValue')"
                size="small"
              />
            </div>
            <div v-else-if="assertion.type === 'header'" class="param-row">
              <el-input
                v-model="assertion.header_name"
                :placeholder="$t('apiTesting.interface.headerNameLabel')"
                size="small"
              />
              <el-input
                v-model="assertion.expected_value"
                :placeholder="$t('apiTesting.interface.expectedValue')"
                size="small"
              />
            </div>
            <el-input
              v-else-if="assertion.type === 'equals'"
              v-model="assertion.expected"
              :placeholder="$t('apiTesting.interface.expectedMatch')"
              size="small"
            />
          </div>
        </div>

        <div v-if="localAssertions.length === 0" class="no-assertions">
          <p>{{ $t('apiTesting.interface.noAssertions') }}</p>
          <el-button size="small" type="primary" @click="addAssertion">
            <el-icon><Plus /></el-icon>
            {{ $t('apiTesting.interface.addFirstAssertion') }}
          </el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ $t('apiTesting.common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="save">{{ $t('apiTesting.common.save') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import api from '@/utils/api'

const { t } = useI18n()

const props = defineProps({
  modelValue: Boolean,
  suiteRequest: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const localAssertions = ref([])
const saving = ref(false)

// 打开时深拷贝一份可编辑列表：步骤级断言为空但请求自带断言的（旧导入数据），
// 从 request.assertions 预填，避免"编辑起来是空的"
watch(() => props.modelValue, (val) => {
  if (!val || !props.suiteRequest) return
  const req = props.suiteRequest
  const source = (req.assertions && req.assertions.length
    ? req.assertions
    : (req.request && req.request.assertions)) || []
  localAssertions.value = JSON.parse(JSON.stringify(source))
})

const addAssertion = () => {
  localAssertions.value.push({
    name: `${t('apiTesting.interface.assertion')}${localAssertions.value.length + 1}`,
    type: 'status_code',
    operator: 'equals',
    expected: 200
  })
}

const removeAssertion = (index) => {
  localAssertions.value.splice(index, 1)
}

// 各断言类型支持的比较操作符（与后端 utils._compare / JSON_PATH_OPERATOR_CN 保持一致）
const ASSERTION_OPERATORS = {
  status_code: ['equals', 'not_equals', 'greater_than', 'less_than', 'greater_or_equal', 'less_or_equal'],
  response_time: ['less_or_equal', 'less_than'],
  json_path: ['equals', 'not_equals', 'contains', 'not_contains', 'exists', 'not_exists', 'greater_than', 'less_than', 'greater_or_equal', 'less_or_equal'],
  header: ['equals', 'not_equals', 'contains', 'not_contains', 'greater_than', 'less_than', 'greater_or_equal', 'less_or_equal'],
}

function assertionOperators(type) {
  return ASSERTION_OPERATORS[type] || []
}

function assertionOperatorLabel(op) {
  return t(`apiTesting.interface.assertionOperators.${op}`)
}

function isExistenceOperator(op) {
  return op === 'exists' || op === 'not_exists'
}

function normalizeOperator(type, operator) {
  const ops = ASSERTION_OPERATORS[type] || []
  if (ops.includes(operator)) return operator
  return ops[0] || 'equals'
}

const onAssertionTypeChange = (assertion) => {
  assertion.operator = normalizeOperator(assertion.type, assertion.operator)
  if (assertion.type === 'status_code') {
    assertion.expected = 200
  } else if (assertion.type === 'response_time') {
    assertion.expected = 1000
  } else if (assertion.type === 'contains') {
    assertion.expected = ''
  } else if (assertion.type === 'json_path') {
    assertion.json_path = ''
    assertion.expected = ''
  } else if (assertion.type === 'header') {
    assertion.header_name = ''
    assertion.expected_value = ''
  } else if (assertion.type === 'equals') {
    assertion.expected = ''
  }
}

const save = async () => {
  saving.value = true
  try {
    await api.put(`/api-testing/test-suite-requests/${props.suiteRequest.id}/`, {
      assertions: localAssertions.value,
    })
    ElMessage.success(t('apiTesting.automation.assertionSaved'))
    emit('saved', localAssertions.value)
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(t('apiTesting.automation.assertionSaveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.assertion-editor-dialog {
  padding-top: 4px;
}
.assertions-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.assertion-tip {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.assertions-list {
  max-height: 420px;
  overflow: auto;
}
.assertion-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.assertion-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.assertion-name {
  flex: 1;
}
.assertion-type {
  width: 140px;
}
.assertion-operator {
  width: 110px;
}
.assertion-params {
  margin-top: 8px;
}
.param-row {
  display: flex;
  gap: 8px;
}
.no-assertions {
  padding: 20px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.no-assertions p {
  margin: 0 0 10px 0;
}
</style>
