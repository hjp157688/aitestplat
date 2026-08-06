<template>
  <el-dialog :model-value="modelValue" :title="t('apiTesting.knownData.title')"
             width="620px" @update:model-value="(v) => emit('update:modelValue', v)" @open="load">
    <div class="known-data-toolbar">
      <el-button type="primary" size="small" @click="openForm()">{{ t('apiTesting.knownData.add') }}</el-button>
    </div>
    <el-table :data="rows" size="small" border>
      <el-table-column prop="name" :label="t('apiTesting.knownData.name')" min-width="140" />
      <el-table-column prop="value" :label="t('apiTesting.knownData.value')" min-width="180" />
      <el-table-column prop="description" :label="t('apiTesting.knownData.description')" min-width="160" />
      <el-table-column :label="t('apiTesting.common.operation')" width="130">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openForm(row)">{{ t('apiTesting.knownData.edit') }}</el-button>
          <el-button link type="danger" size="small" @click="removeRow(row)">{{ t('apiTesting.knownData.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="formVisible" :title="form.id ? t('apiTesting.knownData.edit') : t('apiTesting.knownData.add')"
               width="460px" append-to-body destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item :label="t('apiTesting.knownData.name')" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item :label="t('apiTesting.knownData.value')" required>
          <el-input v-model="form.value" />
        </el-form-item>
        <el-form-item :label="t('apiTesting.knownData.description')">
          <el-input v-model="form.description" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">{{ t('apiTesting.common.cancel') }}</el-button>
        <el-button type="primary" @click="saveRow" :loading="saving">{{ t('apiTesting.common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import api from '@/utils/api'

const props = defineProps({
  modelValue: Boolean,
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const rows = ref([])
const formVisible = ref(false)
const saving = ref(false)
const form = ref({ id: null, name: '', value: '', description: '' })

async function load() {
  if (!props.projectId) { rows.value = []; return }
  try {
    const res = await api.get('/api-testing/api-known-data/', { params: { project: props.projectId } })
    rows.value = res.data.results || res.data || []
  } catch (e) {
    ElMessage.error(t('apiTesting.messages.error.loadFailed'))
  }
}

function openForm(row) {
  form.value = row ? { ...row } : { id: null, name: '', value: '', description: '' }
  formVisible.value = true
}

async function saveRow() {
  if (!form.value.name || !form.value.value) {
    ElMessage.warning(t('apiTesting.knownData.nameValueRequired'))
    return
  }
  saving.value = true
  try {
    const payload = { project: props.projectId, ...form.value }
    delete payload.id
    if (form.value.id) {
      await api.patch(`/api-testing/api-known-data/${form.value.id}/`, payload)
    } else {
      await api.post('/api-testing/api-known-data/', payload)
    }
    ElMessage.success(t('apiTesting.knownData.saved'))
    formVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || e.message)
  } finally { saving.value = false }
}

async function removeRow(row) {
  await ElMessageBox.confirm(
    t('apiTesting.knownData.confirmDelete'),
    t('apiTesting.messages.confirm.deleteTitle'),
    { type: 'warning' }
  )
  await api.delete(`/api-testing/api-known-data/${row.id}/`)
  ElMessage.success(t('apiTesting.knownData.deleted'))
  await load()
}
</script>