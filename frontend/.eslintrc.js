module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: ['plugin:vue/vue3-essential'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  ignorePatterns: ['dist/', 'node_modules/'],
  rules: {
    // 允许刻意单字的入口/框架组件（重命名会牵连路由与导入，成本大于收益）
    'vue/multi-word-component-names': [
      'error',
      { ignores: ['index', 'Index', 'Home', 'Dashboard', 'Login', 'Register'] },
    ],
  },
  overrides: [
    {
      files: ['*.vue'],
      parser: 'vue-eslint-parser',
      parserOptions: { parser: '@typescript-eslint/parser' },
    },
    {
      files: ['*.ts', '*.tsx'],
      parser: '@typescript-eslint/parser',
    },
  ],
}
