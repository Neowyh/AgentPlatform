# Skill、Agent、Workflow 资源治理 V2 架构决策

> audience: developers, architects, security reviewers, operators
> status: implemented
> owner: engineering maintainers
> last-verified: 2026-08-16
> canonical-path: `docs/decisions/2026-08-14-resource-governance-v2.md`
> switch-to-canonical: 2026-08-15, local worktree `resource-governance-v2`, mode `canonical`

## 决策摘要

Skill、Agent、Workflow 统一使用 UUID 标识的权威资源目录。每个资源只有一份规范源，非 owner 直接只读使用已发布版本，不再按用户复制安装。旧 `resource_metadata` 在兼容期保留，继续承载 Tool 和旧名称接口；新的 `resources` 及配套表独立承担三类资源的 owner、可见性、生命周期、版本、依赖、草稿、收藏和运行快照。

该决策同时收敛存储与运行权限。资源可见不等于无条件可运行；每次新 Run 必须在产生队列、文件或外部调用等副作用前，以调用者身份解析完整依赖闭包、工具上限和实际版本，随后将 UUID、版本及内容 hash 固化到运行快照。Worker 只消费快照，不按名称或 owner 目录重新猜测定义。

## 背景与问题

当前实现由多套事实源共同决定资源行为：

- Skill 使用 public/custom 目录与 metadata 混合发现；
- Agent 定义优先从 `users/<owner>/agents/<name>` 加载，并保留 legacy shared fallback；
- Workflow 定义版本存数据库，但依赖仍以名称解析；
- `resource_metadata` 同时承载 Tool，唯一键与查询条件不一致，并把收藏状态放在资源行上；
- Workflow Worker 会在执行阶段重新按名称加载 definition 和 Agent，并可能从 owner 目录加载共享 Agent 配置与 SOUL；
- 用户删除与部门删除直接批量更新或删除 metadata，并可能清除历史 Run、Thread 和文件。

因此，“API 列表可见”不能证明“运行时可达且权限正确”。共享资源还可能把 owner 的工具声明、凭据解析路径或个人记忆带入调用者运行。名称冲突、文件与数据库非事务、最新版传播、紧急下架和历史引用也缺少统一语义。

## 目标和非目标

目标：

1. 为 Skill、Agent、Workflow 建立 UUID、版本化、可审计的单一资源真源。
2. 统一浏览、使用、编辑、发布、可见性、归档、下架、Fork、转移和清理授权。
3. 保证共享执行使用调用者权限、凭据和隔离记忆，不借用 owner 身份。
4. 使新 Run 自动使用当时的完整 latest 闭包，已启动 Run 使用冻结快照。
5. 覆盖 API、Frontend、SDK、Worker、删除/reconcile、安装、部署和离线资产。
6. 以 dual 模式完成无损迁移和对比验证，再切换 canonical。

非目标：

- 本次不把 Tool 迁入 owner/版本/Fork 模型；
- 不允许匿名访问 public 资源；
- 不提供 per-user 共享资源安装副本；
- 不在 canonical 验收、备份、hash 核对、保留期和明确授权之前物理清理旧数据；
- 回滚不会倒退版本号，而是以旧内容发布一个新版本。

## 权威数据模型

`resources` 是目录主表：

| 字段组 | 字段 | 约束 |
|---|---|---|
| 标识 | `id`, `type`, `slug`, `display_name` | `id` 为 UUID；`type` 为 skill/agent/workflow；`(type, owner_id, slug)` 唯一 |
| 所有权 | `owner_id`, `system_owned` | 系统资源使用稳定 UUID 和 system owner |
| 可见性 | `visibility`, `scope_department_id`, `authz_revision` | private/department/public；权限语义不从路径或 manifest 推导 |
| 生命周期 | `lifecycle_status` | active/archived/suspended |
| 版本 | `latest_version`, `draft_revision` | 发布版本单调递增；草稿使用乐观锁 |
| 存储 | `storage_kind`, `storage_key` | filesystem/database/bundled；路径不包含 owner 或 visibility |
| 审计 | `created_at`, `updated_at` | 所有变更由服务层写入 |

配套表：

- `resource_versions`：不可变版本、内容 hash、扫描结果、创建者、发布时间和来源 Fork 信息；
- `resource_dependencies`：源资源到 Skill/Agent 的 UUID 引用；
- `run_resource_snapshots`：Run 的完整依赖闭包、实际版本、hash 和解析序号；
- `resource_favorites`：用户与资源的多对多收藏；
- `resource_drafts`：草稿 revision、hash、修改者和 staging 引用；
- visibility application：新增 `resource_id`、申请时版本和 hash，兼容期保留旧 type/name 字段。

`resource_metadata` 不改造成上述主表。dual 期间由类型 facade 维护兼容读写；canonical 后仅保留 Tool 和明确的旧接口兼容数据。

## 存储与发布一致性

文件资源布局：

```text
IDEER_HOME/resources/
├── skills/<resource_uuid>/
│   ├── draft/
│   ├── staging/
│   └── versions/<version>/
└── agents/<resource_uuid>/
    ├── draft/
    ├── staging/
    └── versions/<version>/
```

Workflow 内容继续在数据库中按 `resource_id + version` 保存。Skill 和 Agent 发布采用以下顺序：

1. 在同一文件系统的 staging 目录写入候选内容；
2. 拒绝 symlink、路径穿越、超限文件/归档和未经允许的可执行内容；
3. 校验格式、类型契约、依赖闭包和工具能力声明；
4. 对规范化内容逐文件计算 hash；
5. 原子重命名为只读 `versions/<version>`；
6. 数据库事务写入版本并推进 latest 指针；
7. DB 失败时保留为未引用对象，由 reconcile/GC 报告和回收；DB 不得提交指向不存在文件的版本。

Sandbox 只挂载快照解析出的具体只读版本，禁止挂载 draft、staging 或整个资源根目录。

## 授权模型

所有资源操作通过 `ResourceService`。服务公开 `list_visible`、`get_visible`、`get_published_content`、`get_owner_draft`、`assert_modify`、`resolve_for_use`、`publish`、`change_visibility`、`archive`、`suspend`、`fork` 和 `transfer_owner`。

统一规则：

- 浏览和运行必须同时满足 visibility 与调用者 action permission；
- public 仅对已登录用户开放；
- 非 owner 只能读取已发布版本；owner 可编辑草稿、发布、归档和缩小 visibility；
- 扩大 visibility 需审批；缩小立即生效并撤销待审批申请；
- super admin 不静默编辑 owner 内容，只能 suspend/恢复、转移和执行保留策略清理；
- department admin 的申请列表和审批都在 SQL 查询阶段限制到本部门；
- 资源 tool groups 是上限，实际集合为资源声明、调用者权限、平台/沙箱/网络策略的交集；
- 凭据只能来自调用者或未来显式服务身份；资源包不得携带明文密钥；
- Agent 长期记忆按 `(runner_id, agent_resource_id)` 隔离。

## 依赖、运行与撤权

Agent 和 Workflow 依赖保存 UUID，不固定版本。新 Run 在任何副作用前通过同一数据库事务视图解析 latest 闭包，拒绝环、缺失、不可见、archived/suspended 依赖和调用者无权限的工具。快照落库后才创建或入队 Run。

可见性闭包：public 只能依赖 public；department 只能依赖 public 或相同部门；private 可依赖 owner 当前可使用的资源。依赖缩小可见性后，新的不合法 Run 立即 fail-closed，并通知上层 owner。

普通 visibility 缩小允许已启动 Run 使用冻结版本完成。管理员 suspend 是紧急下架：阻止新 Run，并取消快照闭包包含该资源的 queued、running、paused Run。

## 生命周期、转移和 Fork

- owner 的删除映射为 archive；资源从默认列表和新 Run 中隐藏，但版本、依赖、快照和审计保留；
- transfer 保持 UUID、版本和路径，自动降为 private，撤销待审批申请并通知依赖方；目标 owner 存在同 type/slug 时预检返回冲突，必须先明确 rename；
- 用户删除继续提供 transfer/archive/purge 管理流程，但 purge 只执行保留策略允许的安全清理；
- 部门删除的 scope 转移或 private 降级通过 ResourceService 事务完成；
- Fork 复制最新发布内容为新 UUID、当前用户 owner、private v1，记录来源资源和版本；依赖保持原 UUID 并重新授权校验。

## 兼容与切换

系统提供 `legacy | dual | canonical` 三种模式，默认 dual：

- legacy：旧路径和 metadata 是读写真源，用于紧急回退；
- dual：canonical 主写并生成兼容投影，读取结果做可观测对比；不允许静默选择冲突名称；
- canonical：三类资源只从新目录读取，旧 facade 通过 alias resolver 访问。

旧名称解析顺序是当前用户资源优先，其次唯一可见共享资源；多个可见匹配返回 409。`lead_agent` 保留为特殊 assistant 值，其余 `assistant_id` 接受资源 UUID。

bundled Agent 发布时 `config.skills` 中的 slug 引用会被改写为依赖资源的稳定 UUID（`bundled._prepare_agent`）；运行时依赖闭包解析同时按 UUID 与 slug 匹配（`runtime.load_agent_skill_definitions`），缺失引用 fail-closed。

## 失败处理与可观测性

- 发布、审批、Fork、转移使用乐观锁或唯一约束处理并发；
- reconcile 报告 DB 缺文件、文件无 DB、hash 不一致、非法链接、旧目录漂移和 bundled UUID 漂移；
- migration audit、migrate、verify、rollback 是四个独立命令；audit 和 verify 只读；
- 部署初始化任一资源失败必须返回失败，不得仅记录日志后输出成功；
- 所有迁移、可见性、发布、归档、下架、转移、Fork 和清理动作写审计。

## 采用该方案的代价

该方案新增目录表、不可变版本和运行快照，迁移期还需维护兼容投影，短期复杂度高于原地修改 `resource_metadata`。代价换来三项必要保证：Tool 不被误迁移；同名多 owner 内容不被覆盖；运行历史和权限撤销具备可证明语义。由于文件系统与数据库不能原子提交，仍需接受未引用文件的补偿清理，而不能宣称跨介质事务。

## 验收与退出条件

实现必须满足 [Resource Governance V2 验收矩阵](../testing/resource-governance-v2-acceptance-matrix.md)。迁移字段和旧入口对应关系见 [迁移映射](../governance/resource-governance-v2-migration-map.md)。只有 dual 对比、真实旧库迁移、全套测试、Worker/兼容 API、部署和离线新装均真实 exit 0 后，才可将默认模式切换 canonical。
