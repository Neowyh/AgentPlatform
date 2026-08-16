# Resource Governance V2 迁移映射

> audience: developers, database maintainers, operators
> status: implementation contract
> last-verified: 2026-08-17
> canonical-path: `docs/governance/resource-governance-v2-migration-map.md`

## 映射原则

迁移以“零覆盖、可审计”为硬约束。旧名称不是新主键；每条 Skill、Agent、Workflow 记录分配或复用稳定 UUID。迁移不合并同名多 owner 资源，不自动改名，不把个人运行状态搬进资源定义目录。本版本为 canonical-only，迁移工具（`audit`/`migrate`/`verify`）仅存在于旧版本，由部署侧在升级前执行。

## 数据映射

| 旧事实源 | V2 目标 | 迁移规则 | 冲突/异常处理 |
|---|---|---|---|
| `resource_metadata` 的 skill/agent/workflow 行 | `resources` | type、owner、slug、visibility、department 映射；生成稳定 UUID；旧行保留为兼容投影 | 同 owner/type/slug 重复时报审计冲突并停止正式迁移 |
| `resource_metadata` 的 tool 行 | 原表 | 不迁移 | canonical 后仍由系统能力策略治理 |
| `is_favorited` | `resource_favorites` | 只能在能确定具体用户时转换 | 旧全局布尔值无法证明用户时仅审计，不伪造收藏人 |
| visibility application type/name/applicant | application 的 `resource_id`、version、hash | 通过 owner+type+slug 唯一映射 | 多匹配/缺失映射停止该记录迁移并报告 |
| custom Skill 目录 | `resources/skills/<uuid>/versions/1` | 逐文件安全检查和 hash；内容成为不可变 v1 | symlink、穿越、超限、hash 漂移均 fail-closed |
| per-user Agent 目录 | `resources/agents/<uuid>/versions/1` | `config.yaml`、`SOUL.md` 及定义支持文件迁移 | 同名不同 owner 分配不同 UUID；不覆盖 |
| legacy shared Agent 目录 | bundled/system 或明确 owner 的 Agent | 由清单决定稳定 UUID 和 owner | 无清单时只审计，不猜 owner |
| Workflow name/version DB 行 | `resource_versions` 或 UUID 化 definition version | 保留 JSON/YAML、版本、hash、创建者；补 `resource_id` | 同名多 owner 需由 metadata 唯一绑定，否则停止 |
| Workflow Agent/Skill name 引用 | `resource_dependencies` UUID | 按旧运行身份解析唯一可见资源 | 多匹配返回冲突，不取第一条 |
| `workflow_v2_runs.snapshot` | 保留执行状态；新增 `run_resource_snapshots` | 历史 run 不追溯伪造闭包；仅迁移可证明的 definition version | 无法证明的历史依赖标记 `legacy_unresolved`，保留原字段 |

## 明确不迁移的用户状态

以下内容继续留在用户/Run 域，只把 Agent 名称键逐步替换为资源 UUID：

- `users/<id>/agent-memory`；
- thread、checkpoint、Run、event 和 audit；
- uploads、workspace、outputs、ACP workspace；
- 调用者凭据、个人配置和网络授权。

迁移后的共享 Agent 记忆键为 `(runner_id, agent_resource_id)`。定义 owner 的记忆和凭据不得复制、回退加载或作为缺省值。

## 名称与 ownership

- canonical 唯一键为 `(type, owner_id, slug)`，不是全局名称；
- 转移保持 UUID 和版本不变，visibility 降为 private；
- 目标 owner 同 type/slug 已存在时，预检失败并要求明确 rename；
- alias resolver 仅用于确定性兼容入口：当前 owner 匹配优先，唯一可见共享资源次之，多匹配返回 409；
- bundled UUID 来自版本控制中的稳定清单，安装和升级不得重新生成。

## 存量迁移的部署侧契约

迁移工具随旧版本交付，本版本不再携带。升级流程：

1. 在旧版本上执行 `audit`（只读枚举、冲突、hash、预计 UUID）→ 无未决冲突后执行 `migrate`（staging→hash→原子 rename→DB，幂等）→ `verify`（只读对比行数、UUID、owner、visibility、版本、依赖、hash 与 bundled 清单），三者 exit 0 后再升级；
2. 升级到本版本后旧名称路由（`/api/agents`、`/api/skills`、`/api/workflows`）不存在（404），外部集成需切 `/api/resources`；`IDEER_RESOURCE_CATALOG_MODE` 已移除；
3. 无存量数据时直接安装，无需迁移；
4. 回滚：`git revert` 本分支；legacy 源未删时可在旧版本重跑迁移。

## 切换检查点

1. 空库、旧库和重复升级都只有一个 Alembic head；
2. audit 无未决冲突后才可 migrate；
3. 升级前 verify 全绿（旧版本执行）；升级后以 canonical-only 语义运行验收矩阵；
4. 旧目录与 `resource_metadata` 兼容数据在观察期内保留，物理清理另需备份、hash 校验、保留期满足和超级管理员明确授权。

## 旧版本命令调用（升级前执行）

`audit` 和 `verify` 只读；`migrate` 幂等可重复执行。

```bash
cd backend
PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 audit \
  --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 migrate \
  --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
PYTHONPATH=packages/harness uv run python -m ideer.scripts.resource_catalog_v2 verify \
  --legacy-base-dir /path/to/IDEER_HOME --skills-root /path/to/skills
```

旧版本提供的 `rollback` 仅允许回退仍为迁移 v1、无草稿、无 Run 快照、无外部依赖的资源；文件内容先移入备份目录，数据库提交失败时补偿移回。旧 Skill、Agent、Workflow 源不会被命令删除。
