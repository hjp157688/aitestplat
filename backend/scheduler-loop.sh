#!/bin/sh
# scheduler 容器命令:周期性执行 run_all_scheduled_tasks(驱动 API/UI 自动化定时任务)
# 间隔由 SCHEDULER_INTERVAL 覆盖,默认 300s
set -e

INTERVAL="${SCHEDULER_INTERVAL:-300}"

echo "[scheduler] run_all_scheduled_tasks every ${INTERVAL}s"
while true; do
    # 单个任务失败不中断循环(否则 set -e 使容器崩溃重启,触发整轮迁移/静态重建)
    python manage.py run_all_scheduled_tasks || echo "[scheduler] run_all_scheduled_tasks failed, continuing in ${INTERVAL}s"
    sleep "$INTERVAL"
done
