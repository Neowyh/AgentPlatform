# Upstream Patch Ledger

对 `backend/packages/harness/`（上游 DeerFlow harness）的每一处修改必须在此登记，
含测试证据、原因、Owner 与移除条件（架构基线 §"架构不变量"上游修改纪律）。
仅改 `backend/app/`（AgentPlatform 控制面）或 `backend/packages/agentplatform-extension/`
（扩展包）不属上游修改，无需登记。

> **唯一权威登记处**（2026-10-01 起）：本文件是 harness 本地补丁的唯一权威台账。
> 对照命令：`git diff 0f7d8709d3bbf0be26460b6277fbad9329302243 -- backend/packages/harness/deerflow`。
> `docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_PATCH_LEDGER.md` 已冻结为历史档案，
> 后续巡检只更新本文件。

## 巡检记录

| 日期 | 候选 | 结果 |
| --- | --- | --- |
| 2026-09-08 | m0 票 03（deerflow-main-0f7d8709 全量巡检） | 对照 `0f7d8709` 实测 20 个差异文件，全部归属 PATCH-002..015，无未登记差异；上游锁定 `0f7d8709`，各 open 行移除条件均未因上游变化满足，逐项复评结论均为 keep（见下表）。 |
| 2026-09-13 | feature/m4-knowledge-revisions（M4 票 06 Gate 5/6 巡检） | 本轮涉及 `community/ragflow/client.py`（PATCH-001）；未发现未登记的上游修改。GitNexus 在本工作区不可用（无索引、npx 无法引导，见 dev-log），以人工调用方分析替代。 |
| 2026-10-01 | v2.1.0 合并前置（票 01） | 发现 4 个未登记 sandbox 补丁文件并补登记（见 PATCH-016..019）；PATCH-016/017 与上游 v2.1.0 变更重叠。全面对账 44 个 harness 文件（43 个代码文件 + 1 个文档）后另发现 15 个未登记文件，补登记为 PATCH-020..032（其中 `config/app_config.py`、`runtime/runs/manager.py` 与既有行共享文件），44 个原始 harness 文件全部归属、未登记清零；本候选新增 17 个 CLAUDE.md 文档，预算据此从 44（43 代码 + 1 文档）修订为 61（43 代码 + 18 文档），代码预算仍为 43（见"2026-10-01 全量对账"）。 |

### 2026-09-08 巡检逐项结论（2026-10-01 自历史档案迁入，内容保持原文）

| ID | Conclusion | Reassess |
|---|---|---|
| PATCH-002 | keep — the extension (`EvidenceLifecycleContributor`) owns the envelope only in binding/authorization configurations; the harness stamp is the runtime guarantee of a bare envelope for non-participating extensions, pinned by `tests/test_extension_task_lifecycle.py::test_start_and_stop_reach_contributors_in_order`. Removal requires upstream (not the extension) to own bare-envelope seeding | next upstream sync |
| PATCH-003 | keep — doc-only alignment of `config/AGENTS.md` with the upstream `memory_config.py` schema (files otherwise identical); the guidance stays where profile authors read it. Candidate to upstream verbatim, then revert the local line | next upstream sync |
| PATCH-004 | keep (schema clause) — compatibility-import clause verified satisfied (see row); the schema itself remains until upstream provides equivalent durable-workflow limits | next upstream sync |
| PATCH-005 | keep — the extension API ships `MiddlewareContributor`, but the runtime-owned receipt key and the sub-agent citation verdict are not exposed through it, so the receipt→evidence bridge cannot move behind the extension boundary yet | next upstream sync |
| PATCH-007 | keep — no upstream Code Evidence contract exists | next upstream sync |
| PATCH-008 | keep — no upstream scanner contract matching the fixed command/finding shape | next upstream sync |
| PATCH-009 | keep — removal condition (upstream/extension persistence contract for Workflow V2 tables and Run Evidence) still unmet; full DB execution verified 2026-09-08 (see row) | upstream contract, or the Workflow ExecutionTarget milestone (M10) |
| PATCH-010 | keep — upstream offers post-assembly observers only; no pre-assembly frozen-input seam | next upstream sync |
| PATCH-011 | keep — upstream SQLite connect hook assumes a sync driver | next upstream sync |
| PATCH-012 | keep — upstream projection config cannot express run-scoped frozen skill closures | next upstream sync |
| PATCH-013 | keep — upstream admission mints its own run id unconditionally | next upstream sync |
| PATCH-014 | keep — guards are permanent no-ops on fresh databases; removal is hygiene only | once no deployed database predates `20260908_unify_migration_chains` (M0 rollout complete) |
| PATCH-015 | keep — registration of the ticket-01 unified-entry machinery the inspection found unlisted; the machinery itself is verified and load-bearing for every deployed pre-merge database | next upstream sync |

### 2026-10-01 全量对账（票 01）

`git diff 0f7d8709d3bbf0be26460b6277fbad9329302243 --name-only -- backend/packages/harness/deerflow`
上游基线实测 44 个文件（36 修改 + 8 新增；43 个代码文件 + 1 个文档），逐个归属如下（路径省略
`backend/packages/harness/deerflow/` 前缀；带 `*` 的文件承载两个登记项的改动）：

| 登记项 | 文件（44） |
| --- | --- |
| PATCH-001 | `community/ragflow/client.py` |
| PATCH-002 | `extensions/notify.py` |
| PATCH-003 | `config/AGENTS.md` |
| PATCH-004 | `config/workflow_runtime_config.py`、`config/app_config.py*` |
| PATCH-005 | `agents/middlewares/tool_receipt_middleware.py`、`tools/builtins/task_tool.py` |
| PATCH-006 | `persistence/bootstrap.py`（含 legacy 表 `create_all` 块，与 PATCH-031 配套）、`persistence/migrations/env.py` |
| PATCH-007 | `uploads/code_evidence.py` |
| PATCH-008 | `uploads/code_analysis.py` |
| PATCH-009 | `persistence/models/workflow_v2.py` |
| PATCH-010 | `agents/lead_agent/agent.py`、`agents/lead_agent/prompt.py` |
| PATCH-011 | `persistence/engine.py` |
| PATCH-012 | `sandbox/local/local_sandbox_provider.py` |
| PATCH-013 | `runtime/runs/manager.py*` |
| PATCH-014 | `persistence/migrations/versions/0001_baseline.py` |
| PATCH-015 | `persistence/migrations/_chain_meta.py`、`persistence/migrations/alembic.ini`、`persistence/migrations/versions/20260908_unify_migration_chains.py` |
| PATCH-016 | `sandbox/local/local_sandbox.py` |
| PATCH-017 | `sandbox/tools.py` |
| PATCH-018 | `sandbox/encoding.py` |
| PATCH-019 | `sandbox/search.py` |
| PATCH-020 | `agents/middlewares/tool_error_handling_middleware.py` |
| PATCH-021 | `community/aio_sandbox/aio_sandbox_provider.py` |
| PATCH-022 | `community/ragflow/tools.py` |
| PATCH-023 | `config/app_config.py*`（`KnowledgeConfig`；其余差异属 PATCH-004） |
| PATCH-024 | `extensions/__init__.py`、`extensions/registry.py` |
| PATCH-025 | `models/openai_codex_provider.py` |
| PATCH-026 | `runtime/journal.py` |
| PATCH-027 | `runtime/runs/worker.py`、`runtime/runs/manager.py*`（`persist_current_record`；其余差异属 PATCH-013） |
| PATCH-028 | `subagents/executor.py` |
| PATCH-029 | `subagents/registry.py` |
| PATCH-030 | `agents/middlewares/input_sanitization_middleware.py`、`client.py`、`extensions/gateway.py`、`skills/frontmatter.py`、`skills/projection.py`、`skills/storage/user_scoped_skill_storage.py` |
| PATCH-031 | `persistence/models/legacy_tables.py`、`persistence/models/__init__.py` |
| PATCH-032 | `utils/readability.py` |

## 登记项

### PATCH-001: RAGFlow 管理端 client 兼容 v0.27+ 批量文档端点

- **文件**: `backend/packages/harness/deerflow/community/ragflow/client.py`
- **修改**: `parse_document` 改用批量解析端点
  `POST /datasets/{id}/documents/parse`（body `{"document_ids": [...]}`）；
  `get_document_status` 改经列表端点解析单文档状态（单文档 GET 返回非 JSON）；
  `delete_document` 改为 JSON body `{"ids": [...]}`（旧 query 参数形式被拒绝）；
  新增 `create_dataset`、`list_dataset_documents`（M4 发布/对账所需）。
- **上游替代方案**: 上游 RAGFlow 社区 client 提供批量解析、状态查询、删除和建库等价能力后采用上游实现。
- **原因**: 真实 RAGFlow v0.27.1 隔离栈验收（M4 票 06）发现单文档 parse 404、
  单文档 GET 非 JSON、DELETE query 形式被拒——既有单元测试的假 client 无法暴露。
- **测试**: `tests/test_ragflow_client.py`（批量 parse、列表化状态、JSON body 删除、
  create/list 端点、分页与响应形）；真实 provider 验收脚本全链路通过（dev-log）。
- **Owner**: knowledge 域维护者
- **移除条件**: 上游 RAGFlow 社区 client 提供等价能力（批量 parse/状态/删除/建库）
  并被本仓库采纳时，可整体移除。

### PATCH-002..015（2026-10-01 自 docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_PATCH_LEDGER.md 整体迁入，行内容保持原文）

| ID | Path / symbol (impact scope) | Reason local behavior is required | Upstream alternative considered | Removal trigger | Verification | Owner | Status |
|---|---|---|---|---|---|---|
| PATCH-002 | `deerflow/extensions/notify.py` (`notify_task_start/stop`) | Initialize and finalize the shared Run Evidence Envelope at the runtime task lifecycle boundary | Upstream task lifecycle hooks do not own AgentPlatform's cross-cutting evidence envelope | Remove when the AgentPlatform extension owns this lifecycle binding without a harness patch | `tests/test_extension_task_lifecycle.py`, extension API contract tests | runtime evidence maintainers | open |
| PATCH-003 | `deerflow/config/AGENTS.md` (memory schema guidance) | Document the merged host-shared/pluggable Memory schema and migration boundary | Upstream documentation does not describe AgentPlatform's legacy profile migration | Remove when equivalent guidance is supplied by the extension/config package | `tests/test_memory_manager_pluggable.py` | memory configuration maintainers | open |
| PATCH-004 | `deerflow/config/workflow_runtime_config.py`, `deerflow/config/app_config.py` (`WorkflowRuntimeConfig`) | Move durable workflow admission/lease limits into the DeerFlow-owned configuration schema while preserving AgentPlatform compatibility imports | No upstream workflow-v2 config model covers the AgentPlatform durable workflow limits | Remove compatibility import after all AgentPlatform callers use the DeerFlow symbol directly; retain schema until upstream provides equivalent limits | `tests/unit/workflows/test_v2_runtime_config.py` (3 passed), Ruff check/format | workflow runtime maintainers | open — compatibility-import clause verified satisfied 2026-09-08 (zero AgentPlatform-side compat imports remain; all consumers import the DeerFlow symbol directly), only the schema clause still blocks |
| PATCH-005 | `deerflow/agents/middlewares/tool_receipt_middleware.py` (`ToolReceiptMiddleware._stamp_message`), `deerflow/tools/builtins/task_tool.py` (`_record_run_evidence_verification`) | Forward runtime-owned tool receipts and sub-agent verification verdicts into the AgentPlatform Run Evidence Envelope when the optional extension is active | Upstream receipt middleware/task tool have no enterprise Run Evidence sink; message-carried receipts remain unchanged without the extension | Remove once the runtime exposes equivalent extension callbacks for receipt contribution | `tests/test_tool_receipt_middleware.py`, extension boundary tests (44 combined), receipt projection tests | runtime evidence maintainers | open |
| PATCH-006 | `deerflow/persistence/bootstrap.py`, `deerflow/persistence/migrations/env.py` (`deerflow_alembic_version`) | Isolate DeerFlow migration state from AgentPlatform's control-plane Alembic head during dual runtime | A shared `alembic_version` table cannot represent two independent histories | Remove only after a verified single forward-only migration chain replaces both histories | `tests/unit/persistence/test_unified_chain_adoption.py` (8 passed), Ruff | persistence maintainers | **closed 2026-09-08** — chains unified by merge revision `20260908_unify_migration_chains` (single `alembic_version`, `alembic heads` single-head verified); dedicated table bridged and dropped via `_chain_meta.adopt_unified_version_state`; control-plane `alembic.ini`/`env.py` retired; fresh/existing/dual-recorded/control-plane-only/pre-alembic DB shapes verified |
| PATCH-007 | `deerflow/uploads/code_evidence.py` (`package_root`) | Expose only the caller-scoped frozen package path to runtime tools after Code Evidence acceptance moved to AgentPlatform | No upstream Code Evidence contract exists; runtime tools need a neutral path projection | Remove when the runtime provides an equivalent package-root capability through the extension API | `tests/unit/gateway/test_code_evidence_package.py` (13 passed), Ruff | code evidence maintainers | open |
| PATCH-008 | `deerflow/uploads/code_analysis.py` (scanner inventory/normalization/report contract) | Keep deterministic, shell-free C analysis available to the DeerFlow built-in tool while removing the product implementation from `ideer` | No upstream scanner implementation provides AgentPlatform's fixed command and finding contract | Remove when the extension/runtime API supplies the same fixed scanner contract | `tests/unit/gateway/test_code_analysis.py` (5 passed), Ruff | code analysis maintainers | open |
| PATCH-009 | `deerflow/persistence/models/workflow_v2.py` | Provide a DeerFlow-owned Workflow V2 model namespace for Gateway/runtime callers while keeping the enterprise table family out of standalone DeerFlow's generic model registry | Upstream runtime has no AgentPlatform Workflow V2 tables or Run Evidence fields | Remove only after Workflow V2 tables and Run Evidence are represented by an upstream/extension persistence contract | Gateway, Worker, Store, RunRecord and resource-governance service now import the DeerFlow namespace; six-table Alembic/ORM contract plus standalone/combined metadata checks passed; duplicate `ideer` Workflow mapping deleted; full DB execution verified on both backends (`tests/integration/workflows/test_v2_db_execution.py`: unified-chain `upgrade head` over an empty SQLite and PostgreSQL database and over a 20260715-shaped legacy database, driving the six-table family through Store/RunRepository and the Gateway canonical-run + Worker lease-takeover path) | workflow persistence maintainers | open |
| PATCH-010 | `deerflow/agents/lead_agent/agent.py` (`FrozenAgentInputs`, `assemble_lead_agent(frozen=...)`, `_intersect_tool_groups`, read-only update_agent withholding, skill tool-policy application), `deerflow/agents/lead_agent/prompt.py` (`soul_override`, `requested_skill_name`) | Canonical resource runs must assemble from the server-frozen UUID/version/hash closure instead of the mutable on-disk agent store, with caller tool-group intersection and read-only semantics; the per-Run frozen carrier cannot be expressed through the process-global agent store or client-injectable configurable keys | Upstream extension API offers assembly observers (post-assembly) but no pre-assembly input override; the agent store is process-global and cannot represent per-Run isolation | Remove when upstream exposes a pre-assembly frozen-input parameter or an equivalent extension seam | `tests/unit/agentplatform/test_frozen_agent_inputs.py` (5 passed, incl. the escaped `<soul>` block regression), `tests/unit/agentplatform/test_runtime_adapter.py` (2 passed), lead-agent model resolution + assembly descriptor + prompt suites (110 passed combined) | agent runtime maintainers | open |
| PATCH-011 | `deerflow/persistence/engine.py` (`init_engine` SQLite connect hook) | Upstream executes synchronous `PRAGMA journal_mode=WAL/...` on the DB-API cursor inside SQLAlchemy's connect event; with aiosqlite that adapted connection cannot run sync cursor calls, so the hook is bridged through `dbapi_conn.run_async` to keep WAL/foreign-key/busy-timeout semantics on the async engine | Upstream connect hook assumes a sync driver; no extension point exists for driver-specific connect configuration | Remove when upstream's SQLite connect hook supports async drivers (or upstream adopts the same bridge) | Gateway/persistence suites on the SQLite backend (WAL asserted in integration persistence tests) | persistence maintainers | open |
| PATCH-012 | `deerflow/sandbox/local/local_sandbox_provider.py` (`RUN_SKILL_VIEW_RESOLVER` hook, `_build_thread_path_mappings` forced-view branch) | Canonical runs key their sandbox on a run-scoped identity and must serve the run's frozen, hash-verified skill closure read-only at `/mnt/skills` — fail-closed when the view is missing — instead of the mutable per-thread projection; the run-snapshot concept does not exist upstream, and the hook keeps the dependency direction (the runtime never imports `app.agentplatform`) | Upstream projection config cannot express per-run frozen closures; the enterprise layer installs the resolver at startup (`app.agentplatform.resources.canonical_sandbox.install_run_skill_view_resolver`) | Remove when upstream exposes an equivalent pre-acquire mapping override or a run-snapshot projection contract | `tests/unit/resources/test_canonical_sandbox.py` (6 passed, incl. fail-closed case) | sandbox maintainers | open |
| PATCH-013 | `deerflow/runtime/runs/manager.py` (`create_or_reject(..., run_id=...)`, `_admit_thread_operation(..., run_id=...)`) | Canonical resource runs must admit the Run under the server-frozen run id: `prepare_run` freezes the dependency closure and run-skill view under `canonical_run_id` before `start_run` admits the record, so the Run row, `run_resource_snapshots`, and evidence binding must share one identity. Upstream's admission mints a fresh uuid unconditionally and offers no id override | No upstream extension seam or admission parameter carries a caller-supplied run id | Remove when upstream admission accepts a caller-supplied id (or an equivalent identity-binding hook) | `tests/test_run_repository.py`, `tests/test_run_manager.py` (129 passed); exercised end-to-end by `tests/integration/api/test_shared_resource_run_e2e.py` | runtime maintainers | open |
| PATCH-014 | `deerflow/persistence/migrations/versions/0001_baseline.py`, `app/agentplatform/persistence/migrations/versions/16147afec43b_add_departments_and_users_ext_tables.py`, `app/agentplatform/persistence/migrations/versions/c4d5e6f7a8b9_add_missing_core_tables.py`, `app/agentplatform/persistence/migrations/versions/f3a2b1c4d5e6_add_disabled_column_and_indexes.py` (inspector-guarded `create_table` / `add_column` / `create_index` blocks) | The unified migration chain (`20260908_unify_migration_chains`) can replay these revisions against databases where the tables already exist via `Base.metadata.create_all` (runtime-only Gateway DBs recorded at the runtime head) or via the other chain (control-plane-only DBs recorded at the control-plane head); `op.create_table` would crash with `table already exists`, and SQLite batch `add_column` on an already-present column builds a contradictory column-order dependency (`CircularDependencyError`) | Restamping such databases below the affected revisions is impossible (single version row) and replaying history is forbidden; guarding mirrors `create_all`'s `checkfirst` semantics | Remove when no deployed database predates `20260908_unify_migration_chains` (the guards are permanent no-ops for fresh databases, so removal is hygiene, not correctness) | `tests/unit/persistence/test_unified_chain_adoption.py`, `tests/integration/persistence/test_migration_schema.py` (unified-chain suites incl. the create_all-current stamp and pre-alembic enterprise pins), fresh/existing/dual-recorded/control-plane-only/pre-alembic SQLite upgrade matrix, Ruff | persistence migration maintainers | open |
| PATCH-015 | `deerflow/persistence/migrations/_chain_meta.py`, `deerflow/persistence/migrations/alembic.ini`, `deerflow/persistence/migrations/versions/20260908_unify_migration_chains.py` (unified-chain entry machinery, registered 2026-09-08 after being found unlisted by the ledger inspection) | One forward-only chain must serve both historical migration trees: the merge revision joins them under a single `alembic_version`; `_chain_meta` is the chain-identity single source and the adoption state machine that restamps legacy databases (dedicated-table, hybrid, create_all-current, pre-alembic shapes); the ini plus `version_locations` pair exposes both version directories to every `command.upgrade` | Upstream keeps two independent trees with no merge revision and no adoption machinery | Remove only when upstream represents both historical chains natively or no deployed database needs the adoption restamp paths; the merge revision itself is permanent chain history | `tests/unit/persistence/test_unified_chain_adoption.py`, `tests/integration/persistence/test_migration_schema.py` (unified-chain suites), fresh/existing/dual-recorded/control-plane-only/pre-alembic SQLite upgrade matrix, dual-backend `tests/integration/workflows/test_v2_db_execution.py` | persistence migration maintainers | open |

### PATCH-016: LocalSandbox.read_file 编码嗅探（GB18030）

- **文件**: `backend/packages/harness/deerflow/sandbox/local/local_sandbox.py`
- **修改**: `read_file` 改为整文件字节读取后经 `sniff_decode` 严格解码
  （UTF-8 → UTF-8 BOM → GB18030），返回携带嗅探标签的 `DecodedText`
  （标签只作元数据、绝不嵌入文本，str_replace 读改写往返不变）；行切片与 grep
  共用 universal-newline 行号契约；`grep` 结果透传 `match.encoding`。
- **原因**: fault-zeroing 工具链承诺 GBK 中文源码/日志可读
  （`resources/skills/fault-zeroing/SKILL.md` 与 code-evidence 上下文中间件）；
  此前非 UTF-8 文本要么解码失败、要么被 `errors="replace"` 静默替换成乱码。
  引入提交 `280298ad7`（feat(sandbox): sniff GB18030 encoding in read_file and grep）。
- **测试**: `backend/tests/unit/sandbox/test_encoding_sniffing.py`
  （`test_read_file_carries_gb18030_encoding_label`、`test_read_file_gbk_line_slice`、
  `test_read_file_sliced_read_keeps_line_numbers_aligned`、
  `test_read_file_preserves_trailing_newline_on_full_read` 等）；
  `backend/tests/test_local_sandbox_provider_mounts.py::test_read_file_line_range_reads_file_in_single_pass`。
- **Owner**: fault-zeroing 域维护者
- **移除条件**: 上游 sandbox 读取路径提供等价编码嗅探（UTF-8→GB18030 严格序）
  并被本仓库采纳时。注意：与上游 v2.1.0 的 read_file 变更重叠，合并时须逐 hunk
  比对后再定去留。

### PATCH-017: read_file/grep 工具层渲染编码标记

- **文件**: `backend/packages/harness/deerflow/sandbox/tools.py`
- **修改**: `read_file` 工具输出在 GB 命中时前置 `[encoding: GB18030]` 标记行
  （`read_current_file_content` 同步处理，保证 ReadBeforeWriteMiddleware
  哈希的字节与读工具所见一致）；`_format_grep_results` 在每个 fallback 解码
  文件的行组前插入标记；二进制错误文案改为"supports UTF-8 and GB18030"。
- **原因**: 同 PATCH-016（同一提交 `280298ad7`）——工具层须向 agent 显式暴露
  非 UTF-8 命中，避免 agent 把 GB 文本当乱码或误改写。
- **测试**: `backend/tests/unit/sandbox/test_encoding_sniffing.py`
  （`test_read_file_tool_prepends_gb18030_marker_for_gbk_file`、
  `test_grep_tool_output_carries_gb18030_group_marker`、
  `test_str_replace_on_gb_file_never_persists_the_marker_line`、
  `test_read_file_tool_illegal_bytes_report_binary_file_error` 等）。
- **Owner**: fault-zeroing 域维护者
- **移除条件**: 上游 read_file/grep 工具层渲染等价编码标记并被采纳时；
  与上游 v2.1.0 变更重叠，合并时逐 hunk 比对。

### PATCH-018: sandbox 编码嗅探共享模块（新增）

- **文件**: `backend/packages/harness/deerflow/sandbox/encoding.py`
- **修改**: 新模块：`sniff_decode`（严格嗅探序 + NUL 字节守卫，拒绝二进制
  落入 GB18030 伪解码）、`DecodedText`（携带标签的 str 子类）、
  `encoding_label_of`、`universal_newlines(_lines)`、`with_encoding_prefix`。
- **原因**: read_file 与 grep 共享同一解码契约与行号契约（`280298ad7`）。
- **测试**: `backend/tests/unit/sandbox/test_encoding_sniffing.py`
  （`test_sniff_decode_pure_ascii_is_utf8_without_label`、
  `test_sniff_decode_gbk_hits_gb18030_fallback`、
  `test_sniff_decode_binary_with_nul_keeps_explicit_error`、
  `test_with_encoding_prefix_adds_marker_line_only_for_gb_hits`、
  `test_encoding_label_of_plain_str_is_none` 等）。
- **Owner**: fault-zeroing 域维护者
- **移除条件**: 上游 sandbox 提供等价 sniff/带标签解码能力并被采纳时。

### PATCH-019: grep 严格解码与编码标注

- **文件**: `backend/packages/harness/deerflow/sandbox/search.py`
- **修改**: `find_grep_matches` 弃用 `errors="replace"`，改为整文件
  `sniff_decode` 严格解码；无法解码的文件按二进制跳过；`GrepMatch` 新增
  `encoding` 字段；行号与 read_file 共用 `universal_newline_lines` 契约。
- **原因**: 同 PATCH-016/018（`280298ad7`）——旧路径对 GB 文本产生静默乱码
  匹配，对混合内容行号与 read_file 切片不对齐。
- **测试**: `backend/tests/unit/sandbox/test_encoding_sniffing.py`
  （`test_find_grep_matches_decodes_gbk_file_and_labels_matches`、
  `test_find_grep_matches_skips_undecodable_file_without_crashing`、
  `test_find_grep_matches_single_file_root_with_illegal_bytes_yields_no_matches`、
  `test_grep_match_encoding_defaults_to_none_for_other_providers` 等）。
- **Owner**: fault-zeroing 域维护者
- **移除条件**: 上游 grep 提供等价严格解码与编码标记并被采纳时。

### PATCH-020: workflow 子代理终止型中间件子集

- **文件**: `backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py`
- **修改**: 新增 `_WORKFLOW_SUBAGENT_RUNTIME` ContextVar
  （`workflow_subagent_runtime` / `reset_workflow_subagent_runtime`）与
  `_filter_workflow_subagent_middlewares`：workflow 子代理组装图时只保留
  input 消毒、工具错误/回执/LLM 错误、ThreadData、Sandbox、SafetyFinish、
  日期上下文等终止型中间件，其余（守卫、durable-context、扩展钩子等
  条件型 after-model 边）被滤除，由显式 max_turns/timeout 兜底。
- **原因**: LangGraph 条件工具路由在完整原生中间件图与 workflow
  ThreadData/Sandbox before-agent 钩子组合下无法终止 workflow 子代理
  （已完结节点会被路由回模型）。引入提交 `ca65c5770`
  （feat(knowledge): complete M4 revision publish and run freeze）。
- **测试**: `backend/tests/test_tool_error_handling_middleware.py::test_workflow_subagent_runtime_avoids_non_terminating_after_model_hooks`。
- **Owner**: workflow 域维护者
- **移除条件**: 上游/workflow 执行器提供终止型子代理中间件组装开关
  （或中间件图可组合终止）并被采纳时。

### PATCH-021: AIO sandbox 挂载 canonical Run 冻结技能视图

- **文件**: `backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py`
- **修改**: 引入与 PATCH-012 相同的 `RUN_SKILL_VIEW_RESOLVER` 中立钩子；
  `_build_thread_path_mappings` 命中 run 视图时强制只读挂载冻结视图，
  视图缺失即 fail-closed（`Canonical Run Skill view is missing`）。
- **原因**: AIO（容器池）沙箱与本地沙箱必须对 canonical Run 施加同一份
  冻结只读技能闭包；钩子保持依赖方向（harness 不 import `app.agentplatform`）。
  引入提交 `6a79bab11`（fix(sandbox): mount frozen skill aliases in aio runs）。
- **测试**: `backend/tests/test_aio_sandbox_provider.py::test_canonical_run_skill_view_mounts_frozen_root`、
  `::test_canonical_run_extra_mounts_do_not_overlay_frozen_skill_root`；
  resolver 安装侧 `backend/tests/unit/resources/test_canonical_sandbox.py`
  （含 fail-closed 用例）。
- **Owner**: canonical-run 域维护者（与 PATCH-012 同域）
- **移除条件**: 与 PATCH-012 相同——上游暴露 pre-acquire 映射覆盖或
  run-snapshot 投影契约并被采纳时，两行同步移除。

### PATCH-022: RAGFlow 检索工具遥测/端点脱敏/文档级检索范围

- **文件**: `backend/packages/harness/deerflow/community/ragflow/tools.py`
- **修改**: `_record_retrieval_metric` 低基数检索遥测
  （operation/result/latency_ms/error_category，不含查询与身份数据）；
  连接错误分支不再向模型回显内部 `base_url`（§51：端点只进 admin 侧告警日志，
  模型只见脱敏错误码与异常类名）；`_retrieve_dataset_groups` 新增
  `document_ids_by_dataset` 文档级检索范围（修订发布按冻结文档集合检索）。
- **原因**: 引入提交 `5d35c6d77`/`094f4d7f0`（knowledge 生命周期与授权检索）、
  `67c991c90`（Gate 1 脱敏验收发现连接错误分支向模型泄露内部 base_url）。
- **测试**: `backend/tests/test_ragflow_tools.py::test_connection_error_does_not_leak_internal_base_url`、
  `::test_connection_error_is_english_and_does_not_leak_key`；文档级范围经
  扩展包 `knowledge/runtime_adapter.py` 传入，由
  `backend/tests/unit/knowledge/test_knowledge_revisions.py`（修订文档集合）
  覆盖；`knowledge_metric` 遥测断言待补。
- **Owner**: knowledge 域维护者
- **移除条件**: 上游检索工具提供等价遥测/脱敏/文档级范围能力并被采纳时。

### PATCH-023: AppConfig 新增 KnowledgeConfig

- **文件**: `backend/packages/harness/deerflow/config/app_config.py`
  （仅 `KnowledgeConfig` 段；该文件其余本地差异属 PATCH-004）
- **修改**: 新增 `KnowledgeConfig`（`publish_eval_required`、
  `reconciliation_interval_seconds`）并挂到 `AppConfig.knowledge`。
- **原因**: M4 修订发布/对账需要 harness 侧配置 schema（引入提交 `ca65c5770`）。
- **测试**: 待补（schema 本身无专测；修订发布/对账行为由
  `backend/tests/unit/knowledge/` 系列覆盖）。
- **Owner**: knowledge 域维护者
- **移除条件**: 上游 app config 提供等价 knowledge 配置 schema，或该配置
  迁回控制面并被采纳时。

### PATCH-024: extension 注册面扩展（ToolContributor / RuntimeEvidenceHooks）

- **文件**: `backend/packages/harness/deerflow/extensions/__init__.py`、
  `backend/packages/harness/deerflow/extensions/registry.py`
- **修改**: `LoadedExtensions`/`ExtensionRegistry` 新增 `tool_contributors` 与
  `runtime_evidence_hooks` 桶（含 mark/rollback/install 位置快照与
  `resolve_runtime_evidence_hooks` 解析入口）。
- **原因**: 扩展 API 需要在不 patch harness 的前提下贡献运行时证据钩子与
  工具；引入提交 `3bc6aa7a8`（m6 retrieval/eval）、`f3cd1793d`（M8 设备执行环）。
- **测试**: 端到端由 `backend/tests/test_run_worker_delivery.py::test_retrieval_evidence_is_persisted_with_terminal_run`
  与 `backend/tests/unit/knowledge/test_retrieval_receipts.py`（经扩展包
  runtime_evidence 注册驱动）覆盖；注册桶本身的单元测试待补。
- **Owner**: evidence/extension 边界域维护者
- **移除条件**: 上游 extension API 原生提供等价 ToolContributor/
  RuntimeEvidenceHooks 注册面并被采纳时。

### PATCH-025: Codex provider 错误详情安全渲染

- **文件**: `backend/packages/harness/deerflow/models/openai_codex_provider.py`
- **修改**: 新增 `_safe_error_detail`：流式错误响应先 drain 再解析（规避
  `ResponseNotRead`）、字典键白名单（detail/error/message/code/type）、
  截断 500 字符并去换行；`HTTPStatusError` 分支记录 status/request-id/detail
  告警日志。其余差异为 import/格式重排。
- **原因**: 引入提交 `c8534ea0b`（fix(workflows): preserve state across
  parallel control nodes）与 `7d6c44e8f`（M9 runtime/Windows lane）；
  此前 rate-limit/provider 错误无 actionable 诊断且可能泄露凭据。
- **测试**: `backend/tests/test_codex_provider.py::test_safe_error_detail_is_bounded_and_selective`、
  `::test_safe_error_detail_reads_streaming_error_responses`。
- **Owner**: models 域维护者
- **移除条件**: 上游 Codex provider 提供等价有界错误详情与拒绝日志并被采纳时。

### PATCH-026: RunJournal 首 token 计时（TTFT）

- **文件**: `backend/packages/harness/deerflow/runtime/journal.py`
- **修改**: `on_llm_new_token` 记录首个非空流式 token 的 `llm_ttft_ms` 日志
  （trace_id/caller/thread_id 维度，不缓存 token 块）；journal 挂
  `ensure_trace_id`；其余大段差异为纯格式重排。
- **原因**: 引入提交 `e4bcfa718`（feat(ttft): add multi-attachment timing
  diagnostics）。
- **测试**: `backend/tests/test_run_journal.py::test_on_llm_new_token_logs_only_first_non_empty_token`
  （gateway 侧另有 `backend/tests/unit/gateway/test_first_token_timing.py`）。
- **Owner**: runtime 可观测域维护者
- **移除条件**: 上游 RunJournal 提供等价首 token 计时并被采纳时。

### PATCH-027: Run 完成时归档 run evidence

- **文件**: `backend/packages/harness/deerflow/runtime/runs/worker.py`；
  `backend/packages/harness/deerflow/runtime/runs/manager.py`
  （仅 `persist_current_record`；该文件其余本地差异属 PATCH-013）
- **修改**: worker 收尾时经 `resolve_runtime_evidence_hooks` 读取当前 run 的
  证据绑定，写入 `record.metadata["run_evidence"]`（`archive_status`=
  archived/failed，失败时经 `persist_current_record` 重写）；manager 新增
  `persist_current_record`（完整持久化内存 run 记录含 metadata）。
- **原因**: 引入提交 `79556489f`（feat(knowledge): add retrieval receipt
  evidence view）、`3bc6aa7a8`——检索引用必须先归档成功才对模型可见（fail-closed）。
- **测试**: `backend/tests/test_run_worker_delivery.py::test_retrieval_evidence_is_persisted_with_terminal_run`；
  `backend/tests/unit/knowledge/test_retrieval_receipts.py::test_retrieval_citation_is_delivered_only_after_archive_callback_succeeds`、
  `::test_archive_failure_does_not_deliver_a_verifiable_citation`。
- **Owner**: evidence 域维护者
- **移除条件**: 上游 run 生命周期暴露等价完成时证据归档回调
  （RuntimeEvidenceHooks 上游化）并被采纳时。

### PATCH-028: 委托检索谱系回执

- **文件**: `backend/packages/harness/deerflow/subagents/executor.py`
- **修改**: `SubagentResult` 新增 `retrieval_receipts` 字段及
  update/snapshot（带锁）；子代理收尾时从 evidence hooks 绑定的
  `binding.retrieval_receipts` 收割，保持父任务可见的委托检索谱系。
- **原因**: 引入提交 `3bc6aa7a8`、`4595e95e4`（fix(evidence): preserve
  delegated retrieval lineage）。
- **测试**: `backend/tests/unit/knowledge/test_retrieval_receipts.py::test_retrieval_receipt_from_child_task_is_visible_to_parent`。
- **Owner**: evidence 域维护者
- **移除条件**: 与 PATCH-027 相同（RuntimeEvidenceHooks 上游化）后随之移除。

### PATCH-029: managed 子代理解析保留全局 runtime 覆盖

- **文件**: `backend/packages/harness/deerflow/subagents/registry.py`
- **修改**: `_managed_definitions` 解析默认存储前快照 subagents 配置单例，
  解析后若被 AppConfig 的同步副作用改写则恢复，避免丢弃
  `load_subagents_config_from_dict()` 刚设置的 runtime 覆盖。
- **原因**: 引入提交 `5fcb8fe6a`（fix(subagents): preserve global runtime
  overrides）。
- **测试**: `backend/tests/test_managed_subagent_registry.py::test_config_yaml_overrides_remain_explicitly_higher_priority`
  （覆盖优先级守护；单例快照/恢复路径无专测，待补）。
- **Owner**: subagents 域维护者
- **移除条件**: 上游 managed subagent 解析不再以配置单例副作用覆盖调用方
  覆盖时。

### PATCH-030: lane/测试环境加固捆绑（3d078973f）

- **文件**: `backend/packages/harness/deerflow/agents/middlewares/input_sanitization_middleware.py`、
  `backend/packages/harness/deerflow/client.py`、
  `backend/packages/harness/deerflow/extensions/gateway.py`、
  `backend/packages/harness/deerflow/skills/frontmatter.py`、
  `backend/packages/harness/deerflow/skills/projection.py`、
  `backend/packages/harness/deerflow/skills/storage/user_scoped_skill_storage.py`
- **修改**: 输入消毒 denylist 增补 `requested_skill`（与 PATCH-010 的
  `requested_skill_name` 联动防注入）；`client.py` 流关闭改经
  `contextvars.copy_context().run(_close_stream_generator, ...)`，同步关闭被
  委托的 agent 迭代器，使其 `finally` 在绑定 trace id 的上下文内执行；
  gateway 路由把 `/api/webhooks/github` 加入 CSRF 豁免；skills frontmatter
  允许 `description_zh`/`requires-internet`（企业捆绑技能）；projection 重建
  重试 2→5（吸收并发技能写入的短暂签名漂移）；user-scoped 存储把临时文件
  写入挪入投影锁内（避免并发写者把 temp 文件暴露给签名扫描）。
- **原因**: 引入提交 `3d078973f`（test: unify lanes and harden test
  environment）——统一测试 lane 时暴露的运行时正确性/健壮性修复一并合入。
- **测试**: `backend/tests/test_input_sanitization_middleware.py::test_denylist_covers_framework_authority_blocks`
  （denylist 反漂移守护）；`backend/tests/test_client.py::test_abandoned_embedded_stream_releases_execution_lease`；
  `backend/tests/test_github_webhooks.py`、`backend/tests/test_gateway_request_path.py`
  （CSRF 豁免）；`backend/tests/unit/skills/test_skills_validation.py`
  （`description_zh` 白名单）、`backend/tests/unit/gateway/test_resources_api.py::test_skill_description_prefers_description_zh`；
  `backend/tests/unit/skills/test_local_skill_storage_write.py::test_write_is_atomic_overwrite`；
  projection 重试上限与锁内临时文件路径无专测，待补。
- **Owner**: 平台工程（lane 加固）域维护者
- **移除条件**: 逐项评估——各修复被上游等价实现并采纳后按文件移除，
  本捆绑行不整体移除。

### PATCH-031: legacy 表 ORM 对齐 create_all

- **文件**: `backend/packages/harness/deerflow/persistence/models/legacy_tables.py`（新增）、
  `backend/packages/harness/deerflow/persistence/models/__init__.py`
- **修改**: 无活跃 ORM 实体的历史表 `workflow_runs`、`skill_applications` 以
  Core `sa.Table` 形式登记进 `Base.metadata` 并从 models 包导出，保证全新
  `Base.metadata.create_all` 数据库与统一 Alembic 链 base→head 升级产出同构
  （`persistence/bootstrap.py` 中同表的 create_all 块与 PATCH-006/015 行配套）。
- **原因**: 引入提交 `3d078973f`——统一链接管两棵历史迁移树后，create_all-only
  安装必须包含链内全部表，否则两套全新安装形态发散。
- **测试**: `backend/tests/integration/persistence/test_migration_schema.py`、
  `backend/tests/unit/persistence/test_migration_versions.py`、
  `backend/tests/integration/persistence/test_migrate_skill_applications.py`。
- **Owner**: persistence 域维护者
- **移除条件**: 与 PATCH-014/015 同前提——legacy 表由上游/扩展持久层契约
  承载，或不再有部署前置于 `20260908_unify_migration_chains` 的数据库时。

### PATCH-032: readability 纯 Python 回退容错

- **文件**: `backend/packages/harness/deerflow/utils/readability.py`
- **修改**: `simple_json_from_html_string(use_readability=False)` 失败
  （IndexError/TypeError/ValueError）时记告警并回退空文章，不再让整页抓取崩溃。
- **原因**: 引入提交 `7ae6b5907`（fix(testing): make backend and smoke lanes
  hermetic）——hermetic lane 中纯 Python readability 路径崩溃。
- **测试**: `backend/tests/test_readability.py::test_extract_article_falls_back_when_readability_js_fails`、
  `::test_extract_article_re_raises_unexpected_exception`。
- **Owner**: tools 域维护者
- **移除条件**: 上游 readability 封装提供等价回退并被采纳时。

### PATCH-033: DeerFlow CLAUDE.md guidance mirrors

- **文件**: 17 个 `backend/packages/harness/deerflow/**/CLAUDE.md` 文件；完整路径见下方结构化登记。
- **修改**: 每个 CLAUDE.md 都是同目录 AGENTS.md 的 UTF-8 字节副本，为读取 CLAUDE.md 的代理工具提供相同的作用域规则；AGENTS.md 是唯一编辑源。
- **原因**: 团队要求所有规则目录同时支持读取 AGENTS.md 与 CLAUDE.md，且两者内容保持一致。
- **上游替代方案**: 当前没有扩展或运行时接口适用于代理指导文件；若所有受支持工具直接读取 AGENTS.md，可移除这些副本。
- **测试**: `python scripts/sync_agent_guidance.py --check`（检查 24 组指导文件配对）。
- **Owner**: Agent tooling maintainers
- **移除条件**: 所有受支持代理工具直接读取 AGENTS.md，或仓库改用统一的新指导文件格式时移除。

## Enforcement

每次收敛提交前重跑对照命令并更新本台账；存在未登记差异即门禁失败。
属于 AgentPlatform 的运行时行为必须实现在 `backend/app/agentplatform/` 或
`backend/packages/agentplatform-extension/`，不得靠扩张本 fork 解决。

## Machine-readable registration

The registry below is part of this root ledger. Historical evidence remains visible
in the entries above. Any harness file changed in a new candidate requires a
`current` verification entry with the command and result for that candidate.
The checker reads rationale, alternative, impact scope, owner, removal trigger, and test references from the patch entries above (an omitted alternative is derived from the stated upstream removal condition); the registry below stores only paths and gate state. PATCH-033 explicitly adds 17 generated CLAUDE.md documents: the prior budget was 44 (43 code + 1 document), and the amended budget is 61 (43 code + 18 documents). The code-file budget remains 43. The checker reports code and documentation separately and enforces the total budget.

<!-- upstream-registry:start -->
```json
{
  "schema_version": 1,
  "upstream_baseline": "0f7d8709d3bbf0be26460b6277fbad9329302243",
  "file_budget": 61,
  "budget_basis": {
    "code_files": 43,
    "document_files": 18,
    "previous_code_files": 43,
    "previous_document_files": 1,
    "amendment": "The prior budget of 44 comprised 43 code files and config/AGENTS.md; PATCH-033 adds 17 generated CLAUDE.md documents. The code-file budget remains 43."
  },
  "patches": [
    {
      "id": "PATCH-001",
      "paths": [
        "backend/packages/harness/deerflow/community/ragflow/client.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-002",
      "paths": [
        "backend/packages/harness/deerflow/extensions/notify.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "current",
      "current_verification": {
        "command": "cd backend && UV_CACHE_DIR=/tmp/deer-flow-uv-cache PYTHONPATH=.:tests uv run --locked pytest -q tests/blocking_io/test_uploads_router.py tests/integration/api/test_devices_router.py tests/test_run_journal.py tests/unit/agentplatform/test_runtime_adapter.py tests/unit/device_control/test_broker.py tests/unit/device_control/test_secrets_gate.py tests/unit/gateway/test_local_runtime_context.py tests/unit/gateway/test_run_evidence.py tests/test_extension_task_lifecycle.py tests/test_tool_receipt_middleware.py tests/test_harness_boundary.py",
        "result": "passed; 173 tests, 4 warnings; format-only cleanup with identical Python ASTs; 2026-10-01"
      }
    },
    {
      "id": "PATCH-003",
      "paths": [
        "backend/packages/harness/deerflow/config/AGENTS.md"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-004",
      "paths": [
        "backend/packages/harness/deerflow/config/workflow_runtime_config.py",
        "backend/packages/harness/deerflow/config/app_config.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-005",
      "paths": [
        "backend/packages/harness/deerflow/agents/middlewares/tool_receipt_middleware.py",
        "backend/packages/harness/deerflow/tools/builtins/task_tool.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "current",
      "current_verification": {
        "command": "cd backend && UV_CACHE_DIR=/tmp/deer-flow-uv-cache PYTHONPATH=.:tests uv run --locked pytest -q tests/blocking_io/test_uploads_router.py tests/integration/api/test_devices_router.py tests/test_run_journal.py tests/unit/agentplatform/test_runtime_adapter.py tests/unit/device_control/test_broker.py tests/unit/device_control/test_secrets_gate.py tests/unit/gateway/test_local_runtime_context.py tests/unit/gateway/test_run_evidence.py tests/test_extension_task_lifecycle.py tests/test_tool_receipt_middleware.py tests/test_harness_boundary.py",
        "result": "passed; 173 tests, 4 warnings; format-only cleanup with identical Python ASTs; 2026-10-01"
      }
    },
    {
      "id": "PATCH-006",
      "paths": [
        "backend/packages/harness/deerflow/persistence/bootstrap.py",
        "backend/packages/harness/deerflow/persistence/migrations/env.py"
      ],
      "lifecycle_status": "closed",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-007",
      "paths": [
        "backend/packages/harness/deerflow/uploads/code_evidence.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-008",
      "paths": [
        "backend/packages/harness/deerflow/uploads/code_analysis.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-009",
      "paths": [
        "backend/packages/harness/deerflow/persistence/models/workflow_v2.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-010",
      "paths": [
        "backend/packages/harness/deerflow/agents/lead_agent/agent.py",
        "backend/packages/harness/deerflow/agents/lead_agent/prompt.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-011",
      "paths": [
        "backend/packages/harness/deerflow/persistence/engine.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-012",
      "paths": [
        "backend/packages/harness/deerflow/sandbox/local/local_sandbox_provider.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-013",
      "paths": [
        "backend/packages/harness/deerflow/runtime/runs/manager.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-014",
      "paths": [
        "backend/packages/harness/deerflow/persistence/migrations/versions/0001_baseline.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-015",
      "paths": [
        "backend/packages/harness/deerflow/persistence/migrations/_chain_meta.py",
        "backend/packages/harness/deerflow/persistence/migrations/alembic.ini",
        "backend/packages/harness/deerflow/persistence/migrations/versions/20260908_unify_migration_chains.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-016",
      "paths": [
        "backend/packages/harness/deerflow/sandbox/local/local_sandbox.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-017",
      "paths": [
        "backend/packages/harness/deerflow/sandbox/tools.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-018",
      "paths": [
        "backend/packages/harness/deerflow/sandbox/encoding.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-019",
      "paths": [
        "backend/packages/harness/deerflow/sandbox/search.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-020",
      "paths": [
        "backend/packages/harness/deerflow/agents/middlewares/tool_error_handling_middleware.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-021",
      "paths": [
        "backend/packages/harness/deerflow/community/aio_sandbox/aio_sandbox_provider.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-022",
      "paths": [
        "backend/packages/harness/deerflow/community/ragflow/tools.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-023",
      "paths": [
        "backend/packages/harness/deerflow/config/app_config.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-024",
      "paths": [
        "backend/packages/harness/deerflow/extensions/__init__.py",
        "backend/packages/harness/deerflow/extensions/registry.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-025",
      "paths": [
        "backend/packages/harness/deerflow/models/openai_codex_provider.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-026",
      "paths": [
        "backend/packages/harness/deerflow/runtime/journal.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "current",
      "current_verification": {
        "command": "cd backend && UV_CACHE_DIR=/tmp/deer-flow-uv-cache PYTHONPATH=.:tests uv run --locked pytest -q tests/blocking_io/test_uploads_router.py tests/integration/api/test_devices_router.py tests/test_run_journal.py tests/unit/agentplatform/test_runtime_adapter.py tests/unit/device_control/test_broker.py tests/unit/device_control/test_secrets_gate.py tests/unit/gateway/test_local_runtime_context.py tests/unit/gateway/test_run_evidence.py tests/test_extension_task_lifecycle.py tests/test_tool_receipt_middleware.py tests/test_harness_boundary.py",
        "result": "passed; 173 tests, 4 warnings; format-only cleanup with identical Python ASTs; 2026-10-01"
      }
    },
    {
      "id": "PATCH-027",
      "paths": [
        "backend/packages/harness/deerflow/runtime/runs/worker.py",
        "backend/packages/harness/deerflow/runtime/runs/manager.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-028",
      "paths": [
        "backend/packages/harness/deerflow/subagents/executor.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-029",
      "paths": [
        "backend/packages/harness/deerflow/subagents/registry.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-030",
      "paths": [
        "backend/packages/harness/deerflow/agents/middlewares/input_sanitization_middleware.py",
        "backend/packages/harness/deerflow/client.py",
        "backend/packages/harness/deerflow/extensions/gateway.py",
        "backend/packages/harness/deerflow/skills/frontmatter.py",
        "backend/packages/harness/deerflow/skills/projection.py",
        "backend/packages/harness/deerflow/skills/storage/user_scoped_skill_storage.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-031",
      "paths": [
        "backend/packages/harness/deerflow/persistence/models/legacy_tables.py",
        "backend/packages/harness/deerflow/persistence/models/__init__.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-032",
      "paths": [
        "backend/packages/harness/deerflow/utils/readability.py"
      ],
      "lifecycle_status": "open",
      "verification_status": "historical"
    },
    {
      "id": "PATCH-033",
      "paths": [
        "backend/packages/harness/deerflow/CLAUDE.md",
        "backend/packages/harness/deerflow/agents/CLAUDE.md",
        "backend/packages/harness/deerflow/agents/memory/CLAUDE.md",
        "backend/packages/harness/deerflow/agents/middlewares/CLAUDE.md",
        "backend/packages/harness/deerflow/config/CLAUDE.md",
        "backend/packages/harness/deerflow/extensions/CLAUDE.md",
        "backend/packages/harness/deerflow/mcp/CLAUDE.md",
        "backend/packages/harness/deerflow/models/CLAUDE.md",
        "backend/packages/harness/deerflow/persistence/migrations/CLAUDE.md",
        "backend/packages/harness/deerflow/reflection/CLAUDE.md",
        "backend/packages/harness/deerflow/runtime/CLAUDE.md",
        "backend/packages/harness/deerflow/sandbox/CLAUDE.md",
        "backend/packages/harness/deerflow/skills/CLAUDE.md",
        "backend/packages/harness/deerflow/subagents/CLAUDE.md",
        "backend/packages/harness/deerflow/tools/CLAUDE.md",
        "backend/packages/harness/deerflow/tracing/CLAUDE.md",
        "backend/packages/harness/deerflow/tui/CLAUDE.md"
      ],
      "lifecycle_status": "open",
      "verification_status": "current",
      "current_verification": {
        "command": "python scripts/sync_agent_guidance.py --check",
        "result": "passed; 24 guidance pairs checked, including all 17 DeerFlow harness mirrors"
      }
    }
  ]
}
```
<!-- upstream-registry:end -->
