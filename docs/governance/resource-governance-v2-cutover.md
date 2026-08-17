# Resource Governance V2 部署与回滚手册

> audience: operators, release engineers
> status: operations contract
> last-verified: 2026-08-17
> canonical-path: `docs/governance/resource-governance-v2-cutover.md`

本文档是 [Resource Governance V2 架构决策](../decisions/2026-08-14-resource-governance-v2.md) 的可执行化。本版本为 canonical-only 定案：无模式开关（`IDEER_RESOURCE_CATALOG_MODE` 已移除），旧名称路由已删除（404），迁移工具仅存在于旧版本。回滚只退回代码版本，不删除任何 canonical 版本或历史审计。

## 1. 升级前置条件（全部必须满足）

1. 单 Alembic head 且数据库处于 head：

   ```bash
   cd backend
   uv run python -m alembic -c packages/harness/ideer/persistence/migrations/alembic.ini heads
   # 输出必须只有 20260814_resource_catalog_v2 (head)
   ```

2. 有存量数据：先在旧版本执行 `audit → migrate → verify` 且三者 exit 0（命令见[迁移映射](resource-governance-v2-migration-map.md)）；无存量数据直接安装，跳过本步。

3. 升级前备份运行时数据（`runtime/` 或 `IDEER_HOME`）与数据库。

## 2. 升级步骤（canonical-only）

1. 在旧版本完成迁移验证后，用本版本替换镜像/源码并重启 Gateway 与 Worker（无需设置任何模式环境变量）。
2. 升级后旧名称接口（`/api/agents`、`/api/skills`、`/api/workflows` 等）不存在，返回 `404`；外部集成需切 `/api/resources`。
3. 冒烟验证：
   - `GET /api/resources` 返回 canonical 资源列表（bundled 资源含稳定 UUID）；
   - `GET /api/resources/aliases/{type}/{slug}` 与运行时 alias 解析可访问旧名称资源；
   - 新 Run 走 UUID 冻结快照路径，`run_resource_snapshots` 正常落库。
4. 进入观察期：保留旧目录与 `resource_metadata` 兼容数据，运行 reconcile 报告监控一致性。

## 3. 回滚

回滚只退回代码版本，不删除 canonical 版本、依赖、快照或历史审计：

```bash
git revert <本分支合并提交>
```

约束：

- legacy 源未删时，可在旧版本重跑 `audit → migrate → verify` 完成新一次迁移；
- 已产生的 canonical 版本、Run 快照与审计保留在数据库中；
- 旧 Skill、Agent、Workflow 源不会被任何命令删除。

## 4. 物理清理（观察期结束后，另行授权）

`purge_eligible_versions`（`ideer.resources.retention`）只回收满足全部条件的归档版本：

- 资源已 `archived`、非预装（`storage_kind != "bundled"`）、非 system-owned、超出保留期、未被 Run 快照引用；
- 磁盘内容 hash 与 catalog 一致；
- 显式授权（`authorized_by` 非空）与备份目录；
- 内容先移入备份目录，DB 失败补偿移回；资源无剩余版本且无入边依赖时连同 Resource 行移除。

物理清理必须满足：备份存在、hash 校验通过、保留期满足、历史与审计保留、超级管理员明确授权。任何一条不满足即 fail-closed，不删除任何内容。

## 5. 验收矩阵与文档同步

升级完成后更新：

- ADR 状态保持 `implemented`（canonical-only 定案已记录）；
- 验收矩阵逐行标注证据来源（fresh exit 0 的日志/CI 记录）；
- 本手册记录观察期起止与清理授权记录。

## 6. 执行记录（2026-08-15 ~ 2026-08-17，本地 worktree `resource-governance-v2`）

- canonical 冒烟（canonical-only，Gateway 8001）：`/api/resources` 返回 34 项 canonical；`/api/agents|skills|workflows/{name}` 全部 404（路由已删除）；老名字 `fault-zeroing` run 经 alias 解析为 UUID 56e2423d… 成功创建；`run_resource_snapshots` 落库 agent+skill 各 1 行（version/hash 正确）；前端 admin 资源页经同源代理渲染 canonical 数据。
- Workflow Worker canonical 冒烟（2026-08-16）：worker 消费 workflow run，状态 queued→running→failed（冒烟占位 `upload_dir` 不存在导致业务失败），`run_resource_snapshots` 完整闭包 3 行落库；runtime 修复后全量 `make test` 通过。
- 冒烟发现并修复：bundled Agent 的 `config.skills` 为稳定 UUID 引用，`runtime.load_agent_skill_definitions` 原先仅按 slug 匹配导致 run 409；修复为 UUID 优先、slug 次之，缺失 fail-closed。
- 离线部署项（2026-08-16，本 worktree）：断网新装隔离模拟完成（详见[验收矩阵"部署/离线"行执行记录](../testing/resource-governance-v2-acceptance-matrix.md)）——离线包 checksum/manifest 6/6 OK；无沙箱包部署 exit 0；bundled 27 资源全量 created、fault-zeroing workflow seeded；`/api/resources` 27 项全 bundled；fail-fast 语义实测（缺源时整体失败 exit 1）。
- 离线部署项中发现并修复打包链缺陷：compose intranet 未挂载 `docs/` 与 `workflows/`，bundled agent/workflow 源在容器内缺失导致 seed 失败；`docker/docker-compose.intranet.yaml` 为 gateway 与 workflow-worker 增加挂载后隔离模拟部署 exit 0、27 created。
- 硬切换（2026-08-16，阶段 4）：删除 `routers/agents.py`、`routers/skills.py`、`routers/workflows.py`、`mode.py`、`compare.py`、`resource_catalog_mode.py`、`migration.py` 与 `scripts/resource_catalog_v2.py`；部署资产移除 `IDEER_RESOURCE_CATALOG_MODE` env。
- 全量验收（2026-08-17，阶段 5）：backend 11933 passed / 48 skipped、ruff 干净；frontend 7879 passed + `pnpm check` 0 errors；E2E 149 passed（18 spec）；GitNexus detect_changes 0 执行流受影响。
- 待办：观察期结束评估；重新打包离线包携带 compose 修复；物理清理按授权另行执行。