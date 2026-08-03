# TestHub - AI 驱动的测试管理平台

<div align="center">

**全栈测试管理平台，集成 AI 需求分析、用例管理、API 测试、UI/APP 自动化**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.3-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

## 项目简介

TestHub 是一个 AI 驱动的测试管理平台，集成了测试用例管理、API 测试、Web UI 自动化、Android APP 自动化、数据工厂、缺陷管理、需求分析等模块，覆盖测试全生命周期。

## 核心功能

### 🤖 AI 智能化
- **需求分析**：自动解析 PDF/Word/TXT 需求文档，AI 提取业务需求并生成测试用例
- **智能助手**：集成 Dify AI 聊天助手，提供测试咨询
- **多模型支持**：DeepSeek、通义千问、硅基流动、OpenAI 等多种 AI 模型
- **Browser-Use 智能模式**：AI 理解页面结构，自动完成浏览器操作

### 📋 测试用例管理
- 用例生命周期管理（创建、编辑、版本控制、归档）
- 步骤化用例设计，支持前置条件、操作步骤、预期结果
- 附件上传、团队协作评论
- 多维度分类（项目、版本、标签）

### 🔍 用例评审
- 多人评审流程，支持评审模板和检查清单
- 多层反馈（整体意见、用例意见、步骤意见）
- 评审状态跟踪（待评审、评审中、已通过、已拒绝）

### 🐛 缺陷管理
- 缺陷全生命周期管理（创建、分配、修复、关闭）
- 流转历史记录，操作人追溯
- 附件上传，状态流转控制

### 🌐 API 测试
- HTTP/WebSocket 协议支持
- 环境变量管理（全局/局部），变量替换
- 测试套件批量执行，断言配置
- 定时任务调度，邮件/Webhook 通知
- Allure 测试报告自动生成

### 🖥️ UI 自动化测试（Web）
- Selenium + Playwright 双引擎支持
- 元素库管理，多种定位策略（ID、XPath、CSS、text 等）
- 页面对象模式（POM）
- 可视化脚本编辑器，支持录制回放
- 多浏览器支持（Chrome / Firefox / Edge）
- AI 智能模式：基于 Browser-Use 的智能浏览器自动化

### 📱 APP 自动化测试（Android）
- 基于 Airtest 框架的图像识别自动化
- 设备管理（本地模拟器 + 远程设备），设备锁定机制
- 三种元素定位方式（图片、坐标、区域）
- 组件化编排 + UI Flow JSON 流程编排
- Celery 异步执行 + pytest + Allure 报告
- WebSocket 实时执行进度推送

### 🏭 数据工厂
- **字符工具**（9 个）：字符串处理、文本对比、正则测试、字数统计等
- **编码工具**（12 个）：Base64、时间戳、Unicode、进制转换、URL 编解码、条形码/二维码等
- **随机工具**（6 个）：随机数、随机字符串、UUID、随机布尔值等
- **加密工具**（8 个）：MD5/SHA 系列哈希、AES 加解密、HMAC 签名
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

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Django 4.2 + Django REST Framework |
| 数据库 | MySQL 8.0+ |
| 缓存 | Redis |
| 异步任务 | Celery |
| WebSocket | Django Channels + Daphne |
| 安全认证 | JWT 双 Token 机制 |
| API 文档 | drf-spectacular (Swagger / ReDoc) |
| 前端框架 | Vue 3.3 + Composition API |
| 构建工具 | Vite 4 |
| UI 组件 | Element Plus |
| 状态管理 | Pinia |
| 数据可视化 | ECharts |
| 代码编辑器 | Monaco Editor |
| 自动化引擎 | Selenium, Playwright, Airtest |
| AI 框架 | browser-use, langchain-openai |
| 测试报告 | Allure |

## 项目结构

```
testhub_platform/
├── apps/                           # Django 应用模块
│   ├── users/                      # 用户管理
│   ├── projects/                   # 项目管理
│   ├── testcases/                  # 测试用例管理
│   ├── testsuites/                 # 测试套件管理
│   ├── executions/                 # 测试执行管理
│   ├── reviews/                    # 用例评审管理
│   ├── defects/                    # 缺陷管理
│   ├── versions/                   # 版本管理
│   ├── reports/                    # 测试报告
│   ├── api_testing/                # API 测试
│   ├── ui_automation/              # UI 自动化测试
│   ├── app_automation/             # APP 自动化测试
│   ├── data_factory/               # 数据工厂
│   ├── requirement_analysis/       # AI 需求分析
│   ├── assistant/                  # 智能助手
│   ├── analytics/                  # 用户行为分析
│   └── core/                       # 核心功能模块
│       └── management/commands/    # 管理命令
├── backend/                        # Django 项目配置
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
├── frontend/                       # Vue 3 前端
│   └── src/
│       ├── api/                    # API 接口层
│       ├── components/             # 公共组件
│       ├── views/                  # 页面视图
│       ├── stores/                 # Pinia 状态管理
│       ├── router/                 # 路由配置
│       └── utils/                  # 工具函数
├── requirements.txt
└── manage.py
```

## 快速开始

### 环境要求

- **Python** 3.12+
- **Node.js** 18+
- **MySQL** 8.0+
- **Redis** 6.0+（可选，APP 自动化需要）
- **Java** 17+（可选，Allure 报告生成需要）

### 后端部署

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 配置数据库连接等信息

# 4. 初始化数据库
mysql -u root -p -e "CREATE DATABASE testhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# 5. 初始化配置
python manage.py init_locator_strategies
python manage.py load_component_pack

# 6. 启动服务
python manage.py runserver

# 可选：启动 Celery（APP 自动化需要）
celery -A backend worker -l info

# 可选：启动定时任务调度器
python manage.py run_all_scheduled_tasks
```

### 前端部署

```bash
cd frontend
npm install
npm run dev        # 开发模式
npm run build      # 生产构建
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/api/docs/ |
| Admin 后台 | http://localhost:8000/admin/ |

## 配置说明

### JWT 安全认证

平台采用 JWT 双 Token 机制：
- **Access Token**：30 分钟有效期，用于 API 认证
- **Refresh Token**：7 天有效期，用于无感刷新 Access Token
- **Token 黑名单**：登出时自动拉黑，防止重放攻击
- **自动刷新**：Token 过期前 5 分钟自动续期

### AI 模型配置

在统一配置中心按角色配置 AI 模型：

| 角色 | 用途 |
|------|------|
| `testcase_writer` | 测试用例编写 |
| `testcase_reviewer` | 测试用例评审 |
| `browser_use_text` | Browser Use 文本模式 |

支持的 AI 提供商：OpenAI、DeepSeek、通义千问、硅基流动、智谱等。

### 通知配置

支持企业微信、钉钉、飞书 Webhook 通知，可按模块独立开关。

## 许可证

MIT License