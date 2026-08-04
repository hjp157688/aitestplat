# AITestPlat 全局视觉系统「靛蓝精密石板」Design Spec

> **Goal:** 用一套全局设计令牌（CSS 变量）+ Element Plus 主题覆写 + 公共样式/组件，把整个前端统一升级为「靛蓝精密石板」浅色现代管理端视觉，并顺带修复沿途页面缺陷。一次令牌改造，所有页面自动继承。

**Status:** 已与用户确认（2026-08-04）

**设计方向来源：** 用户在头脑风暴中明确选择「A · 靛蓝精密石板」（现代化浅色 SaaS：冷灰底、靛蓝主色、锐利清晰层级）+「浅色侧边栏」+「纯系统无衬线字体」。此决策**取代**此前 BusinessKnowledge 反馈中「与其他页面保持一致、不做自定义身份」的限制（见记忆 `aitestplat-business-knowledge-design`，该记忆已同步更新）。

---

## 1. 设计主语与识别度

- **产品：** AITestPlat —— AI 驱动的测试管理平台（用例 / 接口测试 / UI 自动化 / APP 自动化 / 数据工厂 / 需求分析）。
- **用户：** QA 工程师、测试负责人、开发者。
- **页面唯一工作：** 更高效率地编写、运行、评审测试。
- **反 AI 默认审视：** 避开三种 AI 生成默认（米白+衬线+赤陶、近黑+荧光绿、报纸发丝线）。主色选靛蓝 `#4F46E5`（比平台原有的 `#2563EB` 更沉、更有识别度）；签名元素取自测试行业母语（HTTP 方法徽章），不是无意义装饰。

## 2. 色彩令牌（`tokens.scss` 中定义 `--aitest-*`）

| 变量 | 值 | 角色 |
|---|---|---|
| `--aitest-canvas` | `#F8FAFC` | 页面背景（替代 #f5f5f5） |
| `--aitest-surface` | `#FFFFFF` | 卡片/面板 |
| `--aitest-surface-subtle` | `#F1F5F9` | 表头行 / 悬停 / 禁用底 |
| `--aitest-border` | `#E2E8F0` | 发丝线 |
| `--aitest-border-strong` | `#CBD5E1` | 分隔线 / 强调边 |
| `--aitest-primary` | `#4F46E5` | 主色（按钮/链接/焦点） |
| `--aitest-primary-hover` | `#4338CA` | 主色 hover |
| `--aitest-primary-active` | `#3730A3` | 主色按下 |
| `--aitest-primary-subtle` | `#EEF2FF` | 选中底色 / 图标圆底 |
| `--aitest-accent` | `#0EA5E9` | 信息链接 / 强调 |
| `--aitest-text-1` | `#0F172A` | 主文字 |
| `--aitest-text-2` | `#475569` | 次级文字 |
| `--aitest-text-3` | `#94A3B8` | 弱化文字/占位 |
| 语义成功 | `#10B981` / 底 `#ECFDF5` | 状态、通过 |
| 语义警告 | `#F59E0B` / 底 `#FFFBEB` | 状态、告警 |
| 语义危险 | `#EF4444` / 底 `#FEF2F2` | 状态、失败 |
| 语义中性 | `#94A3B8` / 底 `#F1F5F9` | 停用/归档 |
| 语义信息 | `#3B82F6` / 底 `#EFF6FF` | 信息态 |

- 阴影体系：卡片 `0 1px 3px rgba(15,23,42,.06)`；下拉/抽屉 `0 12px 32px rgba(15,23,42,.12)`。
- 圆角：卡片 8px；控件 6px；徽章/状态胶囊 full。

## 3. 字体令牌（纯系统无衬线，不引入 webfont）

- 字体栈：`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif`。
- 层级：页头 20px/600；小节标题 16px/600；正文 14px/400；次级 13px；标签 12px/500。
- 数据：表格启用 `font-variant-numeric: tabular-nums`；HTTP 方法徽章与请求路径使用等宽栈 `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`。
- 理由：平台主要语言为中文，拉丁展示字体对中文标题无效，引入 webfont 收益低。

## 4. 布局概念

- **浅色侧边栏**：白底 + 右侧发丝线 `--aitest-border`；选中菜单项 = `--aitest-primary-subtle` 底 + 靛蓝文字 + 3px 左侧指示条；Logo 区适配浅色底（处理对比度）。
- **内容区**：`--aitest-canvas` 画布；页面头部 = 模块眉题（如「接口测试 / 接口管理」）+ 标题 + 右侧操作区；新增公共类 `.page-eyebrow`。
- **卡片**：白底 + 发丝线边框 + 轻阴影（边框叠加阴影 →「精密」而非「漂浮」）。
- **表格**：表头 `--aitest-surface-subtle`、12px/600 小字、行高更紧凑、悬停淡灰、选中行 `--aitest-primary-subtle` + 左侧靛蓝边。
- **空状态**：图标置于靛蓝淡底圆内 + 一句可行动引导文案（“没有用例——点击新建开始”式）+ 引导按钮；方向性，不只报丧。

## 5. 签名元素（唯一的记忆点）

**HTTP 方法徽章（`.method-badge`）**：等宽小字 + 淡底胶囊。
`GET` 蓝 / `POST` 绿 / `PUT` 琥珀 / `DELETE` 红 / `PATCH` 紫 / `HEAD`、`OPTIONS` 中性。
在接口管理、请求历史、自动化、执行日志中一致出现 —— 功能上让眼睛一瞥识别方法，辨识上成为平台「干这行」的印记。
配以状态点（圆点 + 淡色标签）作为支撑。其余全部安静克制。

## 6. 落地载体（范围 = 全局令牌层 + 公共组件）

1. **新增 `frontend/src/assets/css/tokens.scss`** —— 唯一事实源（`--aitest-*` 变量 + 阴影/圆角令牌）。
2. **覆写 Element Plus** —— 在 `global.scss` 的 `:root` 中把令牌映射到 `--el-color-primary`（含 `light-3/5/7/8/9`、`dark-2`）、`--el-bg-color`、`--el-border-color(-light)`、`--el-text-color-primary/regular/secondary/placeholder`、`--el-border-radius-base`、`--el-box-shadow-*`。→ **所有 `el-*` 组件自动继承，免逐页改动。**
3. **重写 `frontend/src/assets/css/global.scss`** —— `.page-container/.page-header/.page-title/.card-container/.status-tag/.priority-tag` 改用令牌（**类名保持不变，现有页面零破坏**）；新增 `.page-eyebrow`、`.method-badge`、`.empty-state`、表头辅助类等。
4. **改 `frontend/src/layout/index.vue`** —— 浅色侧边栏重设计（el-menu 换浅色主题、选中态指示条、Logo 适配）。
5. **公共组件**（按需新增，保持轻量）：`MethodBadge.vue`、`StatusTag.vue`（如需）、`EmptyState.vue`。**不强推组件化** —— 现有页面多数用类名模式，优先用类。
6. **缺陷修复 + 落地验证**：在 api-testing 与 requirement-analysis 各挑 2-3 个代表页（含 `InterfaceManagement.vue`、`BusinessKnowledge.vue`）实际接入令牌并肉眼验证，沿途修复发现的样式错乱/布局/对齐缺陷。令牌层自动覆盖其余页面。

## 7. 不做（Out of scope）

- 不动路由 / 交互逻辑 / 业务代码 / 后端。
- 不做暗色模式切换（本轮范围外）。
- 不引入任何 webfont。
- 不逐页手改（靠令牌层 + 代表页验证，不承诺“每个页面像素级重排”）。

## 8. 提交约定

- 遵循项目 CLAUDE.md：默认不自动提交；相关修改合并为一个 commit；`<type>: <简短描述>` 格式；提交前跑 lint（`npm run lint`）与构建（`npm run build`）。

## 9. 验证标准

- `npm run lint` 通过；`npm run build` 无报错。
- 打开代表页面（接口管理、请求历史、BusinessKnowledge、仪表盘）肉眼确认：新令牌生效、无样式错乱、侧边栏浅色正常、方法徽章与状态点显示正确、空状态有引导文案。
