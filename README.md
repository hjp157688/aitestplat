# AITestPlat

AI 驱动的测试管理平台（Test Management Platform）。基于 **Django 4.2**（后端）+ **Vue 3**（前端）构建，融合 AI 能力为测试工程师提供端到端的测试管理与自动化测试解决方案。

## 功能特性

- **测试用例管理**：手工用例 CRUD、步骤管理、附件、评论、用例评审工作流
- **测试套件与执行**：测试套件组织、测试计划执行、执行结果与报告生成
- **接口测试**：HTTP/WebSocket 测试、环境管理、定时任务调度、Allure 报告、OpenAPI/Swagger 导入
- **UI 自动化**：基于 Selenium/Playwright、元素管理、页面对象（Page Object）、AI 智能模式（browser-use + LangChain）
- **APP 自动化**：基于 Airtest + 图像识别（OCR）、设备管理、WebSocket 实时执行进度、Allure 报告
- **AI 需求分析**：PDF/Word/TXT 需求文档解析、AI 生成测试用例（writer / reviewer 双角色）
- **测试数据工厂**：测试数据生成工具（中文姓名、手机号、身份证、银行卡、条形码、二维码、JSON/字符串/编码工具）
- **AI 助手**：MCP Server（AI Agent 连接平台）
- **用户行为分析**：可选埋点（`ANALYTICS_ENABLED`）
- **智能体（Knowledge Base）**：项目绑定智能体，生成时自动注入回答（WeKnora RAG）

## 技术架构

### 后端分层（`apps/`）

| 模块 | 说明 |
| --- | --- |
| `users` | 用户认证与资料（自定义 User 模型） |
| `projects` | 项目与团队管理 |
| `testcases` | 手工测试用例（步骤、附件、评论） |
| `testsuites` | 测试套件组织 |
| `executions` | 测试计划执行与结果跟踪 |
| `reports` | 测试报告生成 |
| `reviews` | 用例评审工作流（模板与指派） |
| `versions` | 版本/发布管理 |
| `requirement_analysis` | AI 需求文档解析与用例生成 |
| `api_testing` | 接口测试（HTTP/WebSocket、环境、定时任务、Allure） |
| `ui_automation` | UI 自动化（Selenium/Playwright、元素、页面对象、AI 模式） |
| `app_automation` | APP 自动化（Airtest + OCR、设备管理、WebSocket 实时进度、Allure） |
| `core` | 跨模块共享功能、管理命令、变量解析器 |
| `data_factory` | 测试数据生成与工具 |
| `analytics` | 可选用户行为分析（埋点） |
| `ai` | AI 统一网关（模型配置、客户端、提示词、调用记录） |
| `agent` | MCP Server（AI Agent 连接平台，FastMCP） |

### 前端（`frontend/src/`）

- **views/**：按功能模块划分的页面组件
- **api/**：API 服务层
- **stores/**：Pinia 状态管理
- **router/**：Vue Router 配置
- **components/**: 通用组件
- **layout/**：布局组件
- **locales/**：国际化（zh-hans / en / ja / ko）
- **utils/**：共享工具（HTTP 客户端、代码生成、请求模型、埋点跟踪）

### 核心依赖

- **后端**：Django REST Framework、drf-spectacular、django-filter、Celery、httpx、Selenium、Playwright、browser-use、langchain-openai、Channels + Daphne + channels-redis（WebSocket）、Airtest + EasyOCR + OpenCV、PyPDF/python-docx/reportlab/openpyxl、python-barcode/qrcode/pyzbar、Redis
- **前端**：Vue 3、Element Plus、Pinia、Vue Router、Axios、ECharts、Monaco Editor、vue-i18n、vuedraggable、curlconverter、dayjs、lodash-es、xlsx

## 快速开始

### 本地开发

```bash
# ---------- 后端 ----------
# 1. 创建并激活虚拟环境（macOS/Linux）
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: d:\aitestplat\venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（复制并填写）
cp .env.example .env

# 4. 初始化数据库
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# 5. 启动服务（HTTP only）
python manage.py runserver
# 需要 WebSocket（APP 自动化实时进度）时用 Daphne
# daphne -b 0.0.0.0 -p 8000 backend.asgi:application

# ---------- 前端 ----------
cd frontend
npm install
npm run dev
```

前端默认访问 `http://localhost:5173`，后端 API 文档位于 `http://localhost:8000/api/docs/`。

### Docker 全栈一键部署（推荐）

```bash
cp .docker_env.example .docker_env   # 填写 SECRET_KEY / 数据库密码等
docker compose --env-file .docker_env up -d --build
```

- 服务构成：mysql / redis / backend（daphne） / scheduler / frontend（nginx）
- 访问：前端 http://localhost:18081，后端直连 http://localhost:18181/api/docs/
- 配置模板与说明见 `.docker_env.example`；全栈 nginx 配置见 `deploy/nginx.conf`

### 离线部署（内网服务器）

- **构建机**（有 Docker + 外网）：`./build-offline.sh`（可用 `VER=x.y.z` 覆盖版本号）产出 `aitestplat-offline-<VER>.tar.gz`（含 backend/frontend/mysql/redis 四镜像）
- **内网服务器**：解压 → `./install.sh`（自动 `docker load` 镜像、生成 `.docker_env`、`docker compose --env-file .docker_env up -d --no-build`），全程零外网
- 详见包内 `README.offline.txt` 与源码 `offline/install.sh`

## 常用命令

```bash
# 运行所有定时任务（接口测试 + UI 自动化）
python manage.py run_all_scheduled_tasks

# 初始化 UI 自动化定位策略
python manage.py init_locator_strategies

# 下载 UI 自动化 webdriver
python manage.py download_webdrivers

# 种子化/版本化所有 AI 提示词模板（幂等；--type X 限定类型，--force 重建）
python manage.py seed_prompts

# 从 YAML 加载 APP 自动化 UI 组件包（加 --overwrite 覆盖）
python manage.py load_component_pack
```

所有管理命令位于 `apps/core/management/commands/`。

## 项目结构

```
├── apps/               # Django 模块化应用（见上方后端分层）
├── backend/            # Django 工程配置（settings.py / asgi.py / urls.py）
├── frontend/           # Vue 3 + Vite 前端
├── deploy/             # 部署配置（nginx 等）
├── offline/            # 离线部署脚本
├── docs/               # 项目文档
├── docker-compose.yml  # 全栈编排
├── build-offline.sh    # 离线部署包构建脚本
├── requirements.txt    # 后端依赖
└── manage.py
```

## API 概览

所有 API 以 `/api/` 为前缀。API 文档（Swagger）位于 `/api/docs/`，ReDoc 位于 `/api/redoc/`。

| 模块 | 前缀 |
| --- | --- |
| 用户认证 / 用户 | `/api/auth/`、`/api/users/` |
| 项目管理 | `/api/projects/` |
| 测试用例 / 套件 | `/api/testcases/`、`/api/testsuites/` |
| 执行 / 报告 | `/api/executions/`、`/api/reports/` |
| 评审 / 版本 | `/api/reviews/`、`/api/versions/` |
| AI 助手 / 需求分析 | `/api/assistant/`、`/api/requirement-analysis/` |
| 接口测试 / UI 自动化 | `/api/`（api_testing）、`/api/ui-automation/` |
| APP 自动化 | `/api/app-automation/` |
| 核心 / 数据工厂 | `/api/core/`、`/api/data-factory/` |
| 分析事件 | `/api/analytics/`（仅 `ANALYTICS_ENABLED`）|
| AI 调用记录 | `/api/ai/ai-call-records/` |

WebSocket 端点：`ws/app-automation/executions/<execution_id>/`（APP 自动化实时执行进度）。

## 数据库

- **MySQL 8.0+**，`utf8mb4` 字符集，通过环境变量配置：`DB_NAME`、`DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`
- **Redis**（可选，APP 自动化 WebSocket / Channels 需要）：`REDIS_URL`（如 `redis://127.0.0.1:6379/0`）

## AI 集成

所有 AI 模型调用统一通过 **`apps/ai/`** 网关：

- **配置**：`ai_model_config` 单表（`requirement_analysis.AIModelConfig`）。供应商（以 `apps/ai/providers.py` 为准）：DeepSeek、通义千问（Qwen）、硅基流动（SiliconFlow）、智谱（Zhipu）、小米、OpenAI、Azure OpenAI、Anthropic、Google Gemini 等。角色：`writer`、`reviewer`、`browser_use_text`、`embedding`、`tokenizer`、`api_testcase_generator`。每个 `(role, scope)` 一个激活配置。
- **客户端**：`apps/ai/client.py` 的 `AIClient`（异步 + 同步 + 流式 + 嵌入 + 连接测试）。
- **提示词**：数据库 `prompt_config`（版本化），由 `python manage.py seed_prompts` 种子化。
- **可观测性**：每次调用写入 `AiCallRecord`，可在「配置中心 → AI 调用记录」查看。

UI 自动化 AI 模式使用 `browser-use` + LangChain（`apps/ui_automation/ai_agent.py`）。

## MCP Server

`apps/agent` 提供 FastMCP 服务，允许 AI Agent 连接平台执行业务操作。基于 HTTP transport，需配置 `MCP_SERVER_TOKEN`、`MCP_SERVICE_USER`、`MCP_HOST`、`MCP_PORT`（详见 `.env.example`）。

## 环境变量

主要环境变量（完整见 `.env.example`）：

| 变量 | 说明 |
| --- | --- |
| `SECRET_KEY` | Django 密钥（生产必改） |
| `DEBUG` | 调试模式（生产设为 False） |
| `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS` | 主机 / 跨域白名单 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | MySQL 配置 |
| `REDIS_URL` | Redis（APP 自动化 WebSocket） |
| `MCP_SERVER_TOKEN` / `MCP_SERVICE_USER` | MCP Server 配置 |
| `LANGUAGE_CODE` / `TIME_ZONE` | 本地化（默认 `zh-hans` / `Asia/Shanghai`） |
