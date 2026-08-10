#!/bin/sh
# scheduler 容器命令:周期性执行 run_all_scheduled_tasks(驱动 API/UI 自动化定时任务)
# 间隔由 SCHEDULER_INTERVAL 覆盖,默认 300s
set -e

INTERVAL="${SCHEDULER_INTERVAL:-300}"

echo "[scheduler] run_all_scheduled_tasks every ${INTERVAL}s"
while true; do
    python manage.py run_all_scheduled_tasks
    sleep "$INTERVAL"
done
