<template>
  <div class="dashboard-container">
    <!-- 数据概览 -->
    <div class="stats-section">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-blue">
                <el-icon><Folder /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value tab-nums">{{ projectCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.apiProjects') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-green">
                <el-icon><Link /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value tab-nums">{{ interfaceCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.interfaceCount') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-purple">
                <el-icon><Collection /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value tab-nums">{{ suiteCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.testSuites') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon bg-orange">
                <el-icon><Timer /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value tab-nums">{{ historyCount }}</div>
                <div class="stat-label">{{ $t('apiTesting.dashboard.executionRecords') }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
    
    <!-- 最近活动和快速操作 -->
    <el-row :gutter="20" class="content-section">
      <!-- 最近活动 -->
      <el-col :span="12">
      <el-card class="recent-activities" :title="$t('apiTesting.dashboard.operationLogs')" shadow="hover">
        <div v-if="loading" class="loading-container">
          <el-empty :description="$t('apiTesting.dashboard.loading')" />
        </div>
        <div v-else-if="operationLogs.length === 0" class="activities-list">
          <el-empty :description="$t('apiTesting.dashboard.noLogs')" />
        </div>
        <div v-else class="activities-list">
          <div v-for="log in operationLogs" :key="log.id" class="activity-item">
            <div class="activity-icon">
              <el-icon v-if="log.operation_type === 'create'" color="var(--aitest-success)"><Plus /></el-icon>
              <el-icon v-else-if="log.operation_type === 'edit'" color="var(--aitest-primary)"><Edit /></el-icon>
              <el-icon v-else-if="log.operation_type === 'delete'" color="var(--aitest-danger)"><Delete /></el-icon>
              <el-icon v-else-if="log.operation_type === 'execute'" color="#722ed1"><VideoPlay /></el-icon>
              <el-icon v-else color="var(--aitest-text-2)"><Operation /></el-icon>
            </div>
            <div class="activity-content">
              <div class="activity-description">{{ log.description }}</div>
              <div class="activity-meta">
                <span class="activity-user">{{ log.user_name || $t('apiTesting.dashboard.system') }}</span>
                <span class="activity-time">{{ formatTime(log.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-card>
      </el-col>
      
      <!-- 快速操作 -->
      <el-col :span="12">
        <el-card class="quick-actions" :title="$t('apiTesting.dashboard.quickActions.title')" shadow="hover">
          <div class="actions-grid">
            <div class="action-item" @click="goToProjects">
              <div class="action-icon bg-blue">
                <el-icon><Folder /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.projectManagement') }}</div>
            </div>
            <div class="action-item" @click="goToInterfaces">
              <div class="action-icon bg-green">
                <el-icon><Link /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.interfaceManagement') }}</div>
            </div>
            <div class="action-item" @click="goToAutomation">
              <div class="action-icon bg-cyan">
                <el-icon><VideoPlay /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.automationTesting') }}</div>
            </div>
            <div class="action-item" @click="goToHistory">
              <div class="action-icon bg-purple">
                <el-icon><Timer /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.requestHistory') }}</div>
            </div>
            <div class="action-item" @click="goToEnvironments">
              <div class="action-icon bg-orange">
                <el-icon><Setting /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.environmentManagement') }}</div>
            </div>
            <div class="action-item" @click="goToReports">
              <div class="action-icon bg-indigo">
                <el-icon><DataAnalysis /></el-icon>
              </div>
              <div class="action-label">{{ $t('apiTesting.dashboard.quickActions.testReport') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 核心功能介绍 -->
    <div class="features-section">
      <h2 class="section-title">{{ $t('apiTesting.dashboard.coreFeatures') }}</h2>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><Link /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.interfaceManagement.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.interfaceManagement.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><VideoPlay /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.automationTesting.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.automationTesting.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><Timer /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.scheduledTask.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.scheduledTask.description') }}</p>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="feature-card">
            <div class="feature-icon">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <h3 class="feature-title">{{ $t('apiTesting.dashboard.features.multiDimensionalReport.title') }}</h3>
            <p class="feature-description">{{ $t('apiTesting.dashboard.features.multiDimensionalReport.description') }}</p>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import {
  Folder, Link, Collection, Timer,
  VideoPlay, Setting, DataAnalysis,
  Plus, Edit, Delete, Operation
} from '@element-plus/icons-vue'
import router from '@/router'
import {
  getDashboardStats,
  getOperationLogs
} from '@/api/api-testing'

const { t } = useI18n()

// 统计数据
const projectCount = ref(0)
const interfaceCount = ref(0)
const suiteCount = ref(0)
const historyCount = ref(0)

const loading = ref(false)
const operationLogs = ref([])

// 加载数据
const loadDashboardData = async () => {
  loading.value = true
  try {
    // 并行加载统计数据和操作日志
    const [statsRes, logsRes] = await Promise.all([
      getDashboardStats(),
      getOperationLogs({ page_size: 20, ordering: '-created_at' })
    ])

    // 更新统计数据
    const stats = statsRes.data
    projectCount.value = stats.project_count || 0
    interfaceCount.value = stats.interface_count || 0
    suiteCount.value = stats.suite_count || 0
    historyCount.value = stats.history_count || 0
    
    // 更新操作日志
    operationLogs.value = logsRes.data.results || []

  } catch (error) {
    // ElMessage.error('加载仪表板数据失败')
    console.error('加载仪表板数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 导航到各功能页面
const goToProjects = () => {
  router.push('/api-testing/projects')
}

const goToInterfaces = () => {
  router.push('/api-testing/interfaces')
}

const goToAutomation = () => {
  router.push('/api-testing/automation')
}

const goToHistory = () => {
  router.push('/api-testing/history')
}

const goToEnvironments = () => {
  router.push('/api-testing/environments')
}

const goToReports = () => {
  router.push('/api-testing/reports')
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  // const diff = now - date
  if (isNaN(date.getTime())) return ''; // 处理无效日期
  const diff = Date.now() - date.getTime();

  // 小于1分钟
  if (diff < 60000) {
    return t('apiTesting.dashboard.timeFormat.justNow')
  }
  // 小于1小时
  if (diff < 3600000) {
    return t('apiTesting.dashboard.timeFormat.minutesAgo', { n: Math.floor(diff / 60000) })
  }
  // 小于1天
  if (diff < 86400000) {
    return t('apiTesting.dashboard.timeFormat.hoursAgo', { n: Math.floor(diff / 3600000) })
  }
  // 小于7天
  if (diff < 604800000) {
    return t('apiTesting.dashboard.timeFormat.daysAgo', { n: Math.floor(diff / 86400000) })
  }
  // 超过7天显示具体日期
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 组件挂载时加载数据
onMounted(() => {
  loadDashboardData()
})
</script>

<style scoped>
.dashboard-container {
  width: 100%;
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

.stat-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon :deep(.el-icon svg) {
  width: 100%;
  height: 60%;
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
  background-color: #fa8c16;
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

.quick-actions {
  height: 100%;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--aitest-space-4);
}

.action-item {
  text-align: center;
  padding: var(--aitest-space-4) var(--aitest-space-3);
  border-radius: var(--aitest-radius-lg);
  background-color: var(--aitest-surface-subtle);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-item:hover {
  background-color: var(--aitest-primary-subtle);
  transform: translateY(-2px);
  box-shadow: var(--aitest-shadow-sm);
}

.action-item .action-icon {
  margin: 0 auto var(--aitest-space-4);
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.action-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
}

.action-icon.bg-blue {
  background-color: var(--aitest-primary);
}

.action-icon.bg-green {
  background-color: var(--aitest-success);
}

.action-icon.bg-cyan {
  background-color: #13c2c2;
}

.action-icon.bg-purple {
  background-color: #722ed1;
}

.action-icon.bg-orange {
  background-color: #fa8c16;
}

.action-icon.bg-indigo {
  background-color: #597ef7;
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
  background-color: var(--aitest-primary-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--aitest-space-5);
  font-size: 36px;
  color: var(--aitest-primary);
}

.feature-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
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

.loading-container {
  padding: var(--aitest-space-10) 0;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  padding: var(--aitest-space-3) 0;
  border-bottom: 1px solid var(--aitest-border);
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--aitest-canvas);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--aitest-space-3);
  flex-shrink: 0;
}

.activity-icon :deep(.el-icon) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.activity-icon :deep(.el-icon svg) {
  width: 60%;
  height: 60%;
}

.activity-content {
  flex: 1;
  min-width: 0;
}

.activity-description {
  font-size: var(--aitest-font-size-md);
  color: var(--aitest-text-1);
  margin-bottom: var(--aitest-space-1);
  word-break: break-all;
}

.activity-meta {
  display: flex;
  align-items: center;
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
}

.activity-user {
  margin-right: var(--aitest-space-3);
}

.activity-time {
  color: var(--aitest-text-3);
}

@media screen and (max-width: 1920px) {
  .stats-section {
    margin-bottom: 36px;
  }
  
  .stat-content {
    height: 90px;
  }
  
  .stat-icon {
    width: 55px;
    height: 55px;
    font-size: 22px;
  }
  
  .stat-value {
    font-size: 26px;
  }
  
  .content-section {
    margin-bottom: 36px;
  }
  
  .features-section {
    margin-bottom: 36px;
  }
}

@media screen and (max-width: 1600px) {
  .stats-section {
    margin-bottom: var(--aitest-space-8);
  }
  
  .stat-content {
    height: 85px;
  }
  
  .stat-icon {
    width: 50px;
    height: 50px;
    font-size: var(--aitest-font-size-xl);
  }
  
  .stat-value {
    font-size: 24px;
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-8);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-8);
  }
  
  .section-title {
    font-size: 22px;
  }
}

@media screen and (max-width: 1440px) {
  .stats-section {
    margin-bottom: 28px;
  }
  
  .stat-content {
    height: 80px;
  }
  
  .stat-icon {
    width: 48px;
    height: 48px;
    font-size: 18px;
  }
  
  .stat-value {
    font-size: 22px;
  }
  
  .content-section {
    margin-bottom: 28px;
  }
  
  .features-section {
    margin-bottom: 28px;
  }
  
  .section-title {
    font-size: var(--aitest-font-size-xl);
  }
  
  .actions-grid {
    gap: var(--aitest-space-3);
  }
  
  .action-item {
    padding: var(--aitest-space-3) var(--aitest-space-2);
  }
  
  .action-icon {
    width: 45px;
    height: 45px;
    font-size: 22px;
  }
  
  .action-label {
    font-size: 15px;
  }
}

@media screen and (max-width: 1366px) {
  .stats-section {
    margin-bottom: var(--aitest-space-6);
  }
  
  .stat-content {
    height: 75px;
  }
  
  .stat-icon {
    width: 45px;
    height: 45px;
    font-size: 18px;
  }
  
  .stat-value {
    font-size: var(--aitest-font-size-xl);
  }
  
  .stat-label {
    font-size: var(--aitest-font-size-base);
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-6);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-6);
  }
  
  .section-title {
    font-size: 18px;
  }
  
  .activities-list {
    max-height: 350px;
  }
  
  .actions-grid {
    gap: var(--aitest-space-3);
  }
  
  .action-item {
    padding: var(--aitest-space-3) var(--aitest-space-2);
  }
  
  .action-icon {
    width: 40px;
    height: 40px;
    font-size: var(--aitest-font-size-xl);
  }
  
  .action-label {
    font-size: var(--aitest-font-size-md);
  }
  
  .feature-card {
    padding: var(--aitest-space-5);
  }
  
  .feature-icon {
    width: 70px;
    height: 70px;
    font-size: 32px;
  }
  
  .feature-title {
    font-size: var(--aitest-font-size-lg);
  }
  
  .feature-description {
    font-size: var(--aitest-font-size-base);
  }
}

@media screen and (max-width: 1280px) {
  .stats-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .stat-content {
    height: 70px;
  }
  
  .stat-icon {
    width: 42px;
    height: 42px;
    font-size: var(--aitest-font-size-lg);
  }
  
  .stat-value {
    font-size: 18px;
  }
  
  .stat-label {
    font-size: var(--aitest-font-size-sm);
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .section-title {
    font-size: 18px;
  }
  
  .activities-list {
    max-height: 300px;
  }
  
  .action-item {
    padding: var(--aitest-space-2) var(--aitest-space-1);
  }
  
  .action-icon {
    width: 38px;
    height: 38px;
    font-size: 18px;
  }
  
  .action-label {
    font-size: var(--aitest-font-size-base);
  }
  
  .feature-card {
    padding: var(--aitest-space-4);
  }
  
  .feature-icon {
    width: 60px;
    height: 60px;
    font-size: 28px;
  }
}

@media screen and (max-width: 1024px) {
  .stats-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .stat-content {
    height: 65px;
  }
  
  .stat-icon {
    width: 40px;
    height: 40px;
    font-size: var(--aitest-font-size-lg);
  }
  
  .stat-value {
    font-size: var(--aitest-font-size-lg);
  }
  
  .stat-label {
    font-size: var(--aitest-font-size-sm);
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-5);
  }
  
  .section-title {
    font-size: var(--aitest-font-size-lg);
  }
  
  .activities-list {
    max-height: 280px;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aitest-space-3);
  }
  
  .action-item {
    padding: var(--aitest-space-3) var(--aitest-space-2);
  }
  
  .action-label {
    font-size: var(--aitest-font-size-base);
  }
  
  .feature-card {
    padding: var(--aitest-space-3);
  }
  
  .feature-icon {
    width: 50px;
    height: 50px;
    font-size: 24px;
  }
  
  .feature-title {
    font-size: var(--aitest-font-size-md);
  }
  
  .feature-description {
    font-size: var(--aitest-font-size-sm);
  }
}

@media screen and (max-width: 768px) {
  .stats-section {
    margin-bottom: var(--aitest-space-4);
  }
  
  .stat-content {
    height: 60px;
  }
  
  .stat-icon {
    width: 35px;
    height: 35px;
    font-size: var(--aitest-font-size-md);
  }
  
  .stat-value {
    font-size: var(--aitest-font-size-md);
  }
  
  .stat-label {
    font-size: var(--aitest-font-size-xs);
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-4);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-4);
  }
  
  .section-title {
    font-size: var(--aitest-font-size-lg);
    margin-bottom: var(--aitest-space-4);
  }
  
  .activities-list {
    max-height: 250px;
  }
  
  .activity-item {
    padding: var(--aitest-space-3) 0;
  }
  
  .activity-icon {
    width: 28px;
    height: 28px;
  }
  
  .activity-description {
    font-size: var(--aitest-font-size-base);
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aitest-space-2);
  }
  
  .action-item {
    padding: var(--aitest-space-2) var(--aitest-space-1);
  }
  
  .action-icon {
    width: 35px;
    height: 35px;
    font-size: var(--aitest-font-size-lg);
  }
  
  .action-label {
    font-size: var(--aitest-font-size-sm);
  }
  
  .feature-card {
    padding: var(--aitest-space-3);
  }
  
  .feature-icon {
    width: 45px;
    height: 45px;
    font-size: var(--aitest-font-size-xl);
  }
  
  .feature-title {
    font-size: var(--aitest-font-size-base);
  }
  
  .feature-description {
    font-size: var(--aitest-font-size-xs);
  }
}

@media screen and (max-width: 480px) {
  .stats-section {
    margin-bottom: var(--aitest-space-3);
  }
  
  .stat-content {
    height: 55px;
  }
  
  .stat-icon {
    width: 30px;
    height: 30px;
    font-size: var(--aitest-font-size-sm);
  }
  
  .stat-value {
    font-size: var(--aitest-font-size-base);
  }
  
  .stat-label {
    font-size: 10px;
  }
  
  .content-section {
    margin-bottom: var(--aitest-space-3);
  }
  
  .features-section {
    margin-bottom: var(--aitest-space-3);
  }
  
  .section-title {
    font-size: var(--aitest-font-size-md);
    margin-bottom: var(--aitest-space-3);
  }
  
  .activities-list {
    max-height: 200px;
  }
  
  .activity-item {
    padding: var(--aitest-space-2) 0;
  }
  
  .activity-icon {
    width: 24px;
    height: 24px;
  }
  
  .activity-description {
    font-size: var(--aitest-font-size-sm);
  }
  
  .activity-meta {
    font-size: var(--aitest-font-size-xs);
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aitest-space-2);
  }
  
  .action-item {
    padding: var(--aitest-space-2) 3px;
  }
  
  .action-icon {
    width: 30px;
    height: 30px;
    font-size: var(--aitest-font-size-md);
  }
  
  .action-label {
    font-size: var(--aitest-font-size-xs);
  }
  
  .feature-card {
    padding: var(--aitest-space-2);
  }
  
  .feature-icon {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }
  
  .feature-title {
    font-size: var(--aitest-font-size-sm);
  }
  
  .feature-description {
    font-size: 10px;
  }
}
</style>
