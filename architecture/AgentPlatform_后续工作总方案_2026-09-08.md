# AgentPlatform 后续工作总方案

> **文档性质**：三线工作统一编排 / 阶段映射 / 任务卡索引
> **制定日期**：2026-09-08
> **上位文档**：《AgentPlatform 总体架构与模块边界基线》（Baseline v1.0，2026-09-06）
> **下位文档**：三份专项实施方案（DeerFlow 收敛 / 知识库 / Local Runtime，均 2026-09-04）
> **决策来源**：2026-09-08 设计评审会话（见 §2 决策记录）

---

# 1. 本方案的定位与使用方式

本方案**不替代**任何一份既有文档。四份既有文档继续作为各自领域的详细实施依据：

- 基线文档回答「边界、真源、不变量」；
- 专项方案回答「字段、API、测试矩阵、commit 序列」。

本方案只负责一件事：**统一编排**。它告诉每一个 coding agent：

```text
现在做哪个里程碑
→ 它的硬前置是什么
→ 只需要装载哪些文档章节切片
→ 交付什么、Gate 是什么
→ 用哪条测试 lane 验收
→ 收尾时必须做什么清理
```

约束来源优先级不变：`AGENTS.md`（仓库规则） > 基线 > 本方案 > 专项方案细节。

**文档切片纪律**：单个里程碑开工时，coding agent 只装载 §7 对应任务卡列出的章节切片，不整包装载四份文档（总计约 1.1 万行，超出单次任务上下文的合理占用）。

---

# 2. 决策记录（2026-09-08 评审）

以下决策由项目维护者拍板，后续里程碑按此执行；推翻需显式修订本节。

| # | 决策 | 内容 |
|---|---|---|
| D1 | 主线顺序 | Knowledge 主线先行（遵守基线 Phase 顺序）。**唯一允许的并行线**是 Device Control Plane + Secure WSS（M7），因其与 Knowledge 线几乎无共享代码。其余一律串行。 |
| D2 | 收敛债务排期 | 统一 alembic migration 链并关闭 PATCH-006 是 **M2 建表的硬前置**；PATCH-009（Workflow V2 全量 DB 验证）是 **M10 Workflow ExecutionTarget 的硬前置**；其余 open patches 不阻塞主线，每个里程碑收尾时尝试关闭可关闭者。 |
| D3 | RAGFlow 环境 | 当前**没有**可用 RAGFlow 实例。dev RAGFlow（docker compose profile + 内网 embedding 配置）纳入 M1 作为第一批任务。 |
| D4 | 执行资源 | 按单 coding agent 串行 vertical slices 设计任务卡；M7 标注为可拆出的并行任务包（将来扩容时启用）。 |
| D5 | 交付物 | 本总方案 + 仓库根 `CONTEXT.md` 术语表 + `docs/decisions/` 三份 ADR（ExecutionTarget / 知识双层真源 / 本地否决权）。 |

---

# 3. 当前状态基线（2026-09-08 仓库事实）

以下为编码前核实过的事实，coding agent 不得凭旧印象假设状态：

**已完成（基线 Phase 0 收敛）：**

- DeerFlow `main` 已锁定在 `0f7d8709` 并合入 `develop`（merge commit `cd28a054`）；
- `backend/packages/harness/` 下仅存 `deerflow`，`ideer` harness 已删除（仅 `backend/app/agentplatform/legacy/memory/compat.py` 保留记忆兼容垫片）；
- 企业层位于 `backend/app/agentplatform/`（resources / workflows / fault_zeroing / persistence / skills 等）；
- `backend/packages/agentplatform-extension/` 已建立，当前含 `network_policy.py`、`evidence.py`；
- `backend/packages/extension-api/`（`deerflow_extension_api`）已可用；
- 升级台账齐备：`docs/upgrades/deerflow-main-0f7d8709/`（UPSTREAM_LOCK / CONFLICT_LEDGER / PATCH_LEDGER / 各验收报告）；
- 上游 `knowledge_search` 已随 runtime 进入仓库：`backend/packages/harness/deerflow/community/ragflow/tools.py`；
- `run_resource_snapshots` 表已存在并含 version / authz_revision 约束。

**未开始：**

- `ResourceType` 仍只有 `skill / agent / workflow`（`backend/app/agentplatform/resource_models.py:18`），无 `KNOWLEDGE_BASE`；
- `knowledge/`、`devices/`、`local_runtime/` 模块均不存在；
- 无任何 RAGFlow 部署（D3）。

**未清偿债务（Patch Ledger，均 open）：**

- PATCH-006：双 `alembic_version` 表隔离，统一 forward-only migration 链未完成 → 阻塞 M2；
- PATCH-009：Workflow V2 模型命名空间已建，但全量 DB 执行验证 incomplete → 阻塞 M10；
- 其余 11 个 patch：不阻塞，按 D2 巡检策略处理。

---

# 4. 统一阶段映射表

三个编号体系对应关系如下。**后续沟通、commit、任务卡一律使用 M 编号**，引用专项方案时注明其原 Phase 号。

| 总方案 | 基线 Phase | 知识方案 Phase | Local 方案 Phase | 名称 | 可并行 |
|---|---|---|---|---|---|
| M0 | Phase 1 收尾（本次评审新增） | — | — | 收敛债务清偿 | — |
| M1 | Phase 3 | Phase 1（含环境准备前置） | — | dev RAGFlow + Runtime Smoke | — |
| M2 | Phase 4 + Phase 2（knowledge 部分） | Phase 2 + 3 | — | KnowledgeBase Resource Governance | — |
| M3 | — | Phase 4 | — | 文档管理 + Knowledge Center | — |
| M4 | Phase 5 前半 | Phase 5 + 6 | — | Revision + Publish + Run Snapshot | — |
| M5 | Phase 5 后半 | Phase 7 | — | Retrieval Receipt + Evidence UI | — |
| M6 | — | Phase 8 | — | Retrieval Test + Eval | — |
| M7 | Phase 6 + 7 | — | Phase 1 + 2 | Device Control Plane + Secure WSS | ✅ 唯一并行线 |
| M8 | Phase 8 + 9 + 10 | — | Phase 3 + 4 + 5 | Local Files / Python / Tool Integration | — |
| M9 | Phase 11 | — | Phase 6 + 7 + 8 | Local MCP + Local Secrets + Tray | — |
| M10 | Phase 12 | — | Phase 9 | Workflow ExecutionTarget | — |
| M11 | Phase 13 | — | Phase 10 | Local Knowledge | — |
| M12 | Phase 14 + 15 | Phase 10 | Phase 11 | 统一 Evidence E2E + Offline Distribution | — |

**延后不排期**：知识方案 Phase 9（Knowledge Routing）——待单 Agent 可见 KB 数量实际增长后再启动（知识方案 §68 已明确不要提前复杂化）。

---

# 5. 已裁决冲突（coding agent 必须遵守）

评审中确认的跨文档不一致，均按「基线 > 专项」裁决并在此登记。实现时以本表为准，不遵循专项方案中被推翻的原文：

| # | 冲突点 | 裁决 |
|---|---|---|
| C1 | ExecutionTarget 第一阶段枚举：基线 §10 写 `SERVER`，Local 方案 §3.2 写 `SERVER_SANDBOX` | 用 `SERVER` / `USER_DEVICE` |
| C2 | Local 方案 §3.2 把 `local.knowledge.search` 列为模型可见工具 | 模型业务层只有 `knowledge_search`；`local.knowledge.search` 仅作内部 capability / routing key（基线 Decision 1） |
| C3 | 知识方案 §19 建议企业模块放 `backend/app/knowledge/` | 企业模块落点为 `backend/app/agentplatform/knowledge/`（与现有 resources / workflows 同级）；runtime 适配层落点为 `backend/packages/agentplatform-extension/agentplatform_extension/knowledge/` |
| C4 | 三份文档 Phase 编号体系互不对应 | 以本方案 M 编号为准（§4 映射表） |
| C5 | 知识方案假设 `agentplatform.*` 为顶层包 | 按仓库现状：企业层在 `backend/app/agentplatform/`，runtime 集成在 `backend/packages/agentplatform-extension/` |

---

# 6. 依赖图

```text
M0 收敛债务清偿
│   ├── T0.1 统一 migration 链（关闭 PATCH-006）───────┐
│   └── T0.2 Workflow V2 全量 DB 验证（PATCH-009）──┐  │
│                                                  │  │
M1 dev RAGFlow + Runtime Smoke                     │  │
│                                                  │  │
▼                                                  │  │
M2 KB Resource Governance ◄───────────────────────┼──┘（硬前置 T0.1）
│
├──► M3 文档管理 / Knowledge Center
│      │
│      ▼
├──► M4 Revision + Publish + Run Snapshot
│      │
│      ▼
├──► M5 Retrieval Receipt + Evidence UI
│      │
│      ▼
└──► M6 Retrieval Test + Eval

M7 Device Control Plane + Secure WSS   ←—— 可与 M3~M6 并行（唯一并行线）
│
▼
M8 Local Files / Python / Tool Integration
│
▼
M9 Local MCP + Secrets + Tray
│
▼
M10 Workflow ExecutionTarget ◄———— T0.2 硬前置
│
▼
M11 Local Knowledge ◄———— M4/M5 硬前置（KB 治理先行，基线不变量）
│
▼
M12 统一 Evidence E2E + Offline Distribution
```

---

# 7. 任务卡

每张卡的通用前置（不再重复写入）：

1. 读取 `AGENTS.md`、`backend/AGENTS.md`（及涉及目录更近的 AGENTS.md）；
2. 对将修改的符号执行 GitNexus impact analysis（HIGH/CRITICAL 停下报告；UNKNOWN 补充文本核实）；
3. TDD 切片：每个 vertical slice 一个 focused regression test。

---

## M0 — 收敛债务清偿

- **目标**：把收敛合并留下的硬债务降到不阻塞后续建表/改表的水平。
- **硬前置**：无。
- **文档切片**：收敛方案 §15（数据库与 Migration 融合）、§19（删除 Dual Runtime）、§20（Patch Ledger）；`docs/upgrades/deerflow-main-0f7d8709/UPSTREAM_PATCH_LEDGER.md`。
- **主要交付**：
  - T0.1：单一 forward-only migration 链（本地 resource 族 + 上游 runtime 族经 merge revision 合一），关闭 PATCH-006；fresh DB 与 existing DB 双验证（收敛方案 §15.2 三类数据库中 A/B 两类）；
  - T0.2：在真实 SQLite + PostgreSQL fixture 上完整执行 Workflow V2 表族的 migration 与读写验证，将 PATCH-009 状态推进（完全关闭可留到 M10）；
  - T0.3：Patch Ledger 巡检——逐项评估 13 个 open patch，凡移除条件已实际满足者当场关闭；不可关闭者在 Ledger 中补注「阻塞原因」。
- **Gate**：`alembic heads` 单头；`alembic upgrade head` 在 fresh + existing 两类库上通过；资源/版本/snapshot 计数一致；Ledger 更新后 diff 归零。
- **测试 lane**：`cd backend && make test` + `bash scripts/run-test-lane.sh pr-standard`（persistence 高风险路径）。
- **收尾**：detect_changes → Ledger 更新 → commit（`fix(migrations): ...` / `chore(upstream): ...`）。

---

## M1 — dev RAGFlow 环境 + Runtime Smoke

- **目标**：证明「AgentPlatform + DeerFlow Runtime + RAGFlow」基础链路在 dev 环境成立（知识方案 Gate 1）。
- **硬前置**：无（与 M0 无依赖，可紧随其后；D3 决策：环境从零搭建）。
- **文档切片**：知识方案 §2、§58~60（Phase 0~1）、§53（Network Policy）、§72~73（Health Check / Config）。
- **主要交付**：
  - dev RAGFlow compose profile：遵循 `docker/` 现有多 profile 惯例（如 `docker-compose-knowledge-dev.yaml` 或 dev compose 内 profile），含内网 embedding/模型 endpoint 配置，断网可运行；
  - knowledge 配置 namespace 落入收敛后的真实 config schema（以锁定 SHA 的 `config.example.yaml` 为准，禁止凭印象硬编码）；
  - Smoke：创建测试 dataset → 上传少量文档 → Agent Tool Call `knowledge_search` → Tool Receipt 生成 → 错误脱敏 → 断网工作。
- **明确不做**：KnowledgeBase Resource、Revision、Knowledge Center（知识方案 §60）。
- **Gate**：知识方案 Gate 1 全项。
- **测试 lane**：focused smoke 脚本 + `cd backend && make test`。

---

## M2 — KnowledgeBase Resource Governance

- **目标**：KB 成为第四类一等 Resource；Agent/Workflow 可声明 KB 依赖；Effective Knowledge Scope 在 Assembly 与检索时双层生效。
- **硬前置**：**M0-T0.1**（migration 链统一后才能建表）、M1。
- **文档切片**：知识方案 §3~§14、§16~§21、§35、§58~§62（Phase 0~3）、§74~75（API / Content Schema）、§79~80（Sub-Agent / Tool Authorization）；基线 §7、§12、§15、§17、§28。
- **主要交付**：
  - `ResourceType.KNOWLEDGE_BASE` + `knowledge_bases` 表（provider binding 为 opaque 映射，dataset ID 不做主键）；
  - KB 继承 owner / department / visibility / lifecycle / archive / suspend / audit 全套治理语义；
  - `AGENT → KNOWLEDGE_BASE`、`WORKFLOW → KNOWLEDGE_BASE` 依赖（含 LIVE/PINNED 语义字段）；
  - Effective Knowledge Scope 计算（依赖 ∩ caller 权限 ∩ workflow policy ∩ runtime authz）；
  - `agentplatform_extension/knowledge/`（context / scope / runtime_adapter / receipts / provenance），把 run-scoped allowlist 接入上游 `knowledge_search`，模型不见 dataset ID；
  - API 走 canonical `/api/resources` + 子资源路由（知识方案 §74）。
- **Gate**：知识方案 Gate 2 + Gate 3（越权矩阵：猜 dataset ID / 改 Tool args / 隐藏 KB / shared agent caller-owner 交叉 / Sub-Agent / Workflow）。
- **测试 lane**：focused → `make test` → `pr-standard`（resources/authz 高风险）。
- **收尾**：Patch Ledger 巡检；本里程碑不得产生任何 `harness/deerflow` 新 diff（知识方案 §94）。

---

## M3 — 文档管理 + Knowledge Center

- **目标**：用户可创建/上传/管理 KB 文档，Agent Runtime 保持只读。
- **硬前置**：M2。
- **文档切片**：知识方案 §15（数据流）、§23~§27（生命周期 / Pipeline / 存储 / Source / Metadata）、§41~43（前端）、§49~52、§54（安全）、§81~84（缓存 / 预算 / 观测 / 审计）。
- **主要交付**：upload pipeline（校验 → hash → 对象存储 → provider 上传 → parse/index 状态）；Knowledge Center 列表/详情页；检索预算控制；`/api/features` 反映 knowledge.enabled 与 provider 可达性。
- **Gate**：知识方案 Gate 4（create → upload → parse → index → search → delete draft 全链）。
- **测试 lane**：`make test` + `pnpm test` → `pr-standard`。

---

## M4 — Revision + Publish + Run Snapshot

- **目标**：知识可复现——每个正式 KB 有不可变 Published Revision；Run 创建时冻结知识版本。
- **硬前置**：M3。
- **文档切片**：知识方案 §7~§11、§32~§36、§46、§65~66（Phase 5~6）、§85~88（备份 / 对账 / Drift）；基线 §16、不变量 15。
- **主要交付**：`knowledge_base_revisions`（manifest_hash、状态机）；发布门禁（可配置 eval_required）；Immutable Dataset per Published Revision 路径；`run_resource_snapshots` 扩展冻结 KB UUID / revision / manifest / profile；LIVE 依赖 Run 启动时解析、运行中不漂移；provider drift 检测（DRIFTED 状态 + 对账 job）。
- **Gate**：知识方案 Gate 5 + Gate 6（Run A 留在 Rev 1、Run B 用 Rev 2；运行中发布不漂移）。
- **测试 lane**：focused → `make test` → `pr-standard`（persistence + resources）。

---

## M5 — Retrieval Receipt + Evidence UI

- **目标**：任何最终引用可追溯到 Run → Tool Call → KB → Revision → Document → Chunk。
- **硬前置**：M4。
- **文档切片**：知识方案 §37~§40、§67（Phase 7）、§95~98（测试矩阵）；基线 §26~27。
- **主要交付**：`knowledge_retrieval_receipts`（header + items）；与 DeerFlow Tool Receipt 建立父子关联（不另造平行证据系统）；Citation 输出（《规范》4.2 节而非 chunk id）；聊天 Evidence Panel 复用上游 evidence component。
- **Gate**：知识方案 Gate 7。
- **测试 lane**：`make test` + `pnpm test` → `pr-standard`。

---

## M6 — Retrieval Test + Eval

- **目标**：检索质量可度量、可调优、发布前可回归。
- **硬前置**：M5。
- **文档切片**：知识方案 §43~§45、§68（Phase 8）、§101（性能基线）、§106（不许用最终答案正确率代替检索验收）。
- **主要交付**：Retrieval Test 页（可切换 Revision / Profile）；eval cases + 首版指标（Expected Document Hit / Recall@K / MRR）；发布前 A/B Eval 接口。
- **Gate**：知识方案 Gate 8（改 Retrieval Profile → 跑 A/B Eval → 再发布）。
- **测试 lane**：`make test` + `pnpm test`。

---

## M7 — Device Control Plane + Secure WSS 【唯一可并行线】

- **目标**：设备可配对/撤销/上下线，任务可安全下发与回执（本阶段不执行任何系统命令）。
- **硬前置**：与 M3~M6 无代码依赖，可并行（D1/D4）；若串行则排在 M6 后。
- **文档切片**：Local 方案 §1~§10、§24、§28~§31、§36（Phase 0~2）、§37（Device/Protocol Security 测试组）；基线 §6.1、§19、§10。
- **主要交付**：
  - `backend/app/agentplatform/devices/`（models / service / pairing）：Device 为 Control Plane Entity（不是 Resource）；
  - `backend/app/agentplatform/local_runtime/` broker：outbound-only 认证 WSS、session/heartbeat、task envelope、ack/timeout/cancel、replay protection、protocol version 协商；
  - `local-runtime/` 客户端骨架（Python core，顶层新目录，不入 frontend / harness）：device key pair、pairing 流程、capability 上报。
- **Gate**：Local 方案 Phase 1 + 2 Gate（pair → online → disconnect → revoke → reconnect denied；signed test task → receipt）。
- **测试 lane**：`make test` → `pr-standard`（authz 高风险）。
- **收尾**：Patch Ledger 巡检——本里程碑必须零 harness diff。

---

## M8 — Local Files / Python / Tool Integration

- **目标**：模型可见、可执行、可审计的本地文件与 Python 能力。
- **硬前置**：M7。
- **文档切片**：Local 方案 §8~§13、§17~§18、§32~§33、§36（Phase 3~5）；基线 §20~21、§23~25、§27。
- **主要交付**：Allowed Roots（逻辑 root + canonical path 校验，防 traversal/symlink/junction/UNC/case 绕过）；`local.files.list/read/write`（写走 consent policy）；`local.python`（working root / timeout / cancel / 子进程清理）；`agentplatform_extension/local_runtime/`（tools / authorization / routing / receipts / provenance）；Assembly-time 裁剪——无可用设备时模型看不到 `local.*`；LocalExecutionReceipt 进入 Tool Receipt / Run Evidence；artifact upload（显式 Upload 模式优先）。
- **Gate**：Local 方案 Phase 3~5 Gate（含「无设备 → 模型不可见」关键断言）。
- **测试 lane**：focused → `make test` → `pr-standard`。

---

## M9 — Local MCP + Local Secrets + Tray

- **目标**：本机 MCP 受控接入；凭据不出设备；用户有可见可控的托盘。
- **硬前置**：M8。
- **文档切片**：Local 方案 §14~§15、§22~§23、§36（Phase 6~8）；基线 §22、§25。
- **主要交付**：MCP supervisor（stdio / localhost HTTP，链路必须是 Server → Local Task → Local Runtime → MCP）；tool 能力上报 + Server 侧裁剪；OS 安全存储（Windows Credential Manager / DPAPI），Server 只见 `local:*` 逻辑引用；Tray（连接状态 / roots / consent / pause / 本地 audit）。
- **Gate**：Server DB、日志、Tool args、Receipt 中不存在 secret 明文（Local 方案 Phase 7 Gate）。
- **测试 lane**：`make test` → `pr-standard`。

---

## M10 — Workflow ExecutionTarget

- **目标**：「在哪里执行」成为 Workflow Step 的正式声明维度。
- **硬前置**：M9；**M0-T0.2**（Workflow V2 全量 DB 验证，D2）。
- **文档切片**：Local 方案 §25；基线 §10；收敛方案 §15（migration 原则）。
- **主要交付**：Workflow step 支持 `execution_target`（`SERVER` / `USER_DEVICE`，冲突裁决 C1）与 `requires_device_online` / `requires_user_consent` / `timeout` / `retry` / `fallback`；Run 创建时冻结 device_id（不漂移）；设备离线语义（`DEVICE_OFFLINE`、task `expires_at`）。
- **Gate**：含 ExecutionTarget 的 Workflow E2E（server 知识检索 → local python 分析 → server 解释 → 报告 → 证据链）。
- **测试 lane**：`make test` → `pr-standard`（workflow 高风险）。

---

## M11 — Local Knowledge

- **目标**：本地知识库在不上传原始文件的前提下接入统一治理。
- **硬前置**：**M4 + M5**（KB 治理与 Receipt 先行——基线不变量「Local Knowledge 不得早于 KnowledgeBase 基础治理」）、M10。
- **文档切片**：Local 方案 §16；知识方案 §14（Knowledge Location 在基线 §14 的定位）；基线 §14、§16、Decision 5。
- **主要交付**：`KnowledgeBase.location = SERVER | USER_DEVICE`；`LocalKnowledgeProvider`（轻量本地索引，方案不写死向量选型）；本地文件留设备、manifest hash / revision / retrieval receipt 回传 Server；统一 `knowledge_search` 语义路由（冲突裁决 C2：模型不感知 local.knowledge.search）。
- **Gate**：Local 方案 Phase 10 Gate（原始文件不上传，Server Agent 获得授权内最小检索证据）。
- **测试 lane**：`make test` → `pr-standard`。

---

## M12 — 统一 Evidence E2E + Offline Distribution

- **目标**：全平台验收闭环与离线交付。
- **硬前置**：M2~M11 全部完成。
- **文档切片**：基线 §36、§39、§45；知识方案 §69~71、§100、§104~105；Local 方案 §11（Network Policy）、§35、§37（Offline 测试组）、§38、§41（V1 DoD）。
- **主要交付**：故障归零综合 E2E（基线 §39 十项必须证明项）；SRS smoke；离线 bundle 更新（RAGFlow 以可选 profile 打包：`agentplatform-core` / `agentplatform-knowledge-ragflow`）；Windows Local Runtime installer；真实断网 fresh install 验收（server 与 device 两端）。
- **Gate**：基线 §45 Baseline Success Criteria 全清单；收敛方案 §29 Definition of Done 中仍然适用的离线/安全项。
- **测试 lane**：`bash scripts/run-test-lane.sh core-full` + `check-intranet.sh` + 业务验收脚本 + 断网安装。

---

# 8. 测试与验收纪律

- lane 选择遵循 `AGENTS.md` Test Lane Selection 表；本方案各任务卡已标注最低 lane；
- 高风险模块（resources / authz / persistence / knowledge scope / workflow / devices）每次改动 `pr-standard`；
- release 级验证只在 M12 跑 `core-full`，不作为普通里程碑的默认收尾；
- focused 测试挂起/超时 → 如实报 incomplete（命令、耗时、最后用例），不得改生产代码迁就受限环境；
- 每个里程碑收尾动作固定为：Patch Ledger 巡检 → detect_changes → Ledger/文档同步 → conventional commit。

# 9. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| migration 合并（T0.1）引入数据丢失 | Critical | 收敛方案 §15 原则：不改历史 revision、三类库验证、backup-aware |
| KB 建表在双 head 上先行造成合并成本 | High | D2 硬前置已排序 |
| `harness/deerflow` diff 失控回潮 | High | 每里程碑收尾 Ledger diff 归零检查 |
| Local Runtime 体量超预期（安全矩阵大） | Medium | 严格按 M7~M9 切片，每片 Gate 后再前进；不提前做 V2/V3 能力 |
| RAGFlow dev 环境含公网依赖 | Medium | M1 任务卡含断网验证与内网 embedding 配置 |
| 单 agent 上下文超载 | Medium | §1 文档切片纪律 + 任务卡自包含 |

# 10. 给 coding agent 的总指令（模板）

每个里程碑开工时，将下述模板 + 对应任务卡交给 coding agent：

```text
在 AgentPlatform 仓库执行里程碑 M<n>（任务卡见
architecture/AgentPlatform_后续工作总方案_2026-09-08.md §7）。

先读取 AGENTS.md 与 backend/AGENTS.md；只装载任务卡列出的文档切片；
遵守 §5 已裁决冲突（C1~C5）与基线 §40 架构不变量。

约束：
1. deerflow.* 是唯一 Runtime 真源；本里程碑不得新增
   backend/packages/harness/deerflow/** 下的 diff（除非任务卡显式允许，
   且必须登记 Upstream Patch Ledger）。
2. 企业逻辑只进 backend/app/agentplatform/ 与 agentplatform_extension/。
3. TDD vertical slices；GitNexus impact 先行；commit 前 detect_changes。
4. 完成定义 = 任务卡 Gate 全过 + 指定测试 lane 绿 + Ledger 巡检完成。
5. 不得超范围实现后续里程碑的能力。
```
