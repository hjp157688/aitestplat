<template>
  <div class="register-container">
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

    <div class="register-card">
      <!-- 品牌锁 -->
      <div class="brand-lockup">
        <img :src="logoSvg" alt="AITestPlat" class="brand-logo-img" />
        <div class="brand-eyebrow">{{ $t('auth.appTagline') }}</div>
      </div>

      <div class="form-header">
        <h2>{{ $t('auth.welcomeRegister') }}</h2>
        <p>{{ $t('auth.registerSubtitle') }}</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="register-form"
        @submit.prevent="handleRegister"
      >
        <el-row :gutter="24">
          <!-- 账号信息 -->
          <el-col :xs="24" :sm="12">
            <el-form-item prop="username" :label="$t('auth.username')">
              <el-input
                v-model="form.username"
                :placeholder="$t('auth.username')"
                size="large"
                :prefix-icon="User"
              />
            </el-form-item>

            <el-form-item prop="email" :label="$t('auth.email')">
              <el-input
                v-model="form.email"
                type="email"
                :placeholder="$t('auth.email')"
                size="large"
                :prefix-icon="Message"
              />
            </el-form-item>

            <el-form-item prop="phone" :label="$t('auth.phone')">
              <el-input
                v-model="form.phone"
                :placeholder="$t('auth.phonePlaceholder')"
                size="large"
                :prefix-icon="Phone"
                maxlength="11"
              />
            </el-form-item>

            <el-form-item prop="password" :label="$t('auth.password')">
              <el-input
                v-model="form.password"
                type="password"
                :placeholder="$t('auth.password')"
                size="large"
                :prefix-icon="Lock"
                show-password
              />
            </el-form-item>

            <el-form-item prop="password_confirm" :label="$t('auth.confirmPassword')">
              <el-input
                v-model="form.password_confirm"
                type="password"
                :placeholder="$t('auth.confirmPassword')"
                size="large"
                :prefix-icon="Lock"
                show-password
                @keyup.enter="handleRegister"
              />
            </el-form-item>
          </el-col>

          <!-- 个人信息 -->
          <el-col :xs="24" :sm="12">
            <el-form-item prop="first_name" :label="$t('auth.firstName')">
              <el-input
                v-model="form.first_name"
                :placeholder="$t('auth.firstName')"
                size="large"
              />
            </el-form-item>

            <el-form-item prop="last_name" :label="$t('auth.lastName')">
              <el-input
                v-model="form.last_name"
                :placeholder="$t('auth.lastName')"
                size="large"
              />
            </el-form-item>

            <el-form-item prop="department" :label="$t('auth.department')">
              <el-input
                v-model="form.department"
                :placeholder="$t('auth.department')"
                size="large"
              />
            </el-form-item>

            <el-form-item prop="position" :label="$t('auth.position')">
              <el-input
                v-model="form.position"
                :placeholder="$t('auth.position')"
                size="large"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item class="submit-item">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleRegister"
            class="submit-button"
          >
            {{ $t('auth.register') }}
          </el-button>
        </el-form-item>

        <div class="form-footer">
          <span>{{ $t('auth.hasAccount') }}</span>
          <router-link to="/login" class="toggle-link">{{ $t('auth.login') }}</router-link>
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
import { User, Lock, Message, Phone, ArrowDown } from '@element-plus/icons-vue'
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
  phone: '',
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  password_confirm: '',
  department: '',
  position: ''
})

// 手机号可选：填写时才校验格式
const validatePhone = (rule, value, callback) => {
  if (!value) {
    callback()
  } else if (!/^1[3-9]\d{9}$/.test(value)) {
    callback(new Error(t('auth.phoneFormat')))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: computed(() => t('auth.usernameRequired')), trigger: 'blur' },
    { min: 3, max: 20, message: computed(() => t('auth.usernameLength')), trigger: 'blur' }
  ],
  email: [
    { required: true, message: computed(() => t('auth.emailRequired')), trigger: 'blur' },
    { type: 'email', message: computed(() => t('auth.emailFormat')), trigger: 'blur' }
  ],
  phone: [
    { validator: validatePhone, trigger: 'blur' }
  ],
  password: [
    { required: true, message: computed(() => t('auth.passwordRequired')), trigger: 'blur' },
    { min: 6, message: computed(() => t('auth.passwordLength')), trigger: 'blur' }
  ],
  password_confirm: [
    { required: true, message: computed(() => t('auth.confirmPasswordRequired')), trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error(t('auth.passwordMismatch')))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const handleRegister = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await userStore.register(form)
        ElMessage.success(t('auth.registerSuccess'))
        router.replace('/home')
      } catch (error) {
        ElMessage.error(error.response?.data?.error || t('auth.registerFailed'))
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style lang="scss" scoped>
.register-container {
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

/* 注册卡片 */
.register-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 640px;
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

  .register-form {
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

    .submit-button {
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
  .register-card,
  .register-container::before,
  .register-container::after {
    animation: none;
  }
}

@media (max-width: 640px) {
  .register-container {
    padding: 32px 16px;
    justify-content: flex-start;
  }

  .lang-switcher {
    top: 16px;
    right: 16px;
  }

  .register-card {
    padding: 28px 20px 20px;
  }
}
</style>
