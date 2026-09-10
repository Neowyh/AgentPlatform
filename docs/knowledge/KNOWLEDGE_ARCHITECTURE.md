# Knowledge Architecture — 三层职责在本仓库的落点（M2 Ticket 01 产出）

> audience: developers, architects, security reviewers<br>
> status: current<br>
> owner: engineering maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/knowledge/KNOWLEDGE_ARCHITECTURE.md`

知识模型三层职责由双层真源 ADR（`docs/decisions/2026-09-08-knowledge-dual-source-of-truth.md`）固定：**AgentPlatform 管治理、Provider 管解析/索引/检索、DeerFlow 管 `knowledge_search` 工具运行时与回执**。本文把三层映射到本仓库的具体目录与接缝，作为 M2 三张实施票（02/03/04）的结构约束。现状细节见 `IMPLEMENTATION_INVENTORY.md`。

## 1. 总览

```text
┌────────────────────────────────────────────────────────────────────┐
│ 层 1  AgentPlatform 治理（控制面）                                   │
│ backend/app/agentplatform/                                         │
│   resources/（ResourceService：唯一授权与生命周期边界）              │
│   knowledge/（M2 新增：KB 服务、scope 计算，总方案裁决 C3）          │
│   gateway: /api/resources canonical API（唯一身份真源）              │
├────────────────────────────────────────────────────────────────────┤
│ 层 3  AgentPlatform Runtime 扩展（边界包，仅依赖 deerflow-extension-api）│
│ backend/packages/agentplatform-extension/agentplatform_extension/   │
│   knowledge/（M2 票 04 新增：context / scope / runtime_adapter）     │
│   evidence.py（Run Evidence Envelope：resource_snapshots + receipts）│
├────────────────────────────────────────────────────────────────────┤
│ 层 2  DeerFlow 上游运行时 + Knowledge Provider（执行面，M2 零 diff） │
│ backend/packages/harness/deerflow/community/ragflow/                │
│   tools.py（knowledge_search：query-only 工具）                      │
│   client.py（GET /datasets、POST /retrieval）、formatting.py         │
│ RAGFlow（docker/ragflow/ profile：dataset、解析、embedding、检索）    │
└────────────────────────────────────────────────────────────────────┘
```

## 2. 层 1：AgentPlatform 治理

**管**：KB UUID 身份、owner/department/visibility、lifecycle（active/archived/suspended）、draft/publish、依赖声明与校验、审批、Run 资源快照、Effective Knowledge Scope 计算、审计。

**落点**：

- 目录：`backend/app/agentplatform/knowledge/`（总方案裁决 C3——**不是**知识方案 §19 原文的 `backend/app/knowledge/`；与 `resources/`、`workflows/` 同级）。
- 治理语义不新写：KB 经 `ResourceType.KNOWLEDGE_BASE` 挂进 `ResourceService`（`backend/app/agentplatform/resources/service.py:106`）与 canonical `/api/resources`（`backend/app/gateway/routers/resources.py`），继承 owner/visibility/lifecycle/audit/快照全套机制（清单见 `IMPLEMENTATION_INVENTORY.md` §1–2）。知识子资源路由委托 ResourceService，**禁止** `/api/knowledge-bases` 第二身份真源（基线不变量 5，知识方案 §74）。
- Scope 计算是控制面职责（票 04）：`资源依赖 ∩ caller 权限 ∩ Workflow 策略 ∩ 运行时授权`，在 Run 装配期算出、随 Run 冻结；依据是既有闭包解析（`resolve_dependency_closure`，service.py:1213）与 Run 快照写入（`create_run_snapshot`，service.py:1250）的同一模式。
- Schema：`knowledge_bases` 等表见 `SCHEMA_PLAN.md`；迁移走统一链（当前 head 见 `IMPLEMENTATION_INVENTORY.md` §9）。

**红线**：不做 chunking/embedding/向量检索/rerank（知识方案 §16）；不在治理 API 暴露 provider dataset ID；不复制治理字段进 `knowledge_bases` 造成双真源。

## 3. 层 3（扩展包）：AgentPlatform Runtime 适配

**管**：Run 开始绑定 KB 快照、scope 注入运行时、logical KB → provider dataset 映射、越权 dataset 阻断、知识 provenance 进 Run Evidence。

**落点**：

- 目录：`backend/packages/agentplatform-extension/agentplatform_extension/knowledge/`（总方案裁决 C3/C5），子包现状空缺，与既有 `local_runtime/`、`evidence.py` 平级；票 04 范围为 `context.py / scope.py / runtime_adapter.py`（context/scope/runtime_adapter），receipts/provenance 文件留 M5。
- 包边界：扩展包**只依赖 `deerflow-extension-api`**（`agentplatform_extension/__init__.py` docstring；API 面 `backend/packages/extension-api/deerflow_extension_api/`：`ExtensionRegistry`、`RunEvidenceEnvelope`、`RunEvidenceBinding` 等）。scope 数据从控制面经 Run 装配接缝传入（`run_preparation.py:211-233` 的 Run metadata / `runtime_adapter.py` 的 `FrozenAgentInputs`），扩展包不 import 企业模型。
- 注入路径（票 04）：M1 验证过的部署级静态 `knowledge_search.datasets` allowlist（`community/ragflow/tools.py:211-240 _resolve_datasets`，fail-closed）保留为**最外层交集**；扩展包在工具装配/调用链注入 run-scoped dataset allowlist 作为内层交集，最终生效集合 = `Deployment Allowlist ∩ Resource Scope ∩ Caller Permission`。
- 检索时二次强制：请求涉及的 dataset 不在 scope → `KNOWLEDGE_ACCESS_DENIED`（与空结果 `No relevant content found.` 严格区分）；模型只见 logical KB 选择器（现状工具已是 `query` 单参，票 04 决定是否扩 logical selector 参数），永不接触 raw dataset ID（基线不变量 12）。

**红线**：不改 `harness/deerflow`（M2 收尾约束"零 diff"，知识方案 §94——总方案 M2 卡明确登记）；注入只能经企业接缝 `backend/app/agentplatform/tool_adapter.py` / `runtime_adapter.py` / 扩展包装配，不得修改 `community/ragflow/*`。

## 4. 层 2：DeerFlow 运行时 + Knowledge Provider

**管**：`knowledge_search` 工具执行（分组并行检索、结果格式化、错误脱敏）、RAGFlow HTTP 协议、dataset/解析/索引状态。

**落点**：

- 运行时：`backend/packages/harness/deerflow/community/ragflow/`——`tools.py`（`knowledge_search_tool`，query-only，:395-400）、`client.py`（`RAGFlowClient`，retrieval-only）、`formatting.py`（`format_retrieval_result`，dataset ID 只映射为名称）。工具注册经 config `tools:` 列表 + `deerflow/tools/tools.py get_available_tools`，企业可见性/授权在 `app/agentplatform/tool_adapter.py` 装配后追加。
- Provider：RAGFlow，部署形态 `docker/docker-compose-knowledge-dev.yaml`（dev profile）+ `docker/ragflow/bootstrap.sh`（smoke dataset `ideer-knowledge-smoke`、`RAGFLOW_API_KEY` 产出，交接物清单见 `IMPLEMENTATION_INVENTORY.md` §8）。连接配置真源是部署侧 `knowledge_search` 工具配置组（`config.example.yaml:726-748` 注释示例，启用值在未跟踪 `config.yaml`）——票 02 的 KB 绑定**沿用此配置源**，不出现第二份连接配置。
- 未来管理写操作（M3 上传/解析）由层 1 的 Provider 封装调用，必须复用/包装 `RAGFlowClient` 共享 base_url/认证/timeout/错误映射/脱敏，禁止另写不一致的第二套 HTTP client（知识方案 §18）。

**红线**：Provider dataset ID 不进任何模型可见面；Provider 侧人工编辑造成漂移属禁止形态（ADR 后果条款，正式 Published Dataset 不从 Provider UI 编辑）。

## 5. 端到端数据流（M2 完成后）

```text
Run Create
  → 层1 解析依赖闭包（agent/workflow → KB，LIVE/PINNED）      service.py:1184/:1213
  → 层1 计算 Effective Knowledge Scope（∩ caller 权限 ∩ 策略）  knowledge/scope（票04）
  → 层1 写 run_resource_snapshots（含 KB，冻结）               service.py:1250
  → Run 装配把 scope 交给扩展包                                run_preparation.py / runtime_adapter.py
  → 层3 runtime_adapter：logical KB → run-scoped dataset allowlist
  → 层2 knowledge_search（外层 Deployment Allowlist 交集内检索）  tools.py:344-378
  → 层2 RAGFlow POST /retrieval                                client.py:160-187
  → 层2 结果格式化（无 dataset ID）+ Tool Receipt              formatting.py / tool_receipt_middleware.py
  → 层3 provenance 写 Run Evidence Envelope（M5）              evidence.py
```

LIVE/PINNED 都在 Run 启动时冻结（知识方案 §36）；Run 中途不漂移。

## 6. 与相邻体系的关系（防混淆）

- **Memory**：严格分离（知识方案 §47–48），KnowledgeBase 记录组织正式知识，Memory 记录个人/Agent 经验；`legacy/memory/prompt.py` 的 knowledge 分类词与本体系无关。
- **Local Knowledge**（M11）：服从统一 KB Governance（基线不变量 14）；`local.knowledge.search` 仅内部 capability/routing key，模型业务层只有 `knowledge_search`（总方案裁决 C2）。
- **AuthorizationProvider**（`harness/deerflow/authz/`）与 **LocalAuthorization**（扩展包 `local_runtime/authorization.py`）：前者是 server 工具/路由/沙箱授权面，后者是本地能力交集 veto；KB 数据 ACL 在层 1 ResourceService 可见性语义内求值，Tool 权限（`knowledge:search`）与 KB ACL 两层都要过（知识方案 §80）。开放决策记录在 `IMPLEMENTATION_INVENTORY.md` §12。
