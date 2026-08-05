# AITestPlat - AI 驱动的测试管理平台

<div align="center">

**覆盖测试全生命周期的 AI 测试管理平台：需求分析、用例生成、知识库 RAG、API 测试、UI/APP 自动化**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

## 项目简介

AITestPlat 是一个 AI 驱动的测试管理平台，基于 Django 4.2 + Vue 3 构建，集成了 AI 需求分析与用例生成、业务知识库（向量检索 RAG）、测试用例管理、用例评审、缺陷管理、API 测试、Web UI 自动化、Android APP 自动化、数据工厂等模块，覆盖从需求到缺陷闭环的测试全生命周期。

## 核心功能

### 🤖 AI 需求分析与用例生成
- **需求来源多样**：上传 PDF/Word/TXT 需求文档自动解析、直接输入需求文本、同步禅道（产品/项目/需求）三方来源
- **AI 生成测试用例**：由测试用例编写专家模型生成，再由测试评审专家模型二次评审，产出高可用用例
- **业务知识库注入（RAG）**：生成前自动从知识库检索相关业务知识，作为上下文增强生成质量
- **生成配置**：支持用例类型补充指令与生成颗粒度（标准/精细）自定义
- **流式生成**：实时流式输出生成过程，支持任务进度跟踪与失败重试
- **异步任务**：文档解析、分析、生成均通过异步任务执行，支持进度回显

### 📚 业务知识库（向量检索）
- **知识沉淀**：上传业务文档（按项目隔离或全局共享），沉淀验收标准、业务规则等测试资产
- **智能分块**：按标题、段落、语义进行多级分块，保留章节层级关系
- **语义向量化**：基于 Embedding 模型将分块向量化，存入 ChromaDB 向量库（`chroma_data/`）
- **语义检索 + 重排序**：相似度检索 + LLM 重排序，精准命中相关知识
- **检索增强生成**：检索结果自动拼接到用例生成提示词，让 AI 依据真实业务规则出用例

### 📋 测试用例管理
- 用例生命周期管理（创建、编辑、版本控制、归档）
- 步骤化用例设计，支持前置条件、操作步骤、预期结果
- 附件上传、团队协作评论
- 多维度分类（项目、版本、标签），支持从 AI 生成用例一键收养

### 🔍 用例评审
- 多人评审流程，支持评审模板和检查清单
- 多层反馈（整体意见、用例意见、步骤意见）
- 评审状态跟踪（待评审、评审中、已通过、已拒绝）

### 🐛 缺陷管理
- 缺陷全生命周期管理（创建、分配、修复、关闭）
- 流转历史记录，操作人追溯
- 附件上传、状态流转控制、缺陷统计

### 🌐 API 测试
- HTTP/WebSocket 协议支持，支持 OpenAPI/Swagger 导入接口
- 环境变量管理（全局/局部），变量替换
- 测试套件批量执行，断言配置
- 定时任务调度，邮件 / 企业微信 / 钉钉 / 飞书 Webhook 通知
- 可视化报告 + Allure 报告自动生成

### 🖥️ UI 自动化测试（Web）
- Selenium + Playwright 双引擎支持
- 元素库管理，多种定位策略（ID、XPath、CSS、text 等）
- 页面对象模式（POM），可视化脚本编辑器
- 多浏览器支持（Chrome / Firefox / Edge）
- AI 智能模式：基于 Browser-Use 的智能浏览器自动化

### 📱 APP 自动化测试（Android）
- 基于 Airtest + 图像识别（OCR）的自动化执行
- 设备管理（本地模拟器 + 远程设备），设备锁定机制
- 三种元素定位方式（图片、坐标、区域）
- 组件化编排 + UI Flow JSON 流程编排
- Celery 异步执行 + pytest + Allure 报告
- WebSocket 实时执行进度推送（需 Daphne 启动）

### 🏭 数据工厂
- **字符工具**（9 个）：字符串处理、文本对比、正则测试、字数统计等
- **编码工具**（12 个）：Base64、时间戳、Unicode、进制转换、URL 编解码、条形码/二维码等
- **随机工具**（6 个）：随机数、随机字符串、UUID、随机布尔值等
- **加密工具**（8 个）：MD5/SHA 哈希、AES 加解密、HMAC 签名
- **测试数据**（4 个）：中文姓名、手机号、邮箱、地址生成
- **JSON 工具**（8 个）：格式化、压缩、校验、JSONPath 查询、对比、转换
- **Crontab 工具**（4 个）：生成/解析表达式、下次执行时间、验证
- 标签系统 + 数据引用，可在 API/UI 测试中引用工厂数据

### 📊 测试执行与报告
- 测试计划管理，关联项目、版本和用例
- 手动/自动执行，实时记录测试结果
- 执行历史追踪和结果对比
- 多维度数据统计和可视化图表

### 👥 项目与团队
- 多项目支持，成员角色权限管理
- 版本管理，测试用例关联
- 个性化用户配置

### 🌍 国际化与其他
- **多语言**：vue-i18n 国际化（中文 zh-cn / 英文 en）
- **用户行为分析**：可选埋点模块，通过 `ANALYTICS_ENABLED` 开关
- **通知集成**：企业微信、钉钉、飞书 Webhook

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Django 4.2 + Django REST Framework |
| 数据库 | MySQL 8.0+ |
| 缓存 / 异步 | Redis + Celery |
| 向量检索 | ChromaDB（持久化于 `chroma_data/`） |
| WebSocket | Django Channels + Daphne |
| 安全认证 | JWT 双 Token 机制（SimpleJWT） |
| API 文档 | drf-spectacular (Swagger / ReDoc) |
| 前端框架 | Vue 3 + Composition API |
| 构建工具 | Vite |
| UI 组件 | Element Plus |
| 状态管理 | Pinia |
| 数据可视化 | ECharts |
| 代码编辑器 | Monaco Editor |
| 自动化引擎 | Selenium, Playwright, Airtest, EasyOCR, OpenCV |
| AI 框架 | browser-use, langchain-openai / langchain-community |
| 测试报告 | Allure |
| 国际化 | vue-i18n (zh-cn / en) |

## 项目结构

```
aitestplat/
├── apps/                           # Django 应用模块
│   ├── users/                      # 用户与认证
│   ├── projects/                   # 项目管理
│   ├── testcases/                  # 测试用例管理
│   ├── testsuites/                 # 测试套件管理
│   ├── executions/                 # 测试执行管理
│   ├── reviews/                    # 用例评审管理
│   ├── defects/                    # 缺陷管理
│   ├── versions/                   # 版本管理
│   ├── reports/                    # 测试报告
│   ├── api_testing/                # API 测试
│   ├── ui_automation/              # UI 自动化测试（含 AI 智能模式）
│   ├── app_automation/             # APP 自动化测试
│   ├── data_factory/               # 数据工厂
│   ├── requirement_analysis/       # AI 需求分析与用例生成
│   │   ├── embedding_service.py    #   Embedding 向量化服务
│   │   ├── knowledge_chunker.py    #   知识智能分块
│   │   ├── knowledge_retriever.py  #   语义检索 + LLM 重排序
│   │   └── vector_store.py         #   ChromaDB 向量存储
│   ├── analytics/                  # 用户行为分析（可选，ANALYTICS_ENABLED）
│   └── core/                       # 核心共享模块 + 管理命令
│       └── management/commands/    # 管理命令
├── backend/                        # Django 项目配置
│   ├── settings.py                 # 数据库 / Redis / Celery / JWT / AI 配置
│   ├── urls.py                     # 根路由
│   └── asgi.py                     # ASGI 入口（WebSocket 支持）
├── frontend/                       # Vue 3 前端
│   └── src/
│       ├── api/                    # API 接口层
│       ├── components/             # 公共组件
│       ├── views/                  # 模块页面（api-testing / ui-automation /
│       │                           #   app-automation / data-factory /
│       │                           #   requirement-analysis / configuration 等）
│       ├── stores/                 # Pinia 状态管理
│       ├── router/                 # 路由配置
│       ├── locales/                # vue-i18n（zh-cn / en）
│       └── utils/                  # 工具函数
├── chroma_data/                    # ChromaDB 向量数据（运行时生成）
├── docs/                           # 使用手册与设计文档
├── media/                          # 上传文件存储
├── logs/                           # 日志
├── requirements.txt
└── manage.py
```

## 快速开始

### 环境要求

- **Python** 3.12+
- **Node.js** 18+
- **MySQL** 8.0+
- **Redis** 6.0+（Celery 与 APP 自动化 WebSocket 需要）
- **Java** 17+（可选，Allure 报告生成需要）

### 后端部署

```bash
# 1. 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 配置数据库、Redis 等连接信息

# 4. 初始化数据库
mysql -u root -p -e "CREATE DATABASE aitestplat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# 5. 初始化配置数据
python manage.py init_locator_strategies      # UI 自动化定位策略
python manage.py load_component_pack          # APP 自动化组件包（--overwrite 覆盖）

# 6. 启动服务（HTTP）
python manage.py runserver

# 需要 WebSocket（APP 自动化实时进度）时用 Daphne 启动：
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### 后端管理命令

所有管理命令位于 `apps/core/management/commands/`：

| 命令 | 说明 |
|------|------|
| `python manage.py run_all_scheduled_tasks` | 运行全部定时任务（API 测试 + UI 自动化） |
| `python manage.py init_locator_strategies` | 初始化 UI 自动化定位策略 |
| `python manage.py download_webdrivers` | 下载 UI 自动化 WebDriver |
| `python manage.py load_component_pack` | 导入 APP 自动化组件包（`--overwrite` 覆盖） |

### 前端部署

```bash
cd frontend
npm install
npm run dev        # 开发模式（http://localhost:3000）
npm run build      # 生产构建
npm run lint       # 代码检查
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档（Swagger） | http://localhost:8000/api/docs/ |
| API 文档（ReDoc） | http://localhost:8000/api/redoc/ |
| Django Admin | http://localhost:8000/admin/ |

## API 结构

所有 API 均以 `/api/` 为前缀：

- `/api/auth/`、`/api/users/`：用户认证与信息
- `/api/requirement-analysis/`：AI 需求分析与用例生成
  - 文档 `documents`、分析 `analyses`、需求 `requirements(-manage)`、生成用例 `test-cases`、任务 `tasks`、用例生成任务 `testcase-generation`
  - 知识库 `knowledge-documents` / `knowledge-entries` / 语义检索 `knowledge`
  - 配置 `ai-models` / `prompts` / `generation-config` / `config`，禅道接入 `zentao-*`
- `/api/projects/`、`/api/versions/`：项目管理 / 版本管理
- `/api/testcases/`、`/api/testsuites/`：用例与套件 CRUD
- `/api/executions/`、`/api/reports/`：测试执行与报告
- `/api/reviews/`：用例评审
- `/api/defects/`：缺陷管理
- `/api/`（api_testing）：API 测试接口
- `/api/ui-automation/`：UI 自动化接口
- `/api/app-automation/`：APP 自动化接口（WebSocket：`ws/app-automation/executions/<execution_id>/`）
- `/api/core/`：核心共享接口
- `/api/data-factory/`：数据工厂
- `/api/analytics/`：行为分析（仅 `ANALYTICS_ENABLED` 时启用）

## 配置说明

### JWT 安全认证

平台采用 JWT 双 Token 机制（SimpleJWT）：

- **Access Token**：60 分钟有效期，用于 API 认证
- **Refresh Token**：7 天有效期，刷新时自动轮换
- **Token 黑名单**：刷新后旧 Refresh Token 自动列入黑名单

### AI 模型配置

在「配置中心 → AI 模型」中按角色配置模型，每个角色仅一个激活配置：

| 角色 | 用途 |
|------|------|
| `writer` | 测试用例编写专家 |
| `reviewer` | 测试评审专家 |
| `browser_use_text` | Browser Use 文本模式（UI 自动化 AI） |
| `api_testcase_generator` | 接口测试用例生成 |
| `embedding` | 知识库向量化嵌入模型 |
| `tokenizer` | 分词模型 |

支持的 AI 提供商：DeepSeek、通义千问、硅基流动、智谱、小米（含小米 coding plan）、OpenAI 兼容接口等。

自定义提示词模板见 `docs/tester.md`（用例编写）与 `docs/tester_pro.md`（用例评审）。

### 通知配置

支持企业微信、钉钉、飞书 Webhook 通知，可按模块独立开关；邮件通知与阿里云短信见 `.env` 配置。

```

## 许可证

MIT License
