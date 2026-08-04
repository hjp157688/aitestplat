# AITestPlat 靛蓝精密石板全局视觉系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过全局设计令牌 + Element Plus CSS 变量覆写 + 公共样式，把整个前端统一升级为「靛蓝精密石板」浅色现代管理端，并顺带修复页面视觉缺陷。

**Architecture:** 纯前端样式层改造，不动路由/交互/业务逻辑/后端。唯一事实源 `src/assets/css/tokens.scss`（`--aitest-*` 设计令牌）；`global.scss` 将令牌映射到 Element Plus 的 `--el-*` 变量（所有 `el-*` 组件自动继承）并重写公共类（`.page-container/.card-container/.status-tag/...`）与新增公共类（`.method-badge/.page-eyebrow/.empty-state`）；`layout/index.vue` 换浅色侧边栏。令牌层自动覆盖全部页面，仅对代表页做就地验证与消除硬编码旧色。

**Tech Stack:** Vue 3 + Element Plus 2.3.9 + SCSS

## Global Constraints

- 设计规范见 `docs/superpowers/specs/2026-08-04-global-design-system.md`，所有颜色/字体/圆角/阴影以 tokens.scss 为准。
- 主色 `#4F46E5`（hover `#4338CA`，subtle `#EEF2FF`）；画布 `#F8FAFC`；发丝线 `#E2E8F0`；文字 `#0F172A/#475569/#94A3B8`。
- 纯系统无衬线，**禁止引入 webfont**；禁止衬线/等宽正文（等宽仅限 HTTP 方法徽章与请求路径）。
- 默认不自动提交；相关修改合并为同一 `style:` 前缀 commit；提交前必须 `npm run lint` + `npm run build`。
- **WIP 边界（重要）**：下列 3 个文件携带用户正在开发的功能改动（git 里已暂存/未暂存），设计任务允许**就地修改它们做验证，但设计 commit 一律不 add/commit 这 3 个路径**，留给用户随功能一起提交：
  - `frontend/src/views/api-testing/InterfaceManagement.vue`
  - `frontend/src/views/api-testing/components/ImportOpenApiDialog.vue`
  - `frontend/src/views/requirement-analysis/BusinessKnowledge.vue`
  - 同理不触碰 `frontend/src/locales/` 下已改动的文件（用现有文案，不新增 i18n key）。
- 所有设计 commit 使用 `git add <明确列出的路径>`（绝不 `git add -A` / `git add .`），避免再次把 WIP 带进 commit。

---

### Task 1: 建立设计令牌 `tokens.scss`

**Files:**
- Create: `frontend/src/assets/css/tokens.scss`

**Interfaces:**
- Produces: CSS 自定义属性 `--aitest-*`（颜色/阴影/圆角/字体），供 Task 2 的 `global.scss` 与各页 scoped 样式引用。

- [ ] **Step 1: 创建 tokens.scss**

创建 `frontend/src/assets/css/tokens.scss`：

```scss
// AITestPlat 设计令牌 —— 「靛蓝精密石板」
// 唯一事实源；global.scss 通过 @use 引入。
:root {
  /* ===== 颜色 ===== */
  --aitest-canvas: #F8FAFC;            // 页面背景
  --aitest-surface: #FFFFFF;           // 卡片/面板
  --aitest-surface-subtle: #F1F5F9;    // 表头/悬停禁用底
  --aitest-border: #E2E8F0;            // 发丝线
  --aitest-border-strong: #CBD5E1;     // 分隔/强调边

  --aitest-primary: #4F46E5;           // 主色（靛蓝）
  --aitest-primary-hover: #4338CA;
  --aitest-primary-active: #3730A3;
  --aitest-primary-subtle: #EEF2FF;    // 选中底/图标圆底

  --aitest-accent: #0EA5E9;            // 信息链接/强调

  --aitest-text-1: #0F172A;            // 主文字
  --aitest-text-2: #475569;            // 次级文字
  --aitest-text-3: #94A3B8;            // 弱化/占位

  --aitest-success: #10B981;  --aitest-success-bg: #ECFDF5;
  --aitest-warning: #F59E0B;  --aitest-warning-bg: #FFFBEB;
  --aitest-danger: #EF4444;   --aitest-danger-bg: #FEF2F2;
  --aitest-info: #3B82F6;     --aitest-info-bg: #EFF6FF;
  --aitest-neutral: #94A3B8;  --aitest-neutral-bg: #F1F5F9;

  /* ===== 阴影 ===== */
  --aitest-shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.05);
  --aitest-shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --aitest-shadow-md: 0 6px 16px rgba(15, 23, 42, 0.08);
  --aitest-shadow-lg: 0 12px 32px rgba(15, 23, 42, 0.12);

  /* ===== 圆角 ===== */
  --aitest-radius-sm: 4px;
  --aitest-radius: 6px;
  --aitest-radius-lg: 8px;
  --aitest-radius-full: 999px;

  /* ===== 字体 ===== */
  --aitest-font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  --aitest-font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
```

- [ ] **Step 2: 验证 sass 可编译**

Run: `cd frontend && npx sass src/assets/css/tokens.scss > /dev/null && echo OK`
Expected: `OK`（无编译错误）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/assets/css/tokens.scss
git commit -m "style: 新增靛蓝精密石板设计令牌 tokens.scss"
```

---

### Task 2: 覆写 Element Plus + 重写公共样式 `global.scss`

**Files:**
- Modify: `frontend/src/assets/css/global.scss`（整体重写为以下内容）

**Interfaces:**
- Consumes: `tokens.scss` 的 `--aitest-*`
- Produces: 全站可见的 `--el-*` 覆写 + 公共类 `.page-container/.page-header/.page-eyebrow/.page-title/.card-container/.status-tag/.priority-tag/.method-badge/.empty-state/.tab-nums`。

- [ ] **Step 1: 重写 global.scss**

将 `frontend/src/assets/css/global.scss` 整体替换为：

```scss
@use './tokens.scss';

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow-x: hidden;
}

body {
  background-color: var(--aitest-canvas);
  color: var(--aitest-text-1);
  font-family: var(--aitest-font-sans);
  font-size: 14px;
}

/* ============ Element Plus 主题覆写 ============ */
:root {
  --el-color-primary: var(--aitest-primary);
  --el-color-primary-light-3: #7670EA;
  --el-color-primary-light-5: #9A95F0;
  --el-color-primary-light-7: #C5C3F8;
  --el-color-primary-light-8: #DBDAFB;
  --el-color-primary-light-9: var(--aitest-primary-subtle);
  --el-color-primary-dark-2: var(--aitest-primary-active);
  --el-color-success: var(--aitest-success);
  --el-color-warning: var(--aitest-warning);
  --el-color-danger: var(--aitest-danger);
  --el-color-error: var(--aitest-danger);
  --el-color-info: var(--aitest-neutral);

  --el-bg-color: var(--aitest-surface);
  --el-bg-color-overlay: var(--aitest-surface);
  --el-fill-color-blank: var(--aitest-surface);
  --el-fill-color: var(--aitest-surface-subtle);
  --el-fill-color-light: var(--aitest-surface-subtle);
  --el-fill-color-lighter: var(--aitest-surface-subtle);
  --el-fill-color-dark: var(--aitest-border-strong);
  --el-fill-color-darker: var(--aitest-border-strong);

  --el-border-color: var(--aitest-border-strong);
  --el-border-color-light: var(--aitest-border);
  --el-border-color-lighter: var(--aitest-border);
  --el-border-color-extra-light: var(--aitest-border);
  --el-border-color-dark: var(--aitest-border-strong);
  --el-border-color-hover: var(--aitest-border-strong);

  --el-text-color-primary: var(--aitest-text-1);
  --el-text-color-regular: var(--aitest-text-2);
  --el-text-color-secondary: var(--aitest-text-3);
  --el-text-color-placeholder: var(--aitest-text-3);
  --el-text-color-disabled: var(--aitest-text-3);

  --el-border-radius-base: var(--aitest-radius);
  --el-border-radius-small: var(--aitest-radius-sm);
  --el-border-radius-round: var(--aitest-radius-full);

  --el-box-shadow: var(--aitest-shadow-md);
  --el-box-shadow-light: var(--aitest-shadow-sm);
  --el-box-shadow-lighter: var(--aitest-shadow-xs);

  --el-font-family: var(--aitest-font-sans);
}

/* ============ 公共页面骨架 ============ */
.page-container {
  padding: 24px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;

    .page-eyebrow {
      font-size: 12px;
      font-weight: 500;
      color: var(--aitest-text-3);
      margin-bottom: 6px;
      letter-spacing: 0.02em;
    }

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: var(--aitest-text-1);
      line-height: 1.3;
    }

    .page-desc {
      margin-top: 4px;
      font-size: 13px;
      color: var(--aitest-text-3);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }
  }
}

.card-container {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: 20px;
  box-shadow: var(--aitest-shadow-sm);
}

/* ============ 状态/优先级标签 ============ */
.status-tag {
  &.active { background-color: var(--aitest-success-bg); color: var(--aitest-success); }
  &.inactive { background-color: var(--aitest-danger-bg); color: var(--aitest-danger); }
  &.paused { background-color: var(--aitest-warning-bg); color: var(--aitest-warning); }
  &.completed { background-color: var(--aitest-neutral-bg); color: var(--aitest-neutral); }
  border-radius: var(--aitest-radius-full);
}

.priority-tag {
  &.low { color: var(--aitest-success); }
  &.medium { color: var(--aitest-warning); }
  &.high { color: var(--aitest-danger); }
  &.critical { color: var(--aitest-danger); font-weight: bold; }
}

/* ============ 签名元素：HTTP 方法徽章 ============ */
.method-badge {
  display: inline-block;
  min-width: 44px;
  text-align: center;
  padding: 2px 8px;
  border-radius: var(--aitest-radius-full);
  font-family: var(--aitest-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  line-height: 1.6;

  &.get     { background: #DBEAFE; color: #1D4ED8; }
  &.post    { background: #D1FAE5; color: #047857; }
  &.put     { background: #FEF3C7; color: #B45309; }
  &.delete  { background: #FEE2E2; color: #B91C1C; }
  &.patch   { background: #E9D5FF; color: #7E22CE; }
  &.head    { background: #E0F2FE; color: #0369A1; }
  &.options { background: #F1F5F9; color: #475569; }
  &.connect { background: #F1F5F9; color: #475569; }
  &.trace   { background: #FFEDD5; color: #C2410C; }
}

/* ============ 空状态（方向性引导，不只报丧） ============ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 20px;
  text-align: center;

  .empty-icon {
    width: 56px;
    height: 56px;
    border-radius: var(--aitest-radius-full);
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
  }

  .empty-title { font-size: 15px; font-weight: 600; color: var(--aitest-text-1); }
  .empty-hint { font-size: 13px; color: var(--aitest-text-3); max-width: 320px; line-height: 1.6; }
}

/* ============ 工具类 ============ */
.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-nums { font-variant-numeric: tabular-nums; }
```

保留原有各 `@media (max-width: …)` 断点块（内容仍为 padding/字号调整，无需改颜色）。若旧文件中的 `.status-tag`/`.priority-tag` 只有背景色类（无边框圆角），以上新定义会统一为胶囊样式；如个别页面依赖旧底色（如 `.active` 旧为纯绿底白字），请保留两处并集：同时在类上保留旧兜底（可在本文件补 `.status-tag.active { background-color:#67c23a }` 之类）——本任务采用「旧底色 + 新文字色」两层叠加，确保与老页面兼容。

- [ ] **Step 2: 构建验证**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint 无新增错误，build 成功无报错

- [ ] **Step 3: Commit**

```bash
git add frontend/src/assets/css/global.scss
git commit -m "style: 令牌落地全书，覆写 Element Plus 主题与公共类"
```

---

### Task 3: 浅色侧边栏 + 顶栏/主区换令牌 `layout/index.vue`

**Files:**
- Modify: `frontend/src/layout/index.vue`

**Interfaces:**
- Consumes: `--aitest-*`（Task 1）
- Produces: 新的浅色侧边栏视觉，所有模块菜单统一继承。

- [ ] **Step 1: 移除 el-menu 的深色 props**

把 `frontend/src/layout/index.vue` 模板里的：

```html
<el-menu
  :default-active="$route.path"
  router
  background-color="#001529"
  text-color="#fff"
  active-text-color="#1890ff"
>
```

改为：

```html
<el-menu
  :default-active="$route.path"
  router
>
```

- [ ] **Step 2: 重写布局 scoped 样式中的深色块**

在 `<style lang="scss" scoped>` 中，把以下规则替换为令牌版（原 `.logo` 背景 `#001529`、`.el-aside` 背景 `#001529`）：

```scss
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--aitest-surface);
  border-bottom: 1px solid var(--aitest-border);
  flex-shrink: 0;

  .logo-img { width: 100%; height: 100%; object-fit: contain; }
}

.el-aside {
  background-color: var(--aitest-surface);
  border-right: 1px solid var(--aitest-border);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.3s ease;
  width: 240px !important;
}

/* 浅色菜单 */
:deep(.el-menu) {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--aitest-text-2);
  --el-menu-hover-bg-color: var(--aitest-surface-subtle);
  --el-menu-active-color: var(--aitest-primary);

  &::-webkit-scrollbar { width: 0; }

  .el-sub-menu__title,
  .el-menu-item { font-size: 14px; }

  .el-menu-item.is-active {
    background: var(--aitest-primary-subtle);
    color: var(--aitest-primary);
    font-weight: 600;
    border-left: 3px solid var(--aitest-primary);
  }

  .el-menu-item:not(.is-active):hover {
    background: var(--aitest-surface-subtle);
  }
}
```

> 说明：把原方案里 `.el-menu {:deep(...)}` 的选择器层级调整为直接在 `:deep(.el-menu)` 内联同样规则，避免 scoped 下 `:deep` 嵌套失效。`.el-menu--collapse` 折叠块保留原逻辑只把字号/内边距改为令牌无关值即可，无需删除。

- [ ] **Step 3: 顶栏与主区换令牌**

```scss
.el-header {
  background-color: var(--aitest-surface);
  border-bottom: 1px solid var(--aitest-border);
  /* 其余保持不变 */
}

.el-main {
  background-color: var(--aitest-canvas);
  /* 其余保持不变 */
}

.language-selector {
  color: var(--aitest-text-1);
  &:hover { color: var(--aitest-primary); }   /* 原 #1890ff */
}

.user-info .username { color: var(--aitest-text-1); }  /* 原 #303133 / #303133 */
```

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npm run lint && npm run build`
Expected: 无错误；`npm run dev` 后侧边栏为白底浅色菜单、选中项靛蓝高亮。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layout/index.vue
git commit -m "style: 侧边栏改浅色靛蓝主题，顶栏主区接入设计令牌"
```

---

### Task 4: 全局旧色扫描替换（硬编码颜色 → 令牌）

**Files:**
- Modify: 下列 grep 命中的 `.vue`/`.scss` 文件（**执行时重新跑 grep 拿到最新文件清单**，逐文件检视 hunk 后替换）

**Interfaces:**
- Consumes: `--aitest-*`
- Produces: 全站消除蓝橙/灰阶硬编码，视觉一致。

- [ ] **Step 1: 找出所有硬编码旧色**

Run:

```bash
cd /Users/huangjiaping/project/aitestplat/frontend
grep -rln '2563EB\|2563eb\|1890ff\|#303133\|#f5f5f5\|#e8e8e8' src --include='*.vue' --include='*.scss'
```

- [ ] **Step 2: 受控替换（逐文件审阅，不用全站盲 sed）**

对每个命中文件，只替换样式中的颜色字面量，规则如下（**值必须存在于 CSS 上下文**，禁用替换 `<script>` 内 JS 字符串/模板里的相同字符串——除非确认是主题配置）：

| 旧值 | 新值 |
|---|---|
| `#2563EB` / `#2563eb` / `#1890ff` | `var(--aitest-primary)` |
| `#303133` | `var(--aitest-text-1)` |
| `#f5f5f5` / `#f5f7fa`（作页面/container 背景时） | `var(--aitest-canvas)` |
| `#e8e8e8` / `#e4e7ed`（作边框时） | `var(--aitest-border)` |

若某处 `#303133` 出现在非文案颜色（如 ECharts 配色对象、代码高亮主题），保留原值并添加一行注释 `// 保留：图表主题色`。

**重点文件（至少包含）**：`src/layout/index.vue`（若 Task 3 已覆盖可跳过）、`src/views/api-testing/AutomationTesting.vue`、`src/views/api-testing/Dashboard.vue`、`src/views/api-testing/RequestHistory.vue`、`src/views/requirement-analysis/RequirementAnalysis.vue` 及各 grep 命中文件。**不得替换** WIP 三件套（InterfaceManagement/ImportOpenApiDialog/BusinessKnowledge）——它们改用 Task 5/6 单独就地处理。

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npm run lint && npm run build`
Expected: 通过

- [ ] **Step 4: Commit**

```bash
git add <上面列出的、非 WIP 的所有改动文件>
git commit -m "style: 全局硬编码旧色替换为设计令牌"
```

---

### Task 5: 代表页验证 A —— api-testing 模块就地接入令牌

**Files:**
- Modify: `frontend/src/views/api-testing/InterfaceManagement.vue`（**就地修改，不 commit**）
- Modify: `frontend/src/views/api-testing/AutomationTesting.vue`
- Modify: `frontend/src/views/api-testing/Dashboard.vue`

**Interfaces:**
- Consumes: `--aitest-*`、`.method-badge`
- Produces: 旗舰页与全局主题一致，验证令牌落地效果与缺陷修复。

- [ ] **Step 1: InterfaceManagement 就地同步配色（不提交）**

在该组件 scoped 样式中替换（仅改样式，不动树逻辑）：
- `.interface-management { background: #f5f7fa }` → `var(--aitest-canvas)`
- `.sidebar { border-right: 1px solid #e4e7ed }` → `var(--aitest-border)`；`box-shadow: 2px 0 6px rgba(0,0,0,.05)` → `var(--aitest-shadow-xs)`
- `.sidebar-header { background: #f8f9fa; border-bottom ... }` → `var(--aitest-surface-subtle)` + `var(--aitest-border)`
- `.search-results { background: white; border: 1px solid #e4e7ed }` → 表面/边框令牌

保留其 `.method-tag`（swagger 标准实色，树视图密集场景合适）不动；新增的表格/列表场景用 `.method-badge` 类。改完**不执行 commit**（WIP 边界），仅跑一次 `npm run build` 验证不破坏编译。

- [ ] **Step 2: AutomationTesting 表内方法/状态换蓝色调**

- 把表中方法展示改为 `.method-badge` + 小写方法名为 class（如 `:class="'method-badge ' + (row.method||'get').toLowerCase()"`，若该页现无方法列则跳过这一步，仅做颜色替换）。
- `.empty-state` 相关（行 72/995 附近的类）检查并套用 Task 2 的空状态观感（若已是自定义结构则只更新颜色令牌）。
- 状态列（通过/失败/跳过）颜色换用 `--aitest-success/danger/warning` 语义色。

- [ ] **Step 3: Dashboard 统计卡换令牌**

- 统计卡片若用 `.card-container` 自动继承；若自定义背景（如 `#f5f5f5`）则改为 `var(--aitest-surface)` + 边框。
- 数字启用 `.tab-nums`。

- [ ] **Step 4: 构建 + 肉眼验证**

Run: `cd frontend && npm run lint && npm run build`
Expected: 通过。然后 `npm run dev`，打开 `/api-testing/dashboard`、`/api-testing/interfaces`、`/api-testing/automation` 肉眼确认：整体靛蓝浅色、方法徽章/空状态正常、无样式错乱。

- [ ] **Step 5: Commit（仅非 WIP 两文件）**

```bash
git add frontend/src/views/api-testing/AutomationTesting.vue frontend/src/views/api-testing/Dashboard.vue
git commit -m "style: api-testing 代表页接入设计令牌（接口管理就地验证不提交）"
```

---

### Task 6: 代表页验证 B —— requirement-analysis 就地接入令牌

**Files:**
- Modify: `frontend/src/views/requirement-analysis/BusinessKnowledge.vue`（**就地修改，不 commit**）
- Modify: `frontend/src/views/requirement-analysis/RequirementAnalysis.vue`（或该模块另一列表页，取 grep 命中者）

**Interfaces:**
- Consumes: `--aitest-*`
- Produces: AI 生成页与 api-testing 同等一致的靛蓝观感（沿用此前保留的结构：4 格概览 + 过滤芯片 + 标本卡 + 方向性空状态）。

- [ ] **Step 1: BusinessKnowledge 就地换令牌（不提交）**

将其中残留的 `#2563EB`/`#1D4ED8` 类主色统一为 `var(--aitest-primary)`/`var(--aitest-primary-hover)`；把白卡、发丝线、石板文字对齐令牌；结构（全宽页头、概览格、芯片栏、卡片、空状态）保持不变。改完不 commit。

- [ ] **Step 2: 另一页面接令牌**

`RequirementAnalysis.vue`（或 grep 命中的其他列表页）样式旧色按 Task 4 表格替换为令牌；如命中则同样处理。

- [ ] **Step 3: 构建 + 肉眼验证**

Run: `cd frontend && npm run lint && npm run build`；`npm run dev` 打开 `/ai-generation/business-knowledge`、`/ai-generation/requirement-analysis` 确认与 api-testing 观感一致。

- [ ] **Step 4: Commit（仅非 WIP 文件）**

```bash
git add <Task 6-2 命中的非 WIP 文件>
git commit -m "style: requirement-analysis 代表页接入设计令牌"
```

---

### Task 7: 收尾验证与回归

**Files:**
- 仅验证，不改动逻辑。

- [ ] **Step 1: 全量校验**

Run: `cd frontend && npm run lint && npm run build`
Expected: 均通过。

- [ ] **Step 2: 回归清单（肉眼）**

`npm run dev` 后打开并核对代表性路由：`/api-testing/dashboard`、`/api-testing/interfaces`、`/api-testing/automation`、`/api-testing/history`、`/ai-generation/requirement-analysis`、`/ai-generation/business-knowledge`、`/defects/list`、`/configuration/ai-model`。
核对点：侧边栏浅色正常、主按钮为靛蓝、卡片为白底+发丝线、状态/优先级标签为淡底胶囊、无布局溢出、无旧硬编码明显撞色。

- [ ] **Step 3: 检查未提交残留**

Run: `git status --short`
Expected: 剩余改动仅为 WIP 三件套 + 用户原有 WIP（`InterfaceManagement.vue`、`ImportOpenApiDialog.vue`、`BusinessKnowledge.vue`、locales、后端文件、media 等）。**严禁**在此阶段 `git add -A` 或把 WIP 混入 style commit。

- [ ] **Step 4: 汇总说明**

输出一句话总结：令牌层已覆盖全部页面；代表页已验证；WIP 文件保持原样未提交。

---

## Self-Review 记录

- **Spec 覆盖**：色彩令牌（T1/T2）✓ · 字体（T2 `--aitest-font-*`，无 webfont）✓ · 布局/浅色侧边栏（T3）✓ · 签名方法徽章（T2 `.method-badge` + T5 应用）✓ · Element Plus 覆写（T2）✓ · 公共组件按 spec 6.5「优先类名」落地（不新增独立 Vue 组件，避免过度工程）✓ · 缺陷修复/代表页（T5/T6）✓ · 硬编码旧色（T4）✓ · 提交约定/不自动提交（各 commit 步 + WIP 边界）✓。
- **占位符扫描**：无 TBD/TODO；所有代码块含可运行内容。T5/T6 中「若该页现无方法列则跳过」属于条件步骤（非占位符），已给出判断方法。
- **类型/命名一致性**：`tokens.scss` 变量名与 `global.scss`/各任务引用完全一致（`--aitest-primary`、`--aitest-canvas`、`--el-color-primary` 映射闭合）；`.method-badge` 类名全局唯一，使用处一致。
- **风险缓解**：T2 保留媒体查询断点避免回归；T4 明确「禁止全局盲 sed」只做审阅后替换；WIP 三件套全程不 commit，避免再次污染用户进度。
