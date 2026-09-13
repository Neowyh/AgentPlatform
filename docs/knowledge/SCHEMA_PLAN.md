# Schema Plan — 知识域建表草案（M2 Ticket 01 产出）

> audience: developers<br>
> status: draft（字段草案供 02/03 号票执行时定稿）<br>
> owner: engineering maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/knowledge/SCHEMA_PLAN.md`

本文把知识方案 §6 的语义模型翻译为本仓库现有 ORM / Alembic 风格的字段草案。语义模型不要求逐字照搬（知识方案 §6 原则）；符号与风格以 `backend/app/agentplatform/resource_models.py` 为准。现状勘察见 `IMPLEMENTATION_INVENTORY.md` §9。

## 1. 分期与落点

| 表 | 期 | 落点模块 | 说明 |
| --- | --- | --- | --- |
| `knowledge_bases` | **M2（票 02）** | `backend/app/agentplatform/knowledge_models.py`（新建，同 `Base`） | KB 1:1 扩展 resources 行；provider binding 内嵌（知识方案 §6.4：第一版合入，不单独建 `knowledge_provider_bindings`） |
| `resource_dependencies` 加列 | **M2（票 03）** | `resource_models.py` + 迁移 ALTER | dependency_mode / revision_id / required / purpose |
| `knowledge_documents` | M3 | `knowledge_models.py` | 文档管理（Phase 4） |
| `knowledge_base_revisions` | M4 | `knowledge_models.py` | Revision / manifest hash（Phase 5） |
| `knowledge_retrieval_receipts(+_items)` | M5 | 见 §6 开放决策 | Retrieval Receipt（Phase 7） |

企业模块落点为 `backend/app/agentplatform/knowledge/`（总方案裁决 C3）；上表 ORM 所在文件可与其同层新增，不改 `harness/deerflow`（M2 收尾约束，知识方案 §94）。

## 2. `knowledge_bases`（M2 核心）

字段风格：SQLAlchemy 2.0 `Mapped[...] = mapped_column(...)`；String UUID 主键；显式命名 `ck_*`/`uq_*`/`ix_*` 约束；时间列 `DateTime(timezone=True)` + `default=_now`。

```python
class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ragflow")
    provider_dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieval_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ingestion_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedding_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        CheckConstraint("provider_type <> ''", name="ck_knowledge_bases_provider_type"),
        UniqueConstraint("provider_type", "provider_dataset_id", name="uq_knowledge_bases_provider_binding"),
        Index("ix_knowledge_bases_provider_dataset", "provider_dataset_id"),
    )
```

设计对应关系（与既有语义逐条挂钩，详见 `IMPLEMENTATION_INVENTORY.md` 引用）：

- **主键即外键** `resource_id` → `resources.id`：KB 的企业身份就是 canonical Resource UUID（双层真源 ADR、基线不变量 5/6）。`ondelete="CASCADE"` 与 `resource_dependencies.source_resource_id` 同型——目录无 DELETE 端点，正常生命周期不触发；仅随资源行存亡。治理字段（owner/department/visibility/lifecycle/版本/审计）**不复制**，一律读 `resources` 行，避免第二真源。
- `provider_dataset_id` **可空、opaque**：dataset ID 不是企业 ID（基线不变量 6）。可空对应"KB 先建、后绑 dataset"（票 02 的手动绑定路径）；`(provider_type, provider_dataset_id)` 唯一防重复绑定同一 dataset；**不进可导出 Resource Content**（知识方案 §75：Content 只存 `description / provider_type / retrieval_profile / default_dependency_mode` 等声明式配置，无 API key、无 raw dataset id、无 chunk 内容）。
- `active_revision_id` M2 先留可空字符串列、不建 FK——`knowledge_base_revisions` 是 M4 表；M4 迁移再补 FK（沿用 `20260828_run_snapshot_selection_role` 式的小步加列风格）。
- `sync_status` 表达 provider 对账状态（`ok | drifting | unreachable | orphaned`，知识方案 §86–88 预留；M2 仅写 `ok`/`unreachable`）。
- 三个 `*_profile_json` 对应知识方案 §32–34 的 profile 概念；M2 允许空 dict，检索参数实际仍以 `knowledge_search` 工具配置为真源（不出现第二份连接/检索配置，票 02 红线）。

## 3. `resource_dependencies` 加列（M2，票 03）

对既有边零破坏：全部新列可空，旧行为等价于 `dependency_mode=NULL ⇒ live`、`required=NULL ⇒ 必选`（`ResourceDependency` 现有 schema 见 `IMPLEMENTATION_INVENTORY.md` §2.1）。

```python
dependency_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)   # live | pinned
revision_id:     Mapped[str | None] = mapped_column(String(36), nullable=True)   # pinned 锚点
required:        Mapped[bool | None] = mapped_column(Boolean, nullable=True)
purpose:         Mapped[str | None] = mapped_column(String(256), nullable=True)
```

- 校验落点：`replace_dependencies`（`resources/service.py:1184`）扩展——`dependency_mode="pinned"` 时 `revision_id` 必填且必须属于目标 KB；`live` 时 `revision_id` 必须为空；类型矩阵 `_assert_dependency_type`（:1067）扩为 `agent → {skill, knowledge_base}`、`workflow → {agent, skill, knowledge_base}`、`knowledge_base → ∅`。
- **锚点语义为票 03 开放决策**：M2 阶段 Knowledge Revision（数据 manifest）尚未建表（M4），PINNED 的 `revision_id` 可先指向 KB 的 `resource_versions`（声明式内容版本），待 M4 引入 `knowledge_base_revisions` 后对齐或加列迁移；票 03 执行时按"声明/校验/展示/持久化"最小闭环裁决。
- 迁移形态：`ALTER TABLE resource_dependencies ADD COLUMN ...` ×4，无数据回填；CHECK 约束（mode 取值）可选在 ORM 层校验优先，避免 SQLite/PG 双方言的约束差异（参照仓库既有倾向：`selection_role` 用 DB CHECK，业务枚举校验多在 service 层——票 03 执行时二选一并写明）。

## 4. `knowledge_documents`（M3 草案）

```python
id: String(36) PK
knowledge_base_id: FK knowledge_bases.resource_id, ondelete="CASCADE", nullable=False
revision_id: String(36), nullable        # M4 前为空
logical_document_id: String(36), nullable=False   # 同一逻辑文件的 v1/v2/v3（知识方案 §6.3）
provider_document_id: String(128), nullable       # opaque
filename / display_name / source_type / source_uri / mime_type: 文本列
file_size: Integer
content_hash: String(64)
metadata_json: JSON
parse_status: String(16), default="pending"       # pending|parsing|ready|failed
parse_error_code: String(64), nullable
created_by / created_at / updated_at
```

约束：`uq_knowledge_documents_logical`（knowledge_base_id, logical_document_id）+ `ix_knowledge_documents_kb`。文件本体存储与上传管线属 M3（知识方案 §24–25），本表不存路径以外内容。

## 5. `knowledge_base_revisions`（M4 草案）

```python
id: String(36) PK
knowledge_base_id: FK knowledge_bases.resource_id, ondelete="CASCADE", nullable=False
revision_no: Integer, nullable=False              # KB 内自增
status: String(16), nullable=False                # draft|indexing|ready|published|failed|superseded|archived
manifest_hash: String(64), nullable=False
document_count: Integer, nullable=False
provider_dataset_id: String(128), nullable        # immutable dataset per revision（知识方案 §9.1）
provider_revision_hint: String(128), nullable
created_by / created_at / published_at
```

约束：`uq_knowledge_base_revisions_no`（knowledge_base_id, revision_no）、`ck_..._status`。发布即不可变（CONTEXT.md "Knowledge Revision" 词条）；LIVE/PINNED 冻结语义（知识方案 §36）在 `run_resource_snapshots` 侧落 `resource_id + version` 已可复用——M4 时确认 KB 的 Run 快照行用 `version` 承载 revision_no 或经 `selection_role` 扩展，不在 M2 改表。

## 6. `knowledge_retrieval_receipts`（M5 草案 + 开放决策）

知识方案 §6.5：receipt header + N items 两表（header 承载 run/thread/tool_call/tool_receipt/kb/revision/query_hash；items 承载 document/chunk/score/rank/citation_label/provider refs）。字段草案照 §6.5 直译，此处不展开。

**存储归属开放决策**（`IMPLEMENTATION_INVENTORY.md` §12）：

- 选项 A（倾向）：控制面表，模型放 `knowledge_models.py`，审计/保留期与 `audit_logs`/`run_resource_snapshots` 同域。写入需 host 侧接缝——扩展包 `agentplatform_extension.knowledge` 只依赖 `deerflow-extension-api`（现状约束，`agentplatform_extension/__init__.py` docstring），不能 import 企业模型；receipt 由 runtime 适配层产生、经现有 `bind_run_evidence`/`record_tool_receipt` 通道交 host 持久化。
- 选项 B：扩展自有表，走 `ExtensionSpec.table_prefix` 机制（`deerflow/extensions/loader.py:28`，env.py 自动排除 autogenerate）。代价：审计/retention 报告需跨域聚合。

## 7. 迁移操作规程（统一链上新增 revision）

1. 前置确认单 head（当前 head 见 `IMPLEMENTATION_INVENTORY.md` §9）：`cd backend && uv run python -m alembic -c app/agentplatform/persistence/migrations/alembic.ini heads`。
2. 新建 `backend/app/agentplatform/persistence/migrations/versions/2026MMDD_<snake_name>.py`，`down_revision = "20260909_device_control_plane"`（M2 两张票各自一个 revision，串行排队：`knowledge_bases` → `resource_dependencies_kb_fields`）。
3. ORM 与迁移 DDL 双写约束（对照 `20260814_resource_catalog_v2.py` 的建表 + `20260817_split_bundled_provenance.py` 的列变更风格）。
4. 更新守卫测试期望：`backend/tests/unit/persistence/test_migration_versions.py`（单 head 断言）、`test_persistence_migrations_env.py`；schema 断言在 `backend/tests/integration/persistence/test_migration_schema.py` 增行。
5. gateway 启动自动 `bootstrap_schema` upgrade（`deerflow/persistence/engine.py:196-233`），无需手动步骤；验收命令沿用 cutover 手册 §1.1 的 heads 检查。
