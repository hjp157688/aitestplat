#!/usr/bin/env bash
# AITestPlat 离线部署安装脚本(服务器侧自动,全程零外网)
# 用法: ./install.sh   (可重复执行,幂等)
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[1;32m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[install]\033[0m %s\n' "$*" >&2; }

# --- 1. 预检 ---
if ! command -v docker >/dev/null 2>&1; then
  err "未找到 docker,请先安装 Docker Engine 20.10+"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "未找到 'docker compose' (v2 插件)。Docker Engine 20.10+ 通常自带;缺插件请安装 docker-compose-plugin 后重试。"
  exit 1
fi
free_gb=$(df -k . | awk 'NR==2{print int($4/1024/1024)}')
say "磁盘可用: ${free_gb} GB(镜像约 8-10GB,建议 >=15GB)"
if [ "${free_gb:-0}" -lt 15 ]; then
  warn "可用空间低于 15GB,可能不够,请留意"
fi

# --- 2. 可选:完整性校验 ---
if [ -f SHA256SUMS ] && command -v sha256sum >/dev/null 2>&1; then
  say "校验 SHA256SUMS ..."
  if ! sha256sum -c SHA256SUMS >/dev/null 2>&1; then
    err "SHA256 校验失败,包可能损坏,终止。请重新传输。"
    exit 1
  fi
  say "SHA256 校验通过"
fi

# --- 3. 加载镜像(幂等) ---
for img in images/*.tar; do
  [ -e "$img" ] || { warn "缺少镜像归档: $img"; continue; }
  say "加载镜像 $img ..."
  docker load -i "$img"
done

# --- 4. 生成 .docker_env(仅首次;已存在则不动) ---
gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v xxd >/dev/null 2>&1; then
    head -c 32 /dev/urandom | xxd -p | tr -d '\n'
  else
    od -A n -t x1 -N 32 /dev/urandom | tr -d ' \n'
  fi
}
if [ ! -f .docker_env ]; then
  say "首次运行,依据 .docker_env.example 生成 .docker_env(自动随机密钥)..."
  cp .docker_env.example .docker_env
  # shellcheck disable=SC2028
  sed -i.bak \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(gen_secret)|" \
    -e "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=$(gen_secret)|" \
    -e "s|^DB_PASSWORD=.*|DB_PASSWORD=$(gen_secret)|" \
    .docker_env
  rm -f .docker_env.bak
  say "已生成 .docker_env(如需调整端口/密钥,改后重跑本脚本)"
else
  say ".docker_env 已存在,保留现配置"
fi

# --- 5. 启动(显式 --no-build:离线不尝试联网构建) ---
say "启动: docker compose --env-file .docker_env up -d --no-build"
docker compose --env-file .docker_env up -d --no-build

# --- 6. 等待就绪 ---
health_check() { # $1=url;curl 或 wget 任一,成功返回 0
  if command -v curl >/dev/null 2>&1; then
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$1" 2>/dev/null || true)" = "200" ]
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O /dev/null --timeout=3 "$1" 2>/dev/null
  else
    return 1
  fi
}
say "等待服务就绪(最长 180s)..."
frontend_ok=0; backend_ok=0
for _ in $(seq 1 60); do
  if [ "$frontend_ok" -eq 0 ] && health_check "http://localhost:18081/health"; then frontend_ok=1; fi
  if [ "$backend_ok" -eq 0 ] && health_check "http://localhost:18181/api/docs/"; then backend_ok=1; fi
  if [ "$frontend_ok" -eq 1 ] && [ "$backend_ok" -eq 1 ]; then break; fi
  sleep 3
done

docker compose --env-file .docker_env ps

[ "$frontend_ok" -eq 1 ] && say "前端就绪: http://localhost:18081"
[ "$frontend_ok" -eq 0 ] && warn "180s 内前端未就绪,请: docker compose --env-file .docker_env logs -f --tail 200"
[ "$backend_ok" -eq 1 ] && say "后端 API 就绪: http://localhost:18181/api/docs/"
[ "$backend_ok" -eq 0 ] && warn "180s 内后端未就绪,请: docker compose --env-file .docker_env logs -f --tail 200"

say "完成。管理: docker compose --env-file .docker_env ps|logs -f|up -d --no-build|down"