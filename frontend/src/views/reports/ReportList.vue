<template>
  <div class="page-container">
    <PageHeader :title="$t('report.title')" />

    <div class="card-container">
      <div class="empty-state">
        <el-empty :description="$t('report.inDevelopment')" />
      </div>
    </div>
  </div>
</template>

<script setup>
import PageHeader from '@/components/common/PageHeader.vue'
// Test report list component
</script>