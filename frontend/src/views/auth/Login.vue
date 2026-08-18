<template>
  <div class="login-container">
    <!-- 语言切换 -->
    <div class="lang-switcher">
      <el-dropdown @command="handleLanguageChange" class="language-dropdown">
        <span class="el-dropdown-link">
          <span class="lang-icon">{{ currentLanguage === 'zh-cn' ? '🇨🇳' : '🇺🇸' }}</span>
          <span class="lang-text">{{ currentLanguage === 'zh-cn' ? $t('auth.languageZhCN') : $t('auth.languageEn') }}</span>
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="zh-cn" :disabled="currentLanguage === 'zh-cn'">
              🇨🇳 {{ $t('auth.languageZhCN') }}
            </el-dropdown-item>
            <el-dropdown-item command="en" :disabled="currentLanguage === 'en'">
              🇺🇸 English
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <div class="login-card">
      <!-- 品牌锁 -->
      <div class="brand-lockup">
        <img :src="logoSvg" alt="AITestPlat" class="brand-logo-img" />
        <div class="brand-eyebrow">{{ $t('auth.appTagline') }}</div>
      </div>

      <div class="form-header">
        <h2>{{ $t('auth.welcomeBack') }}</h2>
        <p>{{ $t('auth.loginSubtitle') }}</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="login-form"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username" :label="$t('auth.username')">
          <el-input
            v-model="form.username"
            :placeholder="$t('auth.usernamePlaceholder')"
            size="large"
            :prefix-icon="User"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item prop="password" :label="$t('auth.password')">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('auth.passwordPlaceholder')"
            size="large"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item class="submit-item">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="login-button"
          >
            {{ $t('auth.login') }}
          </el-button>
        </el-form-item>

        <div class="form-footer">
          <span>{{ $t('auth.noAccount') }}</span>
          <router-link to="/register" class="toggle-link">{{ $t('auth.signUpNow') }}</router-link>
        </div>
      </el-form>
    </div>

    <div class="bottom-info">
      <p>{{ $t('auth.copyright') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { User, Lock, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import logoSvg from '@/assets/images/logo.svg'

const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()
const { t } = useI18n()

const currentLanguage = computed(() => appStore.language)

// 语言切换（无刷新）
const handleLanguageChange = (lang) => {
  appStore.setLanguage(lang)
}

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [
    { required: true, message: computed(() => t('auth.usernameRequired')), trigger: 'blur' }
  ],
  password: [
    { required: true, message: computed(() => t('auth.passwordRequired')), trigger: 'blur' },
    { min: 6, message: computed(() => t('auth.passwordLength')), trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await userStore.login(form)
        ElMessage.success(t('auth.loginSuccess'))
        router.replace('/home')
      } catch (error) {
        ElMessage.error(error.response?.data?.error || t('auth.loginFailed'))
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style lang="scss" scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 48px 24px;
  background-color: var(--aitest-canvas);

  // 靛蓝氛围光斑
  &::before,
  &::after {
    content: '';
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    z-index: 0;
    filter: blur(80px);
  }

  &::before {
    width: 520px;
    height: 520px;
    top: -160px;
    left: -120px;
    background: radial-gradient(circle, var(--aitest-primary-subtle) 0%, transparent 70%);
    animation: drift 18s ease-in-out infinite;
  }

  &::after {
    width: 460px;
    height: 460px;
    bottom: -140px;
    right: -100px;
    background: radial-gradient(circle, var(--aitest-prim-indigo-100) 0%, transparent 70%);
    animation: drift 22s ease-in-out infinite reverse;
  }
}

/* 语言切换 */
.lang-switcher {
  position: absolute;
  top: 24px;
  right: 32px;
  z-index: 2;

  .el-dropdown-link {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    color: var(--aitest-text-2);
    background: var(--aitest-surface);
    border: 1px solid var(--aitest-card-border);
    box-shadow: var(--aitest-shadow-xs);
    padding: 8px 14px;
    border-radius: var(--aitest-radius-full);
    font-size: var(--aitest-font-size-md);
    transition: all 0.2s ease;
    outline: none;

    &:hover {
      border-color: var(--aitest-border-strong);
      color: var(--aitest-text-1);
    }

    .lang-icon {
      font-size: 16px;
      line-height: 1;
    }
  }
}

/* 登录卡片 */
.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-card-border);
  border-radius: var(--aitest-radius-lg);
  box-shadow: var(--aitest-card-shadow);
  padding: 40px 40px 28px;
  animation: fadeInUp 0.5s ease-out;

  .brand-lockup {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 28px;

    .brand-logo-img {
      height: 34px;
      width: auto;
      flex-shrink: 0;
    }

    .brand-eyebrow {
      margin-left: auto;
      font-size: var(--aitest-font-size-sm);
      font-weight: 500;
      color: var(--aitest-text-3);
      letter-spacing: 0.5px;
    }
  }

  .form-header {
    margin-bottom: 28px;

    h2 {
      font-size: 24px;
      font-weight: 700;
      color: var(--aitest-text-1);
      margin: 0 0 8px 0;
      letter-spacing: -0.3px;
    }

    p {
      font-size: var(--aitest-font-size-md);
      color: var(--aitest-text-2);
      margin: 0;
      line-height: 1.6;
    }
  }

  .login-form {
    :deep(.el-form-item) {
      margin-bottom: 20px;

      .el-form-item__label {
        font-size: var(--aitest-font-size-sm);
        font-weight: 500;
        color: var(--aitest-text-2);
        line-height: 1.4;
        padding-bottom: 6px;
      }
    }

    .submit-item {
      margin-top: 28px;
      margin-bottom: 16px;
    }

    .login-button {
      width: 100%;
      height: 48px;
      font-size: var(--aitest-font-size-lg);
      font-weight: 600;
      background: var(--aitest-primary);
      border: none;

      &:hover {
        background: var(--aitest-primary-hover);
      }

      &:active {
        background: var(--aitest-primary-active);
      }

      &.is-loading {
        background: var(--aitest-primary);
      }
    }

    .form-footer {
      text-align: center;
      font-size: var(--aitest-font-size-md);
      color: var(--aitest-text-2);

      .toggle-link {
        color: var(--aitest-primary);
        font-weight: 600;
        text-decoration: none;
        margin-left: 6px;

        &:hover {
          color: var(--aitest-primary-hover);
          text-decoration: underline;
        }
      }
    }
  }
}

.bottom-info {
  position: relative;
  z-index: 1;
  margin-top: 24px;
  text-align: center;

  p {
    font-size: var(--aitest-font-size-sm);
    color: var(--aitest-text-3);
    margin: 0;
  }
}

/* 动效 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes drift {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  50% {
    transform: translate(20px, -20px) scale(1.08);
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-card,
  .login-container::before,
  .login-container::after {
    animation: none;
  }
}

@media (max-width: 480px) {
  .login-container {
    padding: 32px 16px;
    justify-content: flex-start;
  }

  .lang-switcher {
    top: 16px;
    right: 16px;
  }

  .login-card {
    padding: 28px 20px 20px;
  }
}
</style>
