<template>
  <div class="page-container">
    <PageHeader :title="$t('testSuite.title')">
      <template #actions>
        <el-button type="primary">
          <el-icon><Plus /></el-icon>
          {{ $t('testSuite.newSuite') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="card-container">
      <EmptyState
        icon="FolderOpened"
        :title="$t('testSuite.inDevelopment')"
        desc="点击右上角「新建套件」开始创建测试套件" />
    </div>
  </div>
</template>

<script setup>
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
// 测试套件列表组件（占位）
</script>
