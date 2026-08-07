<template>
  <div class="empty-state">
    <div class="empty-icon">
      <el-icon :size="24"><component :is="icon" /></el-icon>
    </div>
    <div class="empty-title">{{ title }}</div>
    <div v-if="desc || $slots.desc" class="empty-hint">
      <slot name="desc">{{ desc }}</slot>
    </div>
    <div v-if="$slots.actions" class="empty-state__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'EmptyState' })
defineProps({
  icon: { type: [String, Object], required: true },
  title: { type: String, required: true },
  desc: { type: String, default: '' }
})
</script>
