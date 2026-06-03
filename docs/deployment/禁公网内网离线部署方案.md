# iDeer 禁公网内网离线部署方案

## 1. 方案目标

本方案用于在不能访问公网的企业内网中部署 iDeer。整体思路是：先在一台可以访问依赖源或企业镜像源的构建机上打包，再把离线包拷贝到内网服务器上运行。

面向的使用场景：

- 内网服务器不能访问公网。
- 内网服务器可以运行 Docker 和 Docker Compose v2。
- 部署人员希望尽量少改命令，按固定步骤完成启动。
- 模型服务地址、API Key、运行数据目录需要在部署后单独调整，不重新构建镜像。

本方案当前覆盖：

- 架构：`linux/amd64`
- 运行方式：`docker compose`
- 服务组成：`nginx`、`frontend`、`gateway`
- 沙箱方式：本地沙箱模式
- 交付形式：Docker 镜像 tar 包 + 源码 tar 包 + 启停脚本 + 作业指导书

## 2. 部署目录和路径原则

示例部署目录使用：

```text
/home/deploy/ideer
```

这只是示例，不是强制路径。可以换成任意有读写权限的目录，例如：

```text
/home/yourname/ideer
/data/apps/ideer
/srv/ideer
```

真实路径由以下任一方式决定：

1. 当前所在目录：进入离线包目录后直接运行 `./deploy-intranet.sh up`。
2. 命令参数：`./deploy-intranet.sh --bundle-root /home/deploy/ideer up`。
3. 环境变量：`IDEER_BUNDLE_ROOT=/home/deploy/ideer ./deploy-intranet.sh up`。

原理说明：

- 离线包里的 `deploy-intranet.sh` 默认把“脚本所在目录”记作 bundle root。
- 如果从源码仓库的 `scripts/deploy-intranet.sh` 运行，默认 bundle root 是仓库根目录。
- `--bundle-root` 和 `IDEER_BUNDLE_ROOT` 用于显式指定 bundle root，适合不在部署目录内执行脚本的场景。
- bundle root 下会生成 `source/`、`runtime/`、`env.intranet`。
- 容器内路径是固定的，例如 `/app/backend/config.yaml`；宿主机路径是可配置的，例如 `/home/deploy/ideer/runtime/config.yaml`。
- Docker Compose 通过 volume 把宿主机 runtime 文件挂载到容器内固定路径。

## 3. 离线包内容

打包脚本默认输出目录：

```text
dist/intranet/ideer-<version>/
```

目录内包含：

| 文件 | 用途 |
| --- | --- |
| `ideer-images-<version>.tar` | Docker 镜像包，内网服务器用 `docker load` 导入 |
| `ideer-source-<version>.tar.gz` | 运行所需源码、compose、脚本、基础配置和归零排故智能体预置可用配置 |
| `deploy-intranet.sh` | 内网服务器上的统一部署入口 |
| `禁公网内网离线部署作业指导书.md` | 操作手册 |
| `MANIFEST.txt` | 离线包清单 |
| `SHA256SUMS` | 文件完整性校验 |

原理说明：

- 镜像包负责“程序运行环境”。
- 源码包负责“运行配置、compose 文件、脚本和静态资源”。
- 离线包根目录不再提供参考 Compose 或参考 env 文件，真实 Compose 来自 `source/docker/docker-compose.intranet.yaml`，真实环境变量文件由 `prepare` 生成。
- runtime 配置不打进镜像，便于部署后修改模型地址、API Key 和运行数据。

## 4. 运行时目录结构

在内网服务器执行 `./deploy-intranet.sh prepare` 后，部署目录会变成类似：

```text
/home/deploy/ideer/
├── ideer-images-<version>.tar
├── ideer-source-<version>.tar.gz
├── deploy-intranet.sh
├── env.intranet
├── source/
│   ├── backend/
│   ├── frontend/
│   ├── docker/
│   └── ...
└── runtime/
    ├── config.yaml
    ├── .env
    ├── frontend.env
    ├── extensions_config.json
    └── data/
        ├── agents/
        │   └── fault-zeroing/
        │       ├── config.yaml
        │       └── SOUL.md
        ├── .better-auth-secret
        └── .internal-auth-token
```

关键文件说明：

| 文件 | 谁读取 | 作用 |
| --- | --- | --- |
| `runtime/config.yaml` | Gateway | iDeer 主配置，模型、工具、沙箱等配置在这里 |
| `runtime/.env` | Gateway | 后端环境变量，例如模型 API Key |
| `runtime/frontend.env` | Frontend | 前端/Next.js 环境变量 |
| `runtime/extensions_config.json` | Gateway | MCP、技能等扩展配置 |
| `env.intranet` | Docker Compose | 告诉 compose 宿主机文件在哪里、使用哪些镜像 |
| `runtime/data/agents/fault-zeroing/config.yaml`、`SOUL.md` | Agents API / Gateway | 归零排故智能体预置可用配置，作为共享智能体对所有用户可见 |
| `runtime/data/.better-auth-secret` | Frontend/Auth | 持久化登录会话密钥 |
| `runtime/data/.internal-auth-token` | Gateway | 多 worker 内部调用共享 token |

原理说明：

- `runtime/` 是真正需要长期保留的运行配置和数据目录。
- `source/` 可以随版本升级替换。
- `runtime/data/` 中的 secret 不要随便删除，否则可能导致登录态失效或内部调用异常。

## 5. 配置生成策略

`prepare` 会自动做这些事：

1. 解压 `ideer-source-<version>.tar.gz` 到 `source/`。
2. 从模板生成 `runtime/config.yaml`。
3. 从模板生成 `runtime/.env` 和 `runtime/frontend.env`。
4. 生成或复用 `runtime/data/.better-auth-secret`。
5. 生成或复用 `runtime/data/.internal-auth-token`。
6. 按当前部署目录生成 `env.intranet`。
7. 安装归零排故智能体预置可用配置到 `runtime/data/agents/fault-zeroing/`，并把五个 custom subagent 合并进 `runtime/config.yaml`。

当前修复后的关键行为：

- 如果模板里是裸 `models:`，脚本会生成合法的 `models: []`，避免 `config.yaml` 格式错误。
- `BETTER_AUTH_SECRET` 会从 `runtime/data/.better-auth-secret` 复用，不会因为重建 `env.intranet` 就变化。
- `IDEER_INTERNAL_AUTH_TOKEN` 会从 `runtime/data/.internal-auth-token` 复用，保证多 worker 内部调用一致。
- `runtime/.env` 是隐藏文件，普通 `ls runtime` 可能看不到；请用 `ls -la runtime` 或 `ls -l runtime/.env` 检查。
- `prepare`、`up/start`、`restart` 默认会安装共享归零排故智能体；`IDEER_INSTALL_FAULT_ZEROING=0` 可临时跳过。
- 如果 `runtime/data/agents/fault-zeroing/` 已有不同内容，脚本会拒绝覆盖，需现场人工确认后处理。

注意：

- `models: []` 只能保证应用配置格式正确。
- 要真正使用智能体对话，仍需要在 `runtime/config.yaml` 中补充至少一个模型，并在 `runtime/.env` 中填写对应 API Key。

## 6. 模型配置方式

模型配置分两部分：

1. `runtime/config.yaml`：写模型类型、模型名、服务地址、引用哪个环境变量。
2. `runtime/.env`：写真实 API Key 或占位 key。

OpenAI-compatible 内网模型示例：

```yaml
models:
  - name: intranet-qwen
    display_name: Intranet Qwen
    use: langchain_openai:ChatOpenAI
    model: Qwen3-32B
    api_key: $OPENAI_API_KEY
    base_url: http://10.10.1.20:8000/v1
    request_timeout: 600.0
    max_retries: 2
    max_tokens: 8192
    temperature: 0.7
    supports_vision: false
```

对应 `runtime/.env`：

```bash
OPENAI_API_KEY=dummy
```

原理说明：

- `api_key: $OPENAI_API_KEY` 表示从 `runtime/.env` 里读取 `OPENAI_API_KEY`。
- 很多 OpenAI-compatible 服务即使不校验 key，客户端也要求字段存在，可以填 `dummy`。
- 容器内的 `localhost` 指容器自己，不是宿主机。如果模型服务在宿主机上，通常用 `host.docker.internal`；如果模型服务在其他内网机器上，写那台机器的内网 IP。

## 7. 启动和健康检查

启动命令：

```bash
./deploy-intranet.sh up
```

脚本会执行：

1. `prepare`：准备源码和 runtime 配置。
2. `docker load`：导入镜像。
3. `docker compose up -d`：后台启动容器。
4. 健康检查：访问 `/health`、`/api/v1/auth/setup-status` 和首页 `/`。

原理说明：

- `/health` 能证明 Gateway 能响应。
- `/api/v1/auth/setup-status` 能证明认证接口可用。
- 首页 `/` 通过 nginx 转发到 Frontend，能证明浏览器界面可访问。
- 如果 `/health` 或 `/api/v1/auth/setup-status` 失败，优先看 `gateway` 日志；如果首页 `/` 失败，优先看 `frontend` 和 `nginx` 日志。

## 8. 安全和稳定性说明

- 不要把真实 API Key 写进源码目录或提交到 Git。
- 模型 API Key 写在内网服务器的 `runtime/.env`。
- `runtime/data/.better-auth-secret` 和 `runtime/data/.internal-auth-token` 不要随便删除。
- 默认离线 compose 不挂载 `.claude` 和 `.codex`，避免部署依赖个人 home 目录。
- 如果确实使用 Claude Code 或 Codex CLI 认证，需要单独设计认证目录挂载方案。

## 9. 升级和回滚原则

升级时建议：

1. 保留旧版本离线包。
2. 备份 `runtime/`。
3. 导入新镜像。
4. 替换 `source/`。
5. 保留原 `runtime/`。
6. 运行 `./deploy-intranet.sh restart`。

回滚时：

1. 重新加载旧镜像包。
2. 切回旧源码包或旧部署目录。
3. 保留原 `runtime/` 或恢复备份。
4. 执行 `./deploy-intranet.sh restart`。

原理说明：

- 镜像和源码可以升级。
- `runtime/` 保存本地配置和运行状态，应作为重点备份对象。

## 10. 验证计划

构建机验证：

```bash
bash -n scripts/package-intranet-offline.sh scripts/deploy-intranet.sh
scripts/package-intranet-offline.sh --version test-intranet --force
```

内网服务器验证：

```bash
./deploy-intranet.sh prepare
ls -la runtime
ls -l runtime/.env runtime/config.yaml runtime/frontend.env runtime/extensions_config.json
grep '^IDEER_INTERNAL_AUTH_TOKEN=' env.intranet
./deploy-intranet.sh up
curl -fsS http://127.0.0.1:2026/health
curl -fsS http://127.0.0.1:2026/api/v1/auth/setup-status
curl -fsS http://127.0.0.1:2026/
```

前端验证：

1. 浏览器访问 `http://<内网服务器IP>:2026`。
2. 首次使用时完成管理员初始化。
3. 退出后重新登录。
4. 能进入 `/workspace`。

## 11. 关键假设

- 内网服务器已安装 Docker 和 Docker Compose v2。
- 当前方案不包含 Kubernetes provisioner。
- 当前方案不依赖内网镜像仓库。
- 运行配置由宿主机 `runtime/` 管理，不写入镜像。
