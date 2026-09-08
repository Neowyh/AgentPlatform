# AgentPlatform 知识库能力建设实施方案（Coding Agent 版）

> **目标读者**：Coding Agent、项目维护者、架构评审者  
> **制定日期**：2026-09-04  
> **前置条件**：已经完成 **DeerFlow `main` → AgentPlatform `develop` 收敛**，`deerflow.*` 已成为唯一 Runtime 真源，AgentPlatform 独有能力已经上移至 Control Plane / Workflow / Extension / Business Package 层。  
> **目标仓库**：`https://github.com/Neowyh/AgentPlatform`  
> **上游运行时**：`https://github.com/bytedance/deer-flow`
>
> **总体目标**：  
> 在不破坏 AgentPlatform 已有 Resource Governance V2、Workflow、Run Snapshot、企业权限、离线部署与业务资源包的前提下，引入完整的企业知识库能力，使知识库成为与 Skill / Agent / Workflow 同级受治理的一等资源；充分复用 DeerFlow 上游已具备的 `knowledge_search` / RAGFlow 只读检索 Runtime，同时将知识库的企业身份、版本、权限、依赖、审核、运行快照、检索证据和评测能力建设在 AgentPlatform 层。
>
> **核心原则**：
>
> ```text
> AgentPlatform 管：
>   谁的知识
>   谁能看
>   谁能用
>   哪个版本
>   Agent/Workflow 依赖什么知识
>   本次 Run 使用哪一版知识
>   检索到了什么证据
>   知识如何发布/审核/归档
>
> RAG Provider 管：
>   文档解析
>   Chunk
>   Embedding
>   索引
>   Hybrid Retrieval
>   Rerank
>
> DeerFlow Runtime 管：
>   Agent 如何安全调用 knowledge_search
>   Tool Authorization
>   Context Engineering
>   Tool Receipt
>   Lead Agent / Sub-Agent
> ```
>
> **第一版推荐 Provider：RAGFlow。**
>
> 不把 AgentPlatform 写死为 RAGFlow 平台；通过薄 Provider Boundary 保留未来切换其他知识引擎的能力。

---

# 0. 一句话实施方案

不要把知识库理解成：

```text
上传文件
→ 向量化
→ 加一个 search_knowledge Tool
→ 完成
```

应该建设成：

```text
                      AgentPlatform
                           │
                           ▼
                KnowledgeBase Resource
                           │
         UUID / Owner / Department / Version
          Visibility / Lifecycle / Approval
                           │
                           ▼
                 Knowledge Revision
                           │
            Document Manifest + Content Hash
                           │
                           ▼
              Knowledge Provider Adapter
                           │
                           ▼
                        RAGFlow
                Parse / Chunk / Index / Search
                           │
                           ▼
                DeerFlow knowledge_search
                           │
                           ▼
             Effective Knowledge Scope
                           │
                           ▼
                    Agent / Workflow
                           │
                           ▼
                  Retrieval Receipt
                           │
                           ▼
                     Run Evidence
```

最终要实现：

> **知识库不是 Agent 的一个外挂工具，而是 Resource Governance 体系中的第四类核心资源。**

---

# 1. 前置架构假设

本实施方案默认上游收敛已经完成，因此 Coding Agent 不得重新引入以下旧结构：

```text
ideer.* Runtime
自维护 Memory Runtime
自维护 Sub-Agent Runtime
自维护 MCP Runtime
自维护 Guardrail Runtime
```

当前架构应满足：

```text
deerflow.*                 # upstream-first runtime
agentplatform.*            # enterprise product layer
agentplatform-extension    # runtime integration
resources/**               # business resources
workflows/**               # workflow definitions
```

知识库开发必须遵守同样边界：

```text
deerflow.*            不加入 AgentPlatform 企业知识治理逻辑
agentplatform.*       不复制 DeerFlow knowledge_search Runtime
```

---

# 2. 需要复用的 DeerFlow 上游能力

以当前 DeerFlow `main` 为参考，上游已加入可选的只读 RAGFlow 检索：

```text
knowledge_search(query)
```

支持：

- RAGFlow Dataset；
- Dataset ID allowlist；
- Credential / Dataset ID 错误路径脱敏；
- Agent Tool 方式调用；
- 与 DeerFlow Tool / Runtime / Context 体系集成。

参考：

- DeerFlow CHANGELOG  
  `https://github.com/bytedance/deer-flow/blob/main/CHANGELOG.md`
- RAGFlow integration RFC  
  `https://github.com/bytedance/deer-flow/issues/4900`

Coding Agent 在实际开发前必须读取**当前仓库已经收敛后的 DeerFlow 代码**，确认：

```text
knowledge_search 的当前 Tool schema
RAGFlow client 路径
配置字段
dataset allowlist 实现
tool receipt 行为
authorization hook
frontend 是否已有 Knowledge 页面/API
```

禁止仅根据本文字段名猜实现。

---

# 3. 不照搬 DeerFlow RFC 的部分

DeerFlow RAGFlow RFC 的一个主要设计原则是：

```text
RAGFlow = Knowledge Base 状态唯一真源
DeerFlow 不保存 Knowledge Base 元数据
```

这对于通用开源 Runtime 是合理的。

AgentPlatform **不能原样采用**，因为 AgentPlatform 已有 Resource Governance，需要回答：

```text
这是谁的知识库？
属于哪个部门？
谁能看到？
谁能运行？
谁能上传？
谁能发布？
谁能扩大可见范围？
Agent A 依赖哪一个 KB？
Workflow W 依赖哪一个 KB？
Run R 当时使用的是 KB 哪一版？
半年后能否复现当时的知识状态？
```

因此 AgentPlatform 采用：

```text
双层真源
```

但不是“双向同步所有元数据”。

## 3.1 AgentPlatform 是治理真源

保存：

```text
KB UUID
owner
department
visibility
lifecycle
version/revision
dependency
approval
document manifest
content hash
provider mapping
run snapshot
retrieval receipt
```

## 3.2 RAGFlow 是索引状态真源

保存：

```text
dataset
document parse state
chunks
embeddings
index
retrieval result
reranking state
```

## 3.3 明确禁止

AgentPlatform 不复制：

```text
RAGFlow 每个 Chunk 的完整内容
RAGFlow 内部 embedding
RAGFlow 内部 index schema
RAGFlow parser 内部运行状态历史
```

除非未来为了合规归档有明确需求。

---

# 4. KnowledgeBase：第四类一等 Resource

当前：

```text
Resource
├── Skill
├── Agent
└── Workflow
```

扩展为：

```text
Resource
├── Skill
├── Agent
├── Workflow
└── KnowledgeBase
```

KnowledgeBase 必须继承已有 Resource Governance 的共同语义。

## 4.1 必须具备

```text
stable UUID
owner
department
visibility
lifecycle
draft
publish
approval
archive
suspend
version/revision
content hash
dependency
favorite（如现有 Resource 支持）
audit
run snapshot
```

## 4.2 不要让 RAGFlow dataset ID 变成主键

错误：

```text
knowledge_base_id = ragflow_dataset_id
```

正确：

```text
AgentPlatform KB UUID
    │
    ▼
Knowledge Provider Mapping
    │
    ▼
provider = ragflow
provider_dataset_id = <opaque id>
```

这样未来：

```text
RAGFlow → Internal Retriever
```

不会破坏：

```text
Agent dependencies
Workflow dependencies
History
ACL
Run Snapshot
```

---

# 5. Domain Model

建议最小领域模型：

```text
Resource
   │
   └── KnowledgeBase
          │
          ├── KnowledgeBaseRevision
          │
          ├── KnowledgeDocument
          │
          └── ProviderBinding
```

---

# 6. 建议数据库模型

字段名必须结合 AgentPlatform 当前 ORM / Alembic 风格调整，以下是语义模型，不要求逐字照搬。

## 6.1 `knowledge_bases`

```text
knowledge_bases
---------------------------------------------
resource_id               FK resources.id PK
provider_type             ragflow
provider_dataset_id       nullable/opaque
retrieval_profile_json
ingestion_profile_json
embedding_profile_json
active_revision_id
sync_status
created_at
updated_at
```

注意：

```text
provider_dataset_id
```

不是企业资源 ID。

---

## 6.2 `knowledge_base_revisions`

```text
knowledge_base_revisions
---------------------------------------------
id
knowledge_base_id
revision_no
status
manifest_hash
document_count
provider_dataset_id
provider_revision_hint      optional
created_by
created_at
published_at
```

推荐状态：

```text
DRAFT
INDEXING
READY
PUBLISHED
FAILED
SUPERSEDED
ARCHIVED
```

---

## 6.3 `knowledge_documents`

```text
knowledge_documents
---------------------------------------------
id
knowledge_base_id
revision_id
logical_document_id
provider_document_id
filename
display_name
source_type
source_uri
mime_type
file_size
content_hash
metadata_json
parse_status
parse_error_code
created_by
created_at
updated_at
```

### `logical_document_id`

用于表达：

```text
同一份逻辑文件
v1
v2
v3
```

不要仅用 filename 判断是否同一文档。

---

## 6.4 `knowledge_provider_bindings`

如果未来明确需要多 Provider，可单独表：

```text
knowledge_provider_bindings
---------------------------------------------
id
knowledge_base_id
provider_type
provider_dataset_id
config_ref
is_active
created_at
```

第一版可以先合入 `knowledge_bases`，避免过度抽象。

---

## 6.5 `knowledge_retrieval_receipts`

这是强烈建议新增的表：

```text
knowledge_retrieval_receipts
---------------------------------------------
id
run_id
thread_id
tool_call_id
tool_receipt_id

knowledge_base_id
knowledge_revision_id

query
query_hash

document_id
provider_document_id
chunk_ref
chunk_hash

retrieval_score
rerank_score
rank

page
section
citation_label

provider_type
provider_dataset_id

created_at
```

如果一次 Tool 返回多个 Chunk：

```text
1 receipt header + N receipt items
```

比每个 Chunk 一行塞全部 query 信息更合适。

可拆：

```text
knowledge_retrieval_receipts
knowledge_retrieval_receipt_items
```

---

# 7. KnowledgeBase Revision：必须从第一版考虑

企业知识库最容易犯的错误：

```text
KB 是一个永远变化的 Dataset
```

这样 Run 无法复现。

AgentPlatform 应引入：

```text
KnowledgeBaseRevision
```

---

# 8. Revision 的定义

Revision 不要求复制整个向量库。

它表示：

> **这一时刻知识库所包含逻辑文档集合及其内容版本的不可变 Manifest。**

例如：

```text
KB: 历史故障案例库

Revision 17
├── document A / SHA256 aaa
├── document B / SHA256 bbb
├── document C / SHA256 ccc
└── document D / SHA256 ddd
```

计算：

```text
manifest_hash = hash(
  sorted(document logical id + content hash + metadata policy)
)
```

---

# 9. Revision 的两种实现路径

## 9.1 推荐第一版：Immutable Dataset per Published Revision

发布 Revision 时：

```text
Draft Dataset
      ↓
完成解析
      ↓
验证
      ↓
形成 Published Dataset
      ↓
该 Dataset 不再修改
```

优点：

```text
真正可复现
简单
不会出现旧 Run 查询到新 Chunk
```

缺点：

```text
RAGFlow Dataset 数量增加
存储增加
发布成本增加
```

适合：

```text
质量
故障归零
规范
设计文档
审计
```

---

## 9.2 第二种：Mutable Dataset + Manifest Snapshot

仅保存 Manifest：

```text
Revision 17
→ document hashes
```

检索仍指向一个不断更新的 Provider Dataset。

这只能提供：

```text
知道当时有哪些文件
```

不能保证：

```text
半年后重新执行得到同样检索结果
```

因此对于 AgentPlatform 的重点业务不推荐作为默认。

---

# 10. 支持 LIVE / PINNED 两种 Knowledge Dependency

依赖关系建议允许：

```text
LIVE
PINNED
```

## LIVE

```text
Agent / Workflow
→ 使用 KB 当前 Published Revision
```

适合：

```text
办公助手
持续更新制度
普通知识问答
```

## PINNED

```text
Agent / Workflow
→ 固定 KB Revision 17
```

适合：

```text
故障归零
质量审核
项目评审
有审计要求的业务
```

---

# 11. 扩展 Resource Dependency Model

当前已有：

```text
AGENT -> SKILL
WORKFLOW -> AGENT
```

扩展为：

```text
AGENT -> KNOWLEDGE_BASE
WORKFLOW -> KNOWLEDGE_BASE
```

依赖附加字段可包括：

```text
dependency_mode = LIVE | PINNED
revision_id
required = true/false
purpose
```

例如：

```text
Fault Zeroing Agent
├── 历史故障案例库        LIVE
├── 产品设计知识库        PINNED rev 12
└── 质量规范库            PINNED rev 7
```

---

# 12. Effective Knowledge Scope

Agent 不能任意搜索平台全部 KnowledgeBase。

实际 Run 可访问知识范围：

```text
Effective Knowledge Scope
=
Resource Dependency Scope
∩ Caller Knowledge Permission
∩ Workflow Policy
∩ Runtime Authorization
∩ Environment Availability
```

---

# 13. Assembly-Time Filtering

上游 DeerFlow 已有 Tool assembly authorization 思路。

知识库也应同样遵循：

> Agent 不应该知道自己无权访问的知识库存在。

因此：

```text
Run Create
    │
    ▼
Resolve Resource Dependency
    │
    ▼
Evaluate Caller Permission
    │
    ▼
Resolve Published/Pinned Revision
    │
    ▼
Create Effective Knowledge Scope
    │
    ▼
Inject runtime context
    │
    ▼
knowledge_search
```

而不是：

```text
模型自己传任意 dataset_id
→ Provider 再报 403
```

---

# 14. 模型不得接触 Provider Dataset ID

推荐 Tool 语义：

```python
knowledge_search(
    query="...",
    knowledge_base="历史故障案例库"   # optional logical selector
)
```

甚至第一版可以只允许：

```python
knowledge_search(query="...")
```

服务端自动搜索当前 Effective Scope。

不要让模型调用：

```python
knowledge_search(
    query="...",
    dataset_ids=["abc123"]
)
```

即使 DeerFlow 上游底层 Tool 使用 Dataset ID：

```text
AgentPlatform Runtime Adapter
```

应负责：

```text
KB UUID/revision
→ provider_dataset_id
```

---

# 15. 推荐 Runtime 数据流

```text
User Request
    │
    ▼
AgentPlatform Run Resolver
    │
    ├── Agent Snapshot
    ├── Skill Snapshot
    ├── Workflow Snapshot
    └── Knowledge Snapshot
              │
              ▼
     Effective Knowledge Scope
              │
              ▼
 AgentPlatform Knowledge Extension
              │
              ▼
      DeerFlow knowledge_search
              │
              ▼
          RAGFlow Client
              │
              ▼
       Retrieval / Rerank
              │
              ▼
 Structured Search Result
              │
              ├── content
              ├── source
              ├── document
              ├── page
              ├── section
              ├── scores
              └── provider refs
              │
              ▼
      Retrieval Receipt
              │
              ▼
        DeerFlow Tool Receipt
              │
              ▼
            Agent
```

---

# 16. AgentPlatform Knowledge Extension

推荐建立：

```text
backend/packages/agentplatform-extension/
└── agentplatform_extension/
    └── knowledge/
        ├── __init__.py
        ├── context.py
        ├── authorization.py
        ├── scope.py
        ├── runtime_adapter.py
        ├── receipts.py
        └── provenance.py
```

职责：

```text
Run 开始时绑定 KB Snapshot
计算 Effective Knowledge Scope
把 logical KB 映射到 provider dataset
阻止越权 dataset
记录 Retrieval Receipt
把知识 provenance 写入 Run Evidence
```

不负责：

```text
Chunking
Embedding
Vector Search
Reranking 算法
```

---

# 17. Knowledge Provider Boundary

AgentPlatform 应有一个薄 Provider Interface。

不要一开始设计重量级 RAG Framework。

建议最小接口：

```python
class KnowledgeProvider(Protocol):
    async def create_dataset(...)
    async def delete_dataset(...)
    async def list_documents(...)
    async def upload_document(...)
    async def delete_document(...)
    async def start_ingestion(...)
    async def get_ingestion_status(...)
    async def search(...)
```

其中：

```text
read methods
write methods
```

必须在 service 层显式分离权限。

---

# 18. 第一版 Provider：RAGFlow

实现：

```text
RAGFlowKnowledgeProvider
```

优先复用 DeerFlow 已有：

```text
RAGFlow client
knowledge_search
formatting
configuration
```

但 Gateway 的知识管理 CRUD 可以由 AgentPlatform Knowledge Service 调用同一 Provider。

关键原则：

> 不再另写一套与 DeerFlow Runtime 行为不一致的 RAGFlow HTTP Client。

如果 DeerFlow Client 已足够：

```text
复用 / wrapper
```

如果缺少写 API：

```text
在 AgentPlatform Provider 中扩展管理 Client
```

但要共享：

```text
base_url
authentication
timeout
error mapping
redaction
```

---

# 19. 目录结构建议

在收敛完成后的仓库中，建议形成：

```text
backend/

packages/
├── harness/
│   └── deerflow/                  # upstream runtime，不改企业逻辑
│
├── extension-api/
│
└── agentplatform-extension/
    └── agentplatform_extension/
        └── knowledge/

app/
├── resources/
│
├── knowledge/
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   ├── provider.py
│   ├── ragflow_provider.py
│   ├── revisions.py
│   ├── permissions.py
│   ├── retrieval.py
│   ├── receipts.py
│   ├── router.py
│   └── errors.py
│
└── workflows/

resources/
├── agents/
├── skills/
├── workflows/
└── knowledge/         # 仅 bundled/default KB manifests，如确有需要
```

实际位置必须遵循当前仓库收敛后的 `AGENTS.md` 与依赖方向。

---

# 20. 写知识与读知识必须分离

默认：

```text
Agent Runtime
→ READ ONLY
```

Agent 不应自动：

```text
create KB
upload files
delete files
reindex
publish revision
```

---

# 21. 权限建议

## Reader

```text
knowledge:read
knowledge:search
```

## Editor

```text
knowledge:upload
knowledge:update_metadata
knowledge:delete_document
knowledge:reindex
```

## Publisher

```text
knowledge:publish
knowledge:visibility
```

## Admin

```text
knowledge:delete
knowledge:transfer
knowledge:provider_admin
```

权限命名最终必须与 AgentPlatform 当前 AuthorizationProvider contract 对齐。

---

# 22. Agent 自动学习

第一阶段禁止：

```text
Agent → 直接写 Published KB
```

未来可以支持：

```text
Agent
   ↓
提出 candidate knowledge
   ↓
Knowledge Draft
   ↓
Eval / Review
   ↓
Human or Policy Approval
   ↓
Publish Revision
```

即：

> **自动提出知识，不自动发布正式知识。**

---

# 23. 文档生命周期

推荐：

```text
UPLOADED
    ↓
VALIDATING
    ↓
PARSING
    ↓
INDEXING
    ↓
READY
    ↓
PUBLISHED

失败：
FAILED
```

删除建议：

```text
SOFT_DELETE
→ 发布新 Revision
→ Provider cleanup
```

避免直接删除造成历史 Revision 无法解释。

---

# 24. Upload Pipeline

```text
User Upload
    │
    ▼
Permission
    │
    ▼
File Validation
    │
    ├── type
    ├── size
    ├── malware/security scan（如有）
    └── content hash
    │
    ▼
Object/File Storage
    │
    ▼
KnowledgeDocument
    │
    ▼
Provider Upload
    │
    ▼
Parse / Index Task
    │
    ▼
Status Poll / Callback
    │
    ▼
READY
    │
    ▼
Revision Candidate
```

---

# 25. 文件本体存储

不要默认认为：

```text
RAGFlow Dataset
```

就是唯一文件归档。

对于企业知识建议考虑：

```text
Original Document Storage
```

由 AgentPlatform 或企业文件系统负责保存原始文件。

至少保证：

```text
content_hash
original filename
logical_document_id
source
provider_document_id
```

可以对应起来。

如果当前平台已有文件/对象存储能力，应复用，不要再创建独立 storage。

---

# 26. Source Types

建议从一开始为文档来源留字段：

```text
UPLOAD
LIBRARY
INTERNAL_URL
DATABASE_EXPORT
PLM
MES
GIT
MANUAL_TEXT
```

第一版实际只实现：

```text
UPLOAD
```

即可。

不要因为未来可能接 PLM/MES，就第一版做全部 connector。

---

# 27. Metadata

文档 Metadata 建议支持：

```text
title
document_no
revision
product
project
department
author
effective_date
classification
tags
custom_fields
```

第一版使用：

```text
metadata_json
```

避免过早把每个企业字段硬编码成列。

但权限敏感字段：

```text
classification
```

如果用于强制 ACL，不应只埋 JSON，应有规范 schema / policy extraction。

---

# 28. Knowledge Routing：渐进式披露

随着 KB 增长，不应把所有知识库名字注入 System Prompt。

建议：

```text
User Query
    │
    ▼
Effective Knowledge Scope
    │
    ▼
Knowledge Router
    │
    ▼
Top Candidate KBs
    │
    ▼
Retriever
```

---

# 29. 第一版 Routing

不要上 LLM Router。

可以先：

```text
Agent Resource 显式 dependency
+
KB name/description/tags
+
简单 lexical/embedding matching
```

多数情况下：

```text
Agent 已经限制到 1~5 个 KB
```

甚至无需 Router。

---

# 30. 第二阶段 Routing

当一个 Agent 可访问几十个 KB 时：

```text
KB Metadata Index
    │
    ▼
Query → Top N KB
    │
    ▼
Chunk Retrieval
```

KB metadata：

```text
name
description
domain
tags
summary
```

可单独做 embedding。

---

# 31. Retrieval Pipeline

第一版不要只依赖纯向量 Top-K。

如果 RAGFlow 已提供 hybrid retrieval / reranking，应优先利用。

目标抽象：

```text
Query
  │
  ▼
Normalization
  │
  ▼
KB Routing
  │
  ▼
Hybrid Retrieval
  │
  ├── Vector
  └── Lexical
  │
  ▼
Fusion
  │
  ▼
Rerank
  │
  ▼
Metadata / ACL Filter
  │
  ▼
Deduplicate
  │
  ▼
Context Budget
  │
  ▼
Evidence
```

---

# 32. Retrieval Profile

知识库 Resource 可以包含：

```text
retrieval_profile
```

例如：

```json
{
  "top_k": 8,
  "similarity_threshold": 0.25,
  "rerank": true,
  "max_total_chars": 8000
}
```

注意：

- 不要让每个 Agent Prompt 自己硬编码这些值；
- Published Revision 应关联其使用的 Retrieval Profile Version；
- 重要生产业务的 profile 变化应走 Eval。

---

# 33. Ingestion Profile

允许定义：

```text
parser
chunk strategy
chunk size
overlap
table handling
OCR
language
```

但第一版尽量采用 RAGFlow 默认/成熟解析配置。

AgentPlatform 保存：

```text
profile id/version
```

而不是复制 RAGFlow 每个内部 parser 参数到 Resource Core。

---

# 34. Embedding Profile

Embedding 变化通常意味着：

```text
重新索引
```

因此必须版本化：

```text
embedding_profile_version
```

发布 Revision 时记录。

不要在运行中静默更换 embedding model。

---

# 35. Knowledge Snapshot

扩展现有：

```text
run_resource_snapshots
```

KnowledgeBase 进入 snapshot：

```text
resource_type = knowledge_base
resource_uuid
resource_version
knowledge_revision_id
manifest_hash
provider_type
provider_dataset_id
retrieval_profile_hash
embedding_profile_hash
```

敏感 provider ID 可仅后端保存，不暴露给用户/模型。

---

# 36. LIVE 依赖的 Run 也必须冻结

即使 Agent 配置为：

```text
LIVE
```

Run 创建时仍应：

```text
resolve current published revision
→ freeze into Run Snapshot
```

`LIVE` 的含义是：

> 每次新 Run 使用启动时最新版本。

而不是：

> 一个正在运行的 Run 可以在中途漂移到新知识。

---

# 37. Retrieval Receipt：核心差异化能力

每次知识检索必须能回答：

```text
谁搜的？
在哪个 Run？
搜了哪个 KB？
哪一版 KB？
Query 是什么？
返回哪个文档？
哪个位置？
哪个 Chunk？
分数多少？
最后哪个证据被 Agent 引用了？
```

---

# 38. 与 DeerFlow Tool Receipt 对接

不要另造平行证据系统。

应：

```text
DeerFlow Tool Receipt
        │
        ▼
Knowledge Retrieval Receipt
        │
        ▼
Run Evidence
```

例如：

```text
tool_receipt_id
→ retrieval_receipt_id
→ N retrieval items
```

最终：

```text
Sub-Agent acceptance
Artifact delivery
Knowledge evidence
```

都能统一进入 Run Evidence。

---

# 39. Citation 输出

Retriever 输出结构应尽量保留：

```text
knowledge_base_uuid
knowledge_revision
document_id
display_name
page
section
chunk_ref
content
scores
```

模型生成引用时显示：

```text
《XXX规范》4.2节
```

而不是：

```text
chunk_827361
```

---

# 40. Citation Evidence UI

聊天回答中的引用建议可点击打开：

```text
Evidence Panel
├── Knowledge Base
├── Revision
├── Document
├── Page/Section
├── Retrieved Text
├── Retrieval Score
└── Retrieval Time
```

这与 DeerFlow 上游已有 citation/evidence UI 方向一致，应尽可能复用其通用 evidence component。

---

# 41. Knowledge Center 前端

新增一级能力：

```text
Knowledge / 知识库
```

推荐页面：

## List

显示：

```text
名称
状态
Owner
Department
Visibility
Current Revision
Document Count
Provider
Updated At
```

## Detail

Tabs：

```text
Documents
Versions
Permissions
Dependencies
Retrieval Test
Evaluation
Audit
Settings
```

---

# 42. Knowledge Create

用户创建：

```text
Name
Description
Department
Visibility
Provider
```

第一版：

```text
Provider = RAGFlow
```

不必让普通用户输入：

```text
RAGFlow URL
API Key
Dataset ID
```

这些属于部署/平台基础设施。

---

# 43. Retrieval Test UI

这是必须做，不是锦上添花。

输入：

```text
测试问题
```

输出：

```text
Top result list

Rank
Document
Page
Section
Raw Score
Rerank Score
Content Preview
```

并可切换：

```text
Revision
Retrieval Profile
```

便于调优。

---

# 44. Knowledge Eval

每个知识库建议支持 Eval Dataset。

最小模型：

```text
knowledge_eval_cases
--------------------------------
id
knowledge_base_id
question
expected_document_ids
expected_sections
expected_fact
tags
created_at
```

---

# 45. 第一阶段 Eval 指标

检索：

```text
Recall@K
MRR
Hit Rate
```

生成：

```text
Citation Correctness
Groundedness
Answer Correctness
```

如果一开始没有 Judge Model 评测框架，先实现：

```text
Expected Document Hit
Expected Section Hit
```

已经非常有价值。

---

# 46. Revision 发布门禁

推荐：

```text
Draft Revision
    │
    ▼
Index Complete
    │
    ▼
Eval
    │
    ├── pass
    │     ▼
    │   Approval
    │     ▼
    │   Publish
    │
    └── fail
          ▼
        remain Draft
```

第一版可配置：

```text
eval_required = false
```

但架构留好接口。

---

# 47. Knowledge 与 Memory 必须完全分开

定义：

```text
Knowledge
= 组织认可的外部事实/文档

Memory
= 用户/Agent 跨会话记忆

Skill
= 工作方法

Tool
= 操作能力
```

例如：

```text
《型号A维修手册》
→ Knowledge

“用户偏好用中文输出”
→ Memory

“如何构建故障树”
→ Skill

“读取 PLM 数据”
→ Tool
```

---

# 48. 禁止 Knowledge 进入 Memory 的旁路

不要实现：

```text
上传企业文档
→ 拆成 memory facts
```

也不要：

```text
检索到的文档内容
→ 自动长期写入 Memory
```

Memory 可保存：

```text
“用户常使用知识库 X”
```

但不能把知识库内容本身当用户事实沉淀。

---

# 49. Security：最低要求

知识库属于高敏企业数据入口。

至少做到：

```text
Resource ACL
Provider credential isolation
Dataset ID redaction
Tool assembly filtering
Runtime re-authorization
Audit
Network policy
Upload validation
No public egress by default
```

---

# 50. Provider Credential

RAGFlow API Key：

```text
不得
写入 Resource Content
写入 Agent Prompt
写入 Skill
返回前端
进入 Tool Error
进入 Retrieval Receipt
```

应来自：

```text
Deployment secret
or
Enterprise secret provider
```

---

# 51. Error Redaction

面向模型和普通用户：

不要返回：

```text
RAGFLOW_API_KEY
internal base URL（视安全策略）
raw dataset ID
SQL
internal stack trace
```

保留：

```text
correlation/trace id
sanitized error code
```

供管理员追查。

---

# 52. Dataset ID Enumeration

模型不能：

```text
list all RAGFlow datasets
```

除非当前请求已经经过：

```text
Effective Knowledge Scope
```

即使 DeerFlow 上游有 `list_knowledge_bases` Tool，AgentPlatform 产品模式也应评估是否注册。

默认建议：

```text
Agent 不注册全局 list_knowledge_bases
```

或者返回：

```text
当前 Run 有权使用的 logical KB only
```

---

# 53. Network Policy

内网部署：

```text
AgentPlatform
→ RAGFlow internal endpoint
ALLOW

RAGFlow
→ 公网
DENY（除非部署明确需要）
```

知识库不能成为恢复互联网访问的旁路。

---

# 54. File Security

如果部署环境有要求，应为上传 pipeline 预留：

```text
file type validation
magic number validation
archive bomb limit
size limit
path traversal defense
malware scan
encrypted document handling
macro document policy
```

不要只看扩展名。

---

# 55. Document-Level ACL

第一版建议：

```text
KB-Level ACL
```

不要立即支持：

```text
同一个 KB 内不同 Document 不同 ACL
```

因为会大幅增加：

```text
Retrieval filter
Index metadata
Citation
Caching
Revision
Testing
```

复杂度。

如果业务确实需要文档级权限：

> 拆成多个 KnowledgeBase。

后续规模明确后再引入 Document ACL。

---

# 56. Provider Abstraction：避免过度设计

第一版禁止为了“未来兼容”创建：

```text
EmbeddingFactory
ChunkFactory
VectorStoreFactory
ParserFactory
RetrieverFactory
RerankerFactory
GraphStoreFactory
```

只需要：

```text
KnowledgeProvider
```

未来真有第二 Provider 时再抽象内部组件。

---

# 57. 第一阶段明确不做

为了控制范围，MVP 不做：

```text
GraphRAG
知识图谱
RAPTOR
Agentic recursive retrieval
多模态知识图谱
自动网页爬虫知识库
自动写 Published Knowledge
Document-Level ACL
跨 Provider 联邦检索
复杂 query rewrite pipeline
LLM-generated ontology
```

---

# 58. Phase 0：Repository Reconnaissance

Coding Agent 必须先读取：

```text
AGENTS.md
backend/AGENTS.md
frontend/AGENTS.md
与知识/资源相关目录下更近的 AGENTS.md
```

然后定位：

```text
Resource models/service/router
resource_dependencies
run_resource_snapshots
AuthorizationProvider adapter
Agent assembly
Run creation
DeerFlow knowledge_search
RAGFlow client
Tool receipt
Evidence/citation frontend
Postgres/Alembic
Offline bundle
```

---

# 59. Phase 0 输出：Implementation Inventory

创建：

```text
docs/knowledge/
├── KNOWLEDGE_ARCHITECTURE.md
├── IMPLEMENTATION_INVENTORY.md
├── SCHEMA_PLAN.md
└── TEST_MATRIX.md
```

`IMPLEMENTATION_INVENTORY.md` 至少记录：

```text
Current Resource type enum
Resource API
Resource dependency schema
Run snapshot schema
Authorization extension points
Knowledge runtime code path
RAGFlow config path
Tool receipt schema
Evidence UI path
Offline deployment dependencies
```

在完成 inventory 前，不允许直接开始大规模编码。

---

# 60. Phase 1：RAGFlow Runtime Smoke

目标：

> 不加企业治理，先确认收敛后的 DeerFlow RAGFlow `knowledge_search` 在 AgentPlatform 内网环境能工作。

## 工作

- 部署 RAGFlow；
- 配置内网 endpoint；
- 创建测试 dataset；
- 上传少量测试文档；
- 开启 DeerFlow knowledge search；
- 确认 Agent Tool Call；
- 确认断网工作；
- 确认错误脱敏；
- 确认 Tool Receipt。

## 不做

此阶段不创建：

```text
KnowledgeBase Resource
Revision
Knowledge Center
```

### Gate 1

必须证明：

```text
AgentPlatform + DeerFlow Runtime + RAGFlow
```

基础链路成立。

---

# 61. Phase 2：KnowledgeBase Resource MVP

目标：

> 把已有 RAGFlow Dataset 纳入 Resource Governance。

新增：

```text
ResourceType.KNOWLEDGE_BASE
knowledge_bases
provider binding
resource CRUD
permissions
dependency
```

第一阶段管理方式：

```text
创建 AgentPlatform KB
→ 管理员绑定一个已有 RAGFlow Dataset
```

先不要同时实现复杂上传管理。

### Gate 2

必须通过：

- owner；
- department；
- visibility；
- archive；
- suspend；
- dependency；
- Agent bind KB；
- unauthorized user denied。

---

# 62. Phase 3：Effective Scope + Runtime Adapter

建立：

```text
Agent Resource
→ Knowledge Dependency
→ Caller Permission
→ Effective Scope
→ RAGFlow Dataset
```

将 Dataset allowlist 从静态全局配置：

```text
configured dataset IDs
```

升级为：

```text
request/run-scoped computed dataset allowlist
```

### 关键要求

静态配置仍可以有：

```text
deployment-level provider allowlist
```

最终 Dataset：

```text
Effective datasets
=
Deployment Allowlist
∩ Resource Scope
∩ Caller Permission
```

### Gate 3

越权测试必须包括：

```text
猜 dataset ID
改 Tool args
调用隐藏 KB
共享 Agent owner/caller 交叉
Sub-Agent
Workflow
```

---

# 63. Phase 4：Upload / Document Management

增加：

```text
Knowledge Center
Document upload
parse/index status
delete
reindex
```

写操作只通过：

```text
Knowledge Service
```

Agent Runtime 仍 read-only。

### Gate 4

完整：

```text
create KB
upload
parse
index
search
delete draft document
```

---

# 64. Phase 5：Revision + Publish

实现：

```text
Draft Revision
Provider Dataset
Manifest
Publish
Immutable Published Revision
```

推荐重要业务采用：

```text
dataset per published revision
```

### Gate 5

测试：

```text
Rev 1 published
→ Agent run A

Edit Draft
→ publish Rev 2

Run A snapshot remains Rev 1
New run B uses Rev 2
```

---

# 65. Phase 6：Run Snapshot

扩展：

```text
run_resource_snapshots
```

必须冻结：

```text
KB UUID
Resource Version
Revision
Manifest Hash
Retrieval Profile
Provider Binding
```

### Gate 6

运行开始后发布新知识：

```text
当前 run 不漂移
```

---

# 66. Phase 7：Retrieval Receipt + Evidence UI

实现：

```text
knowledge_retrieval_receipt
```

与 DeerFlow：

```text
tool receipt
```

关联。

聊天 citation 点击后展示证据。

### Gate 7

任一最终引用都能追溯：

```text
Run
→ Tool call
→ KB
→ Revision
→ Document
→ Chunk
```

---

# 67. Phase 8：Retrieval Test + Eval

增加：

```text
Retrieval Test page
Eval case
Eval run
Metrics
```

第一版：

```text
Expected Document Hit
Recall@K
MRR
```

### Gate 8

修改：

```text
Retrieval Profile
```

能运行 A/B Eval 再发布。

---

# 68. Phase 9：Knowledge Routing

当单 Agent 可见 KB 数量确实增长后再做。

实现：

```text
KnowledgeBase metadata search
→ Top KB
→ RAG retrieval
```

不要提前复杂化。

---

# 69. Phase 10：Offline Distribution

更新内网包：

```text
RAGFlow images
RAGFlow dependencies
DB/vector/search dependencies
AgentPlatform Knowledge migrations
config templates
health check
SBOM
SHA256
backup/restore
```

---

# 70. RAGFlow 是否必须打进同一 Bundle

建议：

```text
Bundle 可选 Profile
```

例如：

```text
agentplatform-core
agentplatform-knowledge-ragflow
```

原因：

- 并非所有部署都需要 KB；
- RAGFlow 依赖较重；
- 避免基础 AgentPlatform 安装强制增加大量服务。

---

# 71. Deployment Profile

## Dev

```text
AgentPlatform
RAGFlow
local/small DB
internal model
```

## Enterprise Single Node

```text
AgentPlatform
PostgreSQL
RAGFlow
RAGFlow dependencies
internal object storage
vLLM
```

## Enterprise HA

按 RAGFlow 当前官方支持与企业基础设施评估，不在 AgentPlatform 内自创 HA 机制。

---

# 72. Health Check

AgentPlatform `/api/features` / health 应能反映：

```text
knowledge.enabled
provider reachable
write capability
search capability
index status
```

但普通用户不暴露：

```text
API keys
internal topology
raw provider exception
```

---

# 73. Config 建议

AgentPlatform runtime 配置增加清晰 namespace，例如：

```yaml
knowledge:
  enabled: true

  provider:
    type: ragflow
    base_url: ${RAGFLOW_BASE_URL}
    api_key: ${RAGFLOW_API_KEY}

  defaults:
    retrieval_profile: balanced

  governance:
    published_revisions_immutable: true
    agent_write_enabled: false

  security:
    expose_provider_ids: false
```

**Coding Agent 必须以收敛后的真实 DeerFlow config schema 为准适配。**

不要复制两个：

```text
DeerFlow knowledge_base
AgentPlatform knowledge
```

中完全重复的 connection config。

应统一 provider connection source。

---

# 74. API 设计建议

延续 canonical Resource API。

## Resource

```text
POST /api/resources
type=knowledge_base
```

或当前统一 Resource create contract。

## Knowledge subresource

可增加：

```text
GET  /api/resources/{kb_id}/knowledge
GET  /api/resources/{kb_id}/documents
POST /api/resources/{kb_id}/documents
DELETE /api/resources/{kb_id}/documents/{doc_id}

GET  /api/resources/{kb_id}/revisions
POST /api/resources/{kb_id}/revisions
POST /api/resources/{kb_id}/revisions/{revision_id}/publish

POST /api/resources/{kb_id}/retrieve-test
GET  /api/resources/{kb_id}/evals
POST /api/resources/{kb_id}/evals/run
```

不要另建一套：

```text
/api/knowledge-bases
```

成为第二 canonical identity source。

可提供 convenience route，但必须委托 ResourceService。

---

# 75. Resource Content Schema

KnowledgeBase Resource Content 建议只存声明式业务配置：

```json
{
  "description": "...",
  "provider_type": "ragflow",
  "retrieval_profile": "balanced",
  "default_dependency_mode": "live"
}
```

不要把：

```text
provider API key
raw dataset id
chunk contents
```

放进可导出 Resource Content。

---

# 76. Bundled KnowledgeBase

是否允许：

```text
resources/knowledge/
```

建议只用于：

```text
demo
template
bootstrap metadata
```

不建议把大型企业原始文档提交 Git。

Bundled manifest 可以描述：

```text
KB template
retrieval profile
expected external document pack
```

但实际企业文档通过：

```text
upload/import
```

进入。

---

# 77. Knowledge Package

如果未来需要离线分发业务知识，可定义：

```text
Knowledge Package
├── manifest
├── documents
├── hashes
├── metadata
├── evals
└── signature
```

导入：

```text
verify
→ draft KB
→ ingest
→ eval
→ publish
```

这是后续能力，不是 MVP。

---

# 78. 与 Workflow 的结合

Workflow 可以依赖 KnowledgeBase：

```text
Workflow
├── Agent A
├── Agent B
└── KnowledgeBase K
```

其中 Workflow 可以做：

```text
知识版本门禁
检索结果数量门禁
必须引用证据
必须命中某类规范
```

例如技术归零：

```text
根因结论
→ 必须引用至少一条历史案例或技术文件证据
→ 无检索证据则进入人工确认
```

---

# 79. 与 Sub-Agent 的结合

Sub-Agent 不继承父 Agent 全部 KB 权限。

应计算：

```text
SubAgent Effective KB Scope
=
Parent Run KB Scope
∩ SubAgent Resource Dependency
∩ Caller Permission
```

禁止通过 Delegation 扩权。

---

# 80. 与 Tool Authorization 的结合

Knowledge search 本身是 Tool：

```text
knowledge:search
```

同时其数据范围还有：

```text
KB ACL
```

两层都要过：

```text
有 Tool 权限
≠
可以搜索所有 KB
```

---

# 81. Caching

第一版不要做复杂语义 Cache。

允许：

```text
Provider HTTP connection pooling
短 TTL KB metadata cache
```

但任何权限结果：

```text
必须与 caller / policy revision 绑定
```

不要缓存：

```text
user A 的 search result
```

给 user B。

---

# 82. Search Result Context Budget

即使 RAGFlow 返回很多结果：

```text
不要全部注入 LLM
```

遵循 DeerFlow Context Engineering：

```text
max chunks
max chars
dedup
rerank
```

把完整检索结果保存 Receipt / debug store，需要时 UI 展示；只把预算内 evidence 交给模型。

---

# 83. Observability

增加指标：

```text
knowledge_search_count
knowledge_search_latency
provider_error_rate
zero_hit_rate
avg_chunks_returned
avg_context_chars
retrieval_acl_denied
ingestion_success_rate
ingestion_latency
revision_publish_count
```

标签避免高基数：

不要直接把：

```text
query
document id
user id
```

放 metrics label。

这些进 trace/audit。

---

# 84. Audit

至少记录：

```text
KB create
upload
delete document
reindex
publish
visibility change
permission change
archive
suspend
search denied
provider binding change
```

---

# 85. Backup / Restore

Knowledge 模块不能只备份 AgentPlatform DB。

需要定义：

```text
AgentPlatform metadata backup
Original documents backup
RAGFlow/provider backup
```

恢复顺序：

```text
DB metadata
→ original document storage
→ provider state
→ consistency reconciliation
```

---

# 86. Reconciliation Job

因为 AgentPlatform 与 Provider 分层，需要一个只读一致性检查：

```text
AgentPlatform KB
→ provider dataset exists?
→ documents match?
→ published dataset immutable?
→ orphan provider dataset?
```

不要自动删除 orphan。

输出：

```text
HEALTHY
MISSING_PROVIDER_DATASET
MISSING_DOCUMENT
HASH_MISMATCH
ORPHAN_PROVIDER_RESOURCE
```

需要 Admin 处理。

---

# 87. Provider 外部编辑

如果允许管理员直接进入 RAGFlow UI 修改 Dataset，会破坏 AgentPlatform Revision。

正式生产建议：

```text
AgentPlatform 管理的 Published Dataset
→ 不允许从 RAGFlow UI 人工编辑
```

或至少：

```text
reconciliation detects drift
→ KB status = DRIFTED
→ 禁止作为 PINNED revision 继续发布
```

---

# 88. Provider Drift

Published Revision 定期/按需检查：

```text
manifest hash
provider document listing
```

发现 drift：

```text
status = DRIFTED
```

不能静默接受。

---

# 89. Failure Semantics

## Search Provider Down

Tool 返回：

```text
KNOWLEDGE_PROVIDER_UNAVAILABLE
```

Agent 可以：

```text
明确说明无法访问知识源
```

不能伪装成：

```text
知识库没有相关内容
```

## Zero Result

单独状态：

```text
NO_RELEVANT_EVIDENCE
```

## Unauthorized

```text
KNOWLEDGE_ACCESS_DENIED
```

不要混在 `NO_RESULT` 中。

---

# 90. Agent Prompt Policy

System prompt 中只需要原则：

```text
有相关企业知识库时优先检索
基于检索证据回答
不捏造未检索到的内部事实
关键结论保留引用
```

不要往 Prompt 注入：

```text
所有 dataset ids
所有 KB 元数据
所有文档列表
```

---

# 91. Retrieval 调用策略

第一版建议允许 Agent 自主决定是否检索，但对重点 Workflow 可强制：

```text
retrieve-before-answer
```

例如：

```text
技术归零 root cause finalization
→ mandatory knowledge evidence
```

这由 Workflow Policy 控制，不写死 DeerFlow Runtime。

---

# 92. Coding Agent Git 策略

建议 feature branch：

```text
feature/knowledge-foundation
feature/knowledge-governance
feature/knowledge-runtime
feature/knowledge-revisions
feature/knowledge-evidence
feature/knowledge-ui
feature/knowledge-evals
feature/knowledge-offline
```

如果一个 Coding Agent 连续执行，可使用单一：

```text
feature/knowledge-platform-v1
```

但必须保持阶段性 commit。

---

# 93. 推荐 Commit 序列

```text
docs(knowledge): record implementation inventory and architecture

feat(resources): add knowledge-base resource type
feat(knowledge): add provider and ragflow binding
feat(knowledge): add knowledge resource service and permissions
feat(resources): support agent and workflow knowledge dependencies

feat(knowledge): compute effective run knowledge scope
feat(extensions): bridge knowledge scope into deerflow retrieval
test(knowledge): enforce dataset authorization and caller boundary

feat(knowledge): add document ingestion and provider status
feat(frontend): add knowledge center and document management

feat(knowledge): add immutable knowledge revisions
feat(resources): snapshot knowledge revision in runs

feat(knowledge): persist retrieval receipts
feat(frontend): show knowledge evidence and citations

feat(knowledge): add retrieval test and eval cases

chore(intranet): package ragflow knowledge profile offline
docs(knowledge): add operations backup and recovery runbook
```

避免：

```text
feat: add knowledge base
```

一个巨大 commit。

---

# 94. Coding Agent 冲突/修改规则

即使上游收敛已经完成，知识开发仍禁止修改：

```text
backend/packages/harness/deerflow/**
```

除非确认：

1. 上游现有 Extension / Adapter 无法实现；
2. 修改是 Runtime 通用 bug，而不是 AgentPlatform 产品需求；
3. 有 focused regression test；
4. 有 Upstream Patch Ledger；
5. 有明确回 upstream 的 Issue/PR 计划。

知识治理不得进入 DeerFlow Harness。

---

# 95. 测试矩阵

## Unit

### Knowledge Service

- create；
- update；
- permission；
- provider mapping；
- revision；
- manifest hash。

### Provider

- upload；
- search；
- status；
- timeout；
- redaction。

### Scope

- dependency；
- visibility；
- caller；
- workflow；
- live/pinned。

---

# 96. Integration Tests

必须覆盖：

## A. Agent Dependency

```text
Agent A → KB 1
Agent B → KB 2
```

A 无法搜索 KB 2。

## B. User Permission

Agent 声明 KB 1，但 User 无权限：

```text
KB 不进入 Effective Scope
```

## C. Shared Agent

Owner 发布 Agent：

```text
Caller 执行
→ 使用 Caller KB permission
→ 不使用 Owner 权限
```

## D. Workflow

Workflow 指定 KB：

```text
Agent step 不能越过 Workflow scope
```

## E. Sub-Agent

Sub-Agent 不因 delegation 获得新 KB。

---

# 97. Revision Tests

## LIVE

```text
Run A created at Rev 1
Publish Rev 2
Run A remains Rev 1
Run B uses Rev 2
```

## PINNED

```text
Agent pinned Rev 1
Publish Rev 2
New Run still Rev 1
```

---

# 98. Retrieval Receipt Tests

验证：

```text
run_id
KB UUID
revision
query hash
document
chunk
scores
tool receipt
```

完整关联。

---

# 99. Security Tests

至少：

```text
raw dataset id injection
provider id guessing
unauthorized logical KB
hidden KB enumeration
API key leakage
provider exception leakage
path traversal upload
oversized file
unsupported file
shared-resource privilege escalation
subagent privilege escalation
```

---

# 100. Offline Tests

完全断网：

```text
install
start
login
create KB
upload
parse
search
agent answer
citation
restart
history
revision
```

如果 RAGFlow 本身需要模型/embedding 服务：

```text
所有 endpoint 必须在内网。
```

---

# 101. Performance Baseline

记录：

```text
upload latency
parse latency
search p50/p95
rerank latency
first token impact
context size
```

不要在没有 baseline 的情况下盲目优化。

---

# 102. Definition of Done — MVP

MVP 完成必须满足：

```text
[ ] KnowledgeBase 成为 Resource Type
[ ] KB 继承 owner/department/visibility/lifecycle
[ ] Agent 可声明 KB dependency
[ ] Workflow 可声明 KB dependency
[ ] Effective Knowledge Scope 生效
[ ] Caller boundary 生效
[ ] DeerFlow knowledge_search 被复用
[ ] 模型无法指定任意 dataset id
[ ] 内网 RAGFlow 检索成功
[ ] 默认 Agent read-only
[ ] Resource API 是 canonical source
[ ] 完全断网可运行
```

---

# 103. Definition of Done — V1 Production

在 MVP 基础上：

```text
[ ] Document upload/parse/index UI
[ ] Knowledge Revision
[ ] Published Revision immutable
[ ] Run Snapshot 冻结 KB revision
[ ] Retrieval Receipt
[ ] Citation Evidence UI
[ ] Retrieval Test UI
[ ] Eval Dataset
[ ] Provider drift detection
[ ] Backup/restore runbook
[ ] Offline bundle
[ ] Security test matrix
[ ] Business acceptance
```

---

# 104. 第一版验收业务场景

建议直接拿已有业务测试知识库。

## 故障归零

Knowledge：

```text
历史故障案例
技术规范
产品说明
质量制度
```

问题：

```text
某故障现象的历史相似案例是什么？
有哪些已知失效模式？
根因结论与哪条设计规范有关？
```

验收：

```text
正确检索
引用
revision snapshot
receipt
workflow evidence
```

---

# 105. SRS

Knowledge：

```text
软件标准
需求模板
项目历史 SRS
术语规范
```

验收：

```text
引用标准
术语一致
不跨越无权限项目资料
```

---

# 106. 不要用最终答案正确率代替 Retrieval 验收

出现：

```text
LLM 本身知道答案
```

可能导致最终答案“看起来正确”，但 KB 实际没工作。

必须分别检查：

```text
retrieval hit
citation
receipt
answer
```

---

# 107. 质量门禁

高风险模块：

```text
resources
permissions
run snapshot
knowledge scope
provider secrets
revision
retrieval receipt
```

每次改动都至少：

```text
focused test
+
project standard test lane
```

最终：

```text
full backend
frontend
business
offline
security
```

全部通过。

实际命令应读取收敛后仓库当前 `AGENTS.md`，不要假设旧命令永远不变。

---

# 108. 未来 V2 演进方向

V1 稳定后再考虑：

## 108.1 多 Provider

```text
RAGFlow
Internal Retrieval
OpenSearch
其他企业 RAG
```

## 108.2 Knowledge Package

离线签名知识包。

## 108.3 Automated Draft Knowledge

Agent 自动生成 Draft，人工批准。

## 108.4 Source Connector

```text
PLM
MES
Git
Wiki
Document System
```

## 108.5 Document-Level ACL

仅业务明确需要时。

## 108.6 GraphRAG

仅在传统 Hybrid RAG Eval 明确证明存在结构关系召回瓶颈时考虑。

---

# 109. 推荐的最终平台概念模型

```text
                       AgentPlatform

       ┌────────────────┬────────────────┐
       │                │                │
       ▼                ▼                ▼

     Skill           Knowledge          Tool
    怎么做             知道什么           能做什么
       │                │                │
       └────────────────┼────────────────┘
                        ▼
                      Agent
                     谁来完成
                        │
                        ▼
                    Workflow
                    如何受控执行
                        │
                        ▼
                 DeerFlow Runtime
                    如何运行
                        │
                        ▼
                   Run Evidence
                    凭什么可信
```

KnowledgeBase 的引入，应该强化而不是绕开这套模型。

---

# 110. Coding Agent Master Instruction

以下可直接作为 Coding Agent 的总任务提示词。

---

## TASK

在已经完成 DeerFlow `main` → AgentPlatform `develop` 收敛的代码基线上，为 AgentPlatform 建设企业知识库能力。

不要 Fork DeerFlow Knowledge Runtime。优先复用上游 DeerFlow 的 RAGFlow `knowledge_search`、Tool Authorization、Tool Receipt、Context Engineering 与 Citation/Evidence 能力。

AgentPlatform 自行建设 KnowledgeBase Resource Governance、Provider Mapping、Knowledge Revision、Dependency、Effective Knowledge Scope、Run Snapshot、Retrieval Receipt、Knowledge Center、Eval 与 Offline Distribution。

---

## ARCHITECTURE INVARIANTS

1. `deerflow.*` 是唯一 Agent Runtime 真源。
2. Knowledge governance 不得写入 DeerFlow Harness。
3. KnowledgeBase 是第四类一等 Resource，与 Skill / Agent / Workflow 同级。
4. AgentPlatform KB UUID 是企业身份真源；RAGFlow dataset ID 只是 Provider 外部 ID。
5. Resource API 是 KnowledgeBase identity 的 canonical source。
6. Agent / Workflow 对 KB 的使用必须进入 `resource_dependencies` 或等价 canonical dependency model。
7. Run 创建时必须冻结实际 Knowledge Revision。
8. LIVE 依赖也只能在新 Run 开始时解析最新版本，运行中不得漂移。
9. Agent Runtime 默认只读知识。
10. 模型不得指定或枚举任意 Provider dataset ID。
11. Effective Knowledge Scope 必须同时考虑 Resource Dependency、Caller Permission、Workflow Policy、Runtime Authorization。
12. Shared Agent 使用 Caller 的知识权限，绝不能继承 Owner 私有知识权限。
13. Sub-Agent delegation 不得扩大 Knowledge Scope。
14. Retrieval 必须生成可追溯 Evidence/Receipt。
15. 企业知识与 DeerFlow Memory 严格分离。
16. 内网模式默认禁止公网依赖与公网 egress。
17. RAGFlow Provider credentials 不进入 Resource、Prompt、Tool result、frontend response。
18. Published Revision 必须不可变，或具有等价的严格可复现保证。
19. 不允许用删除历史数据来规避 migration。
20. 所有上游 `deerflow.*` 修改必须先证明 Extension/Adapter 无法实现。

---

## IMPLEMENTATION ORDER

### Phase 0 — Reconnaissance

- Read applicable `AGENTS.md`.
- Locate current ResourceService, dependencies, Run Snapshot, AuthorizationProvider integration.
- Locate DeerFlow `knowledge_search`, RAGFlow client, Tool Receipt, Evidence UI.
- Create `docs/knowledge/IMPLEMENTATION_INVENTORY.md`.
- Do not start major implementation until inventory exists.

### Phase 1 — Runtime Smoke

- Deploy RAGFlow in intranet/dev.
- Configure existing DeerFlow knowledge retrieval.
- Verify `knowledge_search`.
- Verify Tool Receipt.
- Verify redaction.
- Verify no public egress.

### Phase 2 — KnowledgeBase Resource

- Add `ResourceType.KNOWLEDGE_BASE`.
- Add knowledge metadata/provider binding.
- Add owner/department/visibility/lifecycle behavior.
- Extend Resource API and tests.
- Bind existing RAGFlow dataset manually for first smoke.

### Phase 3 — Dependencies and Effective Scope

- Add `AGENT -> KNOWLEDGE_BASE`.
- Add `WORKFLOW -> KNOWLEDGE_BASE`.
- Add LIVE/PINNED semantics.
- Compute Effective Knowledge Scope at Run assembly.
- Convert logical KB scope to provider dataset allowlist server-side.
- Enforce again at retrieval runtime.

### Phase 4 — Knowledge Extension

- Implement AgentPlatform extension/adapter.
- Inject run-scoped knowledge context.
- Connect Resource Governance to DeerFlow retrieval.
- Do not change DeerFlow Harness unless absolutely necessary.

### Phase 5 — Document Management

- Implement upload/list/delete/reindex.
- Add Knowledge Center.
- Keep agent runtime read-only.

### Phase 6 — Revision

- Add Draft/Published Knowledge Revision.
- Generate manifest hash.
- Prefer immutable provider dataset for published production revision.
- Add publish gate.
- Add provider drift detection.

### Phase 7 — Run Snapshot

- Add KB UUID/revision/manifest/profile to Run Snapshot.
- Verify current Run never moves to newly published revision.

### Phase 8 — Retrieval Receipt

- Persist retrieval receipt linked to DeerFlow tool receipt.
- Capture KB, revision, document, chunk and scores.
- Add evidence UI.

### Phase 9 — Retrieval Test / Eval

- Add retrieval debugger.
- Add eval cases.
- Implement document hit / Recall@K / MRR first.
- Do not add complicated GraphRAG before baseline RAG is measured.

### Phase 10 — Offline Productization

- Add RAGFlow optional offline profile.
- Add images/dependencies/migrations/SBOM/checksums.
- Run real air-gap fresh install acceptance.

---

## CODE BOUNDARY

Preferred:

```text
deerflow.*                         upstream runtime

agentplatform.knowledge            control-plane service
agentplatform.resources            resource governance
agentplatform.workflows            workflow
agentplatform_extension.knowledge  runtime adapter
```

Do not create:

```text
deerflow.enterprise_knowledge
deerflow.resource_governance
```

---

## DATA MODEL MINIMUM

Implement semantically equivalent models:

```text
knowledge_bases
knowledge_base_revisions
knowledge_documents
knowledge_retrieval_receipts
```

Reuse:

```text
resources
resource_dependencies
run_resource_snapshots
```

Do not introduce a second canonical `knowledge_base` identity table detached from `resources.id`.

---

## AUTHORIZATION RULE

At run assembly:

```text
effective_kb_scope =
agent/workflow declared KB
∩ caller KB permission
∩ platform policy
∩ runtime authorization
```

At search execution:

```text
requested provider dataset
MUST belong to effective_kb_scope
```

Perform both checks.

---

## SEARCH RULE

Model-facing Tool should use:

```text
query
logical knowledge selection only if required
```

Never expose raw provider dataset ID.

---

## REVISION RULE

Every Run uses:

```text
resolved revision id
manifest hash
```

LIVE means resolve latest at Run start, not continuously live inside a Run.

---

## RECEIPT RULE

Every knowledge search must be attributable to:

```text
run
tool call
KB UUID
revision
query
document
chunk
score
```

Use DeerFlow Tool Receipt as the parent evidence mechanism.

---

## WRITE RULE

Agent runtime:

```text
READ ONLY
```

Human/API management surface:

```text
CREATE / UPLOAD / INDEX / DELETE / PUBLISH
```

Future autonomous learning:

```text
Agent creates Draft only
→ Review
→ Eval
→ Approval
→ Publish
```

---

## TEST RULE

Do not mark complete based only on final answer quality.

For every test verify separately:

```text
scope
retrieval
evidence
answer
```

Mandatory high-risk tests:

- caller/owner separation;
- hidden KB enumeration;
- raw dataset ID injection;
- shared Agent;
- Workflow;
- Sub-Agent;
- LIVE/PINNED;
- revision drift;
- provider failure vs zero results;
- credential redaction;
- offline no-egress.

---

## OUT OF SCOPE FOR V1

Do not implement unless required by an existing acceptance case:

```text
GraphRAG
Knowledge Graph
RAPTOR
Document-level ACL
Agent auto-publish knowledge
Multi-provider federation
Full connector marketplace
Complex LLM KB router
```

---

## FINAL SUCCESS CRITERIA

V1 is complete only if:

```text
KnowledgeBase is a governed Resource
Agent/Workflow dependency works
Caller boundary works
DeerFlow knowledge_search is reused
RAGFlow is provider-only
Published revision is reproducible
Run snapshots knowledge
Retrieval evidence is traceable
Knowledge Center works
Evaluation works
Offline deployment works
Existing Agent/Skill/Workflow behavior has no regression
```

---

# 111. 建议的最终 Definition of Product Value

知识库能力开发完成后，AgentPlatform 不只是：

> “能对企业文档做 RAG”。

而应做到：

> **能够治理企业知识资产、控制 Agent 可使用的知识边界、冻结业务运行所依赖的知识版本，并对每一个 AI 结论追溯到具体知识版本、文档和检索证据。**

这与 AgentPlatform 已有 Resource Governance / Workflow / Run Evidence 路线保持一致，也能形成区别于普通 RAG 平台的真正企业级价值。

---

# 112. 参考资料

## DeerFlow

- Main Repository  
  https://github.com/bytedance/deer-flow
- CHANGELOG — current main knowledge/RAGFlow capability  
  https://github.com/bytedance/deer-flow/blob/main/CHANGELOG.md
- RAGFlow Integration RFC  
  https://github.com/bytedance/deer-flow/issues/4900

## AgentPlatform

- Repository  
  https://github.com/Neowyh/AgentPlatform
- 执行时必须以**收敛后的最新 `develop`** 中的：
  - `AGENTS.md`
  - Resource Governance ADR
  - ResourceService
  - AuthorizationProvider adapter
  - Run Snapshot
  - Workflow
  - Offline deployment
  为实际代码真源。

---

# 113. 最后原则

遇到任何设计选择时，Coding Agent 应按以下顺序判断：

```text
1. DeerFlow 上游 Runtime 已经解决了吗？
      Yes → 复用
      No  → 下一步

2. 能通过 AgentPlatform Extension / Adapter 实现吗？
      Yes → Extension / Adapter
      No  → 下一步

3. 这是 AgentPlatform 企业产品价值吗？
      Yes → Control Plane / Workflow / Resource 层实现
      No  → 不实现或向上游贡献
```

知识库建设应始终保证：

```text
Runtime 尽量上游化
Governance 明确本地化
Provider 可替换
Data Scope 最小化
Execution 可追溯
Offline 可交付
```

这才是 AgentPlatform 在完成 DeerFlow 上游收敛之后，继续向企业级智能体平台演进的合理路径。
