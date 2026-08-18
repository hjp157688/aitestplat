<template>
  <span class="status-tag" :class="status">
    <span class="status-tag__dot" />
    {{ text }}
  </span>
</template>

<script setup>
defineOptions({ name: 'StatusTag' })
defineProps({
  status: { type: String, required: true }, // active|inactive|paused|completed|success|warning|danger|info
  text: { type: String, required: true }
})
</script>
