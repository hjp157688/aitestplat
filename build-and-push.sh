#!/usr/bin/env bash
# 构建 AITestPlat 前后端镜像并按 .docker_env 打标
# 用法:
#   ./build-and-push.sh           # 仅构建
#   ./build-and-push.sh --push    # 构建并推送
set -euo pipefail
cd "$(dirname "$0")"

# 读取 .docker_env 中的标签变量(若存在);docker compose 无需该脚本
if [ -f .docker_env ]; then
  set -a
  # shellcheck source=/dev/null
  source .docker_env
  set +a
fi

REGISTRY="${DOCKER_REGISTRY:-}"
NAMESPACE="${DOCKER_NAMESPACE:-aitestplat}"
VERSION="${IMAGE_VERSION:-latest}"

backend_tag="${NAMESPACE}/backend:${VERSION}"
frontend_tag="${NAMESPACE}/frontend:${VERSION}"

# DOCKER_REGISTRY=https://hub.docker.com/ 表示公有 Hub,不打前缀;其余作为前缀
if [ -n "$REGISTRY" ] && [ "$REGISTRY" != "https://hub.docker.com/" ]; then
  prefix="${REGISTRY%%/}"
  backend_tag="${prefix}/${backend_tag}"
  frontend_tag="${prefix}/${frontend_tag}"
fi

echo ">> 构建 backend -> ${backend_tag}"
docker build -f backend/Dockerfile -t "${backend_tag}" .

echo ">> 构建 frontend -> ${frontend_tag}"
docker build -f frontend/Dockerfile -t "${frontend_tag}" frontend/

if [ "${1:-}" = "--push" ]; then
  echo ">> 推送镜像..."
  docker push "${backend_tag}"
  docker push "${frontend_tag}"
fi

echo ">> 完成"
