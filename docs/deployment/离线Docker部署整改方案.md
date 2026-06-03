# 离线 Docker 部署整改方案

日期：2026-05-27

## 目标

基于 `docs/deployment/离线Docker部署实操问题代码审查报告.md`，对当前离线 Docker 部署链路制定可执行整改方案。整改目标是：

1. 首次离线部署后，`prepare -> up` 不再因为配置文件命名或格式问题失败。
2. Gateway、Frontend、Nginx 的启动状态可被脚本清晰检查。
3. 登录、首次初始化、进入 `/workspace` 的链路可验证。
4. 离线包只携带必要源码和模板，不泄漏本机 `.env`、测试产物和缓存。
5. 作业指导书与脚本、compose 使用同一套 runtime 文件合同。

## 整改原则

- 保持离线部署 runtime 配置集中在 `runtime/` 目录，不依赖源码目录中的真实 `.env`。
- `deploy-intranet.sh` 是离线部署唯一入口；不要鼓励运维直接操作输出目录根部 compose 文件。
- 先解决阻断启动的问题，再处理稳定性和清理项。
- 对脚本改动优先采用最小闭环：生成、校验、启动、健康检查、日志提示。
- 不把本地开发专用配置混入禁公网内网部署默认路径。

## 分阶段实施计划

### P0：打通离线部署主链路

#### 任务 1：统一离线 runtime env 文件命名

涉及文件：

- `scripts/deploy-intranet.sh`
- `docker/docker-compose.intranet.yaml`
- `scripts/package-intranet-offline.sh`
- `docs/deployment/禁公网内网离线部署作业指导书.md`

修改内容：

1. 固定离线前端环境文件为：

```text
runtime/frontend.env
```

2. `deploy-intranet.sh` 中继续生成：

```bash
seed_file "$RUNTIME_DIR/frontend.env" "$SOURCE_DIR/frontend/.env.example"
```

3. `env.intranet` 和 `env.intranet.example` 保持：

```bash
IDEER_FRONTEND_ENV_FILE=<bundle-root>/runtime/frontend.env
```

4. `docker-compose.intranet.yaml` 中建议去掉误导性 fallback，改成强依赖变量：

```yaml
env_file:
  - ${IDEER_FRONTEND_ENV_FILE:?IDEER_FRONTEND_ENV_FILE must be set}
```

5. 作业指导书中所有 `frontend/.env` 运行时提示改为 `runtime/frontend.env`。

验收标准：

- `./deploy-intranet.sh prepare` 后存在 `runtime/frontend.env`。
- `env.intranet` 中 `IDEER_FRONTEND_ENV_FILE` 指向 `runtime/frontend.env`。
- 文档不再把离线运行时前端 env 指向 `frontend/.env`。

#### 任务 2：避免直接把 config.example.yaml 当可运行配置

涉及文件：

- `scripts/deploy-intranet.sh`
- `config.example.yaml`（可选）
- `docs/deployment/禁公网内网离线部署作业指导书.md`

推荐修改路径：

1. 在 `deploy-intranet.sh` 中新增 `seed_config()`，不要简单复制完整 `config.example.yaml` 后直接启动。
2. 首次 `prepare` 时生成一份最小合法 `runtime/config.yaml`，至少满足：

```yaml
config_version: 10
log_level: info
token_usage:
  enabled: true
models: []
```

并保留原有 sandbox、tools、skills、database 等必需默认段。更稳妥的实现方式是：

- 先复制 `config.example.yaml`。
- 复制后用 YAML 处理或受控文本处理将裸 `models:` 修正为 `models: []`。
- 在文件顶部或旁路提示运维必须补充至少一个真实模型。

3. 如果选择改 `config.example.yaml`，应把裸 `models:` 改成合法空列表，但要评估这是否影响现有示例阅读体验。

验收标准：

- 新生成的 `runtime/config.yaml` 能通过 YAML 解析。
- `models` 字段至少是 list，不再是 `null`。
- Gateway 不再因 `models Input should be a valid list` 在启动阶段失败。

#### 任务 3：补齐 IDEER_INTERNAL_AUTH_TOKEN

涉及文件：

- `scripts/deploy-intranet.sh`
- `scripts/package-intranet-offline.sh`
- `docker/docker-compose.intranet.yaml`

修改内容：

1. `docker-compose.intranet.yaml` 的 Gateway `environment` 中增加：

```yaml
- IDEER_INTERNAL_AUTH_TOKEN=${IDEER_INTERNAL_AUTH_TOKEN}
```

2. `deploy-intranet.sh` 在 `seed_runtime()` 中生成并持久化：

```bash
_internal_auth_token_file="$RUNTIME_DIR/data/.internal-auth-token"
```

3. `env.intranet` 生成时写入：

```bash
IDEER_INTERNAL_AUTH_TOKEN=<stable-token>
```

4. `package-intranet-offline.sh` 的 `env.intranet.example` 增加：

```bash
IDEER_INTERNAL_AUTH_TOKEN=replace-with-a-fixed-internal-token
```

验收标准：

- `env.intranet` 中存在 `IDEER_INTERNAL_AUTH_TOKEN=`。
- `docker compose config` 能看到 Gateway 注入该变量。
- 多 worker 下内部 channel 调用不再依赖各 worker 自行生成随机 token。

#### 任务 4：启动前增加 runtime 文件预检

涉及文件：

- `scripts/deploy-intranet.sh`

修改内容：

1. 增加 `validate_runtime_files()`：

```bash
validate_runtime_files() {
    require_file "$RUNTIME_DIR/config.yaml"
    require_file "$RUNTIME_DIR/.env"
    require_file "$RUNTIME_DIR/frontend.env"
    require_file "$RUNTIME_DIR/extensions_config.json"
    require_file "$ENV_FILE"
}
```

2. `prepare`、`up`、`restart`、`status`、`logs` 在调用 compose 前执行该校验。
3. `seed_file()` 在复制前校验源文件存在：

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

验收标准：

- 缺少 runtime 文件时，脚本在 compose 之前失败，并输出明确文件路径。
- 缺少源模板时，脚本提示 `missing seed source: ...`。

### P1：提升启动可诊断性和会话稳定性

#### 任务 5：增加配置内容校验

涉及文件：

- `scripts/deploy-intranet.sh`
- `docs/deployment/禁公网内网离线部署作业指导书.md`

修改内容：

1. 增加轻量 YAML 校验。宿主机有 Python 时执行：

```bash
python3 -c "import yaml; cfg=yaml.safe_load(open('$RUNTIME_DIR/config.yaml', encoding='utf-8')); assert isinstance(cfg.get('models'), list), 'models must be a list'"
```

2. 如果宿主机无 Python，则跳过该检查，但输出可复制的容器内排查命令。
3. 作业指导书补充 `models must be a list` 的定位和修复方法。

验收标准：

- `models: null` 能在脚本层被提前拦截。
- 错误信息明确指向 `runtime/config.yaml` 和 `models` 字段。

#### 任务 6：增加服务健康检查和启动后验证

涉及文件：

- `docker/docker-compose.intranet.yaml`
- `scripts/deploy-intranet.sh`
- `docs/deployment/禁公网内网离线部署作业指导书.md`

修改内容：

1. compose 为 `gateway` 增加 healthcheck：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 10s
  timeout: 5s
  retries: 6
```

2. 如前端镜像包含可用检查工具，则为 `frontend` 增加 `http://localhost:3000` 检查；否则在脚本层通过 nginx 对外访问检查。
3. `deploy-intranet.sh up` 后执行：

```bash
curl -fsS "http://127.0.0.1:${PORT:-2026}/health"
curl -fsS "http://127.0.0.1:${PORT:-2026}/api/v1/auth/setup-status"
```

4. 检查失败时输出下一步：

```bash
./deploy-intranet.sh logs gateway
./deploy-intranet.sh logs frontend
./deploy-intranet.sh logs nginx
```

验收标准：

- `up` 成功后脚本能给出服务可访问提示。
- Gateway 未启动时，脚本不会只显示 compose 已启动，而是提示查看 Gateway 日志。

#### 任务 7：持久化 BETTER_AUTH_SECRET

涉及文件：

- `scripts/deploy-intranet.sh`
- `scripts/package-intranet-offline.sh`

修改内容：

1. 在 `runtime/data/.better-auth-secret` 中独立持久化 secret。
2. `env.intranet` 缺失时，优先从 `.better-auth-secret` 读取。
3. `env.intranet.example` 保留占位值，但文档说明实际部署由 `prepare` 生成稳定值。

验收标准：

- 删除 `env.intranet` 后重新 `prepare`，只要 `runtime/data/.better-auth-secret` 存在，生成的 secret 不变。
- 重启容器后会话行为稳定。

#### 任务 8：更新作业指导书排障路径

涉及文件：

- `docs/deployment/禁公网内网离线部署作业指导书.md`

修改内容：

1. 增加“登录后无法进入主页”的排查顺序：

```text
1. ./deploy-intranet.sh logs gateway
2. 检查 runtime/config.yaml 是否能解析，models 是否为 list
3. curl /health
4. curl /api/v1/auth/setup-status
5. ./deploy-intranet.sh logs frontend
6. ./deploy-intranet.sh logs nginx
```

2. 增加 runtime 文件说明：

```text
runtime/config.yaml
runtime/.env
runtime/frontend.env
runtime/extensions_config.json
env.intranet
```

3. 明确不要直接编辑源码目录中的 `frontend/.env` 来修复离线运行时配置。

验收标准：

- 文档与脚本实际文件名一致。
- 排障步骤可以直接复制执行。

### P2：打包清理和离线环境收敛

#### 任务 9：完善源码包排除规则

涉及文件：

- `scripts/package-intranet-offline.sh`

修改内容：

在源码 tar 排除规则中增加：

```bash
--exclude='frontend/.env'
--exclude='frontend/test-results'
--exclude='frontend/playwright-report'
--exclude='frontend/tsconfig.tsbuildinfo'
--exclude='backend/.ruff_cache'
```

可同时考虑排除：

```bash
--exclude='**/__pycache__'
--exclude='*.pyc'
```

验收标准：

- 新生成的 `ideer-source-<version>.tar.gz` 中不包含 `frontend/.env`。
- 不包含 Playwright 报告、测试结果和 TypeScript 增量缓存。

#### 任务 10：处理输出目录根部 compose 文件误用

涉及文件：

- `scripts/package-intranet-offline.sh`
- `docs/deployment/禁公网内网离线部署作业指导书.md`

推荐方案：

1. 保留根部 compose 文件只作为参考，并在 `MANIFEST.txt` 明确：

```text
Do not run docker compose directly from the bundle root. Use ./deploy-intranet.sh.
```

2. 或者不再复制根部 compose 文件，只通过 `source/docker/docker-compose.intranet.yaml` 使用。

建议采用方案 1，兼容现有离线包内容结构，风险更低。

验收标准：

- `MANIFEST.txt` 和作业指导书明确要求通过 `deploy-intranet.sh` 操作。
- 直接运行根部 compose 的风险被文档化；如仍保留根部 compose，应复制 `nginx/nginx.conf` 到可解析路径。

#### 任务 11：将 .claude / .codex 挂载改为可选

涉及文件：

- `docker/docker-compose.intranet.yaml`
- `docs/deployment/禁公网内网离线部署作业指导书.md`

推荐方案：

1. 默认离线 compose 移除 `.claude` / `.codex` bind mount。
2. 如果必须支持 CLI OAuth/Codex 认证，新增单独 override 文件，例如：

```text
docker/docker-compose.intranet.cli-auth.yaml
```

3. 作业指导书说明只有选择 Claude Code / Codex CLI provider 时才启用该 override。

验收标准：

- 默认离线部署不依赖 `$HOME/.claude` 或 `$HOME/.codex`。
- 需要 CLI 认证时有明确启用路径。

## 建议提交拆分

### Commit 1：修复离线 runtime 配置合同

包含：

- 统一 `runtime/frontend.env`。
- 修复 `runtime/config.yaml` 生成。
- 增加 runtime 文件预检。
- 补齐 `IDEER_INTERNAL_AUTH_TOKEN`。

验证：

```bash
bash -n scripts/deploy-intranet.sh
./deploy-intranet.sh prepare
```

### Commit 2：补齐启动健康检查和排障文档

包含：

- Gateway/frontend/nginx 健康检查或脚本级健康验证。
- 作业指导书更新。
- `BETTER_AUTH_SECRET` 独立持久化。

验证：

```bash
./deploy-intranet.sh up
curl -fsS http://127.0.0.1:2026/health
curl -fsS http://127.0.0.1:2026/api/v1/auth/setup-status
```

### Commit 3：清理离线打包内容和可选挂载

包含：

- 完善 tar exclude。
- 处理根部 compose 误用。
- `.claude` / `.codex` 可选化。

验证：

```bash
scripts/package-intranet-offline.sh --version test-intranet --force
tar -tzf dist/intranet/ideer-test-intranet/ideer-source-test-intranet.tar.gz | grep -E 'frontend/\\.env|frontend/test-results|frontend/playwright-report|frontend/tsconfig.tsbuildinfo' && echo FAIL || echo OK
```

## 回归验证清单

### 静态检查

```bash
bash -n scripts/package-intranet-offline.sh scripts/deploy-intranet.sh
docker compose -f docker/docker-compose.intranet.yaml config
```

### 打包验证

```bash
scripts/package-intranet-offline.sh --version test-intranet --force
ls dist/intranet/ideer-test-intranet
```

### 离线包准备验证

在离线包目录执行：

```bash
./deploy-intranet.sh prepare
ls runtime/config.yaml
ls runtime/.env
ls runtime/frontend.env
ls runtime/extensions_config.json
grep '^IDEER_INTERNAL_AUTH_TOKEN=' env.intranet
```

### 配置验证

```bash
python3 -c "import yaml; cfg=yaml.safe_load(open('runtime/config.yaml', encoding='utf-8')); assert isinstance(cfg.get('models'), list)"
```

如果宿主机没有 Python，则用 Gateway 容器做等价检查。

### 启动验证

```bash
./deploy-intranet.sh up
./deploy-intranet.sh status
curl -fsS http://127.0.0.1:2026/health
curl -fsS http://127.0.0.1:2026/api/v1/auth/setup-status
```

### 前端登录验证

1. 首次访问 `http://127.0.0.1:2026` 应跳转或引导到 `/setup`。
2. 创建管理员账号后进入 `/workspace`。
3. 退出登录后使用账号密码重新登录。
4. 重启容器后再次访问，确认页面可渲染，登录链路可用。

## 风险与注意事项

- 如果改 `config.example.yaml`，要确认不会破坏现有配置说明和 setup wizard 测试预期。
- 如果为 frontend 增加 healthcheck，要确认生产镜像中有 `curl` 或使用 Node 原生命令替代。
- 如果移除 `.claude` / `.codex` 默认挂载，要为依赖 CLI 认证的模型路径提供 override 方案，避免误伤这类部署。
- 如果脚本新增 Python YAML 校验，要考虑目标离线服务器可能没有 Python 依赖；应允许降级为容器内校验或只做基础文件校验。

## 完成定义

满足以下条件后，本轮整改可认为完成：

1. `./deploy-intranet.sh prepare` 生成的 runtime 文件名与文档完全一致。
2. `runtime/config.yaml` 不再因 `models: null` 导致 Gateway 启动失败。
3. `env.intranet` 包含稳定的 `BETTER_AUTH_SECRET` 和 `IDEER_INTERNAL_AUTH_TOKEN`。
4. `./deploy-intranet.sh up` 后脚本能验证 Gateway 基础健康。
5. 登录后 `/workspace` 可服务端渲染并进入主页。
6. 新离线源码包不包含本机 `frontend/.env` 和测试/缓存产物。
