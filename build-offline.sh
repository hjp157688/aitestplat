#!/usr/bin/env bash
# AITestPlat 离线部署包构建(在【有 Docker + 外网】的机器上执行)
# 产物:仓库根 aitestplat-offline-<VER>.tar.gz
# 用法:
#   ./build-offline.sh            # VER=IMAGE_VERSION(.docker_env) 或最近提交日期
#   VER=1.2.0 ./build-offline.sh  # 显式指定版本
set -euo pipefail
cd "$(dirname "$0")"

# 读取 .docker_env 标签变量(存在则用)
if [ -f .docker_env ]; then
  set -a
  # shellcheck source=/dev/null
  source .docker_env
  set +a
fi

NAMESPACE="${DOCKER_NAMESPACE:-aitestplat}"
if [ -n "${VER:-}" ]; then
  IMAGE_VERSION="$VER"
fi
VERSION="${IMAGE_VERSION:-$(git log -1 --format=%cd --date=short 2>/dev/null || echo 0.1.0)}"
VERSION="${VERSION//\//-}"     # 防路径/标签非法字符
PLATFORM="${PLATFORM:-linux/amd64}"
PKG="aitestplat-offline-${VERSION}"
OUT="dist-offline"

BACKEND_IMG="${NAMESPACE}/backend:${VERSION}"
FRONTEND_IMG="${NAMESPACE}/frontend:${VERSION}"

echo ">> NAMESPACE=${NAMESPACE}  VERSION=${VERSION}  PLATFORM=${PLATFORM}"
command -v docker >/dev/null || { echo "!! 需要 docker(可连外网)"; exit 1; }

echo ">> 构建 backend -> ${BACKEND_IMG}"
docker build --platform "${PLATFORM}" -f backend/Dockerfile -t "${BACKEND_IMG}" .
echo ">> 构建 frontend -> ${FRONTEND_IMG}"
docker build --platform "${PLATFORM}" -f frontend/Dockerfile -t "${FRONTEND_IMG}" frontend/

echo ">> 拉取基础镜像(原 tag 入包,供 compose 直接引用)"
docker pull --platform "${PLATFORM}" mysql:8.0
docker pull --platform "${PLATFORM}" redis:7-alpine

echo ">> 组装 ${OUT}/${PKG}/ ..."
rm -rf "${OUT}/${PKG}"
mkdir -p "${OUT}/${PKG}/images" "${OUT}/${PKG}/deploy"

cp offline/install.sh          "${OUT}/${PKG}/install.sh"
cp offline/README.offline.txt  "${OUT}/${PKG}/README.offline.txt"
cp docker-compose.yml          "${OUT}/${PKG}/docker-compose.yml"
cp deploy/nginx.conf           "${OUT}/${PKG}/deploy/nginx.conf"
# 预填与镜像 tag 一致的 namespace/version(不含任何密钥)
sed -E "s|^DOCKER_NAMESPACE=.*|DOCKER_NAMESPACE=${NAMESPACE}|; s|^IMAGE_VERSION=.*|IMAGE_VERSION=${VERSION}|" \
  .docker_env.example > "${OUT}/${PKG}/.docker_env.example"

echo ">> docker save ..."
docker save -o "${OUT}/${PKG}/images/backend.tar" "${BACKEND_IMG}"
docker save -o "${OUT}/${PKG}/images/frontend.tar" "${FRONTEND_IMG}"
docker save -o "${OUT}/${PKG}/images/mysql.tar" mysql:8.0
docker save -o "${OUT}/${PKG}/images/redis.tar" redis:7-alpine

echo ">> SHA256SUMS ..."
( cd "${OUT}/${PKG}" && { command -v sha256sum >/dev/null 2>&1 && sha256sum images/*.tar > SHA256SUMS || shasum -a 256 images/*.tar > SHA256SUMS; } )

echo ">> 打包 ..."
tar -czf "aitestplat-offline-${VERSION}.tar.gz" -C "${OUT}" "${PKG}"

echo ">> 完成: $(pwd)/aitestplat-offline-${VERSION}.tar.gz"
ls -lh "aitestplat-offline-${VERSION}.tar.gz"
