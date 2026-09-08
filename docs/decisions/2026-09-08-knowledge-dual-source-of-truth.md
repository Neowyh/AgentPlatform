# 知识双层真源：治理真源与索引真源分离

> audience: developers, architects, security reviewers
> status: accepted
> owner: engineering maintainers
> last-verified: 2026-09-08
> canonical-path: `docs/decisions/2026-09-08-knowledge-dual-source-of-truth.md`

## 决策摘要

企业知识采用双层真源：AgentPlatform 持有治理真源（KB UUID、owner、department、visibility、Revision、依赖、审批、运行快照、检索回执），RAGFlow 等 Knowledge Provider 只持有索引状态真源（dataset、解析状态、chunk、embedding、检索结果）。Provider 的 dataset ID 只是外部映射 ID，永远不能成为企业 KnowledgeBase 的身份标识。

## 背景与备选

DeerFlow 上游 RAGFlow 集成 RFC 的设计是「Provider = Knowledge Base 状态唯一真源，Runtime 不保存 KB 元数据」。这对通用开源 Runtime 合理，但 AgentPlatform 已有 Resource Governance 体系，必须回答上游 RFC 不回答的问题：这是谁的知识库、谁能看、谁能用、哪个版本、Agent/Workflow 依赖哪个 KB、半年后能否复现当时的知识状态。

备选一是照搬上游 RFC（Provider 唯一真源）——被否决，因为它使 KB 脱离 Resource Governance，形成企业身份的第二真源，违反基线不变量 3 与 6。备选二是双向同步全部元数据——被否决，因为同步成本高且仍会出现归属歧义。

## 决策

- KnowledgeBase 是第四类一等 Resource；canonical identity 是 AgentPlatform KB UUID。
- Provider 通过 `provider_type` + opaque `provider_dataset_id` 映射绑定，可整体替换（RAGFlow → 内部检索引擎）而不破坏依赖、历史、ACL 与运行快照。
- 知识模型三层职责固定：AgentPlatform 管治理、Provider 管解析/索引/检索、DeerFlow 管 `knowledge_search` 工具运行时与回执。
- 模型不得接触 Provider dataset ID；服务端负责 KB UUID/Revision → provider dataset 的映射。
- 所有正式 KB（含后续 Local Knowledge）必须具备 Revision / manifest hash 语义，本地原始文件可不上传，但治理与可复现信息在 Server。

## 后果

- 需要 Provider 对账机制（dataset 存在性、文档一致性、orphan 检测、DRIFTED 状态），见知识方案 §86~88。
- Provider 侧直接人工编辑会造成漂移，正式 Published Dataset 不允许从 Provider UI 编辑。
- 未来接入第二 Provider 时只新增 Provider 实现，不改治理模型。
