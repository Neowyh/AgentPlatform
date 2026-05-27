# Findings & Decisions

## Requirements

- 使用 `$planning-with-files` 工作流。
- 基于 `docs/deployment/离线Docker部署实操问题代码审查报告.md` 生成修改方案。
- 输出应是持久化文件，放在项目中，便于后续按方案实施。
- 用户后续要求按方案执行，并继续要求将镜像配置目录改为可配置、示例路径改到 `/home` 下。
- 用户最新要求重新更新离线部署方案和作业指导书，适应当前更改，并面向电脑小白细化步骤和原理说明。

## Research Findings

- 审查报告确认的 P0 类问题：
  - `config.example.yaml` 被直接复制为 `runtime/config.yaml`，其中 `models:` 解析为 `null`，会导致 `AppConfig` 校验失败。
  - 前端 env 文件存在 `runtime/frontend.env`、`frontend/.env`、compose fallback `../frontend/.env` 三套命名/路径，脚本、compose、文档合同不一致。
  - Gateway 启动失败会导致 Next SSR 在 `/workspace` 鉴权阶段访问 `/api/v1/auth/me` 失败，表现为登录后无法进入主页或页面无渲染。
  - 离线 compose 缺少稳定的 `DEER_FLOW_INTERNAL_AUTH_TOKEN`，多 worker 内部调用存在鉴权不一致风险。
- 审查报告确认的 P1/P2 类问题：
  - 打包源码未排除 `frontend/.env`、测试报告、缓存文件。
  - `deploy-intranet.sh` 缺少 runtime 文件和种子源文件预检。
  - `BETTER_AUTH_SECRET` 只写在 `env.intranet`，误删后会重新生成。
  - 输出目录根部 compose 文件可能被误用。
  - `.claude` / `.codex` 挂载在离线环境下应改为可选。
- 已核实不采纳的问题：
  - 离线 compose 当前使用 `docker/nginx/nginx.conf`，日志已写 stdout/stderr；不是 `nginx.local.conf` 路径问题。
- 复核完整报告后确认正式方案需覆盖 9 个问题：
  - P0：runtime env 命名合同、运行时 config 生成、前端登录后 SSR 依赖 Gateway 健康、内部鉴权 token。
  - P1：启动预检、配置校验、healthcheck、`BETTER_AUTH_SECRET` 独立持久化、作业指导书排障链路。
  - P2：源码打包排除、根部 compose 误用防护、`.claude` / `.codex` 可选化。
  - 不采纳：nginx stdout/stderr 问题。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| P0 优先修复 runtime config 合同和启动前校验 | 直接解决启动失败、登录后无法进入主页的问题 |
| P1 加固内部 token、secret 持久化和健康检查 | 解决多 worker、重启和排障稳定性问题 |
| P2 处理打包清理和可选挂载 | 降低泄漏和环境差异风险，不阻断首轮启动 |
| 修改方案包含文件级任务和验收标准 | 方便后续按任务直接实施和验证 |
| 示例部署目录统一为 `/home/deploy/deer-flow` | 规避 `/opt` 权限门槛，降低新手操作难度 |
| 宿主机部署目录保持可配置 | 不把离线部署绑定到单一目录，兼容不同服务器分区和权限策略 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| 当前任务从规划演进为执行和文档刷新 | 已同步更新脚本、compose、测试、方案和作业指导书 |

## Resources

- `docs/deployment/离线Docker部署实操问题代码审查报告.md`
- `scripts/deploy-intranet.sh`
- `scripts/package-intranet-offline.sh`
- `docker/docker-compose.intranet.yaml`
- `docs/deployment/禁公网内网离线部署作业指导书.md`
- `scripts/deploy.sh`
- `backend/packages/harness/deerflow/config/app_config.py`
- `backend/app/gateway/internal_auth.py`
- `frontend/src/core/auth/server.ts`
- `frontend/src/app/workspace/layout.tsx`

## Visual/Browser Findings

- 未使用浏览器或图像资料。
