# AITestPlat 后端镜像 - 全量依赖(UI/APP 自动化 + OCR + Allure)
# 构建上下文 = 仓库根目录(见根 .dockerignore);基镜像与本地 Python 3.12 一致
FROM python:3.12-slim-bookworm

# 系统依赖:
#   build-essential g++              - 部分 wheel 缺失时源码编译兜底(lxml/cffi 等)
#   libgl1 libglib2.0-0 libgomp1     - opencv / easyocr 运行库
#   libzbar0                         - pyzbar 条码识别
#   default-jre-headless             - Allure 命令行为 Java 程序
#   curl                             - 下载 Allure
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libzbar0 \
        default-jre-headless \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖(利用层缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Allure 命令行(Linux,与本地开发版本 2.34.1 一致)
# 解压到 /app/allure —— 代码按 {BASE_DIR}/allure/bin/allure 查找(已核实两个调用点)
RUN curl -fsSL -o /tmp/allure.tgz \
        https://github.com/allure-framework/allure2/releases/download/2.34.1/allure-2.34.1.tgz \
    && tar -xzf /tmp/allure.tgz -C /app \
    && mv /app/allure-2.34.1 /app/allure \
    && rm -f /tmp/allure.tgz \
    && /app/allure/bin/allure --version

# Playwright Chromium(UI 自动化开箱即用;--with-deps 自动 apt 装浏览器依赖)
RUN playwright install --with-deps chromium

# 复制项目源码(apps.* 已确认是 INSTALLED_APPS 前缀,必须原样落在 /app/apps)
COPY manage.py .
COPY backend/ backend/
COPY apps/ apps/

# 运行时目录(Django 默认路径;static_files 由卷覆盖)
RUN mkdir -p static_files media logs chroma_data

# 公用入口与 scheduler 命令
COPY backend/entrypoint.sh /entrypoint.sh
COPY backend/scheduler-loop.sh /scheduler-loop.sh
RUN chmod +x /entrypoint.sh /scheduler-loop.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "backend.asgi:application"]
