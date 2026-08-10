# iDeer 离线产品线 v2.0.0 冲突决策登记

状态：冲突处理及发布前验收已完成；待最终合并提交。本文记录的是已完成的验收证据，不替代 Git 的当前状态。

## 基线与合并证据

| 项目 | 值 |
|---|---|
| 离线冻结基线 | `refactor/workflow-module` `50301516de7519e9e633e6431c3f660f5cf49dc8`（`product/offline-1.x` 快进后的等价提交） |
| 1.x 保护引用 | `archive/product-offline-1.x-pre-v2` → `4868cb8e412f93a326d4949a8c89f37d75886cec` |
| 上游稳定标签 | `v2.0.0` → `7e7f0410797693cf882594555ba414e0361d4c6f` |
| 整合分支 | `integration/upstream-v2.0.0` |
| 合并方式 | `git merge --no-commit --no-ff v2.0.0` |
| 当前冲突规模 | 0 个未合并路径（`git diff --name-only --diff-filter=U` 无输出）；456 是初始盘点快照，不再表示当前状态 |

## 决策状态

| 边界 | 当前冲突面 | 决策 | 理由/必须验证 |
|---|---:|---|---|
| 离线部署 | compose、镜像、脚本 | 保留本地并重新实现隔离验收支持 | 保留 workflow-worker、IDEER_HOME、bundled/offline 契约；默认 `LocalSandboxProvider` 且 `allow_host_bash: false`，可用 `IDEER_COMPOSE_PROJECT` 与 `IDEER_CONTAINER_PREFIX` 启动不碰现有服务的验收栈 | `SHA256SUMS`、fresh `prepare/up`、21026 健康检查、运行时配置审计 |
| 认证与 RBAC | 10 个直接冲突，gateway/auth 和 workflow/artifact 消费者广泛受影响 | 部分保留本地 | 已暂时保留本地 auth/authz、认证中间件、auth/run/artifact 路由；本地保留 `users_ext` 多角色、禁用用户和 run/artifact 隔离，上游简化为 admin/user 的变化不能直接覆盖；仍需逐项吸收安全修复并 fresh 负向合约 |
| 存储与数据迁移 | workflow/migration 路径 | 保留本地 | 保留用户/资源元数据/Workflow V2 数据模型，避免上游简化模型覆盖资源归属 | 旧库升级与新库初始化 34 passed；`alembic heads` 唯一 `20260718_workflow_v2_lease_audit` |
| 工具与技能网络隔离 | harness、sandbox、MCP、skills 及 `.agent` | 保留本地并适配质量门禁 | 不放宽权限；默认包不含远程 sandbox 镜像，保留私有 bundled-agent/skill 安装 | fresh 包部署后 2 Agent、13 Skill、1 Workflow 均为 `private`，且 owner 为 super-admin |
| 前端契约 | 185 个 frontend 冲突 | 保留本地并选择性采用 | 保持本地 API、RBAC 和工作台；采用独立 Mermaid 预处理、录制回放与工作台 E2E | 前端单测 7,879 passed；`pnpm check` 0 errors；Chromium E2E 144 passed |
| 其他上游内容 | 外部 IM、联网搜索/网页服务、远程 sandbox、博客/演示/运营资源 | 暂不纳入 | 不属于默认离线产品；没有以批量 ours/theirs 作为决策 | 无 `deerflow`/`DEER_FLOW_*` 运行时导入审计命中；fresh 包无需 API key 即健康 |

## 高风险待决点

- `backend/app/gateway/authz.py`：两侧分别约 612/319 行，影响 43 个索引引用，GitNexus 风险为 `CRITICAL`；已保留本地实现，因为上游侧移除了 `get_current_rbac_user` 和多角色隔离；仍需逐项比较上游认证安全修复。
- `backend/app/gateway/routers/runs.py` 与 `artifacts.py`：同时承载 Workflow V2 run/artifact 所有权边界，不能只按文本冲突标记处理。
- `backend/packages/harness/*` 与 `backend/src/*`：存在重命名/重命名、重命名/删除及两侧新增，需先确定 harness/deerflow 与 harness/ideer 的产品归属和导入边界。
- `vendor/officecli/officecli`、`workflows/fault-zeroing.yaml` 等本地离线资产出现在上游删除差异中，默认不能接受上游删除，必须单独证明替代物和离线回归后才可决策。

## 决策枚举

- `采用上游`：上游行为满足离线产品契约，并保留必要本地测试。
- `保留本地`：上游版本会破坏已验证离线能力或 Workflow V2 约束。
- `重新实现`：两侧模型不兼容，按产品契约重建并补测试。
- `暂不纳入`：明确记录理由、影响和后续入口；不能静默丢弃。

## 当前 stop gate

上述 stop gate 已于 2026-08-11 逐项验证；在本次 merge commit 前仍不得推送或创建发布标签。

- 不创建或更新 `product/offline-2.x`；
- 不创建候选发布标签；
- 不推送任何正式分支或标签；
- 不删除整合分支。

完整逐路径状态以 Git 的未合并索引为准；后续同步仍须为每个边界回填决策、理由、文件范围和验证命令。

## 架构级决策（已锁定）

上游 `v2.0.0` 的 harness 包名是 `deerflow-harness`，源码命名空间是 `deerflow.*`；冻结基线使用 `ideer-harness` 与 `ideer.*`。这不是品牌字符串替换：它影响 backend `pyproject`、所有导入、运行时路径、配置环境变量、容器和测试收集。当前保守策略是保留本地命名空间和本地 RBAC/Workflow V2，不能把上游 `deerflow` 目录作为“已整合”依据；后续必须二选一并补齐完整迁移矩阵：

1. 保持 `ideer.*` 作为产品命名空间，逐项移植上游 v2 行为；或
2. 执行受控的全局命名空间迁移，同时重建离线、RBAC、Workflow V2 和前端契约。

本轮整合明确选择第 1 项：保持 `ideer.*` 作为产品命名空间，逐项移植上游 v2 行为。以下是此决策的执行约束：

| 范围 | 决策 | 理由 | 验证 |
|---|---|---|---|
| `backend/packages/harness/deerflow/**` 与其产品导入 | 暂不纳入 | 上游整套 harness 命名空间会取代本地 `ideer.*`、运行时路径和私有 Agent 产品契约 | `rg -n '(^|[[:space:]])(from|import) deerflow' backend`；后端分层测试 |
| 外部 IM、搜索/网页服务、远程 sandbox | 暂不纳入 | 默认离线部署不得引入联网入口、外部密钥或远程服务依赖 | fresh 断网部署；配置与依赖审计 |
| E2E 录制回放、阻塞 I/O 检查 | 采用上游并适配 | 这些是发布可靠性门禁，不改变公开产品 API | 录制+回放；`make test-blocking-io` |
| Mermaid 渲染与可独立工作台改进 | 重新实现/选择性采用 | 仅接受不改变本地 Agent API、RBAC 或 Workflow V2 行为的改动 | 前端单测、类型检查、工作台 E2E |

因此，本阶段可以按以上文件范围完成冲突决策，但在导入、依赖、运行时和验收门禁未通过前，仍不得提交 merge commit。

## 已执行的分组决策

| 文件范围 | 决策 | 理由 | 验证 |
|---|---|---|---|
| `frontend/src/components/workspace/messages/markdown-content.tsx`、`frontend/src/core/streamdown/{index,mermaid,preprocess}.ts`、对应单测 | 重新实现/采用上游 | 保持本地组件、Vitest 与路径别名，仅接入 Mermaid 预处理；不引入 Rstest 或上游环境变量 | `pnpm exec vitest run tests/unit/components/workspace/messages/markdown-content.test.tsx`（15 passed）；`pnpm exec vitest run tests/unit/core/streamdown/mermaid.test.ts`（10 passed） |
| `frontend/package.json`、`frontend/pnpm-lock.yaml` | 保留本地 | 本地 Vitest、E2E 端口和 `IDEER_*` 运行契约与上游 Rstest / `DEER_FLOW_*` 不兼容 | 上述 Vitest 命令可启动并通过 |

## 用户确认的剩余分组决策（2026-08-10）

用户确认执行 `A1 B1 C1 D1 E1 F1 G1 H1 I3 J3 K1 L1`。以下记录是冲突处理授权，验收仍须以本表的 fresh gates 为准。

| 编号 | 文件范围 | 决策 | 原因 | 验证 |
|---|---|---|---|---|
| A1 | 根配置、`backend/{Dockerfile,Makefile,pyproject.toml,uv.lock}`、部署配置 | 保留本地 | 保持 `IDEER_*`、离线启动和 workflow-worker 契约 | 离线包构建与 fresh 断网部署 |
| B1/E1 | `backend/packages/harness/ideer/**`、`backend/src/**` | 保留本地 | 维持现有命名空间与兼容导入；不作全局迁移 | 后端分层测试；无 `deerflow` 运行时导入 |
| C1 | `backend/app/channels/**`、上游联网工具/远程 sandbox | 暂不纳入 | 默认离线部署不暴露外部渠道或联网入口 | 配置/依赖审计与断网验收 |
| D1/H1 | Gateway 路由、Agent API、认证与前端 Agent/认证/设置契约 | 保留本地，逐项摘取安全修复 | 保护多角色、私有 Agent、资源元数据及 run/artifact 隔离 | RBAC 正反向合约；Agent API/前端单测 |
| F1 | 阻塞 I/O 检测脚本与锚点测试 | 采用并适配 | 质量门禁不改变公开 API | `cd backend && make test-blocking-io` |
| G1 | replay gateway、record/replay 测试与 Playwright 配置 | 采用并适配 | 使用本地回放夹具，无凭据、无公网依赖 | backend golden + replay Playwright |
| I3/J3 | 工作台页面/组件、通用前端逻辑与单测 | 保留本地，逐项摘取已验证稳定性改进 | 页面/API 契约紧密；仅接入独立、可测试的增强 | 前端单测、类型检查、工作台 E2E |
| K1/L1 | 前端内容、博客/演示、文档、公共技能 | 保留本地/暂不纳入上游运营内容 | 不引入品牌、联网或演示资产 | 文档与默认部署审计 |

### I3/J3 首轮逐项筛选

- 已采用：Mermaid fenced-code 预处理；它只改变 Markdown 呈现，已有 25 个聚焦 Vitest 断言。
- 已排除：上游 gateway 离线横幅/降级组件；它既未接入本地布局，又调用本地 `AuthContext` 不提供的 `applyUser`，前端生产构建已据此失败。此类 Auth 契约改造不在本次 I3/J3 的独立增强范围内。
- 未采用 `frontend/src/core/tasks/subtask-result.ts` 上游版本：它依赖上游 `deerflow` task-tool 的结构化状态契约，当前本地 Workflow/Agent 工具未提供该字段。
- 未采用 `frontend/src/components/workspace/chats/use-thread-chat.ts` 上游版本：它引入 `deer-flow:*` 事件与上游线程删除流程，和本地路由/状态生命周期不兼容。
- 未直接采用 `frontend/src/core/threads/hooks.ts` 上游版本：它增加的 run-message 分页、搜索缓存和 403 隐藏语义必须与本地 `/api/threads`、RBAC 和 Workflow V2 run 历史一起重建，不能作为孤立修复。
- 未直接采用 `frontend/src/core/clipboard.ts` 上游版本：它是独立候选，但会替换当前的 Streamdown fallback；需在完成冲突后以独立 TDD 变更评估，避免把未验证浏览器 polyfill 混入本次合并。
- 结论：其余 I3/J3 冲突保留本地；这不是批量忽略，而是因上游差异均与上游 API、状态协议或测试框架绑定。后续可作为独立小变更逐项摘取。

## 2026-08-11 发布前验收记录

| 门禁 | 真实结果 |
|---|---|
| 后端完整套件 | `12517 passed, 46 skipped`，退出码 0 |
| 迁移与 Workflow V2 | 旧库升级/新库初始化 34 passed；唯一 migration head 为 `20260718_workflow_v2_lease_audit` |
| RBAC 与私有资源 | 聚焦 RBAC/Agent/Workflow 342 passed；fresh 部署数据库确认 2 Agent、13 Skill、1 Workflow 都是 super-admin 的 `private` 资源 |
| 前端 | 单测 7,879 passed；`pnpm check` 退出码 0（0 errors）；Chromium E2E 144 passed |
| replay 与阻塞 I/O | golden 1 passed、provider 4 passed、真实 replay Playwright 1 passed；`make test-blocking-io` 5 passed |
| 离线包 | `scripts/package-intranet-offline.sh --no-sandbox --force` 退出码 0；`sha256sum -c SHA256SUMS` 全部 OK |
| fresh 离线验收 | 在 `IDEER_COMPOSE_PROJECT=accept-v2`、`IDEER_CONTAINER_PREFIX=accept-v2`、`PORT=21026` 下，`prepare`、`check-intranet`、`up` 均退出码 0；四个容器健康，`/health` 正常；运行时配置为 `ideer.sandbox.local:LocalSandboxProvider` 与 `allow_host_bash: false` |

该验收不启用外部渠道、联网搜索、网页服务或远程 sandbox；离线包默认不含 sandbox 镜像，也不需要外部 API key 才能完成健康、资源初始化和 Workflow V2 种子。
