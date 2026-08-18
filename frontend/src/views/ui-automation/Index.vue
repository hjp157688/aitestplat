<template>
  <div class="ui-automation-container">
    <!-- 页面头部 -->
    <PageHeader :title="$t('uiAutomation.nav.title')" />

    <!-- 子路由内容显示区域 -->
    <router-view></router-view>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'

// 初始化国际化
const { t } = useI18n()

// 主页面仅包含布局和router-view，所有具体内容已移至各个子页面
</script>

<style scoped>
.ui-automation-container {
  padding: var(--aitest-space-5);
  height: 100%;
  overflow-y: auto;
}

.stats-section {
  margin-bottom: var(--aitest-space-10);
}

.stat-card {
  height: 100%;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--aitest-space-5);
  color: white;
  font-size: 24px;
}

.stat-icon.bg-blue {
  background-color: var(--aitest-primary);
}

.stat-icon.bg-green {
  background-color: var(--aitest-success);
}

.stat-icon.bg-purple {
  background-color: #722ed1;
}

.stat-icon.bg-orange {
  background-color: var(--aitest-warning);
}

.stat-icon.bg-red {
  background-color: var(--aitest-danger);
}

.stat-icon.bg-cyan {
  background-color: #13c2c2;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--aitest-text-1);
  margin-bottom: var(--aitest-space-1);
}

.stat-label {
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-2);
}

.content-section {
  margin-bottom: var(--aitest-space-10);
}

.recent-activities {
  height: 100%;
}

.activities-list {
  max-height: 400px;
  overflow-y: auto;
}

.activity-item {
  display: flex;
  padding: var(--aitest-space-4) 0;
  border-bottom: 1px solid var(--aitest-surface-subtle);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--aitest-surface-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--aitest-space-4);
  color: var(--aitest-text-2);
}

.activity-content {
  flex: 1;
}

.activity-text {
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-1);
  margin-bottom: var(--aitest-space-1);
}

.activity-time {
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
}

.quick-actions {
  height: 100%;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--aitest-space-5);
}

.action-item {
  text-align: center;
  padding: var(--aitest-space-5);
  border-radius: var(--aitest-radius-lg);
  background-color: var(--aitest-surface-subtle);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-item:hover {
  background-color: var(--aitest-surface-subtle);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.action-item .action-icon {
  margin: 0 auto var(--aitest-space-4);
}

.action-label {
  font-size: var(--aitest-font-size-lg);
  color: var(--aitest-text-1);
  font-weight: 500;
}

.features-section {
  margin-bottom: var(--aitest-space-10);
}

.section-title {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: var(--aitest-space-5);
  color: var(--aitest-text-1);
}

.feature-card {
  height: 100%;
  padding: 30px;
  text-align: center;
}

.feature-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background-color: var(--aitest-surface-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--aitest-space-5);
  font-size: 36px;
  color: var(--aitest-primary);
}

.feature-title {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: var(--aitest-space-3);
  color: var(--aitest-text-1);
}

.feature-description {
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-2);
  line-height: 1.6;
}

.loading-container,
.empty-container {
  padding: var(--aitest-space-10) 0;
}
</style>