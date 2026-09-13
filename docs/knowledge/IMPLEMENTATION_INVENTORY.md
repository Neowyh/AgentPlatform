# Implementation Inventory — 知识域现状勘察（M2 Ticket 01）

> audience: developers, security reviewers<br>
> status: current<br>
> owner: engineering maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/knowledge/IMPLEMENTATION_INVENTORY.md`

本文是 M2（KnowledgeBase Resource Governance）的书面勘察底座，对应知识方案 §58–59（Phase 0）与总方案 §7 M2 任务卡。全部结论以当前分支 `feature/m2-kb-resource-governance`（基于 develop，无额外提交）代码为准，标注文件与符号。02（KB 第四类 Resource）、03（LIVE/PINNED 依赖）、04（Effective Scope + 运行时适配）三张实施票以本文为对接基础，不再重新勘察。

来源文档：`architecture/AgentPlatform_知识库能力建设实施方案_CodingAgent版_2026-09-04.md`（下称"知识方案"）、`architecture/AgentPlatform_后续工作总方案_2026-09-08.md`（下称"总方案"）、`architecture/AgentPlatform 总体架构与模块边界基线.md`（下称"基线"）、`docs/decisions/2026-09-08-knowledge-dual-source-of-truth.md`（下称"双层真源 ADR"）。

---

## 1. Resource type 枚举与 API 形态

### 1.1 枚举与常量

- `ResourceType(StrEnum)`：`backend/app/agentplatform/resource_models.py:18`，现有成员 `SKILL="skill"` / `AGENT="agent"` / `WORKFLOW="workflow"`。**无 knowledge 成员**。
- 同文件伴随枚举：`ResourceLifecycleStatus`（:24，`active/archived/suspended`）、`ResourceStorageKind`（:30，`filesystem/database`）、`ResourceProvenance`（:35，`user/bundled`）。
- DB 层 CHECK：ORM `ck_resources_type`（`resource_models.py:90`，`type IN ('skill','agent','workflow')`）+ 迁移 `20260814_resource_catalog_v2.py` 中同名 DDL。**新增枚举值必须同时改 ORM 与迁移**（见 SCHEMA_PLAN）。
- 硬编码类型清单（02 号票需逐一扩展的触点）：
  - 依赖类型矩阵 `_assert_dependency_type`：`resources/service.py:1067-1075`（`skill`→无依赖、`agent`→skill、`workflow`→agent+skill）。
  - 存储规则与目录映射：`resources/service.py:147-157`（workflow⇒database，skill/agent⇒filesystem；`storage_key` 目录 `{"skill": "skills", ...}`）。
  - API 请求 schema 正则 `^(skill|agent|workflow)$`：`backend/app/gateway/routers/resources.py:160`（create）、`:501`（list query）。
  - bundled manifest 类型白名单：`resources/bundled.py:83`（`item.type not in {"skill","agent","workflow"}` 拒绝）。

### 1.2 Canonical API

- 路由：`backend/app/gateway/routers/resources.py`，`router = APIRouter(prefix="/api/resources", tags=["resources"])`（:66），在 `backend/app/gateway/app.py:23-47` 注册。旧名称路由（`/api/agents`、`/api/skills`、`/api/workflows`）已在 Resource Governance V2 硬切换中删除，返回 404（见 `docs/governance/resource-governance-v2-cutover.md`）。
- 主要端点：`GET /`（list_resources :498）、`POST /`（create :774）、`GET /{resource_id}`（:823）、`GET /{resource_id}/published`（:846）、`GET /{resource_id}/export`（:913）、类型专属草稿端点 `PUT /{resource_id}/{workflow|agent|skill|archive}-draft`（:951/:993/:1046/:1088）、`POST /{resource_id}/publish`（:1127）、`PUT /{resource_id}/dependencies`（:1163）、`POST /fork`（:1179）、visibility 申请/审批（:1205/:1251/:1750/:1791）、生命周期 `POST /{archive|suspend|restore|transfer}`（:1282/:1300/:1319/:1338）、favorite（:1366/:1377）、workflow-run 子资源（:1388–1747）。**无 DELETE 端点**——目录内删除语义为 archive/suspend。
- 请求/响应 schema（Pydantic，定义在 `resources.py`）：`ResourceCreateRequest`（:159）、`DependencyRequest`（:187）、`PublishRequest`（:182）等；响应为 dict payload，资源主体 `_resource_payload`（:348）：`id, type, slug, display_name, owner_id, visibility, scope_department_id, lifecycle_status, latest_version, draft_revision, storage_kind, provenance, system_owned, authz_revision, can_modify, is_favorited, created_at, updated_at`。
- 服务层：`ResourceService`（`backend/app/agentplatform/resources/service.py:106`，"Single authorization and lifecycle boundary"）。权限枚举 `ResourceAction`（:30）：`READ/USE/WRITE/SUSPEND/TRANSFER/PURGE/APPROVE`（对应 `resources:*` 权限串）；`ResourceActor`（:40）由路由 `_resource_actor(user)`（`resources.py:296`）从 `UserRole` 构造。
- 错误映射：`_translate_resource_errors`（:313）→ 404/403/409/400；`VisibilityClosureError` → 409 `{"code": "visibility_closure_violation", violations: [...]}`。
- 发布事务边界：`ResourcePublisher`（`resources/publisher.py:40`，filesystem/database 两套 draft→publish→rollback）；存储 `ResourceStorage`（`resources/storage.py:87`，版本目录 `{type}s/{resource_id}/versions/{n}`，`create_run_skill_view` :311 构建每 Run 冻结视图）；发布策略 `resources/publish_policy.py`（skill 发布扫描门禁）。

### 1.3 治理语义（owner / department / visibility / lifecycle / audit）

- `resources` 表（`resource_models.py:67-101`）：`owner_id`（FK users_ext，RESTRICT）、`visibility`（`private|department|public`，CHECK :91）、`scope_department_id`（FK departments，SET NULL）、`lifecycle_status`（CHECK :92）、`latest_version`/`draft_revision`、`storage_kind`/`storage_key`、`provenance`、`system_owned`、`authz_revision`（每次治理变更自增）、唯一 `(type, owner_id, slug)`。
- 可见性查询：`ResourceService._visible_query`（`service.py:117-127`）——super_admin 全量；否则 `owner_id == actor.user_id OR visibility == 'public' OR (visibility == 'department' AND scope_department_id == actor.department_id)`。
- 可见性变更：降级直改（预演影响 `visibility_reduction_impact` :387，可级联修复 `_repair_cascade_dependents` :482 并通知 `_notify_dependent_owners` :274）；升级需审批（`change_visibility` :318 抛 `ResourceApprovalRequired`；申请/审批走 `visibility_applications` 表 `backend/app/agentplatform/visibility_models.py`，乐观锁 `version`，stale 检测用 `requested_version/hash`）。
- 生命周期：`archive`（owner，:711）、`suspend`（super_admin，:726，同时取消引用该资源的 queued/paused workflow run `_cancel_snapshotted_workflow_runs` :746）、`restore`（super_admin，:779）、`transfer_owner`（super_admin，:793，强制降为 private）、owner/部门删除治理（:841/:908）。
- 审计：`backend/app/gateway/audit.py record_audit` 写 `audit_logs`（`backend/app/agentplatform/audit_model.py`）；资源路由动作 `resource_created/imported/published/forked/visibility_requested/visibility_changed/archived/suspended/restored/transferred`；Run 准备拒绝记录 `run_preparation_rejected`（`canonical_agent_run_preparation.py:164`）。

## 2. resource_dependencies 与 run_resource_snapshots 现有 schema

### 2.1 resource_dependencies

- ORM：`ResourceDependency`（`resource_models.py:127-139`）——`id`(String36 PK)、`source_resource_id`(FK resources CASCADE)、`target_resource_id`(FK resources RESTRICT)、`created_at`；约束 `uq_resource_dependencies_edge`（source+target 唯一）、`ck_resource_dependencies_not_self`、`ix_resource_dependencies_target`。**当前无 mode/revision/required/purpose 字段**（03 号票新增）。
- 校验逻辑（均在 `resources/service.py`）：
  - 类型矩阵：`_assert_dependency_type`（:1067，见 §1.1）。
  - 可见性闭合规则：`_visibility_closure_violation`（:1077）——`public` 源只能依赖 `public` 目标；`department` 源可依赖 `public` 或同部门 `department` 目标。`_assert_visibility_closure`（:1133）抛 `VisibilityClosureError`。
  - `replace_dependencies`（:1184）：拒绝重复边、自依赖、不可见目标（`_get_visible`）、类型矩阵违规、可见性闭合违规；整组 delete-then-insert 替换。
  - 环检测**不在保存时**：`resolve_dependency_closure`（:1213）在解析时用 visiting 集合检出环 → `ResourceConflict("Resource dependency cycle includes ...")`（:1221），同时拒绝未发布依赖（`latest_version < 1`，:1226）。
  - bundled seed 自带无环检查：`resources/bundled.py:197 _assert_acyclic`。
  - 发布路径不做依赖校验；校验发生在依赖保存、可见性扩大（`request_visibility` :590）与审批（`review_visibility_application` :684）时。
- 依赖图谱：无专用 GET 端点；最接近的是 `GET /{resource_id}/visibility-impact`（`resources.py:1235`，反向 BFS 模拟级联）。

### 2.2 run_resource_snapshots（Run 冻结）

- ORM：`RunResourceSnapshot`（`resource_models.py:142-161`）——`id`(UUID PK)、`run_id`(String64，无 FK)、`root_resource_id`/`resource_id`(FK resources RESTRICT)、`version`(≥1)、`content_hash`(String64)、`authz_revision`(≥1)、`selection_role`(String16，CHECK `root|resolved|preferred`，来自迁移 `20260828_run_snapshot_selection_role`)、`resolved_at`；唯一 `(run_id, resource_id)`。
- 写入路径 `ResourceService.create_run_snapshot`（`service.py:1250`）：幂等（同 run 重复 → `ResourceConflict` :1258）；接受预算解析好的 closure；`selected_resource_id`（偏好 Skill）必须属于 closure（:1265）；行按 `selection_role` root/preferred/resolved 落库。
  - Agent Run：`backend/app/gateway/canonical_agent_run_preparation.py:33 prepare_canonical_agent_run` —— 构建 USE-only actor、解析 closure 一次（:110）、检查偏好 Skill ∈ closure（`SelectedSkillOutsideClosure` :18）、写快照（:126）、加载冻结定义并构建每 Run skill 视图（`storage.create_run_skill_view` :137）。
  - Workflow Run：`backend/app/agentplatform/workflows/v2/store.py:292 create_canonical_run` —— 在插入 `WorkflowV2RunRow`（queued）**之前**写快照（:310），`definition_version = root_snapshot.version`，run metadata 带 `run_evidence`（:374）；暂停恢复变体 `create_canonical_paused_run`（:393，快照 :418）。fault-zeroing kernel 同样走此路径（`backend/app/agentplatform/fault_zeroing/kernel.py:240`）。
- 运行时冻结加载：`backend/app/agentplatform/resources/runtime.py` `CanonicalResourceLoader` —— `_frozen_version`（:107）按 `(run_id, resource_id)` 查快照，缺失 fail-closed，拒绝 suspended 资源（:127），校验 `content_hash`（:139）；`load_agent`(:143)/`load_workflow`(:165，额外校验 JSON hash)/`load_skill`(:176)；`load_agent_skill_definitions`（:202）**UUID 优先、slug 次之**（`_match = by_id.get(name) or by_slug.get(name)`，:226-230），未解析名 → `ResourceRuntimeError`（:236）。worker 侧消费见 `backend/app/workflow_worker.py:82-183`。

## 3. AuthorizationProvider 集成点

- 协议：`backend/packages/harness/deerflow/authz/provider.py:86` `AuthorizationProvider(Protocol)`（`authorize`/`aauthorize`/`filter_resources`；数据类 `Principal` :30、`AuthzRequest` :50（resource/action/target 自由串）、`AuthzDecision` :76）。
- 内置实现：`deerflow/authz/rbac.py:69 RbacAuthorizationProvider`（角色→资源类型→allow/deny 策略编译，deny 优先，未知角色 fail-closed；`_RESOURCE_POLICY_KEYS` :26 = `tool/model/skill/sandbox/mcp_server/route`）。解析：`deerflow/authz/runtime.py`（`resolve_authorization_provider` 等），配置 `deerflow/config/authorization_config.py`（`enabled/provider.use/fail_closed/default_role`）。
- Gateway 集成：`backend/app/gateway/authz.py` —— 路由权限中间件 `_get_cached_route_provider`(:189)/`resolve_route_permissions`(:208) 覆盖所有 `Permissions.*`；沙箱 `authorize_sandbox_for_request`(:277)。装配期工具过滤：`deerflow/authz/enforcement.py`（`filter_tools_by_authorization`）、`tool_filter.py`；沙箱 `sandbox_authz.py`。
- **关键现状**：canonical `ResourceService` **不经** AuthorizationProvider，它有独立的 `ResourceAction`/`ResourceActor` 边界（§1.2）；`AuthzRequest.resource` 取值域当前不含 knowledge。02/04 号票需要决策 caller 知识权限的求值点：在 ResourceService 边界内（可见性语义已存在）与/或经 `filter_resources` 扩展 `knowledge_base` 类型（知识方案 §80 的两层：Tool 权限 `knowledge:search` ≠ KB 数据 ACL，两层都要过）。
- Local Authorization veto（另一套，勿混淆）：`backend/packages/agentplatform-extension/agentplatform_extension/local_runtime/authorization.py:9 LocalAuthorization`（能力交集，Local DENY 优先，基线不变量 19/20）——仅设备/本地运行时路径，与 server KB scope 无关，但 04 号票越权矩阵中的 Sub-Agent 场景需保证不与其互斥语义冲突。

## 4. Agent assembly 与 Run 装配位置

- 工具装配：`backend/packages/harness/deerflow/tools/tools.py get_available_tools`（:59-202）按 config `tools:` 列表 `use:` 路径反射装载（`deerflow.reflection.resolve_variable`）；企业接缝 `backend/app/agentplatform/tool_adapter.py`（re-export + "enterprise visibility and authorization after assembly"）。
- Agent 冻结输入：`backend/app/agentplatform/runtime_adapter.py build_canonical_agent_factory` → `FrozenAgentInputs`（含 `runner_tool_groups`）——04 号票注入 run-scoped allowlist 的装配接缝。
- Run 准备：`backend/app/gateway/run_preparation.py`（`AuthorizationContext`、`RunEvidenceBinding` :211-233 写入 `run_metadata["run_evidence"]`）；canonical agent run 见 §2.2。
- Agent 依赖声明数据形态：`CanonicalAgentDefinition`（`runtime.py:29`），`definition.config.skills` 过滤 Skill 依赖目标（`load_agent_skill_definitions` :202-236）——KB 依赖将按同一模式扩展（03 号票）。

## 5. 上游 knowledge_search / RAGFlow 现状

### 5.1 Tool

- 定义：`backend/packages/harness/deerflow/community/ragflow/tools.py` —— `knowledge_search_tool = StructuredTool.from_function(coroutine=_knowledge_search_entrypoint, name="knowledge_search", ...)`（:395-400）。**入参仅 `query: str`**（`test_agent_exposes_only_query_on_single_search_tool`，`backend/tests/test_ragflow_tools.py:726-732`）。
- 主流程 `knowledge_search(query)`（:344-378）：读取 settings → 构建 client → `_resolve_datasets`（:211-240）→ `_group_searchable_datasets`（:243-249，按 embedding model 分组、跳过 `chunk_count == 0`）→ `_retrieve_dataset_groups`（:315-341，`asyncio.Semaphore(4)` 并行）→ `_merge_group_results`（:268-312，跨组 rank 交错）→ `format_retrieval_result` → API key 脱敏 → 返回字符串。
- 注册：config `tools:` 列表 `use: deerflow.community.ragflow.tools:knowledge_search_tool`；配置取值 `get_app_config().get_tool_config("knowledge_search")`（`deerflow/config/app_config.py:621`）；`ToolConfig` 允许任意扩展键（`deerflow/config/tool_config.py:11-20`，`extra="allow"`），RAGFlow 专属字段落在 `model_extra` 由 `_RAGFlowRetrievalSettings`（tools.py:36-75）校验。

### 5.2 RAGFlow client

- `backend/packages/harness/deerflow/community/ragflow/client.py` `RAGFlowClient`（:33-187）：无状态异步 httpx 封装；`GET /api/v1/datasets`（`list_datasets` :112-158，分页 page size 100、上限 100 页；绑定 ID 用 `ids=` 过滤，**不用**单数 `id` 过滤，注释 :119-124）与 `POST /api/v1/retrieval`（`retrieve` :160-187：question/dataset_ids/page_size/similarity_threshold/vector_similarity_weight/top_k）。无写端点（上传/解析未实现——M3 范围）。
- 错误体系：`RAGFlowError` → `RAGFlowAPIError`/`RAGFlowConnectionError`/`RAGFlowProtocolError`（:13-30）；所有错误串经 `_redact`（:54-58）脱敏 API key。
- **无任何 NO_RELEVANT_EVIDENCE / KNOWLEDGE_ACCESS_DENIED 错误码体系**：空结果返回普通字符串 `"No relevant content found."`（`formatting.py:54`、`tools.py:25 _NO_RELEVANT_CONTENT`）。04 号票的 `KNOWLEDGE_ACCESS_DENIED` 需要新建错误语义（在扩展包/企业层，避免 harness diff）。

### 5.3 配置字段与 dataset allowlist

- config.example.yaml：`tool_groups` 含 `- name: knowledge`（:718）；`knowledge_search` 工具项**整体注释**（:726-748），字段：`name/group/use/base_url/api_key: $RAGFLOW_API_KEY/datasets/timeout: 30/page_size: 8/similarity_threshold: 0.2/vector_similarity_weight: 0.3/top_k: 256/max_chars_per_chunk: 800/max_total_chars: 8000`。启用值只存在于部署侧未跟踪 `config.yaml`（gitignored，`.gitignore:36`）。
- `knowledge_search.datasets`（部署级静态 allowlist，M1 已验证）：`list[str]`，上限 100（tools.py:41）；`_normalize_dataset_ids`（:52-68）去重、每项 1-256 字符、**空列表直接 ValueError**（fail-closed）。执行点在每次工具调用的 `_resolve_datasets`（:211-240）：逐个绑定 ID 解析，任一不可解析则**整次搜索中止**（无部分检索）；模型侧错误只报序号 `_missing_dataset_error`（:198-199：`Error: The {ordinal} entry of knowledge_search.datasets was not found or is inaccessible; check config.yaml.`），真实 ID 仅管理员日志可见（`_log_missing_dataset` :202-208，测试 `test_missing_bound_dataset_error_does_not_expose_configured_id`）。省略 `datasets` = 搜索 API key 可见的全部 dataset。
- 该 allowlist 就是 04 号票"Deployment Allowlist"最外层交集的现成机制；扩展包将把 run-scoped 资源 scope 注入为内层交集。

### 5.4 M1/Gate-1 对 `community/ragflow/tools.py` 的改动（勘误）

- 该文件历史仅两个提交：`431892e1`（feat(knowledge): add read-only RAGFlow retrieval #4955，2026-08-25，引入 client.py/formatting.py/tools.py 全套 + 测试 + `backend/docs/CONFIGURATION.md`）与 `67c991c9`（fix(ragflow): keep the RAGFlow endpoint out of model-facing connection errors，2026-09-09，连接错误不再携带 base_url，仅管理员日志；回归测试 `test_ragflow_tools.py:574-600`）。
- **勘误**：ticket 01 原文写"M7 对 community/ragflow/tools.py 的改动"——总方案中 M7 是 Device Control Plane + Secure WSS，与知识线无关；上述改动属于知识线 Gate 1（M1）的验收加固（见 `docs/testing/knowledge-gate1-acceptance-report.md`）。02/04 号票对接对象即上述两个提交确立的行为。

## 6. Tool receipt 行为

- Schema：`backend/packages/harness/deerflow/agents/middlewares/tool_receipt.py` `ToolReceipt` TypedDict（:93-101）——`id`（展示序号 r1..rN）、`tool_call_id`、`tool_name`、`status`（`success|error|partial_success`）、`args_sha256`、`output_sha256`（截断 16 hex）、`output_bytes`、`created_at`。**无时长、无结果条数**。
- 生成：`ToolReceiptMiddleware`（`agents/middlewares/tool_receipt_middleware.py:45`，最外层 `wrap_tool_call/awrap_tool_call` :107-121）；runtime 持有 key 防伪覆盖（:67-71）；盖章后转发 `agentplatform_extension.evidence.record_tool_receipt`（:76-81）。落点：`ToolMessage.additional_kwargs` → LangGraph checkpoint（`GET /api/threads/{tid}/state` 可读）。
- 引用体系：`[rN]` / `[rN tool_name]` 引用格式（`CITATION_RE` :65、`parse_citations` :73），账本渲染 `render_tool_receipts_with_snapshot`（:214，2000 字符预算）；校验中间件 `agents/middlewares/receipt_verification.py`。
- knowledge_search 实测样例（Gate 1 验收报告 §1）：`{"tool_call_id": "call_...", "tool_name": "knowledge_search", "status": "success", "args_sha256": "ad2ad1b7b1e697e9", "output_sha256": "077099b7c8313934", "output_bytes": 725, "created_at": "2026-09-08T15:32:02.166583+00:00"}`。
- 局限（对 04/M5）：receipt 是**工具级**哈希账本，不含 KB UUID/revision/query 原文/chunk 定位——知识方案 §98 要求的 Retrieval Receipt 关联（run_id/KB/revision/query hash/document/chunk/scores/tool receipt）需要新的 receipt 结构（扩展包 `knowledge/receipts.py` + 存储见 SCHEMA_PLAN 开放决策）。

## 7. Evidence / citation 现状

### 7.1 后端

- Run Evidence Envelope：`RunEvidenceEnvelope`（`backend/packages/extension-api/deerflow_extension_api/contracts.py:71-89`：run_id/thread_id/trace_id/outcome/resource_snapshots/runtime_assembly_fingerprint/authorization_context/policy_revision/tool_receipts/subagent_verification/artifact_receipts）；`EvidenceLifecycleContributor`（`agentplatform_extension/evidence.py:160-218`）在 task start/stop 写入扩展 task_store；运行期经 ContextVar 绑定 `bind_run_evidence`（:113-131）追加 receipt。
- 快照投影：gateway `run_preparation.py:211-233` 由冻结选择快照 + caller 身份构建 caller-safe 投影写 `run_metadata["run_evidence"]`；workflow 侧 `workflows/v2/store.py:29-75/:374`、worker `workflow_worker.py:52-78` 重新绑定。`resource_snapshots` 元素为 `ResourceSnapshotRef`（resource_id/version/content_hash/selection_role，`evidence.py:19`）。
- **无专用 SSE evidence 事件**；evidence 经三通道：消息流 ToolMessage additional_kwargs（thread state）、Run metadata `run_evidence`、扩展 task_store envelope。
- 检索结果文本形态：`community/ragflow/formatting.py format_retrieval_result`（:34-96）输出 `[1] {dataset_name} / {document_name} (score)\n{content}` + `Matched documents:` 汇总脚注；dataset ID 映射为名称，绝不外发。

### 7.2 前端

- 唯一证据面是 markdown 内嵌引用：`frontend/src/core/citations/sources.ts` `extractCitationSources(markdown)` 解析 `[citation: Title](https://…)`（先遮蔽代码块）；`CitationSource { id, title, url, domain, count, occurrences }`。渲染：`frontend/src/components/workspace/citations/citation-link.tsx`（行内 hover 卡）与 `citation-sources-panel.tsx`（折叠列表），挂载于 `message-list-item.tsx`（≈:461/:589）、artifact 预览、`subtask-card.tsx`。**无结构化 evidence payload，无 KB 来源形态**——KB 证据需扩展 `CitationSource` 或新增结构化通道（M5+）。
- KB 前端仅存静态 stub：`frontend/src/core/library/index.ts`（`Document`/`KnowledgeBase` 类型 + 固定 fixture，注释 TODO 接 RAGFlow API）；`LibraryGallery`（documents/knowledge-bases 两 tab，`app/workspace/library/page.tsx`）；i18n `t.library.*`。
- 管理面：`admin/resources/page.tsx` 为只读目录（类型/可见性/生命周期过滤 + archive/suspend/restore 动作；类型过滤硬编码 `agent|tool|skill|workflow`，`TYPE_STYLES` 需为 `knowledge_base` 增补）；**依赖声明 UI 全站不存在**（03 号票最小可用落点：Agent 编辑页 `capabilities/experts/[agent_name]/edit/page.tsx` 的 Skills checkbox 区旁仿建，Workflow 编辑页为 YAML schema 字段 + `core/workflows/validate.ts` 校验规则）。

## 8. M1 smoke 交接物盘点（02/04 号票对接基础）

- **compose profile**：`docker/docker-compose-knowledge-dev.yaml`（overlay 到 `docker/docker-compose-dev.yaml` 网络 `deer-flow-dev`）：ragflow-mysql/minio/redis(valkey)/es01/ragflow（`infiniflow/ragflow:v0.27.1`，API 9380、UI 8080，healthcheck `/api/v1/system/healthz`）+ 可选 `--profile tei` 嵌入服务；gateway 经 `http://ragflow:9380` 访问；宿主端口默认绑 127.0.0.1（`RAGFLOW_BIND_HOST` 可改）；镜像/端口/口令全部 `${VAR:-default}`，env 文件 `docker/ragflow/.env`（未跟踪，模板 `.env.example`）。
- **bootstrap**：`docker/ragflow/bootstrap.sh` 幂等执行——注册 smoke 租户（`smoke-b05@test.local`，口令 RSA 加密）→ 登录 → 注册 `OpenAI-API-Compatible` provider → 确保 TEI → 设租户默认 embedding → find-or-create dataset **`ideer-knowledge-smoke`** → 上传 `dev-log/knowledge-smoke-docs` 文档 → 触发解析并轮询 → 铸造 API token（`POST /api/v1/system/tokens`）。**产物仅 stdout**："Wire these into the iDeer host" 块给出 `RAGFLOW_API_KEY=<token>`（进 `.env`）、`knowledge_search.datasets: [<dataset_id>]` 与 `knowledge_search.base_url`（进未跟踪 `config.yaml`）；无自动接线，操作员手工复制。02 号票"首个绑定对象即 M1 smoke dataset"就指 `ideer-knowledge-smoke` 的 dataset ID。
- **key 流向**：`RAGFLOW_API_KEY` 经 config 环境变量插值（`config.example.yaml:739`，文件头 :13 注明所有字段支持环境变量）进入工具配置 `api_key`（SecretStr）；代码不直接读 env（`tools.py:112-116` 缺失时 warn-once + 错误串）。
- **Gate 1 验收记录**：`docs/testing/knowledge-gate1-acceptance-report.md`（backend-standard lane + 手工离线 smoke：真实 RAGFlow 栈 + 本地 llama.cpp OpenAI 兼容 stand-in；receipt 样例与脱敏场景为事实上的 LLM-lane 记录）。backend-standard 参考：11973 passed / 19 skipped（2026-09-10）。

## 9. ORM / Alembic 约定与迁移方式

- 模型位置：控制面模型在 `backend/app/agentplatform/*.py`（`resource_models.py`、`visibility_models.py`、`rbac_models.py`、`audit_model.py`），共用基类 `deerflow.persistence.base.Base`（`backend/packages/harness/deerflow/persistence/base.py`）；运行时模型在 `deerflow/persistence/models/`。
- 风格：SQLAlchemy 2.0 `Mapped[...] = mapped_column(...)`；String UUID 主键；显式命名约束 `ck_*`/`uq_*`/`ix_*`；FK 带 ondelete 语义（父目录 RESTRICT/CASCADE 分明，参照 §2.1）。
- **统一迁移链**：单 alembic script dir 双版本目录——`backend/packages/harness/deerflow/persistence/migrations/alembic.ini:8` `version_locations = %(here)s/versions %(here)s/../../../../../app/agentplatform/persistence/migrations/versions`；merge revision `20260908_unify_migration_chains`；**当前 head `20260909_device_control_plane`**（`backend/app/agentplatform/persistence/migrations/versions/20260909_device_control_plane.py`）。env.py 共享 Base.metadata、排除 LangGraph 表与扩展表前缀（`_env_filters.include_object`、`register_configured_extension_table_prefixes`）；链状态桥接 `deerflow/persistence/migrations/_chain_meta.py`。
- 新增方式：在 `backend/app/agentplatform/persistence/migrations/versions/` 新建日期前缀命名 revision（如 `20260910_knowledge_bases.py`），`down_revision = "20260909_device_control_plane"`；CHECK/UNIQUE 约束在 ORM 与迁移 DDL 双写（参照 `20260814_resource_catalog_v2`）。守卫测试：`backend/tests/unit/persistence/test_migration_versions.py`（单 head）、`test_persistence_migrations_env.py`、`tests/integration/persistence/test_migration_schema.py`。gateway 启动自动 upgrade（`deerflow/persistence/bootstrap.py bootstrap_schema` ← `engine.py:196-233`）。
- 资源相关历史 revision：`20260814_resource_catalog_v2`（建 resources/resource_versions/resource_dependencies/run_resource_snapshots/resource_drafts/resource_favorites/resource_notifications）、`20260817_split_bundled_provenance`（加 provenance、删 storage_kind='bundled' 值）、`20260828_run_snapshot_selection_role`。

## 10. 离线部署依赖

- bundled 目录：`bundled-resources.json`（仓库根，schema_version 1，73 项：57 skills / 15 agents / 1 workflow；`{id: 稳定 UUID, type, slug, display_name, visibility: "public", source}`）；源文件 `resources/skills|agents|workflows/`。
- 种子实现：`backend/app/agentplatform/resources/bundled.py` —— `load_bundled_manifest`(:51，校验 UUID/类型白名单 :83/可见性/路径逃逸/唯一性)、`seed_bundled_resources`(:216，stable UUID 建行、provenance=bundled、发布 trusted 版本、`_prepare_agent` :131 / `_prepare_workflow` :172 把 identity 引用改写为资源 UUID)、bundled 可见性闭合（`_allows_dependency` :112 public→public）、无环（:197）、`conflict_policy keep|override`（:337）。
- 启动钩子：`backend/app/gateway/app.py:259 _seed_bundled_resources`（lifespan :461，`_ensure_admin_user` 之后，owner 取首个 active super_admin，`conflict_policy="keep"`）；admin setup 后再触发（`routers/auth.py:890-892`）；启动对账 `app.py:392 _reconcile_canonical_resource_storage`（指针损坏 fail-fast，`resources/reconciliation.py:18`）。CLI：`backend/scripts/seed_bundled_resources.py`。
- 内网 compose：`docker/docker-compose.intranet.yaml` 已为 gateway 与 workflow-worker 挂载 `docs/` 与 `workflows/`（bundled agent/workflow 源在容器内必需；见 cutover 手册 §6 执行记录）。02 号票若引入 bundled KB 模板需同步 manifest 白名单与内网挂载评估（知识方案 §76 建议仅 demo/template，M2 不做）。

## 11. 与基线不变量 3/5/6 的冲突确认

| 不变量 | 内容 | 现状核对 | 结论 |
| --- | --- | --- | --- |
| 3 | KnowledgeBase 是第四类一等 Resource | `ResourceType` 无 KB 成员（§1.1）；治理语义/快照/依赖/审计均为类型无关通用机制（§1–2），02 号票按枚举扩展即可，无需新平行体系 | **无冲突**，纯扩展点 |
| 5 | Resource API 是企业 Resource Identity 真源 | canonical `/api/resources` 是唯一目录 API；旧名称路由已 404；知识方案 §74 明确禁止另建 `/api/knowledge-bases` 第二真源，convenience route 必须委托 ResourceService | **无冲突**；02 号票红线：不出现第二身份 API |
| 6 | RAG Provider ID 不得成为企业 KnowledgeBase ID | dataset ID 当前仅存在于部署侧配置 `knowledge_search.datasets` 与管理员日志；模型面错误只报序号、检索文本只含 dataset 名称（§5.3/§7.1，有测试锁定）；双层真源 ADR 规定 `provider_type` + opaque `provider_dataset_id` 映射；SCHEMA_PLAN 中 KB 主键 = `resources.id` | **无冲突**；04 号票红线：模型不可见 dataset ID、不可传 raw dataset ID |

## 12. 02/03/04 号票对接点速查

| 票 | 直接触点（详见上文章节） |
| --- | --- |
| 02 KB 第四类 Resource | `ResourceType` + 双写 CHECK（§1.1/§9）；`create_resource` 存储规则与 `storage_key` 目录（KB⇒DATABASE，声明式 Content，知识方案 §75）；`/api/resources` create + 知识子资源路由骨架委托 ResourceService（§1.2）；dataset 手动绑定 = opaque `provider_dataset_id`（§5.3，连接配置沿用 `knowledge_search` 组，不出现第二份）；bundled 白名单暂不动（§10）；admin 前端类型枚举与样式映射（§7.2） |
| 03 LIVE/PINNED 依赖 | `resource_dependencies` 加列 dependency_mode/revision_id/required/purpose（§2.1，迁移 §9）；`_assert_dependency_type` 矩阵扩展 agent/workflow→knowledge_base；KB 归档/暂停对依赖方语义接 `_notify_dependent_owners` 与 suspend 取消快照 run（§1.3/§2.2）；前端最小声明 UI（§7.2） |
| 04 Effective Scope + 适配 | scope 计算落 `backend/app/agentplatform/knowledge/`（总方案裁决 C3）；扩展包子包 `agentplatform_extension/knowledge/`（context/scope/runtime_adapter，仅依赖 deerflow-extension-api，§3/§4 接缝）；`knowledge_search.datasets` 保留为最外层 Deployment Allowlist 交集（§5.3）；`KNOWLEDGE_ACCESS_DENIED` 新错误语义（§5.2 无现成错误码）；harness/deerflow 零 diff 约束（总方案 M2 收尾，知识方案 §94）——注入只能经企业接缝（tool_adapter/runtime_adapter/扩展包），不得改 `community/ragflow/*` |

### 开放决策（随实施票裁决，非本票范围）

1. caller 知识权限求值点：ResourceService 可见性语义内 vs AuthorizationProvider `filter_resources` 扩展 `knowledge_base`（§3）——倾向前者为真源、后者仅 Tool 层。
2. Retrieval Receipt 存储：扩展包自有表（`table_prefix` 机制，`extensions/loader.py:28 ExtensionSpec`）vs 控制面表（审计/保留期归属）——倾向控制面，但扩展包不得 import 企业模型，需 host 侧写入接缝（M5 落地时定）。
3. `ResourceStorageKind` 是否为 KB 引入第三种值（如 `external`）还是复用 DATABASE——倾向 DATABASE（声明式 Content 走 `publish_database` 路径，§1.2）。
