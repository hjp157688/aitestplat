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

Windows 部署说明
---------------  (服务器或构建机是 Windows 时)
  1. 跑 compose(全栈起/日常管理):装 Docker Desktop for Windows(WSL2 后端)后,
     PowerShell / CMD 里直接执行(命令与 Linux 完全一致):
       docker compose --env-file .docker_env up -d --no-build
       docker compose --env-file .docker_env ps
  2. 跑 bash 脚本(build-offline.sh / install.sh):Windows 无原生 bash,请用
     「Git for Windows 自带的 Git Bash」或 WSL,在里面执行:
       ./install.sh           (或: bash install.sh)
       ./build-offline.sh     (或: bash build-offline.sh)
     install.sh 用到的 openssl 由 Git Bash 自带;若缺失会走 /dev/urandom+od 兜底,
     同样可生成满熵密钥。
  3. 行尾坑(重要):git 在 Windows 默认(autocrlf=true)会把 *.sh 打成 CRLF,
     容器里的 entrypoint.sh 会因此报 "not found"/bad interpreter 起不来。
     仓库已带 .gitattributes 强制 LF,新克隆一般不用处理;若仍报错,执行:
       git config core.autocrlf false
       git rm --cached -r . >/dev/null
       git reset --hard
     然后重新 ./install.sh。
  4. 端口占用/防火墙:对外端口(默认为 18081/18181)需在 Windows 防火墙放行,
     或改 .docker_env 的 FRONTEND_PORT/BACKEND_PORT。

