<template>
  <div class="ui-env-config page-container">
    <PageHeader :title="$t('configuration.uiEnv.title')" :desc="$t('configuration.uiEnv.description')">
      <template #actions>
        <el-button type="primary" @click="checkEnvironment" :loading="checking">
          <el-icon><Refresh /></el-icon>
          {{ $t('configuration.uiEnv.checkEnvironment') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="card-container">
      <div v-if="lastCheckTime" class="last-check">
        {{ $t('configuration.uiEnv.lastCheckTime') }}: {{ lastCheckTime }}
      </div>

      <div v-if="environmentData" class="env-status-grid">
        <div class="info-row">
          <span class="info-label">{{ $t('configuration.uiEnv.operatingSystem') }}</span>
          <span class="info-value">{{ environmentData.os }}</span>
        </div>

        <!-- 系统浏览器 (Selenium) -->
        <div class="section-title">
          <h3>{{ $t('configuration.uiEnv.systemBrowsers') }}</h3>
        </div>
        <div class="browser-cards">
          <div v-for="browser in environmentData.system_browsers" :key="browser.name" class="browser-card">
              <div class="browser-content">
                <div class="browser-icon" v-html="getBrowserIcon(browser.name)"></div>
                <div class="browser-info">
                  <h3>{{ formatBrowserName(browser.name) }}</h3>
                  <div class="status-row">
                    <el-tag :type="browser.installed ? 'success' : 'info'">
                      {{ browser.installed ? (browser.version || $t('configuration.uiEnv.installed')) : $t('configuration.uiEnv.notInstalled') }}
                    </el-tag>
                  </div>
                </div>
              </div>
          </div>
        </div>

        <!-- Playwright 浏览器 -->
        <div class="section-title">
          <h3>{{ $t('configuration.uiEnv.playwrightBrowsers') }}</h3>
        </div>
        <div class="browser-cards">
          <div v-for="browser in environmentData.playwright_browsers" :key="browser.name" class="browser-card">
              <div class="browser-content">
                <div class="browser-icon" v-html="getBrowserIcon(browser.name)"></div>
                <div class="browser-info">
                  <h3>{{ formatBrowserName(browser.name) }}</h3>
                  <div class="status-row">
                    <el-tag :type="browser.installed ? 'success' : 'warning'">
                      {{ browser.installed ? (browser.version || $t('configuration.uiEnv.installed')) : $t('configuration.uiEnv.notInstalled') }}
                    </el-tag>
                  </div>
                </div>
              </div>
          </div>
        </div>
      </div>

      <div v-else class="loading-container">
        <el-skeleton :rows="4" animated />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const checking = ref(false)
const installing = ref(null)
const lastCheckTime = ref('')
const environmentData = ref(null)

// 内联 SVG 浏览器图标（离线可用；原远程 PNG 依赖 raw.githubusercontent.com，内网/受限网络下不显示）
const browserIconSvgs = {
  chrome: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 24 L4.3 20.5 A20 20 0 0 1 36.9 8.7 Z" fill="#EA4335"/>
    <path d="M24 24 L36.9 8.7 A20 20 0 0 1 30.8 42.8 Z" fill="#FBBC05"/>
    <path d="M24 24 L30.8 42.8 A20 20 0 0 1 4.3 20.5 Z" fill="#34A853"/>
    <circle cx="24" cy="24" r="8.5" fill="#fff"/>
    <circle cx="24" cy="24" r="6.5" fill="#4285F4"/>
  </svg>`,
  firefox: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="20" fill="#FF7139"/>
    <path d="M12.5 26 A12 12 0 1 1 27 36.6" stroke="#FFF3E0" stroke-width="4" fill="none" stroke-linecap="round"/>
  </svg>`,
  safari: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="20" fill="#0FB5EE"/>
    <circle cx="24" cy="24" r="15.5" fill="none" stroke="#FFFFFF" stroke-width="1.5" opacity="0.85"/>
    <path d="M33 15 L22.3 22.3 L25.7 25.7 Z" fill="#FF3B30"/>
    <path d="M15 33 L25.7 25.7 L22.3 22.3 Z" fill="#FFFFFF"/>
  </svg>`,
  edge: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="20" fill="#0078D7"/>
    <path d="M13 28.5 A12.5 12.5 0 1 1 35 32" stroke="#FFFFFF" stroke-width="3.5" fill="none" stroke-linecap="round" opacity="0.95"/>
  </svg>`,
  chromium: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="20" fill="#4285F4"/>
    <circle cx="24" cy="24" r="8.5" fill="#FFFFFF"/>
    <circle cx="24" cy="24" r="6.8" fill="#1A73E8"/>
  </svg>`,
  webkit: `<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="20" fill="#7986CB"/>
    <circle cx="28" cy="20" r="5" fill="#FFFFFF"/>
    <path d="M25 23 L15 33" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/>
  </svg>`
}

const getBrowserIcon = (name) => {
  return browserIconSvgs[name] || ''
}

const formatBrowserName = (name) => {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const checkEnvironment = async () => {
  checking.value = true
  try {
    const response = await api.get('/ui-automation/config/environment/check_environment/')
    environmentData.value = response.data
    lastCheckTime.value = new Date().toLocaleString()
    ElMessage.success(t('configuration.uiEnv.messages.checkSuccess'))
  } catch (error) {
    console.error('Environment check failed:', error)
    ElMessage.error(t('configuration.uiEnv.messages.checkFailed'))
  } finally {
    checking.value = false
  }
}

const installDriver = async (browserName) => {
  installing.value = browserName
  try {
    await api.post('/ui-automation/config/environment/install_driver/', { browser: browserName })
    ElMessage.success(t('configuration.uiEnv.messages.installSuccess', { browser: formatBrowserName(browserName) }))
    // Re-check environment
    await checkEnvironment()
  } catch (error) {
    console.error('Driver installation failed:', error)
    ElMessage.error(`${t('configuration.uiEnv.messages.installFailed')}: ${error.response?.data?.error || error.message}`)
  } finally {
    installing.value = null
  }
}

onMounted(() => {
  checkEnvironment()
})
</script>

<style scoped>
/* 页面骨架：page-container + PageHeader + card-container；留白由全局 .page-container 提供，根容器不私写 max-width */

.last-check {
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-3);
  margin-bottom: var(--aitest-space-4);
}

.loading-container {
  padding: var(--aitest-space-6);
}

.env-status-grid {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-5);
}

.info-row {
  display: flex;
  font-size: var(--aitest-font-size-base);
  line-height: var(--aitest-line-height-normal);
  padding-bottom: var(--aitest-space-3);
  border-bottom: 1px solid var(--aitest-border);
}

.info-label {
  color: var(--aitest-text-3);
  width: 88px;
  flex-shrink: 0;
}

.info-value {
  color: var(--aitest-text-1);
  font-weight: 500;
  word-break: break-all;
  min-width: 0;
}

.section-title {
  margin-top: var(--aitest-space-2);
  border-left: 3px solid var(--aitest-primary);
  padding-left: var(--aitest-space-3);
}

.section-title h3 {
  margin: 0;
  font-size: var(--aitest-font-size-md);
  font-weight: 600;
  color: var(--aitest-text-1);
}

.browser-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--aitest-space-4);
}

.browser-card {
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-card-border);
  border-radius: var(--aitest-card-radius);
  padding: var(--aitest-space-5);
  cursor: default;
}

.browser-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.browser-icon {
  width: 64px;
  height: 64px;
  margin-bottom: var(--aitest-space-3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.browser-icon :deep(svg) {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.browser-info {
  width: 100%;
  text-align: center;
}

.browser-info h3 {
  margin: 0 0 var(--aitest-space-3);
  color: var(--aitest-text-1);
  font-size: var(--aitest-font-size-md);
  font-weight: 600;
}

.status-row {
  display: flex;
  justify-content: center;
}
</style>
