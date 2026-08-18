<template>
  <div class="page-header" :class="{ 'has-actions': !!$slots.actions }">
    <div class="page-header__text">
      <div v-if="eyebrow" class="page-eyebrow">{{ eyebrow }}</div>
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="desc" class="page-desc">{{ desc }}</p>
    </div>
    <div v-if="$slots.actions" class="header-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'PageHeader' })
defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  desc: { type: String, default: '' }
})
</script>
