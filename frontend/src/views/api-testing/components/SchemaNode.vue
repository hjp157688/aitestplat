<template>
  <div class="schema-node">
    <div class="schema-node-header" @click="expanded = !expanded" v-if="hasChildren">
      <el-icon><component :is="expanded ? 'ArrowDown' : 'ArrowRight'" /></el-icon>
      <span class="schema-prop-name">{{ name }}</span>
      <span class="schema-prop-type">{{ typeLabel }}</span>
      <el-tag v-if="isRequired" size="small" type="danger">required</el-tag>
      <span v-if="exampleText" class="schema-prop-example">example: {{ exampleText }}</span>
      <span v-if="defaultText !== undefined" class="schema-prop-default">default: {{ defaultText }}</span>
      <span v-if="description" class="schema-prop-desc">{{ description }}</span>
    </div>
    <div class="schema-node-leaf" v-else>
      <span class="schema-prop-name">{{ name }}</span>
      <span class="schema-prop-type">{{ typeLabel }}</span>
      <el-tag v-if="isRequired" size="small" type="danger">required</el-tag>
      <span v-if="exampleText" class="schema-prop-example">example: {{ exampleText }}</span>
      <span v-if="defaultText !== undefined" class="schema-prop-default">default: {{ defaultText }}</span>
      <span v-if="description" class="schema-prop-desc">{{ description }}</span>
    </div>
    <div v-if="expanded && hasChildren" class="schema-node-children">
      <SchemaNode
        v-for="(propSchema, propName) in children"
        :key="propName"
        :schema="propSchema"
        :name="propName"
        :required-fields="schema.required || []"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  schema: { type: Object, default: () => ({}) },
  name: { type: String, default: '' },
  requiredFields: { type: Array, default: () => [] },
})

const expanded = ref(true)

const isRequired = computed(() => props.requiredFields.includes(props.name))
const description = computed(() => props.schema.description || '')

// 示例/默认值展示：object → JSON 字符串，其余 → String
const stringifyValue = (v) => {
  if (v === undefined || v === null) return undefined
  return typeof v === 'object' ? JSON.stringify(v) : String(v)
}
const exampleText = computed(() => {
  const ex = props.schema.example ?? props.schema['x-example']
  return stringifyValue(ex) || ''
})
const defaultText = computed(() => stringifyValue(props.schema.default))

const schemaType = computed(() => {
  if (props.schema.enum) return 'enum'
  return props.schema.type || 'object'
})

const typeLabel = computed(() => {
  const t = schemaType.value
  if (t === 'enum') return `enum: ${props.schema.enum?.join(', ')}`
  if (t === 'string' && props.schema.format) return `string(${props.schema.format})`
  return t
})

const hasChildren = computed(() => {
  return schemaType.value === 'object' && props.schema.properties
})

const children = computed(() => {
  if (schemaType.value === 'object' && props.schema.properties) {
    return props.schema.properties
  }
  return {}
})
</script>

<style scoped>
.schema-node { margin-left: 16px; font-size: 13px; }
.schema-node-header { display: flex; align-items: center; gap: 6px; cursor: pointer; padding: 4px 0; }
.schema-node-leaf { display: flex; align-items: center; gap: 6px; padding: 4px 0; }
.schema-prop-name { font-weight: 500; color: #268bd2; }
.schema-prop-type { color: var(--el-text-color-secondary); font-family: monospace; }
.schema-prop-desc { color: var(--el-text-color-regular); font-size: 12px; margin-left: 8px; }
.schema-prop-example { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; font-family: monospace; }
.schema-prop-default { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; font-family: monospace; }
.schema-node-children { border-left: 1px dashed #e4e7ed; }
.schema-section { margin-bottom: 16px; }
.schema-section h4 { margin: 0 0 8px; font-size: 14px; }
.schema-status-group h5 { margin: 8px 0 4px; font-size: 13px; color: var(--el-color-primary); }
</style>