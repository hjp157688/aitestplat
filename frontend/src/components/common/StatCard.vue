<template>
  <div class="stat-card" :class="accent ? `stat-card--accent-${accent}` : ''">
    <div class="stat-card__label">{{ label }}</div>
    <div class="stat-card__value">{{ value }}</div>
    <div v-if="hint" class="stat-card__hint">{{ hint }}</div>
  </div>
</template>

<script setup>
defineOptions({ name: 'StatCard' })
defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '' },
  hint: { type: String, default: '' },
  accent: { type: String, default: '' } // success|warning|danger|info
})
</script>
