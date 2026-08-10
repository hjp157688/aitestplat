#!/bin/sh
# AITestPlat 容器入口:等依赖 → 迁移 → 静态 → exec 用户命令(backend/scheduler 共用)
set -e

echo "[entrypoint] waiting for MySQL..."
MAX_DB_WAIT="${MAX_DB_WAIT:-60}"
n=0
until python manage.py check --database default >/dev/null 2>&1; do
    n=$((n + 1))
    if [ "$n" -ge "$MAX_DB_WAIT" ]; then
        echo "[entrypoint] DB not reachable after ${MAX_DB_WAIT} tries, giving up"
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] DB ready"

# 自动迁移:migrations 文件未全部入库,启动时本地生成并应用(均为幂等)
echo "[entrypoint] makemigrations..."
python manage.py makemigrations --noinput

echo "[entrypoint] migrate..."
python manage.py migrate --noinput

echo "[entrypoint] collectstatic..."
python manage.py collectstatic --noinput

echo "[entrypoint] starting: $*"
exec "$@"
