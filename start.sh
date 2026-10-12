#!/usr/bin/env bash
# AITestPlat 一键启动脚本
# 用法: ./start.sh
# 依赖: 本机 MySQL(3306)/Redis(6379) 已运行；虚拟环境 ./aitestplat 已就绪
# set -m: 让每个后台任务拥有独立进程组，便于整组杀掉（npm 的 vite 子进程不会成为孤儿）
set -u -m

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$ROOT_DIR/aitestplat/bin/python"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

BACKEND_PID=""
FRONTEND_PID=""
CLEANED=0

cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1
    echo ""
    echo "==> 正在停止服务..."
    [ -n "$FRONTEND_PID" ] && kill -TERM -- "-$FRONTEND_PID" 2>/dev/null
    [ -n "$BACKEND_PID" ] && kill -TERM -- "-$BACKEND_PID" 2>/dev/null
    sleep 1
    # 兜底：TERM 后仍存活的强制杀掉，避免 vite/daphne 残留
    [ -n "$FRONTEND_PID" ] && kill -KILL -- "-$FRONTEND_PID" 2>/dev/null
    [ -n "$BACKEND_PID" ] && kill -KILL -- "-$BACKEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "==> 已全部停止"
}
trap cleanup EXIT INT TERM

port_up() { # host port -> 0 可达
    (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && { exec 3>&- 3<&-; return 0; }
    return 1
}

echo "==> 前置检查"

if [ ! -x "$VENV_PY" ]; then
    echo "✗ 找不到虚拟环境: $VENV_PY"
    exit 1
fi
echo "✓ 虚拟环境: $($VENV_PY --version)"

if ! port_up 127.0.0.1 3306; then
    echo "✗ MySQL 未运行 (127.0.0.1:3306)，请先启动: brew services start mysql"
    exit 1
fi
echo "✓ MySQL 可达"

if port_up 127.0.0.1 6379; then
    echo "✓ Redis 可达"
else
    echo "⚠ Redis 未运行 (127.0.0.1:6379)，APP 自动化实时进度将不可用"
    echo "  如需完整功能请另开终端执行: brew services start redis"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "✗ 前端依赖未安装，请先执行: cd frontend && npm install"
    exit 1
fi
echo "✓ 前端依赖已安装"

echo ""
echo "==> 启动后端 (daphne, http://127.0.0.1:8000)"
(cd "$ROOT_DIR" && exec "$VENV_PY" -m daphne -b 127.0.0.1 -p 8000 backend.asgi:application) \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "==> 启动前端 (vite dev, http://localhost:3000)"
(cd "$FRONTEND_DIR" && exec npm run dev) > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

sleep 3

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "✗ 后端启动失败，最近日志:"
    tail -20 "$LOG_DIR/backend.log"
    exit 1
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "✗ 前端启动失败，最近日志:"
    tail -20 "$LOG_DIR/frontend.log"
    exit 1
fi

echo ""
echo "=========================================="
echo "  ✓ 启动完成"
echo "  前端: http://localhost:3000"
echo "  后端: http://127.0.0.1:8000/api/docs/"
echo "  日志: logs/backend.log / logs/frontend.log"
echo "  按 Ctrl+C 停止全部服务"
echo "=========================================="

wait
