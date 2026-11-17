# AITestPlat

AI 驱动的测试管理平台。**Django 4.2 + Vue 3** 全栈实现，覆盖「需求 → 用例 → 评审 → 执行 → 报告 → 缺陷」的完整测试链路，并把 AI 能力贯穿其中：需求解析、用例生成与评审、接口用例生成、浏览器智能体执行、自动化用例转写。

---

## 目录

- [功能全景](#功能全景)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [Docker 部署](#docker-部署)
- [离线部署](#离线部署)
- [常用命令](#常用命令)
- [API 概览](#api-概览)
- [环境变量](#环境变量)
- [AI 网关](#ai-网关)
- [MCP Server](#mcp-server)
- [测试](#测试)
- [目录结构](#目录结构)
- [相关文档](#相关文档)
- [注意事项](#注意事项)

---

## 功能全景

平台按 8 个一级模块组织，首页卡片即为模块入口：

| 模块 | 路径前缀 | 能力 |
| --- | --- | --- |
| **AI 用例生成** | `/ai-generation/*` | 项目管理、需求管理（含禅道同步）、测试用例（含 Excel/禅道导入导出、用例版本历史、AI 定向修改/补充）、版本管理、用例评审、测试计划执行、AI 测试报告、**自动化用例**与**执行环境** |
| **接口测试** | `/api-testing/*` | 接口项目管理、接口集合树与调试、HTTP/WebSocket、断言与变量函数、CURL/OpenAPI 导入导出、套件编排执行、请求历史、环境管理、Allure 报告、定时任务与通知 |
| **UI 自动化测试** | `/ui-automation/*` | 元素管理与定位策略、页面对象、脚本生成与脚本库、用例与套件、执行记录、报告、定时任务 |
| **APP 自动化测试** | `/app-automation/*` | 设备管理、安装包管理、UI 元素库与组件包、用例编排（Scene Builder）、套件执行、WebSocket 实时进度、Allure 报告 |
| **Bug 缺陷管理** | `/defects/*` | 缺陷看板、缺陷列表与详情、状态机流转、缺陷报表 |
| **数据工厂** | `/data-factory` | 69 个内置工具：测试数据生成（姓名/手机/身份证/银行卡/营业执照）、JSON 与格式转换、字符串与正则、编码加密、Mock、Crontab 等 |
| **AI 智能模式** | `/ai-intelligent-mode/*` | 自然语言驱动的浏览器自动化（browser-use）：任务执行、AI 用例管理、执行记录与报告 |
| **配置中心** | `/configuration/*` | AI 模型配置、提示词配置（版本化）、生成配置、AI 调用记录、UI/APP 环境、定时任务通知、禅道配置、WeKnora 知识库配置 |

### 亮点能力

- **需求 → 用例闭环**：上传 PDF/Word/TXT/Excel 需求文档，AI 解析出需求条目，再按 writer/reviewer 双角色生成与评审用例。
- **知识库增强**：项目可绑定 WeKnora 智能体，生成用例时自动检索知识库并注入回答。
- **自动化用例（AI 转写）**：勾选手工用例或 AI 生成用例，AI 将步骤转写为 browser-use 可执行的操作指令；支持批量执行、整批只登录一次（`storage_state` 复用）、远端浏览器 CDP 接入、执行截图开关、失败原因 AI 总结与成功路径记忆。
- **禅道打通**：需求从禅道同步、用例按关键词搜索直选导入、用例导出回写（按 `zentao_case_id` 新建或更新）。
- **接口用例 AI 生成**：基于已有 API 请求生成变体用例，断言结构与系统执行器（`path` / `operator` / `value`）对齐。
- **AI 调用可观测**：每次模型调用落库 `AiCallRecord`，配置中心可查。

---

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.12、Django 4.2、Django REST Framework、drf-spectacular（Swagger/ReDoc）、django-filter、django-simpleui |
| 实时 | Django Channels + Daphne + channels-redis（WebSocket） |
| 数据库 | MySQL 8.0+（`utf8mb4`）、Redis（Channel Layer / 缓存） |
| AI | `apps/ai` 统一网关；browser-use + LangChain；EasyOCR / OpenCV / Airtest |
| 自动化 | Selenium、Playwright（Chromium）、Airtest、Allure（需 JRE） |
| 前端 | Vue 3、Vite 7、Element Plus、Pinia、Vue Router、Axios、ECharts、Monaco Editor、vue-i18n、curlconverter、xlsx |
| 部署 | Docker Compose（mysql / redis / backend / scheduler / frontend-nginx） |

---

## 系统架构

```
frontend (Vue 3 + Vite)
  views/ · api/ · stores/ · router/ · locales(zh-cn/en) · utils/
        │  /api/**（开发环境 Vite 代理，生产环境 nginx 反代）
        ▼
backend（Django + Channels，ASGI 入口 backend/asgi.py）
  backend/urls.py → apps/*/urls.py
  ├── apps/ai          统一 AI 网关：providers · client · resolver · prompt_registry
  ├── apps/agent       MCP Server（FastMCP，17 个工具）
  ├── apps/core        跨模块管理命令、变量解析
  └── apps/analytics   可选埋点（ANALYTICS_ENABLED）
        │
        ├── MySQL 8（业务数据）
        └── Redis（Channel Layer / 缓存）
```

### 后端模块（`apps/`）

| 模块 | 说明 |
| --- | --- |
| `users` | 用户认证与资料（自定义 `User` 模型、JWT + Token 双认证、注册/登录/Token 交换） |
| `projects` | 项目与团队管理 |
| `testcases` | 手工用例：步骤、附件、评论、版本历史、AI 修改/补充、Excel 与禅道导入导出 |
| `testsuites` | 测试套件组织 |
| `executions` | 测试计划执行与结果跟踪 |
| `reports` | 测试报告生成 |
| `reviews` | 用例评审工作流（模板与指派） |
| `versions` | 版本/发布管理 |
| `defects` | 缺陷管理与状态流转 |
| `requirement_analysis` | 需求解析、AI 用例生成、生成配置、禅道集成、WeKnora 绑定、**自动化用例/环境/执行** |
| `api_testing` | 接口测试：集合/请求/环境/历史/套件/定时任务/Allure/OpenAPI 导入 |
| `ui_automation` | UI 自动化：元素、页面对象、脚本、套件、执行；`ai_agent.py` / `ai_base.py` 为 browser-use 智能模式 |
| `app_automation` | APP 自动化：设备、安装包、组件包、用例编排、执行、WebSocket 进度、Allure |
| `core` | 跨模块共享：管理命令、变量解析、统一通知配置 |
| `data_factory` | 测试数据生成与工具集 |
| `analytics` | 可选用户行为分析（`ANALYTICS_ENABLED`） |
| `ai` | AI 统一网关：模型配置、客户端、提示词注册表、调用记录 |
| `agent` | MCP Server（基于 FastMCP，stdio / streamable-http） |

### 前端结构（`frontend/src/`）

| 目录 | 说明 |
| --- | --- |
| `views/` | 按模块划分的页面（`api-testing`、`app-automation`、`ui-automation`、`requirement-analysis`、`defects`、`data-factory`、`configuration` 等） |
| `api/` | 后端接口封装 |
| `stores/` | Pinia 状态（用户、应用配置、语言等） |
| `router/` | 路由表（模块前缀 + `requiresAuth` 守卫） |
| `layout/` | 主框架：侧边栏按 `currentModule` 切换模块菜单 |
| `locales/` | i18n（`zh-cn`、`en`，按模块拆文件） |
| `utils/` | HTTP 客户端、代码生成、请求模型、埋点 `tracker.js` |

---

## 快速开始

### 前置条件

- Python 3.12、Node.js 22（Vite 7 要求 ≥20.19 / ≥22.12）
- MySQL 8.0+（必需）、Redis（APP 自动化 WebSocket / Channels 需要）
- JRE 21（Allure 报告；缺失时报告降级为简单实现）

### 本地开发

```bash
# ---------- 后端 ----------
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: d:\aitestplat\venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env               # 填写 SECRET_KEY / 数据库账号等

python manage.py makemigrations
python manage.py migrate
python manage.py seed_prompts      # 初始化/版本化 AI 提示词（幂等）
python manage.py createsuperuser

# 启动方式一：纯 HTTP（无 WebSocket）
python manage.py runserver

# 启动方式二：带 WebSocket（APP 自动化实时进度，推荐）
daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# ---------- 前端 ----------
cd frontend
npm install
npm run dev
```

- 前端：http://localhost:3000 （Vite 代理 `/api`、`/media`、`/app-automation-*`、`/ws` 到 `127.0.0.1:8000`）
- 后端 API 文档：http://localhost:8000/api/docs/ （ReDoc：`/api/redoc/`）
- Django Admin：http://localhost:8000/admin/

也可用一键脚本 `./start.sh`（自动检查 MySQL/Redis/前端依赖，并行拉起 daphne 与 Vite，日志写入 `logs/`）。

### 首次使用建议顺序

1. 配置中心 → **AI 模型配置**：为 `writer`、`reviewer`、`browser_use_text`、`api_testcase_generator` 等角色各建一条启用配置。
2. 配置中心 → **提示词配置**：确认已由 `seed_prompts` 写入种子版本。
3. AI 用例生成 → **项目管理**：新建项目。
4. 按需在配置中心配置**禅道**、**WeKnora**、**UI/APP 环境**。

---

## Docker 部署

```bash
cp .docker_env.example .docker_env    # 填写 SECRET_KEY / MYSQL_ROOT_PASSWORD / DB_PASSWORD 等
docker compose --env-file .docker_env up -d --build
```

| 服务 | 说明 |
| --- | --- |
| `mysql` | MySQL 8.0，数据在命名卷 `mysql_data` |
| `redis` | Redis 7，AOF 持久化 |
| `backend` | Daphne 启动 `backend.asgi:application`，入口脚本自动 `makemigrations` / `migrate` / `collectstatic` |
| `scheduler` | `run_all_scheduled_tasks` 循环（`SCHEDULER_INTERVAL`，默认 300s） |
| `frontend` | 多阶段构建：Node 22 构建 → nginx 托管，并反代后端 |

- 前端：http://localhost:18081
- 后端直连：http://localhost:18181/api/docs/
- nginx 配置：`deploy/nginx.conf`（注意 `client_max_body_size` 需按上传文档大小调整）

---

## 离线部署

面向无外网的内网服务器：

```bash
# 构建机（有 Docker + 外网）
./build-offline.sh                 # VER=x.y.z 可覆盖版本号
# 产出 aitestplat-offline-<VER>.tar.gz（含 backend/frontend/mysql/redis 四镜像）

# 内网服务器
tar -xzf aitestplat-offline-<VER>.tar.gz
cd aitestplat-offline-<VER> && ./install.sh   # docker load + 生成 .docker_env + up -d --no-build
```

详见 `offline/README.offline.txt` 与 `offline/install.sh`。

---

## 常用命令

```bash
# 全部模块定时任务调度器（API 测试 + UI 自动化 + APP 自动化）
python manage.py run_all_scheduled_tasks            # --interval 60 / --once
python manage.py run_all_scheduled_tasks --once

# AI 提示词种子化（幂等；--type X 只处理某类型，--force 重建版本）
python manage.py seed_prompts
python manage.py seed_prompts --type automation_case_converter --force

# UI 自动化
python manage.py init_locator_strategies            # 初始化定位策略
python manage.py download_webdrivers                # 下载 webdriver

# APP 自动化组件包（YAML → 数据库；--overwrite 覆盖）
python manage.py load_component_pack

# MCP Server
python manage.py mcp_server --transport stdio
python manage.py mcp_server --transport http --host 0.0.0.0 --port 8765

# 用例 Markdown 残留清理（--dry-run 预览）
python manage.py clean_testcase_markdown --dry-run
```

> 迁移：各环境启动前请执行 `python manage.py makemigrations && python manage.py migrate`（Docker 入口脚本已自动执行）。若出现 `Unknown column` 类报错，通常是本环境尚未跑迁移。

---

## API 概览

所有接口以 `/api/` 为前缀，默认 JWT 认证（`IsAuthenticated`），分页 20 条。

| 领域 | 前缀 | 备注 |
| --- | --- | --- |
| 认证 / 用户 | `/api/auth/`、`/api/users/` | JWT（access 60 分钟 / refresh 7 天，轮换 + 黑名单） |
| 项目 | `/api/projects/` | |
| 用例 / 套件 | `/api/testcases/`、`/api/testsuites/` | 禅道：`/zentao-import/`、`/zentao-export/`、`/zentao-task/<task_id>/` |
| 执行 / 报告 | `/api/executions/`、`/api/reports/` | |
| 评审 / 版本 / 缺陷 | `/api/reviews/`、`/api/versions/`、`/api/defects/` | |
| AI 需求分析与生成 | `/api/requirement-analysis/` | `documents`、`requirements-manage`、`testcase-generation`、`prompts`、`ai-models`、`zentao-config`、`weknora-config` 等 |
| **自动化用例** | `/api/requirement-analysis/` | `automation-cases`、`automation-environments`、`automation-executions`、`automation-execution-sessions`；批量转化 `batch-convert/`、`{id}/retry-convert/`、单条 `{id}/execute/`、批量 `batch-execute/` |
| 接口测试 | `/api/api-testing/` | `projects`、`collections`、`requests`、`environments`、`test-suites`、`scheduled-tasks`、`api-docs` 等 |
| UI 自动化 | `/api/ui-automation/` | `elements`、`page-objects`、`test-scripts`、`test-suites`、`ai-cases`、`scheduled-tasks` 等 |
| APP 自动化 | `/api/app-automation/` | `devices`、`packages`、`components`、`test-cases`、`executions`、`scheduled-tasks` |
| 数据工厂 | `/api/data-factory/` | 工具执行、分类、批量生成、变量函数 |
| 核心 | `/api/core/` | 统一通知配置 |
| AI 网关 | `/api/ai/ai-call-records/` | AI 调用记录（只读） |
| 埋点 | `/api/analytics/events/` | 仅 `ANALYTICS_ENABLED=True` 时挂载 |

**WebSocket**：`ws/app-automation/executions/<execution_id>/`（APP 自动化实时执行进度，需 Redis Channel Layer）。

---

## 环境变量

完整清单见 `.env.example`（本地）与 `.docker_env.example`（Docker）。

| 变量 | 说明 |
| --- | --- |
| `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` | Django 基础安全配置（生产必改） |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | 跨域与可信来源 |
| `APP_USE_HTTPS` / `TRUST_PROXY_SSL_HEADER` | HTTPS 与反向代理头信任（影响 Cookie Secure） |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | MySQL |
| `REDIS_URL` | Channels / 缓存（如 `redis://127.0.0.1:6379/0`） |
| `MCP_SERVER_TOKEN` / `MCP_SERVICE_USER` / `MCP_HOST` / `MCP_PORT` | MCP Server |
| `SMS_ACCESS_KEY_ID` / `SMS_ACCESS_KEY_SECRET` / `SMS_SIGN_NAME` / `SMS_REGISTER_TEMPLATE_CODE` | 阿里云短信（预留配置，当前注册流程未强制校验验证码） |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | 定时任务通知邮件 |
| `ANALYTICS_ENABLED` / `ANALYTICS_MAX_BATCH_SIZE` | 后端埋点开关 |
| `VITE_ANALYTICS_ENABLED` | 前端埋点开关 |
| `LANGUAGE_CODE` / `TIME_ZONE` | 默认 `zh-hans` / `Asia/Shanghai` |
| `LOG_LEVEL` / `LOG_FILE` | 日志 |

> AI 模型密钥不入环境变量：统一在「配置中心 → AI 模型配置」维护（供应商枚举源码为 `apps/ai/providers.py`）。

---

## AI 网关

所有模型调用收敛到 **`apps/ai/`**：

- **配置表**：`ai_model_config`（`requirement_analysis.AIModelConfig`）。供应商：DeepSeek、通义千问、硅基流动、智谱、小米、小米 coding plan、OpenAI、Azure OpenAI、Anthropic、Google Gemini、其他。
- **角色**：`writer`、`reviewer`、`browser_use_text`、`api_testcase_generator`（运行时消费），另有历史角色用于数据兼容。每个 `(role, scope)` 只应有一条启用配置。
- **解析**：统一走 `apps.ai.resolver.ConfigResolver.active(role, model_type=None)`，禁止直接 `filter(role=..., is_active=True).first()`。
- **客户端**：`apps.ai.client.AIClient`（异步 / 同步 / 流式 / embeddings / 连接测试），透传 `provider_extra`。
- **提示词**：DB 表 `prompt_config`（版本化），种子源 `apps/ai/prompt_seeds.py`；类型含 `writer`、`reviewer`、`requirement_parse`、`api_testcase_generator`、`browser_use_task`、`browser_use_breakdown`、`testcase_modifier`、`testcase_supplement`、`automation_case_converter`、`automation_failure_summary`。
- **可观测**：每次调用写 `AiCallRecord`，在配置中心 → AI 调用记录查看。

### 自动化用例链路

```
手工用例 / AI 生成用例
   │ 勾选 → POST automation-cases/batch-convert/
   ▼
AI 转写（writer 角色 + automation_case_converter 提示词）
   ▼  steps: [{action, verify}]，支持 {{base_url}} / {{username}} / {{password}} / {{变量}}
AutomationCase（可编辑）
   │ execute / batch-execute（指定环境）
   ▼
AutomationExecutionSession（整批登录一次，导出 storage_state 复用）
   ▼
browser-use 逐条执行（支持 cdp_url 接远端浏览器、截图开关）
   ▼
AutomationExecution（逐步结果 + 日志）→ 失败 AI 总结 / 成功路径记忆回写用例
```

---

## MCP Server

`apps/agent` 通过 MCP 把平台能力暴露给 AI Agent（详见 [docs/mcp-server.md](docs/mcp-server.md)）：

```bash
# 本机（stdio，零鉴权）
python manage.py mcp_server --transport stdio

# 远程（streamable http + Bearer Token，需设置 MCP_SERVER_TOKEN）
python manage.py mcp_server --transport http --host 0.0.0.0 --port 8765
```

```bash
# 接入 Claude Code
claude mcp add --transport stdio aitestplat -- python manage.py mcp_server --transport stdio
claude mcp add --transport http aitestplat http://<server>:8765/mcp \
  --header "Authorization: Bearer $MCP_SERVER_TOKEN"
```

工具覆盖面：项目列表、需求→用例生成（run → result → adopt）、接口用例生成与执行、UI 浏览器自动化、数据工厂。长操作返回 `task_id` / `execution_id` 供轮询，错误统一 `{"error": "..."}`。

---

## 测试

```bash
# 后端：Django TestCase（apps/**/tests/）
python manage.py test apps.requirement_analysis.tests
python manage.py test apps.testcases.tests apps.ui_automation.tests apps.agent.tests
python manage.py test apps.api_testing.tests

# 前端（lint 带 --fix，build 同时校验可编译性）
cd frontend && npm run lint && npm run build
```

---

## 目录结构

```
.
├── apps/                  # Django 业务模块（见「后端模块」）
├── backend/               # 工程配置：settings.py / asgi.py / urls.py / middleware.py
│   ├── Dockerfile         # 全量依赖镜像（Playwright / Allure / JRE）
│   ├── entrypoint.sh      # 等待 DB → 迁移 → collectstatic
│   └── scheduler-loop.sh  # scheduler 容器循环
├── frontend/              # Vue 3 + Vite
├── deploy/                # nginx 等部署配置
├── offline/               # 离线部署脚本与说明
├── docs/                  # 项目文档（用户手册 / MCP / 设计文档）
├── allure/                # Allure 命令行（本地）
├── docker-compose.yml     # 全栈编排
├── build-offline.sh       # 离线包构建
├── start.sh               # 本地一键启动（daphne + vite）
├── requirements.txt
└── manage.py
```

---

## 相关文档

| 文档 | 内容 |
| --- | --- |
| [docs/user-manual.md](docs/user-manual.md) | 用户操作手册（按模块逐页说明） |
| [docs/mcp-server.md](docs/mcp-server.md) | MCP Server 启动、接入与工具清单 |
| `docs/superpowers/specs/` | 功能设计文档（如自动化用例模块设计） |
| `docs/superpowers/plans/` | 实现计划 |
| `CLAUDE.md` / `AGENTS.md` | 面向 AI 编码助手的仓库约定 |

> `docs/`、`CLAUDE.md`、`AGENTS.md` 当前为工作区本地文档（未纳入版本管理），克隆仓库后若缺失属正常情况。

---

## 注意事项

- **生产环境**：`DEBUG=False`、指定 `ALLOWED_HOSTS` 与 `CORS_ALLOWED_ORIGINS`、更换 `SECRET_KEY`、启用 HTTPS（`APP_USE_HTTPS`）。
- **Allure 报告**依赖 JRE：镜像已内置 `default-jre-headless`，非 Docker 部署需自行安装（推荐 Temurin 21）。
- **浏览器自动化**：Docker 镜像已 `playwright install --with-deps chromium`；macOS 本地 Chrome 远程调试端口随机，请勿写死 9222，按实际 `cdp_url` 配置。
- **上传体积**：nginx 默认 `client_max_body_size 1m`，导入大 OpenAPI 文档时需调大（`deploy/nginx.conf` 与 `frontend/nginx.conf`）。
- **提交规范**：`<type>: <简短描述>`；提交前跑 lint 与测试；默认不自动提交。
