<template>
  <div class="home-container">
    <div class="portal">
      <!-- PC：语言、用户分开 -->
      <header class="portal-header header-actions-pc">
        <el-dropdown @command="handleLanguageChange" class="language-dropdown">
          <span class="el-dropdown-link dropdown-link">
            <span class="lang-dot">{{ currentLanguage === 'zh-cn' ? '中' : 'EN' }}</span>
            <span class="dropdown-text">{{ $t('home.language.current') }}</span>
            <el-icon class="dd-caret"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">
                {{ $t('home.language.zhCN') }}
              </el-dropdown-item>
              <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">
                {{ $t('home.language.en') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-dropdown @command="handleCommand">
          <span class="el-dropdown-link dropdown-link">
            <el-avatar :size="30" :src="userStore.user?.avatar" :icon="UserFilled" class="user-avatar" />
            <span class="dropdown-text">{{ userStore.user?.username || $t('home.user') }}</span>
            <el-icon class="dd-caret"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">{{ $t('home.logout') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <!-- 移动端：合并菜单 -->
      <header class="portal-header header-actions-mobile">
        <el-dropdown trigger="click" @command="handleHeaderCommand">
          <span class="user-menu-trigger">
            <span class="avatar-wrap">
              <el-avatar :size="26" :src="userStore.user?.avatar" :icon="UserFilled" class="user-avatar" />
              <span class="lang-badge">{{ currentLanguage === 'zh-cn' ? '中' : 'EN' }}</span>
            </span>
            <el-icon class="trigger-arrow"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">
                {{ $t('home.language.zhCN') }}
              </el-dropdown-item>
              <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">
                {{ $t('home.language.en') }}
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                {{ $t('home.logout') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <main class="portal-main">
        <!-- Hero：按时段问候 + 品牌字标 + 签名渐变 -->
        <section class="hero">
          <p class="hero-eyebrow">{{ greeting }}</p>
          <h1 class="hero-title">
            <span class="brand">AITest</span><span class="brand-accent">Plat</span>
          </h1>
          <p class="hero-subtitle">{{ $t('home.subtitle') }}</p>
          <div class="hero-rule"></div>
        </section>

        <!-- 模块导航 -->
        <nav class="module-grid" aria-label="modules">
          <div class="module-card module--ai" @click="handleNavigate('ai')" role="button" tabindex="0" :style="{ animationDelay: stagger(0) }">
            <div class="module-tile"><el-icon><MagicStick /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.aiCaseGeneration') }}</h3>
              <p>{{ $t('home.aiCaseGenerationDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--api" @click="handleNavigate('api')" role="button" tabindex="0" :style="{ animationDelay: stagger(1) }">
            <div class="module-tile"><el-icon><Link /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.apiTesting') }}</h3>
              <p>{{ $t('home.apiTestingDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--ui" @click="handleNavigate('ui')" role="button" tabindex="0" :style="{ animationDelay: stagger(2) }">
            <div class="module-tile"><el-icon><Monitor /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.uiAutomation') }}</h3>
              <p>{{ $t('home.uiAutomationDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--defects" @click="handleNavigate('defects')" role="button" tabindex="0" :style="{ animationDelay: stagger(3) }">
            <div class="module-tile"><el-icon><Tickets /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.defectManagement') }}</h3>
              <p>{{ $t('home.defectManagementDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--data" @click="handleNavigate('data')" role="button" tabindex="0" :style="{ animationDelay: stagger(4) }">
            <div class="module-tile"><el-icon><DataLine /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.dataFactory') }}</h3>
              <p>{{ $t('home.dataFactoryDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--app" @click="handleNavigate('app')" role="button" tabindex="0" :style="{ animationDelay: stagger(5) }">
            <div class="module-tile"><el-icon><Cellphone /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.appAutomation') }}</h3>
              <p>{{ $t('home.appAutomationDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--ai-intelligent" @click="handleNavigate('ai-intelligent')" role="button" tabindex="0" :style="{ animationDelay: stagger(6) }">
            <div class="module-tile"><el-icon><Cpu /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.aiIntelligentMode') }}</h3>
              <p>{{ $t('home.aiIntelligentModeDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>

          <div class="module-card module--config" @click="handleNavigate('config')" role="button" tabindex="0" :style="{ animationDelay: stagger(7) }">
            <div class="module-tile"><el-icon><Setting /></el-icon></div>
            <div class="module-body">
              <h3>{{ $t('home.configCenter') }}</h3>
              <p>{{ $t('home.configCenterDesc') }}</p>
            </div>
            <el-icon class="module-arrow"><Right /></el-icon>
          </div>
        </nav>
      </main>
    </div>

    <el-dialog
      v-model="mobileDialogVisible"
      class="mobile-tip-dialog"
      :title="$t('home.mobileTipTitle')"
      width="88%"
      align-center
      :close-on-click-modal="true"
      append-to-body
    >
      <div class="mobile-tip-dialog-body">
        <div class="dialog-icon-wrap">
          <el-icon><Monitor /></el-icon>
        </div>
        <p class="dialog-desc">{{ $t('home.mobileTipDesc') }}</p>
      </div>
      <template #footer>
        <el-button type="primary" class="dialog-confirm-btn" @click="mobileDialogVisible = false">
          {{ $t('home.mobileTipOk') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { track } from '@/utils/tracker'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Link, Monitor, DataLine, Cpu, Setting, UserFilled, ArrowDown, Right, Cellphone, Tickets } from '@element-plus/icons-vue'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const appStore = useAppStore()

// 当前语言
const currentLanguage = computed(() => appStore.language)
const isMobile = ref(false)
const mobileTipDismissed = ref(false)
const MOBILE_BREAKPOINT = 768
const MOBILE_TIP_STORAGE_KEY = 'aitestplat_home_mobile_tip_seen'

// 按时段问候
const greeting = computed(() => {
  const hour = new Date().getHours()
  const key = hour < 12 ? 'goodMorning' : hour < 18 ? 'goodAfternoon' : 'goodEvening'
  return t(`home.${key}`, { name: userStore.user?.username || t('home.user') })
})

// 卡片交错入场延迟（毫秒）
const stagger = (i) => `${i * 45}ms`

const dismissMobileTip = () => {
  mobileTipDismissed.value = true
  try {
    localStorage.setItem(MOBILE_TIP_STORAGE_KEY, '1')
  } catch {
    // ignore quota / private mode
  }
}

const mobileDialogVisible = computed({
  get: () => isMobile.value && !mobileTipDismissed.value,
  set: (val) => {
    if (!val) dismissMobileTip()
  }
})

const updateMobileTip = () => {
  isMobile.value = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches
}

onMounted(() => {
  try {
    if (localStorage.getItem(MOBILE_TIP_STORAGE_KEY) === '1') {
      mobileTipDismissed.value = true
    }
  } catch {
    // ignore
  }
  updateMobileTip()
  window.addEventListener('resize', updateMobileTip)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMobileTip)
})

const handleLanguageChange = (lang) => {
  appStore.setLanguage(lang)
}

const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  }
}

const handleHeaderCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
    return
  }
  if (command === 'zh-cn' || command === 'en') {
    appStore.setLanguage(command)
  }
}

const handleLogout = () => {
  ElMessageBox.confirm(t('home.logoutConfirm'), t('common.tips'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
    type: 'warning'
  }).then(() => {
    userStore.logout()
    router.push('/login')
    ElMessage.success(t('home.logoutSuccess'))
  }).catch(() => {})
}

const handleNavigate = (type) => {
  const routes = {
    'ai': '/ai-generation/requirement-analysis',
    'api': '/api-testing/dashboard',
    'ui': '/ui-automation/dashboard',
    'defects': '/defects/dashboard',
    'app': '/app-automation/dashboard',
    'ai-intelligent': '/ai-intelligent-mode/testing',
    'config': '/configuration/ai-model',
    'data': '/data-factory'
  }

  if (routes[type]) {
    track('module_card_click', {
      event_type: 'click',
      module: 'home',
      page_path: '/home',
      target_path: routes[type],
      metadata: {
        card_type: type
      }
    })
    // 应用内跳转，避免每次都新开标签页
    router.push(routes[type])
  }
}
</script>

<style scoped lang="scss">
.home-container {
  min-height: 100vh;
  background: var(--aitest-canvas);
  position: relative;
  overflow: hidden;
  display: flex;
  justify-content: center;

  /* 环境光斑：靛蓝→天青签名渐变，克制缓淡 */
  &::before,
  &::after {
    content: '';
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    filter: blur(60px);
  }
  &::before {
    width: 560px;
    height: 560px;
    top: -220px;
    right: -120px;
    background: radial-gradient(circle, rgba(79, 70, 229, 0.14) 0%, transparent 68%);
  }
  &::after {
    width: 480px;
    height: 480px;
    top: -160px;
    left: -140px;
    background: radial-gradient(circle, rgba(14, 165, 233, 0.1) 0%, transparent 70%);
  }
}

.portal {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1160px;
  padding: var(--aitest-space-8) var(--aitest-space-6) var(--aitest-space-12);
}

/* ===== 顶栏 ===== */
.portal-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--aitest-space-5);
}

.header-actions-pc {
  .dropdown-link {
    display: inline-flex;
    align-items: center;
    gap: var(--aitest-space-2);
    cursor: pointer;
    color: var(--aitest-text-2);
    padding: var(--aitest-space-1) var(--aitest-space-3);
    border: 1px solid transparent;
    border-radius: var(--aitest-radius-full);
    transition: color 0.2s, border-color 0.2s, background 0.2s;
    outline: none;

    &:focus-visible {
      outline: 2px solid var(--aitest-primary);
      outline-offset: 2px;
    }

    &:hover {
      color: var(--aitest-primary);
      background: var(--aitest-surface);
      border-color: var(--aitest-border);
      box-shadow: var(--aitest-shadow-xs);
    }

    .dropdown-text {
      font-size: var(--aitest-font-size-md);
    }

    .dd-caret {
      font-size: 12px;
      color: var(--aitest-text-3);
    }
  }

  .lang-dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: var(--aitest-radius-sm);
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    font-size: var(--aitest-font-size-xs);
    font-weight: 600;
    line-height: 1;
  }

  .user-avatar {
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    --el-avatar-bg-color: var(--aitest-primary-subtle);
  }
}

.header-actions-mobile {
  display: none;
}

.user-menu-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--aitest-space-2);
  cursor: pointer;
  color: var(--aitest-text-2);
  padding: var(--aitest-space-1) var(--aitest-space-3) var(--aitest-space-1) var(--aitest-space-1);
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-full);
  box-shadow: var(--aitest-shadow-xs);
  transition: color 0.2s, border-color 0.2s, box-shadow 0.2s;
  outline: none;

  &:focus-visible {
    outline: 2px solid var(--aitest-primary);
    outline-offset: 2px;
  }

  &:hover {
    color: var(--aitest-primary);
    border-color: var(--aitest-border-strong);
    box-shadow: var(--aitest-shadow-sm);
  }

  .avatar-wrap {
    position: relative;
    display: inline-flex;
    flex-shrink: 0;
  }

  .user-avatar {
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    --el-avatar-bg-color: var(--aitest-primary-subtle);
  }

  .lang-badge {
    position: absolute;
    right: -4px;
    bottom: -3px;
    font-size: 9px;
    line-height: 1.4;
    font-weight: 700;
    color: var(--aitest-primary);
    background: var(--aitest-surface);
    border: 1px solid var(--aitest-border-strong);
    border-radius: 50%;
    padding: 0 2px;
  }

  .trigger-arrow {
    font-size: 12px;
    color: var(--aitest-text-3);
  }
}

/* ===== Hero ===== */
.hero {
  max-width: 720px;
  padding: var(--aitest-space-16) 0 var(--aitest-space-12);

  .hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: var(--aitest-space-2);
    margin: 0 0 var(--aitest-space-3);
    font-size: var(--aitest-font-size-md);
    color: var(--aitest-text-2);
    letter-spacing: 0.02em;
    font-weight: 500;

    &::before {
      content: '';
      width: 18px;
      height: 2px;
      border-radius: 2px;
      background: linear-gradient(90deg, var(--aitest-primary), var(--aitest-accent));
    }
  }

  .hero-title {
    margin: 0;
    font-size: clamp(2.75rem, 6vw, 4.5rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1.05;
    color: var(--aitest-text-1);

    .brand-accent {
      background: linear-gradient(90deg, var(--aitest-primary) 0%, var(--aitest-accent) 100%);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
      color: var(--aitest-accent);
    }
  }

  .hero-subtitle {
    margin: var(--aitest-space-4) 0 0;
    font-size: var(--aitest-font-size-lg);
    color: var(--aitest-text-2);
    line-height: var(--aitest-line-height-relaxed);
  }

  .hero-rule {
    margin-top: var(--aitest-space-10);
    height: 1px;
    background: linear-gradient(90deg, var(--aitest-border) 0%, var(--aitest-border-strong) 100%);
  }
}

/* ===== 模块网格 ===== */
.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--aitest-space-4);
}

.module-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--aitest-space-4);
  padding: var(--aitest-space-5);
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  box-shadow: var(--aitest-shadow-xs);
  overflow: hidden;
  opacity: 0;
  animation: rise 0.5s ease forwards;

  /* 左缘强调条：hover 时显现 */
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, var(--aitest-primary), var(--aitest-accent));
    opacity: 0;
    transform: scaleY(0);
    transform-origin: top;
    transition: opacity 0.25s ease, transform 0.25s ease;
  }

  &:hover {
    transform: translateY(-3px);
    border-color: var(--aitest-border-strong);
    box-shadow: var(--aitest-shadow-md);

    &::before {
      opacity: 1;
      transform: scaleY(1);
    }
  }

  &:focus-visible {
    outline: 2px solid var(--aitest-primary);
    outline-offset: 2px;
  }

  .module-tile {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: var(--aitest-radius);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    background: var(--tile-bg, var(--aitest-neutral-bg));
    color: var(--tile-color, var(--aitest-text-2));
    transition: transform 0.25s ease;
  }

  .module-body {
    min-width: 0;

    h3 {
      margin: 0 0 var(--aitest-space-1);
      font-size: var(--aitest-font-size-lg);
      font-weight: 600;
      color: var(--aitest-text-1);
      line-height: var(--aitest-line-height-normal);
    }

    p {
      margin: 0;
      font-size: var(--aitest-font-size-sm);
      color: var(--aitest-text-2);
      line-height: var(--aitest-line-height-normal);
    }
  }

  .module-arrow {
    position: absolute;
    right: var(--aitest-space-4);
    bottom: var(--aitest-space-4);
    font-size: 15px;
    color: var(--aitest-primary);
    opacity: 0;
    transform: translateX(-6px);
    transition: opacity 0.25s ease, transform 0.25s ease;
  }

  &:hover .module-arrow {
    opacity: 1;
    transform: translateX(0);
  }

  &:hover .module-tile {
    transform: scale(1.06);
  }
}

/* 各模块瓷砖色：仅使用令牌族（靛蓝/天青/石板 + 语义色），不引入游离色 */
.module--ai {
  --tile-bg: var(--aitest-primary-subtle);
  --tile-color: var(--aitest-primary);
}
.module--api {
  --tile-bg: var(--aitest-info-bg);
  --tile-color: var(--aitest-info);
}
.module--ui {
  --tile-bg: var(--aitest-primary-subtle);
  --tile-color: var(--aitest-prim-indigo-500);
}
.module--defects {
  --tile-bg: var(--aitest-danger-bg);
  --tile-color: var(--aitest-danger);
}
.module--data {
  --tile-bg: var(--aitest-neutral-bg);
  --tile-color: var(--aitest-prim-slate-500);
}
.module--app {
  --tile-bg: var(--aitest-primary-subtle);
  --tile-color: var(--aitest-prim-indigo-700);
}
.module--ai-intelligent {
  --tile-bg: var(--aitest-info-bg);
  --tile-color: var(--aitest-accent);
}
.module--config {
  --tile-bg: var(--aitest-neutral-bg);
  --tile-color: var(--aitest-prim-slate-500);
}

/* 入场动画 */
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

/* ===== 平板：≤1024 ===== */
@media screen and (max-width: 1024px) {
  .portal {
    padding: var(--aitest-space-8) var(--aitest-space-5) var(--aitest-space-10);
  }

  .hero {
    padding: var(--aitest-space-12) 0 var(--aitest-space-10);
  }

  .module-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}

/* ===== 移动端：≤768 ===== */
@media screen and (max-width: 768px) {
  .home-container {
    background: var(--aitest-canvas);
  }

  .portal {
    padding: calc(var(--aitest-space-4) + env(safe-area-inset-top)) var(--aitest-space-4) var(--aitest-space-8);
  }

  .header-actions-pc {
    display: none;
  }

  .header-actions-mobile {
    display: flex;
    justify-content: flex-end;
  }

  .hero {
    padding: var(--aitest-space-10) 0 var(--aitest-space-8);

    .hero-eyebrow {
      font-size: var(--aitest-font-size-sm);
    }

    .hero-title {
      font-size: clamp(2.1rem, 9vw, 3rem);
    }

    .hero-subtitle {
      font-size: var(--aitest-font-size-md);
    }

    .hero-rule {
      margin-top: var(--aitest-space-8);
    }
  }

  .module-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--aitest-space-3);
  }

  .module-card {
    flex-direction: column;
    gap: var(--aitest-space-3);
    padding: var(--aitest-space-4);
    border-radius: var(--aitest-radius);

    .module-tile {
      width: 40px;
      height: 40px;
      font-size: 18px;
    }

    .module-body {
      h3 {
        font-size: var(--aitest-font-size-md);
      }

      p {
        font-size: var(--aitest-font-size-xs);
      }
    }

    .module-arrow {
      display: none;
    }
  }
}

/* ===== 小屏移动端：≤480 ===== */
@media screen and (max-width: 480px) {
  .portal {
    padding: calc(var(--aitest-space-3) + env(safe-area-inset-top)) var(--aitest-space-3) var(--aitest-space-6);
  }

  .module-card {
    padding: var(--aitest-space-3);
  }
}

/* 减少动效：禁用入场与位移动画 */
@media (prefers-reduced-motion: reduce) {
  .module-card {
    opacity: 1;
    animation: none;
  }

  .home-container::before,
  .home-container::after {
    filter: none;
  }
}
</style>

<style lang="scss">
.mobile-tip-dialog.el-dialog {
  max-width: 340px;
  border-radius: var(--aitest-radius-lg);
  overflow: hidden;

  .el-dialog__header {
    padding: var(--aitest-space-5) var(--aitest-space-5) var(--aitest-space-2);
    margin-right: 0;
    text-align: center;

    .el-dialog__title {
      font-size: var(--aitest-font-size-lg);
      font-weight: 600;
      color: var(--aitest-text-1);
      line-height: 1.4;
    }

    .el-dialog__headerbtn {
      top: var(--aitest-space-4);
      right: var(--aitest-space-4);
    }
  }

  .el-dialog__body {
    padding: var(--aitest-space-1) var(--aitest-space-6) var(--aitest-space-2);
  }

  .el-dialog__footer {
    padding: var(--aitest-space-2) var(--aitest-space-5) var(--aitest-space-5);

    .dialog-confirm-btn {
      width: 100%;
      height: 40px;
      border-radius: var(--aitest-radius-full);
      font-size: var(--aitest-font-size-md);
    }
  }
}

.mobile-tip-dialog-body {
  text-align: center;

  .dialog-icon-wrap {
    width: 56px;
    height: 56px;
    margin: 0 auto var(--aitest-space-4);
    border-radius: var(--aitest-radius);
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
  }

  .dialog-desc {
    margin: 0;
    font-size: var(--aitest-font-size-md);
    color: var(--aitest-text-2);
    line-height: 1.6;
  }
}
</style>
