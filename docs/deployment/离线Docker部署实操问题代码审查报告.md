# 离线 Docker 部署实操问题代码审查报告

日期：2026-05-27

## 审查背景

本次审查聚焦当前项目的内网离线 Docker 部署功能，结合实操中暴露的三个问题进行代码定位：

1. env 文件命名不一致导致脚本运行失败。
2. 容器启动后前端界面无渲染，输入登录信息后无法进入主页。
3. 启动容器时显示 `config.yaml` 文件格式错误。

审查范围主要包括：

- `scripts/deploy-intranet.sh`
- `scripts/package-intranet-offline.sh`
- `docker/docker-compose.intranet.yaml`
- `docs/deployment/禁公网内网离线部署作业指导书.md`
- `frontend/src/core/auth/server.ts`
- `frontend/src/app/workspace/layout.tsx`
- `config.example.yaml`
- `backend/packages/harness/deerflow/config/app_config.py`
- `backend/app/gateway/internal_auth.py`
- `backend/app/channels/manager.py`
- `scripts/deploy.sh`

说明：CodeRabbit CLI 已安装，但本次无法完成 agent 登录，错误为：

```text
authentication_failed: Failed to start server. Is port 0 in use?
```

因此本文为人工代码审查结论，不标记为 CodeRabbit 审查结果。

## 总体结论

当前离线 Docker 部署链路存在可复现的运行时配置合同不一致问题。最关键的风险不是 Docker 镜像本身，而是离线部署脚本在 `prepare` 阶段生成的运行时配置文件不能保证被应用成功加载。

其中，`config.example.yaml` 被直接复制为运行时 `config.yaml` 是最高优先级问题。该模板中 `models:` 下没有实际列表项，YAML 解析后为 `null`，但后端 `AppConfig` 要求 `models` 必须是 list，导致 Gateway 启动阶段直接失败。这会进一步造成前端 SSR 无法访问 Gateway，从而表现为登录后无法进入主页或页面无渲染。

同时，同目录旧审查报告中的意见经核实后，除“离线部署误用 `nginx.local.conf` 导致日志不进 stdout/stderr”这一条不成立外，其余可复现或有明确代码风险的意见已合并到本文。

## 问题 1：运行时 env 文件命名合同不一致

严重级别：高

### 代码证据

`scripts/deploy-intranet.sh` 在 `seed_runtime()` 中生成前端环境文件：

```bash
seed_file "$RUNTIME_DIR/frontend.env" "$SOURCE_DIR/frontend/.env.example"
```

同一脚本生成 `env.intranet` 时写入：

```bash
DEER_FLOW_FRONTEND_ENV_FILE=$RUNTIME_DIR/frontend.env
```

`docker/docker-compose.intranet.yaml` 中前端容器读取：

```yaml
env_file:
  - ${DEER_FLOW_FRONTEND_ENV_FILE:-../frontend/.env}
```

但作业指导书的故障提示写的是：

```text
frontend 启动失败：确认 frontend/.env 存在
```

### 影响

离线部署中同时出现三种命名或位置：

- `runtime/frontend.env`
- `frontend/.env`
- compose fallback `../frontend/.env`

运维按文档补 `frontend/.env` 时，实际 compose 仍可能读取 `runtime/frontend.env`。如果 `env.intranet` 缺失或被手工修改，compose 又会回退到 `../frontend/.env`，导致脚本、文档和容器运行时读取的文件不一致。

### 建议修复

统一离线部署的前端 env 文件合同，建议只使用：

```text
runtime/frontend.env
```

需要同步修改：

1. `scripts/deploy-intranet.sh`：启动前显式校验 `$RUNTIME_DIR/frontend.env` 存在。
2. `docker/docker-compose.intranet.yaml`：保留 `${DEER_FLOW_FRONTEND_ENV_FILE}`，但避免误导性 fallback。
3. `docs/deployment/禁公网内网离线部署作业指导书.md`：把 `frontend/.env` 改为 `runtime/frontend.env`。
4. `scripts/package-intranet-offline.sh` 生成的 `env.intranet.example`：保持同一命名。

## 问题 2：离线脚本生成的 config.yaml 默认不可启动

严重级别：高

### 代码证据

`scripts/deploy-intranet.sh` 直接将模板复制为运行时配置：

```bash
seed_file "$RUNTIME_DIR/config.yaml" "$SOURCE_DIR/config.example.yaml"
```

`config.example.yaml` 中模型配置区域为：

```yaml
models:
  # Example: ...
```

因为所有模型项都被注释，YAML 解析结果是：

```python
{"models": None}
```

后端配置模型定义为：

```python
models: list[ModelConfig] = Field(default_factory=list, description="Available models")
```

`AppConfig.from_file()` 直接执行：

```python
result = cls.model_validate(config_data)
```

实测加载 `config.example.yaml` 会报：

```text
ValidationError: models
  Input should be a valid list
```

### 影响

首次离线部署执行 `prepare` 后得到的 `runtime/config.yaml` 不是可运行配置。Gateway 在启动阶段读取该文件并失败，容器会出现启动失败或反复重启。

这与实操中“启动容器时显示 config.yaml 文件格式错误”高度一致。

### 建议修复

不要直接把完整 `config.example.yaml` 当运行时配置。

可选修复路径：

1. 将 `config.example.yaml` 中的空模型段改为合法空列表：

```yaml
models: []
```

2. 更推荐：`deploy-intranet.sh prepare` 生成一份最小运行配置，明确要求运维填入至少一个模型。
3. 在 `prepare` 或 `up` 阶段增加配置校验，失败时提前终止并提示具体文件路径。

建议增加类似校验：

```bash
python3 -c "from deerflow.config.app_config import AppConfig; AppConfig.from_file('$RUNTIME_DIR/config.yaml')"
```

离线环境未必有宿主机 Python 依赖，因此也可以提供容器内校验命令，或在 Gateway 启动前通过临时容器执行。

## 问题 3：前端登录后无法进入主页的根因可能在 Gateway 启动失败

严重级别：高

### 代码证据

登录页提交登录请求后跳转：

```ts
router.push(redirectPath);
```

默认 `redirectPath` 为：

```ts
const redirectPath = validateNextParam(nextParam) ?? "/workspace";
```

`/workspace` 不是纯客户端页面，布局层会在服务端调用：

```ts
const result = await getServerSideUser();
```

`getServerSideUser()` 会由 Next 容器访问 Gateway：

```ts
const res = await fetch(`${internalGatewayUrl}/api/v1/auth/me`, {
  headers: { Cookie: `access_token=${sessionCookie.value}` },
  cache: "no-store",
  signal: controller.signal,
});
```

离线 compose 中前端容器配置为：

```yaml
environment:
  - BETTER_AUTH_SECRET=${BETTER_AUTH_SECRET}
  - DEER_FLOW_INTERNAL_GATEWAY_BASE_URL=http://gateway:8001
```

### 影响

如果 Gateway 因 `config.yaml` 校验失败无法启动，浏览器侧登录请求可能失败，或者登录后 `/workspace` 的服务端渲染无法完成 `/api/v1/auth/me` 检查。

用户侧表现可能是：

- 前端页面空白或无渲染。
- 登录后仍停留在登录页。
- 跳转主页后显示服务不可用。
- 容器表面上都启动了，但前端无法进入工作区。

### 建议修复

1. 先修复 `config.yaml` 默认不可启动问题。
2. `deploy-intranet.sh up` 不应只执行 `docker compose up -d`，应增加健康检查：

```bash
docker compose ps
curl -fsS http://127.0.0.1:${PORT:-2026}/health
curl -fsS http://127.0.0.1:${PORT:-2026}/api/v1/auth/setup-status
```

3. compose 中为 `gateway`、`frontend`、`nginx` 增加 `healthcheck`。
4. 作业指导书中把“前端无渲染/登录后无法进入主页”定位顺序写清楚：先查 Gateway 日志，再查前端日志，最后查 nginx 代理。

## 问题 4：离线 compose 缺少 DEER_FLOW_INTERNAL_AUTH_TOKEN

严重级别：高

### 代码证据

正式 Docker compose 在 Gateway 环境变量中注入内部鉴权 token：

```yaml
- DEER_FLOW_INTERNAL_AUTH_TOKEN=${DEER_FLOW_INTERNAL_AUTH_TOKEN}
```

`scripts/deploy.sh` 会把该 token 生成并持久化到：

```text
$DEER_FLOW_HOME/.internal-auth-token
```

但 `docker/docker-compose.intranet.yaml` 的 Gateway `environment` 中没有该变量，`scripts/deploy-intranet.sh` 的 `seed_runtime()` 和 `env.intranet` 生成逻辑也没有生成或持久化它。

后端内部鉴权实现位于 `backend/app/gateway/internal_auth.py`：

```python
def _load_internal_auth_token() -> str:
    token = os.environ.get(INTERNAL_AUTH_ENV_VAR)
    if token:
        return token
    return secrets.token_urlsafe(32)
```

这意味着未设置环境变量时，每个 Gateway worker 会在进程内生成自己的 token。

`backend/app/channels/manager.py` 会使用：

```python
create_internal_auth_headers()
```

向 Gateway 内部 API 发起请求；`backend/app/gateway/auth_middleware.py` 则用当前 worker 的 token 校验请求。

### 影响

离线 compose 默认 `GATEWAY_WORKERS` 为 4。多 worker 场景下，如果内部调用发起方和接收方落到不同 worker，而这些 worker 各自生成了不同 token，IM 渠道或内部任务调用可能出现鉴权失败。

纯 Web UI 主链路不一定立刻触发该问题，但这是离线部署与正式 Docker 部署行为不一致的明确风险。

### 建议修复

1. 在 `docker/docker-compose.intranet.yaml` 的 Gateway 环境变量中补充：

```yaml
- DEER_FLOW_INTERNAL_AUTH_TOKEN=${DEER_FLOW_INTERNAL_AUTH_TOKEN}
```

2. 在 `scripts/deploy-intranet.sh` 中仿照 `scripts/deploy.sh` 生成并持久化：

```bash
_internal_auth_token_file="$RUNTIME_DIR/data/.internal-auth-token"
```

3. 在 `env.intranet` 和 `env.intranet.example` 中写入稳定的 `DEER_FLOW_INTERNAL_AUTH_TOKEN`。

## 问题 5：源码包可能打入本机 frontend/.env，放大 env 混乱和泄漏风险

严重级别：中

### 代码证据

`scripts/package-intranet-offline.sh` 打包源码目录时排除了部分生成物：

```bash
--exclude='.git'
--exclude='dist'
--exclude='backend/.venv'
--exclude='backend/.deer-flow'
--exclude='backend/.pytest_cache'
--exclude='backend/__pycache__'
--exclude='frontend/node_modules'
--exclude='frontend/.next'
--exclude='frontend/.cache'
--exclude='node_modules'
--exclude='logs'
--exclude='*.log'
```

但没有排除：

- `frontend/.env`
- `frontend/test-results`
- `frontend/playwright-report`
- `frontend/tsconfig.tsbuildinfo`
- `backend/.ruff_cache`

当前工作区中确实存在 `frontend/.env`。

### 影响

1. 可能把本机配置或敏感信息打入离线源码包。
2. 离线包中同时存在源码目录的 `frontend/.env` 和 runtime 目录的 `frontend.env`，进一步造成运维误判。
3. 测试报告和缓存文件会增加包体积，且对部署无用。

### 建议修复

在 `tar` 命令中补充排除规则：

```bash
--exclude='frontend/.env'
--exclude='frontend/test-results'
--exclude='frontend/playwright-report'
--exclude='frontend/tsconfig.tsbuildinfo'
--exclude='backend/.ruff_cache'
```

同时在 `MANIFEST.txt` 或作业指导书中明确：真实运行配置只允许放在 `runtime/` 下。

## 问题 6：离线启动缺少明确的预检和错误提示

严重级别：中

### 代码证据

`deploy-intranet.sh up` 的主流程为：

```bash
prepare_bundle
load_images
compose_cmd up -d --remove-orphans
```

`prepare_bundle` 只做：

```bash
extract_source
seed_runtime
```

缺少以下检查：

- `runtime/config.yaml` 是否能被应用配置模型加载。
- `runtime/.env` 是否存在。
- `runtime/frontend.env` 是否存在。
- `runtime/extensions_config.json` 是否存在。
- `env.intranet` 中关键路径是否指向真实文件。
- `$SOURCE_DIR/config.example.yaml`、`$SOURCE_DIR/.env.example`、`$SOURCE_DIR/frontend/.env.example` 这些种子源文件是否存在。

### 影响

部署失败时，用户只能从容器日志中看到后端异常，脚本层没有给出可操作的提示。离线场景通常排障成本更高，这会显著降低部署可维护性。

另外，`seed_file()` 当前只是直接 `cp "$source" "$target"`。如果源码包结构变化或缺少模板文件，脚本会因 `set -euo pipefail` 退出，但错误信息只是底层 `cp` 报错，无法告诉运维缺的是哪个部署合同文件。

### 建议修复

在 `prepare` 结束和 `up` 前增加 `validate_runtime()`：

```bash
validate_runtime() {
    require_file "$RUNTIME_DIR/config.yaml"
    require_file "$RUNTIME_DIR/.env"
    require_file "$RUNTIME_DIR/frontend.env"
    require_file "$RUNTIME_DIR/extensions_config.json"
    require_file "$ENV_FILE"
}
```

`seed_file()` 应在复制前检查源文件：

```bash
seed_file() {
    local target="$1"
    local source="$2"
    if [ ! -f "$target" ]; then
        [ -f "$source" ] || die "missing seed source: $source"
        cp "$source" "$target"
    fi
}
```

并增加配置内容校验。即使不能在宿主机加载 Python 应用，也应至少检查 YAML 语法和 `models` 字段类型：

```bash
python3 -c "import yaml; cfg=yaml.safe_load(open('$RUNTIME_DIR/config.yaml', encoding='utf-8')); assert isinstance(cfg.get('models'), list), 'models must be a list'"
```

如果目标离线服务器不保证有 Python，则可以把这一步做成可选，并在 Gateway 启动失败时输出固定排查命令。

## 问题 7：BETTER_AUTH_SECRET 只写入 env.intranet，持久化边界偏脆弱

严重级别：中

### 代码证据

`scripts/deploy-intranet.sh` 只在 `env.intranet` 不存在时生成：

```bash
BETTER_AUTH_SECRET=$(generate_secret)
```

该值直接写入 `env.intranet`。相比之下，正式 `scripts/deploy.sh` 会把 secret 单独持久化到：

```text
$DEER_FLOW_HOME/.better-auth-secret
```

### 影响

如果运维误删 `env.intranet`、更换部署目录、重新执行 `prepare`，脚本会生成新的 `BETTER_AUTH_SECRET`。这会导致依赖该 secret 的前端会话状态失效，表现为用户需要重新登录。

这不是容器启动失败的直接原因，但会降低离线部署的可恢复性和可预测性。

### 建议修复

把 secret 独立持久化到 runtime data 下：

```bash
_secret_file="$RUNTIME_DIR/data/.better-auth-secret"
if [ -f "$_secret_file" ]; then
    BETTER_AUTH_SECRET="$(cat "$_secret_file")"
else
    BETTER_AUTH_SECRET="$(generate_secret)"
    printf '%s\n' "$BETTER_AUTH_SECRET" > "$_secret_file"
    chmod 600 "$_secret_file"
fi
```

然后再把该值写入 `env.intranet`。

## 问题 8：输出目录根部的 compose 文件容易被误用

严重级别：低

### 代码证据

`scripts/package-intranet-offline.sh` 会把 compose 文件复制到输出目录根：

```bash
cp "$SOURCE_COMPOSE_FILE" "$COMPOSE_FILE"
```

但 `docker/docker-compose.intranet.yaml` 的 nginx 挂载路径是：

```yaml
- ./nginx/nginx.conf:/etc/nginx/nginx.conf.template:ro
```

`deploy-intranet.sh` 实际使用的是解压后的：

```text
$SOURCE_DIR/docker/docker-compose.intranet.yaml
```

此时 `./nginx/nginx.conf` 能正确解析到 `source/docker/nginx/nginx.conf`。但如果运维直接在离线包输出目录根部执行 `docker compose -f docker-compose.intranet.yaml up`，同级没有 `nginx/nginx.conf`，nginx 挂载会失败或创建错误路径。

### 影响

按脚本操作不会触发；绕过 `deploy-intranet.sh` 直接使用输出目录根部 compose 时容易失败。

### 建议修复

二选一：

1. 不在输出目录根部复制 compose 文件，只保留 `source/docker/docker-compose.intranet.yaml`，强制通过 `deploy-intranet.sh` 管理。
2. 如果保留根部 compose 文件，则同时复制 `docker/nginx/nginx.conf` 到根部可解析的位置，并在 `MANIFEST.txt` 中说明使用方式。

## 问题 9：.claude / .codex 挂载在离线环境下应改为可选

严重级别：低

### 代码证据

`docker/docker-compose.intranet.yaml` 仍保留：

```yaml
- type: bind
  source: ${HOME:?HOME must be set}/.claude
  target: /root/.claude
  read_only: true
  bind:
    create_host_path: true
- type: bind
  source: ${HOME:?HOME must be set}/.codex
  target: /root/.codex
  read_only: true
  bind:
    create_host_path: true
```

### 影响

这两个挂载对使用 Claude Code / Codex CLI 认证的模型路径有意义，但对典型禁公网内网部署并非必需。`create_host_path: true` 通常只会创建空目录，不一定阻断启动；但在 `$HOME` 未设置、权限受限或企业服务器 home 目录策略严格时，compose 可能在无关认证目录上失败。

### 建议修复

将这两个挂载改为可选配置，或在离线 compose 中默认移除，并在需要 CLI OAuth/Codex 认证的部署说明中单独开启。

## 已核实但不采纳的旧意见

### nginx 日志写文件而非 stdout/stderr

旧报告认为离线 compose 复用了 `docker/nginx/nginx.local.conf`，导致日志写入容器内文件。当前代码核实后该问题不成立：

- `docker/docker-compose.intranet.yaml` 挂载的是 `./nginx/nginx.conf`。
- `docker/nginx/nginx.conf` 中 `access_log /dev/stdout;`、`error_log /dev/stderr;` 已正确写入容器标准输出/错误。
- `docker/nginx/nginx.local.conf` 确实写本地 `logs/`，但它是本地非 Docker 场景配置，不在离线 compose 路径上。

## 建议修复优先级

### P0：必须先修

1. 不再直接把 `config.example.yaml` 作为可运行 `config.yaml`。
2. 统一离线前端 env 文件名，建议固定为 `runtime/frontend.env`。
3. `deploy-intranet.sh up` 前增加运行时配置文件存在性校验。
4. 为离线部署补齐稳定的 `DEER_FLOW_INTERNAL_AUTH_TOKEN`。

### P1：建议紧随其后

1. 增加 `config.yaml` YAML 和 `AppConfig` 校验。
2. 增加 Gateway/Frontend/Nginx healthcheck。
3. 作业指导书补充“登录后无法进入主页”的排障顺序。
4. 将 `BETTER_AUTH_SECRET` 独立持久化到 runtime data 目录。

### P2：清理和加固

1. 打包源码时排除 `frontend/.env`、测试报告和缓存。
2. 明确 `runtime/` 是唯一真实运行配置目录。
3. 在 `MANIFEST.txt` 中注明不要直接使用输出目录根部的 compose 文件绕过 `deploy-intranet.sh`。
4. 将 `.claude` / `.codex` 挂载改为可选。

## 建议验证清单

修复后至少验证以下命令：

```bash
bash -n scripts/package-intranet-offline.sh scripts/deploy-intranet.sh
```

```bash
scripts/package-intranet-offline.sh --version test-intranet --force
```

在离线包目录中：

```bash
./deploy-intranet.sh prepare
ls runtime/config.yaml
ls runtime/.env
ls runtime/frontend.env
ls runtime/extensions_config.json
```

校验配置：

```bash
python3 -c "import yaml; cfg=yaml.safe_load(open('runtime/config.yaml', encoding='utf-8')); assert isinstance(cfg.get('models'), list)"
```

启动后验证：

```bash
./deploy-intranet.sh up
./deploy-intranet.sh status
./deploy-intranet.sh logs gateway
curl -fsS http://127.0.0.1:2026/health
curl -fsS http://127.0.0.1:2026/api/v1/auth/setup-status
```

内部鉴权 token 验证：

```bash
grep '^DEER_FLOW_INTERNAL_AUTH_TOKEN=' env.intranet
./deploy-intranet.sh logs gateway
```

前端验证：

1. 首次访问应进入 `/setup`。
2. 创建管理员账号后应进入 `/workspace`。
3. 退出后重新登录，应能进入 `/workspace`。
4. 重启容器后登录态行为应符合预期。

## 结论

本次实操暴露的问题主要来自离线部署运行时配置合同没有闭环。修复重点应放在 `prepare` 阶段：生成明确、合法、可校验的 runtime 配置，并让脚本、compose、文档使用同一套文件名和路径。

在当前代码状态下，`config.example.yaml` 直接复制为 `runtime/config.yaml` 是最直接的启动失败原因；`frontend.env` 与 `frontend/.env` 的命名不一致是脚本失败和排障误导的主要来源；前端登录后无法进入主页则大概率是 Gateway 因配置错误不可用后，在 Next SSR 鉴权阶段表现出来的连锁问题。
