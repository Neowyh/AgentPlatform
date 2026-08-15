# Resource Governance V2 切换与回滚操作手册

> audience: operators, release engineers
> status: operations contract
> last-verified: 2026-08-15
> canonical-path: `docs/governance/resource-governance-v2-cutover.md`

本文档是 [Resource Governance V2 架构决策](../decisions/2026-08-14-resource-governance-v2.md) 退出条件的可执行化。切换 canonical 前必须逐项满足前置条件；回滚只退回运行模式，不删除任何 canonical 版本或历史审计。

## 1. 切换前置条件（全部必须满足）

1. 单 Alembic head 且数据库处于 head：

   ```bash
   cd backend
   uv run python -m alembic -c packages/harness/ideer/persistence/migrations/alembic.ini heads
   # 输出必须只有 20260814_resource_catalog_v2 (head)
   ```

2. `audit` 无未决冲突、`migrate` 幂等、`verify` exit 0：

   ```bash
   cd backend
   PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 audit \
     --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
   PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 migrate \
     --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
   PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 verify \
     --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
   ```

3. dual 对比门结构性全绿（`compare` 仅在 `IDEER_RESOURCE_CATALOG_MODE=dual` 下可运行）：

   ```bash
   IDEER_RESOURCE_CATALOG_MODE=dual PYTHONPATH=packages/harness uv run python \
     -m ideer.scripts.resource_catalog_v2 compare \
     --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
   # exit 0 且 errors 为空；diverged/extras 为预期信号，需记录说明
   ```

4. [验收矩阵](../testing/resource-governance-v2-acceptance-matrix.md) 全行真实 exit 0：backend unit/integration/contracts、blocking-I/O、frontend unit/check/E2E、Workflow Worker、Assistants compatibility、内网部署、私有 bundled 初始化、离线包 checksum/manifest、断网新装。

## 2. 切换步骤

1. 在部署环境设置 `IDEER_RESOURCE_CATALOG_MODE=canonical`（`.env`、docker-compose、systemd 或 Kubernetes env 均支持）。
2. 依次重启 Gateway 与 Worker。
3. 冒烟验证：
   - `GET /api/resources` 返回 canonical 资源列表；
   - 旧名称接口（`/api/agents/{name}`、`/api/skills/{name}`、`/api/workflows/{name}` 等 legacy facade）返回 `410`；
   - 新 Run 走 UUID 冻结快照路径，`run_resource_snapshots` 正常落库。
4. 进入观察期：canonical 模式下继续保留旧目录与 `resource_metadata` 兼容数据，运行 `verify` 与 reconcile 报告监控一致性。

## 3. 回滚

回滚只退回运行模式，不删除 canonical 版本、依赖、快照或历史审计：

```bash
cd backend
PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 rollback \
  --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills \
  --backup-dir /path/to/new-backup-directory
```

约束（与[迁移映射](resource-governance-v2-migration-map.md)一致）：

- 仅允许回退仍为迁移 v1、无草稿、无 Run 快照、无外部依赖的资源；
- `--backup-dir` 必须不存在、且位于 canonical `resources/` 之外；文件先移入备份目录，数据库提交失败时补偿移回；
- 回滚后把 `IDEER_RESOURCE_CATALOG_MODE` 退回 `dual` 或 `legacy` 并重启服务；
- 旧 Skill、Agent、Workflow 源不会被命令删除。

## 4. 物理清理（观察期结束后，另行授权）

`purge_eligible_versions`（`ideer.resources.retention`）只回收满足全部条件的归档版本：

- 资源已 `archived`、非 system-owned、超出保留期、未被 Run 快照引用；
- 磁盘内容 hash 与 catalog 一致；
- 显式授权（`authorized_by` 非空）与备份目录；
- 内容先移入备份目录，DB 失败补偿移回；资源无剩余版本且无入边依赖时连同 Resource 行移除。

物理清理必须满足：备份存在、hash 校验通过、保留期满足、历史与审计保留、超级管理员明确授权。任何一条不满足即 fail-closed，不删除任何内容。

## 5. 验收矩阵与文档同步

切换完成后更新：

- ADR 状态改为 `implemented` 并记录切换时间与模式；
- 验收矩阵逐行标注证据来源（fresh exit 0 的日志/CI 记录）；
- 本手册记录观察期起止与清理授权记录。