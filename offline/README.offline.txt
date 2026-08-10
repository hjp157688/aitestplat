AITestPlat 离线部署包
====================
适用:无法连接外网的服务器(需已装 Docker Engine 20.10+ 及 compose v2 插件)
本包由构建机 build-offline.sh 生成,含 4 个镜像归档 + compose 编排 + 一键安装脚本。

安装(服务器,全程离线)
---------------------
  1. 上传本 tar.gz 到服务器,解压:
       tar -xzf aitestplat-offline-<VER>.tar.gz
  2. 进入目录执行安装(自动加载镜像 + 生成密钥 + 启动):
       cd aitestplat-offline-<VER> && ./install.sh
  3. 访问:
       前端     http://服务器IP:18081
       后端API  http://服务器IP:18181/api/docs/

日常命令
--------
  查看状态:  docker compose --env-file .docker_env ps
  查看日志:  docker compose --env-file .docker_env logs -f --tail 200
  重启:      docker compose --env-file .docker_env up -d --no-build
  停机:      docker compose --env-file .docker_env down
  改端口/密钥: 编辑 .docker_env 里的 FRONTEND_PORT/BACKEND_PORT/SECRET_KEY 等,重跑 ./install.sh

升级
----
  在构建机生成新版本 tar.gz(VER 递增),上传后:
    1. docker load 新镜像(install.sh 自动做;或用 docker load -i images/*.tar)
    2. ./install.sh(数据在命名卷里,升级不清数据)

常见问题
--------
  · "invalid reference format": install 前需 docker load 镜像;install.sh 已自动处理
  · 某端口被占用:改 .docker_env 的 FRONTEND_PORT/BACKEND_PORT 后重跑 install.sh
  · 起不来: docker compose --env-file .docker_env logs -f --tail 200 看报错
  · 需真离线:镜像已内置全部依赖,启动阶段不访问外网(AI/短信等外部 API 为可选)
