# AgentPlatform 总体架构与模块边界基线

> **文档性质**：总体架构基线 / 模块边界基线 / 开发约束基线  
> **适用对象**：架构设计人员、项目维护者、Coding Agent、测试人员、部署人员  
> **适用版本**：DeerFlow `main` 已收敛进入 AgentPlatform `develop` 后的目标架构  
> **制定日期**：2026-09-06  
> **状态**：Baseline v1.0

---

# 1. 文档目的

本基线用于统一以下三项建设工作的总体架构、模块职责、数据真源、依赖方向和接口边界：

1. DeerFlow `main` → AgentPlatform `develop` Runtime 收敛；
2. AgentPlatform 企业知识库能力建设；
3. AgentPlatform Local Runtime / 桌面执行代理建设。

三项工作不得作为三个彼此独立的子系统分别演进。

其统一关系为：

```text
DeerFlow 收敛
    │
    ▼
建立唯一 Server Agent Runtime
    │
    ▼
AgentPlatform Control Plane / Workflow / Extension
    │
    ├───────────────┐
    ▼               ▼
Knowledge         Local Runtime
知识能力           用户设备执行能力
```

其中：

- **DeerFlow 收敛方案定义运行时基础和上游边界；**
- **知识库方案扩展企业 Resource Governance；**
- **Local Runtime 方案扩展 Execution Plane。**

知识库和 Local Runtime 均不得重新形成独立 Agent Runtime。

---

# 2. 总体架构目标

AgentPlatform 的最终定位不是 DeerFlow 的长期 Fork，也不是 DeerFlow 外再建设一套 Agent Runtime。

目标架构应满足：

```text
AgentPlatform
=
DeerFlow Runtime
+
Enterprise Control Plane
+
Workflow
+
Enterprise Extensions
+
Knowledge Governance
+
User Device Execution Plane
+
Business Packages
+
Offline / Intranet Distribution
```

其中 DeerFlow 作为唯一 Server Agent Runtime 真源，AgentPlatform 长期保留的差异应主要集中于企业资源治理、Workflow、企业策略、业务包、扩展适配和内网发行，而不是重新维护 Memory、Sub-Agent、MCP、Guardrail、Sandbox、Run/Checkpoint 等通用 Runtime Fork。该方向与 DeerFlow 收敛方案定义的目标边界一致。fileciteturn3file1L103-L130

---

# 3. 架构基本原则

本项目所有设计、编码、评审和重构必须遵守以下原则。

## 3.1 Upstream First

```text
deerflow.*
=
唯一 Server Agent Runtime 真源
```

以下通用运行时能力原则上由 DeerFlow 提供：

- Lead Agent；
- Sub-Agent Runtime；
- Memory；
- Skill Runtime；
- MCP Runtime；
- Sandbox；
- Guardrail；
- Context Engineering；
- Tool Assembly；
- Tool Runtime；
- Runtime Authorization；
- Run；
- Checkpoint；
- Scheduler；
- Tool Receipt；
- Artifact Receipt。

AgentPlatform 不应长期维护上述能力的平行实现。

---

## 3.2 AgentPlatform Owns Enterprise Semantics

AgentPlatform 负责：

```text
谁拥有资源
谁能看到
谁能使用
使用哪个版本
资源如何审批和发布
Workflow 如何组织任务
Run 使用了哪些资源
企业策略如何约束 Runtime
最终结果如何审计和追溯
```

Control Plane 是 AgentPlatform 的核心产品层，而不是 DeerFlow Runtime 的替代层。

---

## 3.3 Extension Before Fork

AgentPlatform 与 DeerFlow Runtime 的集成优先级固定为：

```text
Extension
    ↓
Adapter
    ↓
Focused Runtime Patch
```

只有 Extension / Adapter 明确无法满足要求时，才允许修改：

```text
backend/packages/harness/deerflow/**
```

所有此类修改必须登记 Upstream Patch Ledger，并具有测试、原因、Owner 和移除条件。

---

## 3.4 One Identity, One Governance

同一种企业对象不得形成两个身份真源。

禁止出现：

```text
AgentPlatform Skill Catalog
+
DeerFlow Skill Catalog
```

或：

```text
AgentPlatform KnowledgeBase
+
RAGFlow Dataset 直接作为业务 KnowledgeBase ID
```

企业身份统一由 AgentPlatform Control Plane 管理。

---

## 3.5 Server Orchestrates, Execution May Move

Agent 的：

```text
Planning
Reasoning
Workflow
Memory
Resource Resolution
Authorization
```

默认在 Server 完成。

实际执行位置可以变化：

```text
SERVER
USER_DEVICE
```

因此必须把：

```text
ExecutionTarget
```

建设为正式运行维度。

---

## 3.6 Data Should Move Less Than Computation

对于大型、敏感或本地专有数据，优先：

```text
数据留在本地
↓
计算下沉到 Local Runtime
↓
仅返回必要结果 / Evidence
```

不得为了让 Agent 工作而默认上传完整本地数据。

---

## 3.7 Everything Important Must Be Provable

运行结果必须能够回答：

```text
谁发起？
使用哪个 Agent？
使用哪个 Skill？
用了哪个知识版本？
调用了什么 Tool？
在哪里执行？
由谁授权？
生成了什么 Artifact？
依据什么证据得到结论？
```

所有关键行为最终进入统一：

```text
Run Evidence
```

---

# 4. 最终总体架构

```text
┌──────────────────────────────────────────────────────────────┐
│                    AgentPlatform UI                          │
│                                                              │
│ Chat / Builder / Resource Center / Workflow / Knowledge      │
│ Admin / Device / Run History / Evidence                      │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│               AgentPlatform Control Plane                    │
│                                                              │
│ Identity                                                     │
│ ├── User                                                     │
│ ├── Department                                               │
│ └── Device                                                   │
│                                                              │
│ Resource Governance                                          │
│ ├── Skill                                                    │
│ ├── Agent                                                    │
│ ├── Workflow                                                 │
│ └── KnowledgeBase                                            │
│                                                              │
│ Governance                                                   │
│ UUID / Owner / Visibility / ACL                              │
│ Draft / Publish / Approval / Archive                         │
│ Version / Revision / Dependency                              │
│ Run Snapshot / Audit / Eval                                  │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                   Workflow Plane                             │
│                                                              │
│ deterministic / semi-agentic orchestration                   │
│                                                              │
│ Step                                                         │
│ ├── Agent / Tool / Knowledge                                 │
│ ├── ExecutionTarget                                          │
│ ├── Policy Gate                                              │
│ ├── Human Gate                                               │
│ ├── Timeout / Retry                                          │
│ └── Fallback                                                 │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│             AgentPlatform Extension Layer                    │
│                                                              │
│ Resource Resolver                                            │
│ Enterprise Authorization                                     │
│ Resource Snapshot                                            │
│ Knowledge Extension                                          │
│ Local Runtime Extension                                      │
│ Workflow Observer                                            │
│ Network Policy                                               │
│ Evidence / Audit / Provenance                                │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    DeerFlow Runtime                          │
│                                                              │
│ Lead Agent / Sub-Agent                                       │
│ Skill / MCP / Memory                                         │
│ Tool Assembly / Runtime                                      │
│ Sandbox / Guardrail                                          │
│ Context / Authz                                              │
│ Run / Checkpoint / Scheduler                                 │
│ Tool Receipt / Artifact Receipt                              │
└───────────────┬─────────────────────────────┬────────────────┘
                │                             │
          SERVER Execution             USER_DEVICE Execution
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌──────────────────────────────┐
│ Server Execution Plane    │   │ AgentPlatform Local Runtime  │
│                           │   │                              │
│ Server Sandbox            │   │ Device Identity              │
│ Server Tools              │   │ Session / Heartbeat          │
│ Server MCP                │   │ Local Policy / Consent       │
│ Server Secrets            │   │ Local Sandbox                │
│                           │   │                              │
│ Server Knowledge          │   │ Local Files                  │
│      │                    │   │ Local Python                 │
│      ▼                    │   │ Local MCP                    │
│ KnowledgeProvider         │   │ Local Secrets                │
│      │                    │   │ Local Knowledge              │
│      ▼                    │   │                              │
│ RAGFlow / Other Provider  │   │ Execution Receipt            │
└──────────────┬────────────┘   └───────────────┬──────────────┘
               │                                │
               └──────────────┬─────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                        Run Evidence                          │
│                                                              │
│ Resource Snapshot                                            │
│ Knowledge Snapshot                                           │
│ Runtime Assembly Fingerprint                                 │
│ Authorization Context                                        │
│ Tool Receipt                                                 │
│ Knowledge Retrieval Receipt                                  │
│ Local Execution Receipt                                      │
│ Artifact Receipt                                             │
│ Sub-Agent Verification                                       │
│ Business Provenance                                          │
└──────────────────────────────────────────────────────────────┘
```

该结构是在 DeerFlow 收敛方案既定的 UI → Control Plane → Workflow → Extension → DeerFlow Runtime 分层基础上，加入 Knowledge 和 Local Execution Plane。fileciteturn3file0L46-L70

---

# 5. 核心概念模型

最终平台围绕以下核心问题组织：

```text
Skill
怎么做

Knowledge
知道什么

Tool
能做什么

Agent
谁来做

Workflow
如何组织做

ExecutionTarget
在哪里做

Evidence
凭什么可信
```

其关系为：

```text
          Skill        Knowledge        Tool
            \              |             /
             \             |            /
                    Agent
                   谁来做
                      │
                      ▼
                  Workflow
                如何组织做
                      │
                      ▼
               ExecutionTarget
                  在哪里做
                 /        \
             SERVER      DEVICE
                \          /
                 \        /
                 Run Evidence
```

---

# 6. Control Plane 边界

## 6.1 Identity Entity

Identity / Control Plane 至少包括：

```text
User
Department
Device
```

Device 是 Control Plane Entity，不属于 Resource。

禁止：

```text
Resource
├── Agent
├── Skill
├── Workflow
├── KnowledgeBase
└── Device      ×
```

正确模型：

```text
Identity
├── User
├── Department
└── Device

Resource
├── Skill
├── Agent
├── Workflow
└── KnowledgeBase
```

---

# 7. Resource Governance 基线

## 7.1 四类一等 Resource

统一 Resource 模型为：

```text
Resource
├── Skill
├── Agent
├── Workflow
└── KnowledgeBase
```

KnowledgeBase 必须正式进入 Resource Governance，而不得建设独立、平行身份体系。知识库方案已明确 KnowledgeBase 是第四类一等 Resource。fileciteturn3file6L831-L846

四类 Resource 统一继承：

- stable UUID；
- owner；
- department；
- visibility；
- lifecycle；
- draft；
- published version；
- approval；
- archive；
- dependency；
- content hash；
- audit；
- Run Snapshot。

---

## 7.2 Canonical Resource API

Resource identity 的 canonical source 必须保持：

```text
/api/resources
```

Knowledge 可以具有 convenience API，但不得形成：

```text
/api/knowledge-bases
```

作为第二身份真源。知识库方案对此已有明确约束。fileciteturn4file6L891-L908

---

# 8. Source of Truth 基线

| 对象 | Canonical Source |
|---|---|
| Agent Identity | AgentPlatform Resource |
| Skill Identity | AgentPlatform Resource |
| Workflow Identity | AgentPlatform Resource |
| KnowledgeBase Identity | AgentPlatform Resource |
| Device Identity | AgentPlatform Control Plane |
| Agent Runtime | DeerFlow |
| Skill Runtime | DeerFlow |
| Memory Runtime | DeerFlow |
| Sub-Agent Runtime | DeerFlow |
| Server MCP Runtime | DeerFlow |
| Server Sandbox | DeerFlow |
| Workflow Definition | AgentPlatform |
| Enterprise ACL | AgentPlatform |
| Knowledge Revision | AgentPlatform |
| RAG Index State | Knowledge Provider |
| Device Capability | Device + AgentPlatform Session State |
| Local Policy | Local Runtime |
| Local Secret Value | User Device OS Secure Store |
| Tool Receipt | DeerFlow Runtime |
| Enterprise Run Evidence | AgentPlatform Evidence Layer |

任何新增模块必须明确自己的 Source of Truth，不允许“双主”。

---

# 9. Workflow Plane 边界

Workflow 是 AgentPlatform 一等 Resource。

Workflow 负责：

```text
任务步骤
确定性流程
业务门禁
人工确认
Agent调用关系
知识版本要求
ExecutionTarget
失败策略
```

Workflow 不负责重新实现：

```text
Agent reasoning loop
Sub-Agent concurrency runtime
Memory runtime
Tool runtime
```

上述能力属于 DeerFlow。

---

# 10. ExecutionTarget 基线

ExecutionTarget 是 AgentPlatform 新的一等运行属性。

第一阶段：

```text
SERVER
USER_DEVICE
```

未来可扩展：

```text
EDGE_NODE
GPU_WORKSTATION
LAB_DEVICE
SERVER_INTERNAL
```

Workflow Step 可声明：

```text
execution_target
requires_device_online
requires_user_consent
timeout
retry
fallback
```

Local Runtime 方案已经要求 Workflow 支持 `USER_DEVICE`。fileciteturn2file10L1337-L1361

---

# 11. Extension Layer 边界

Extension Layer 是 AgentPlatform 和 DeerFlow Runtime 的正式集成边界。

建议：

```text
agentplatform-extension/
└── agentplatform_extension/
    ├── resource_snapshot.py
    ├── authorization.py
    ├── audit.py
    ├── provenance.py
    ├── network_policy.py
    ├── workflow_observer.py
    │
    ├── knowledge/
    │   ├── context.py
    │   ├── scope.py
    │   ├── runtime_adapter.py
    │   ├── receipts.py
    │   └── provenance.py
    │
    └── local_runtime/
        ├── tools.py
        ├── authorization.py
        ├── routing.py
        ├── receipts.py
        └── provenance.py
```

Extension Layer 可以：

- 注入企业 Policy；
- 解析 Resource Snapshot；
- 做企业资源映射；
- 计算 Effective Scope；
- 注册 AgentPlatform Tool；
- 路由 Local Task；
- 观察 Runtime Lifecycle；
- 收集 Evidence。

Extension Layer 不得重新实现：

- Lead Agent；
- Memory；
- Sub-Agent Runtime；
- Generic MCP Runtime；
- Sandbox Core；
- Scheduler；
- Checkpoint。

---

# 12. Knowledge Architecture 基线

## 12.1 三层职责

知识能力必须分为：

```text
AgentPlatform
→ Knowledge Governance

Knowledge Provider
→ Knowledge Processing / Retrieval

DeerFlow
→ Agent Runtime Integration
```

具体：

### AgentPlatform

负责：

- KB UUID；
- Owner；
- Department；
- Visibility；
- Revision；
- Dependency；
- Approval；
- Run Snapshot；
- Effective Knowledge Scope；
- Retrieval Receipt；
- Eval；
- Audit。

### Provider

负责：

- Parse；
- Chunk；
- Embedding；
- Index；
- Hybrid Retrieval；
- Rerank。

### DeerFlow

负责：

- `knowledge_search` Tool Runtime；
- Tool Authorization；
- Context Engineering；
- Tool Receipt；
- Agent / Sub-Agent 调用。

这一职责划分与知识库方案一致。fileciteturn3file7L901-L935

---

# 13. KnowledgeProvider 基线

KnowledgeBase 不绑定具体 RAG 产品身份。

统一模型：

```text
KnowledgeBase
├── location
└── provider_type
```

例如：

```text
KB-A
location = SERVER
provider = RAGFLOW

KB-B
location = USER_DEVICE
provider = LOCAL
```

因此应支持：

```text
KnowledgeProvider
├── RAGFlowKnowledgeProvider
└── LocalKnowledgeProvider
```

第一阶段 Server Provider 可使用 RAGFlow，但 AgentPlatform 不得写死为 RAGFlow 产品。

---

# 14. Knowledge Location 基线

统一定义：

```text
KnowledgeBase.location
=
SERVER
USER_DEVICE
```

## SERVER

```text
KnowledgeBase
↓
KnowledgeProvider
↓
RAGFlow
```

## USER_DEVICE

```text
KnowledgeBase
↓
Local Runtime
↓
LocalKnowledgeProvider
↓
Local Index
```

Local Runtime 方案已提出上述 Server / User Device 双位置模型。fileciteturn3file13L1677-L1719

---

# 15. 统一 Knowledge Search 语义

## 15.1 整合基线决策

模型层只暴露一个统一知识能力：

```text
knowledge_search
```

不得要求模型自己选择：

```text
knowledge_search
or
local.knowledge.search
```

模型也不得感知：

- Provider Dataset ID；
- raw Device ID；
- IP；
- Local Port；
- Local Path。

统一数据流：

```text
Agent
  │
  ▼
knowledge_search
  │
  ▼
Knowledge Scope Resolver
  │
  ├── SERVER
  │     ↓
  │   RAG Provider
  │
  └── USER_DEVICE
        ↓
      Local Runtime
        ↓
      Local Retriever
```

`local.knowledge.search` 可以作为内部 capability / routing key 存在，但不得作为业务层第二知识工具。

---

# 16. Knowledge Revision 基线

所有正式 KnowledgeBase，包括 Local Knowledge，都必须支持 Revision。

```text
Knowledge Revision
├── logical documents
├── content hashes
├── metadata
└── manifest hash
```

本地知识库即使原始文件从不上传 Server，也必须让 Server 能记录：

```text
KnowledgeBase UUID
Revision
Manifest Hash
Document Logical ID
Document Content Hash
Retrieval Receipt
```

原始文件仍可完全留在 Device。

这样：

```text
治理和可复现性在 Server
数据本体在 Device
```

---

# 17. Effective Knowledge Scope

知识范围不是 Tool 权限的简单同义词。

必须同时满足：

```text
Effective Knowledge Scope
=
Resource Dependency Scope
∩ Caller Knowledge Permission
∩ Workflow Policy
∩ Runtime Authorization
∩ Environment Availability
```

Knowledge Tool 权限只能回答：

```text
是否允许搜索知识？
```

KB ACL 负责回答：

```text
具体允许搜索哪些知识？
```

知识方案已经明确二者必须同时成立。fileciteturn4file6L1049-L1069

---

# 18. Local Runtime 定位

Local Runtime 是：

> User Device Execution Plane。

不是：

- Desktop AgentPlatform；
- 第二套 DeerFlow；
- Remote Desktop；
- RPA Platform；
- 远程系统管理工具。

Local Runtime 负责：

```text
Device Identity
Session
Heartbeat
Capability Registry
Local Policy
User Consent
Local Sandbox

Local Files
Local Python
Local MCP
Local Secrets
Local Knowledge

Execution Receipt
Local Audit
```

Server 继续负责：

```text
LLM
Lead Agent
Sub-Agent Orchestration
Memory
Workflow
Resource Governance
Authorization
Run
Evidence
```

Local Runtime 方案明确使用该职责划分。fileciteturn2file3L258-L286

---

# 19. Local Runtime 通信边界

禁止：

```text
Server
→ User PC IP:Port
```

统一采用：

```text
Local Runtime
→ outbound authenticated WSS
→ AgentPlatform Broker
```

服务器不主动扫描、连接用户终端。

Local Runtime 负责主动建立可信连接。

---

# 20. Local Tool 基线

第一阶段允许：

```text
local.files.list
local.files.read
local.files.write

local.python
```

后续：

```text
local.powershell
local.shell
```

必须独立经过更高安全级别评审。

禁止使用：

```text
unrestricted remote shell
```

作为 Local Runtime 基础 API。

---

# 21. File Security 基线

Local Runtime 默认不能访问整个磁盘。

用户必须显式配置：

```text
Allowed Roots
```

模型只使用逻辑路径：

```text
/projects
/quality
/downloads
```

不得向模型暴露：

```text
C:\Users\...
D:\...
```

每次访问必须验证：

- canonical path；
- traversal；
- symlink；
- junction；
- UNC；
- path normalization；
- case bypass。

---

# 22. MCP 总体边界

## 22.1 Server MCP

由 DeerFlow Runtime 负责。

例如：

```text
DeerFlow
↓
Server MCP
↓
Enterprise Service / Database / Server Tool
```

## 22.2 Local MCP

由 Local Runtime 作为 Device-side MCP Host / Client Manager。

例如：

```text
DeerFlow
↓
Local Tool
↓
Local Runtime
↓
stdio / localhost MCP
↓
MATLAB / CAD / Office / Git
```

## 22.3 整合基线决策

DeerFlow 是：

```text
Server-side MCP Runtime 真源
```

Local Runtime 是：

```text
Device-side MCP Execution Host
```

不得复制完整 DeerFlow MCP Runtime 到终端。

Local MCP 必须经过：

```text
Server
→ Local Task
→ Local Runtime
→ MCP
```

不得：

```text
Server
→ User PC localhost MCP
```

Local Runtime 原方案已明确该链路。fileciteturn3file13L1599-L1643

---

# 23. Authorization 总体模型

不得分别建设：

```text
Knowledge Authorization
Local Authorization
Tool Authorization
Workflow Authorization
```

四套互不相关体系。

统一分为三层。

## 23.1 Assembly Authorization

决定：

> 模型能看到什么。

```text
Effective Runtime Capability
=
Resource Declaration
∩ Caller Permission
∩ Workflow Policy
∩ Platform Policy
∩ ExecutionTarget Availability
∩ Environment Availability
∩ Network Policy
```

如果是 Local Tool，再加入：

```text
∩ Device Capability
```

无权能力必须在 Tool Assembly 时移除。

---

## 23.2 Resource Scope Authorization

决定：

> 一个允许调用的 Tool 能操作哪些 Resource/Data。

例如：

```text
Knowledge Scope
File Root Scope
MCP Server Scope
```

---

## 23.3 Local Authorization

Device 收到 Local Task 后再次判断：

```text
trusted server
valid session
valid task
capability
allowed root
command policy
network policy
local secret policy
user consent
```

原则：

```text
Local DENY
>
Server ALLOW
```

服务端授权只能允许“委派”，不能强制 Device 真正执行。

---

# 24. User Consent 基线

操作风险至少分为：

```text
Level 0
Safe Read

Level 1
Modify / Execute

Level 2
Dangerous
```

建议：

### Level 0

可根据策略自动执行：

- read；
- list；
- git status；
- knowledge retrieval。

### Level 1

本地策略决定：

```text
always allow
ask first
deny
```

### Level 2

默认：

```text
DENY
```

Consent 必须绑定：

```text
request_hash
```

防止授权内容与实际执行内容不一致。

---

# 25. Secret 边界

Server Secret 与 Local Secret 必须区分。

Local Secret 示例：

```text
Git Token
SSH Key
Database Password
MATLAB Credential
CAD Credential
```

Server 只能看到：

```text
local:git.company
local:ssh.projectA
```

不得看到 Secret 明文。

本地 Secret Value 必须保存于 OS 安全存储，例如：

```text
Windows Credential Manager
DPAPI
```

---

# 26. Evidence 总体模型

## 26.1 单一 Run Evidence

禁止形成多个彼此平行的：

```text
Runtime Log
Knowledge Log
Local Log
Workflow Log
```

所有正式执行证据统一进入：

```text
Run Evidence
```

---

## 26.2 Evidence 结构

```text
Run Evidence
│
├── Resource Snapshot
├── Knowledge Snapshot
├── Runtime Assembly Fingerprint
├── Authorization Context
├── Policy Revision
│
├── Tool Receipt
│    │
│    ├── Knowledge Retrieval Receipt
│    │
│    ├── Local Execution Receipt
│    │
│    └── Artifact Receipt
│
├── Sub-Agent Verification
└── Business Provenance
```

知识方案明确要求 Knowledge Retrieval Receipt 不得成为独立平行证据系统，而应进入 DeerFlow Tool Receipt / Run Evidence。fileciteturn4file4L413-L445

---

# 27. Local Knowledge Evidence

Local Knowledge Retrieval 同时属于：

```text
Tool Call
+
Local Execution
+
Knowledge Retrieval
```

因此推荐结构：

```text
Tool Receipt
    │
    ▼
Local Execution Receipt
    │
    ▼
Knowledge Retrieval Receipt
```

而不是三条互不相关的日志。

---

# 28. Sub-Agent 边界

Server Sub-Agent Runtime 由 DeerFlow 提供。

AgentPlatform 负责：

```text
哪个 Agent 可委派给谁
企业可见性
业务 delegation policy
resource dependency
caller boundary
```

禁止 Sub-Agent Delegation 扩权。

其有效权限必须满足：

```text
SubAgent Effective Scope
⊆
Parent Run Effective Scope
```

知识范围同样不得因 Delegation 扩大。

---

# 29. Local Worker V3 边界

## 29.1 整合基线决策

未来允许：

```text
Local Worker
```

用于：

- 50GB 数据处理；
- 大型代码仓处理；
- MATLAB 长任务；
- CAD 长任务；
- durable local job。

但 Local Worker 不得演进成完整 Local DeerFlow。

必须继续由 Server 保持：

```text
Lead Agent
Memory Truth
Workflow Truth
Resource Governance
Enterprise Authorization
Run Truth
```

因此：

```text
Local Worker
≠
Local AgentPlatform
≠
Second DeerFlow
```

---

# 30. Memory 与 Knowledge 边界

Memory 和 Knowledge 必须严格区分。

## Memory

回答：

```text
这个用户 / Agent 过去经历了什么？
```

由 DeerFlow Memory Runtime 管理。

## Knowledge

回答：

```text
企业正式知道什么？
```

由 AgentPlatform Knowledge Governance + Provider 管理。

禁止：

- 用 Memory 替代正式企业知识库；
- 把 Knowledge Revision 写入 Memory；
- 把企业正式文档作为私人 Memory 事实管理。

---

# 31. Skill 与 Knowledge 的渐进式披露

平台应统一采用 Progressive Disclosure 思路。

Skill：

```text
Resource Resolver
→ Enabled Skill Projection
→ DeerFlow SkillScan
→ describe_skill
```

Knowledge：

```text
Resource Dependency
→ Effective Knowledge Scope
→ Knowledge Routing
→ Top Candidate KB
→ Retrieval
```

两者共同原则：

> 模型只看到当前任务有权、且有必要看到的能力和知识。

---

# 32. 推荐 Server 代码边界

```text
backend/
│
├── packages/
│   │
│   ├── harness/
│   │   └── deerflow/
│   │       # upstream-first runtime
│   │
│   ├── extension-api/
│   │
│   └── agentplatform-extension/
│       └── agentplatform_extension/
│           ├── resource_snapshot.py
│           ├── authorization.py
│           ├── audit.py
│           ├── provenance.py
│           ├── network_policy.py
│           ├── workflow_observer.py
│           │
│           ├── knowledge/
│           │   ├── context.py
│           │   ├── scope.py
│           │   ├── runtime_adapter.py
│           │   ├── receipts.py
│           │   └── provenance.py
│           │
│           └── local_runtime/
│               ├── tools.py
│               ├── routing.py
│               ├── authorization.py
│               ├── receipts.py
│               └── provenance.py
│
├── app/
│   │
│   ├── resources/
│   │
│   ├── workflows/
│   │
│   ├── knowledge/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── provider.py
│   │   ├── ragflow_provider.py
│   │   ├── revisions.py
│   │   ├── retrieval.py
│   │   ├── receipts.py
│   │   └── evals.py
│   │
│   ├── devices/
│   │   ├── models.py
│   │   ├── service.py
│   │   └── pairing.py
│   │
│   └── local_runtime/
│       ├── broker.py
│       ├── connection.py
│       ├── tasks.py
│       ├── service.py
│       └── receipts.py
│
└── alembic/
```

---

# 33. Local Runtime 代码边界

Local Runtime 独立于 Web Frontend 和 DeerFlow Harness：

```text
local-runtime/
├── core/
├── transport/
├── policy/
├── receipts/
├── storage/
│
├── capabilities/
│   ├── files/
│   ├── exec/
│   ├── mcp/
│   ├── secrets/
│   └── knowledge/
│
├── tray/
└── tests/
```

不得放入：

```text
frontend/
```

不得成为：

```text
backend/packages/harness/deerflow/
```

的一部分。

---

# 34. 依赖方向

必须遵循：

```text
UI
↓
App / Control Plane
↓
Workflow
↓
Extension / Adapter
↓
DeerFlow Runtime
```

Knowledge：

```text
Control Plane
↓
Knowledge Service
↓
Provider Adapter
↓
RAG Provider
```

Local Runtime：

```text
DeerFlow Tool
↓
AgentPlatform Local Extension
↓
Local Runtime Broker
↓
Device Runtime
```

禁止反向依赖：

```text
DeerFlow Runtime
→ AgentPlatform Knowledge ORM      ×

DeerFlow Runtime
→ Device DB                       ×

RAGFlow
→ Resource Governance             ×

Local Runtime
→ Workflow Truth                  ×
```

---

# 35. 部署拓扑

## Server

至少：

```text
AgentPlatform Gateway
DeerFlow Runtime
PostgreSQL
Internal vLLM / Qwen
Knowledge Provider / RAGFlow
File/Object Storage
Redis optional
```

## User Device

按需安装：

```text
AgentPlatform Local Runtime
Tray
Local MCP
Local Index
```

普通用户仍然可以：

```text
Web Only
```

需要本地能力的用户：

```text
Web + Local Runtime
```

因此 Local Runtime 永远是可选组件，不得成为 AgentPlatform Web 使用的强制前置条件。

---

# 36. Offline / Intranet 基线

默认：

```text
NO PUBLIC EGRESS
```

Server 和 Local Runtime 均不得依赖：

- GitHub；
- PyPI Public；
- npm Public；
- Cloud-only API；
- Public Search；
- Public MCP。

允许：

```text
AgentPlatform Server
localhost MCP
approved intranet
internal package registry
internal model endpoint
```

最终 Offline Distribution 应包含：

```text
Server images
Python wheels
Frontend assets
Internal model config
RAG Provider package
Resource packages
Knowledge package（如需要）
Local Runtime installer
Extensions
Config
Migration
SBOM
Checksums
Version Manifest
```

---

# 37. 三方案冲突统一决策

## Decision 1：Knowledge Tool 只保留一个业务语义

统一：

```text
knowledge_search
```

`local.knowledge.search` 仅作为内部 capability。

---

## Decision 2：MCP 按执行位置划分

```text
Server MCP
→ DeerFlow

Device MCP
→ Local Runtime
```

不得建设第二套企业 MCP Governance。

---

## Decision 3：Authorization 统一

Server 统一：

```text
Assembly Authorization
+
Resource Scope Authorization
```

Local Runtime 只有：

```text
Local Veto / Consent
```

不另建企业 RBAC。

---

## Decision 4：Evidence 统一

```text
Tool Receipt
Knowledge Receipt
Local Receipt
Artifact Receipt
```

全部进入：

```text
Run Evidence
```

---

## Decision 5：Local Knowledge 必须版本化

Local KB 不能仅依赖“当前文件夹状态”。

必须保留：

```text
UUID
Revision
Manifest Hash
Document Hash
Retrieval Receipt
```

---

## Decision 6：Local Worker 不是第二套 Runtime

未来 Local Worker 只能扩展执行能力。

不得复制：

```text
Lead Agent
Memory
Workflow
Control Plane
```

---

# 38. 实施顺序基线

三项方案不得完全并行无序开发。

推荐顺序：

```text
Phase 0
DeerFlow main 收敛
        ↓
Phase 1
Control Plane / Resource / Workflow 稳定
        ↓
Phase 2
Extension API 与 AgentPlatform Extension
        ↓
Phase 3
Server Knowledge Runtime Smoke
        ↓
Phase 4
KnowledgeBase Resource Governance
        ↓
Phase 5
Knowledge Revision / Dependency / Scope / Receipt
        ↓
Phase 6
Device Control Plane
        ↓
Phase 7
Secure WSS / Local Task
        ↓
Phase 8
Local Files
        ↓
Phase 9
Local Python
        ↓
Phase 10
Local Tool Integration
        ↓
Phase 11
Local MCP / Local Secret
        ↓
Phase 12
Workflow ExecutionTarget
        ↓
Phase 13
Local Knowledge
        ↓
Phase 14
Unified Evidence / E2E
        ↓
Phase 15
Offline Distribution
```

尤其：

> Local Knowledge 不得早于 KnowledgeBase 基础治理。

Local Runtime 原方案也明确将 Local Knowledge 建立在 KnowledgeBase 基础能力完成之后。fileciteturn2file7L774-L818

---

# 39. Business E2E 基线

以故障归零作为综合验收场景。

```text
User
│
▼
Fault Zeroing Workflow
│
├── Server Knowledge
│   ├── 企业规范
│   └── 历史故障案例
│
├── Local Execution
│   ├── 20GB Test Data
│   ├── Python
│   ├── MATLAB
│   └── Project Files
│
▼
Server Agent Reasoning
│
▼
Workflow Gate
│
▼
Report
│
▼
Run Evidence
```

必须证明：

1. 知识版本正确；
2. ExecutionTarget 正确；
3. 权限正确；
4. Device 正确；
5. 本地数据未越界；
6. Local Secret 未泄漏；
7. 本地执行可取消和超时；
8. Knowledge Evidence 可追踪；
9. Artifact 可验证；
10. 最终结论可回溯到输入和执行证据。

---

# 40. 架构不变量

以下规则作为项目级 Non-Negotiable Architecture Invariants。

1. `deerflow.*` 是唯一 Server Agent Runtime 真源。
2. AgentPlatform 不长期维护 Memory / Sub-Agent / MCP / Sandbox / Scheduler Fork。
3. KnowledgeBase 是第四类一等 Resource。
4. Device 是 Control Plane Entity，不是 Resource。
5. Resource API 是企业 Resource Identity 真源。
6. RAG Provider ID 不得成为企业 KnowledgeBase ID。
7. Workflow 是一等 Resource。
8. ExecutionTarget 是正式运行维度。
9. Local Runtime 是 Execution Plane，不是第二套 DeerFlow。
10. Server 不主动连接用户 PC。
11. 模型不得指定 raw Device ID、IP、Local Port。
12. 模型不得指定 Provider Dataset ID。
13. 模型业务层统一使用 `knowledge_search`。
14. Local Knowledge 服从统一 KnowledgeBase Governance。
15. 所有正式 KB 必须具有 Revision / Snapshot 语义。
16. Shared Agent 使用 Caller 权限，而不是 Owner 私有权限。
17. Sub-Agent Delegation 不得扩权。
18. 无权 Tool 必须在 Assembly 阶段不可见。
19. Server Authorization 和 Local Authorization 必须同时通过。
20. Local DENY 永远优先。
21. Local Files 只能访问 Allowed Roots。
22. 不提供隐藏的任意远程 Shell。
23. Local Secret 明文不得离开 Device。
24. Local MCP 不直接暴露给中心 Server。
25. Knowledge Retrieval 必须生成 Receipt。
26. Local Execution 必须生成 Receipt。
27. Evidence 不得形成多个平行真源。
28. 所有关键 Evidence 必须最终关联到 Run。
29. 内网默认禁止公网 egress。
30. AgentPlatform 企业逻辑不得无理由写入 DeerFlow Harness。
31. Local Worker 不得演进成完整 Local Agent Runtime。
32. Offline Distribution 必须支持真实断网安装和运行。

---

# 41. 明确禁止的架构形态

禁止形成：

```text
AgentPlatform Runtime
+
DeerFlow Runtime
```

长期双 Runtime。

禁止：

```text
Server DeerFlow
+
Full Local DeerFlow
```

禁止：

```text
AgentPlatform KB
+
RAGFlow Dataset
```

两个业务身份源。

禁止：

```text
AgentPlatform Authorization
Knowledge Authorization
Local Authorization
Tool Authorization
```

彼此独立的四套 RBAC。

禁止：

```text
Tool Log
Knowledge Log
Local Log
Workflow Log
```

四套证据真源。

禁止：

```text
Server Tool
```

根据运行环境偷偷切换成 Local Tool。

执行位置必须显式。

---

# 42. 架构评审检查清单

每个新增模块必须回答以下问题：

### Ownership

```text
这个能力属于：
DeerFlow？
Control Plane？
Workflow？
Extension？
Provider？
Local Runtime？
```

### Identity

```text
谁是 canonical identity source？
```

### Runtime

```text
在哪里运行？
SERVER？
USER_DEVICE？
```

### Authorization

```text
谁决定模型是否看得到？
谁决定数据访问范围？
谁拥有最终 veto？
```

### Evidence

```text
执行结束后写入什么 Receipt？
最终如何进入 Run Evidence？
```

### Upgrade

```text
未来 DeerFlow upstream 升级时，
这个模块是否会造成 Runtime Fork？
```

无法明确回答上述问题的模块，不应直接进入正式架构。

---

# 43. 最终项目定位

完成本基线所描述的建设以后，AgentPlatform 不应被定义成：

> “DeerFlow 加了一些企业页面”。

也不应定义成：

> “一个能调用很多 Tool 的聊天系统”。

其最终定位应为：

> **基于 DeerFlow 上游 Agent Runtime 构建的企业级智能体控制、编排与执行平台。**

其中：

```text
DeerFlow
解决：
Agent 如何运行

AgentPlatform Control Plane
解决：
企业如何治理 Agent

Workflow
解决：
任务如何被可靠组织

Knowledge
解决：
Agent 能依据什么知识工作

Tool
解决：
Agent 能做什么

ExecutionTarget
解决：
任务在哪里真正执行

Local Runtime
解决：
如何安全使用用户设备能力

Run Evidence
解决：
整个过程为什么可信、可复现、可审计
```

最终形成：

```text
                AgentPlatform

 Skill       Knowledge       Tool
 怎么做        知道什么        能做什么
    \            |            /
     \           |           /
              Agent
             谁来做
                │
                ▼
             Workflow
            如何组织做
                │
                ▼
          ExecutionTarget
             在哪里做
             /      \
            /        \
        SERVER      DEVICE
          │            │
     DeerFlow       Local Runtime
          \            /
           \          /
            Run Evidence
             凭什么可信
```

---

# 44. 基线优先级

本文件作为三份专项实施方案的上位架构基线。

当专项方案中的局部设计与本基线发生冲突时：

```text
总体架构与模块边界
        >
专项实现细节
```

但本基线不替代专项方案中的：

- 数据库字段细节；
- API Schema；
- Migration；
- Security Test Matrix；
- Coding Agent Commit Sequence；
- Provider 参数；
- Local Protocol Envelope；
- 安装包制作细节。

专项方案继续作为对应模块的详细实施依据。

本基线负责回答：

> **“各模块为什么存在、应该放在哪里、谁拥有它、允许依赖谁、绝不能跨越什么边界。”**

---

# 45. Baseline Success Criteria

只有以下条件同时成立，才能认为 AgentPlatform 总体架构达到本基线目标：

```text
[ ] deerflow.* 已成为唯一 Server Runtime
[ ] ideer Runtime 已退出正式运行路径
[ ] Resource Governance 无语义回退
[ ] KnowledgeBase 已成为正式 Resource
[ ] Knowledge Revision / Snapshot 可工作
[ ] Server Knowledge Provider 可工作
[ ] Device Control Plane 可工作
[ ] Local Runtime 安全连接可工作
[ ] Local Files / Python 可工作
[ ] Local MCP 可工作
[ ] Workflow 支持 ExecutionTarget
[ ] Local Knowledge 复用统一 KB Governance
[ ] Tool Assembly 能正确裁剪权限
[ ] Local Policy 可以否决 Server
[ ] Knowledge / Local / Artifact Receipt 均进入 Run Evidence
[ ] Shared Agent Caller Boundary 正确
[ ] Sub-Agent 无权限扩张
[ ] 默认无公网依赖
[ ] Windows Local Runtime 可离线安装
[ ] Server 可真实 Air-Gapped 部署
[ ] 故障归零完整 E2E 通过
[ ] 后续 DeerFlow upstream 升级不需要重新维护大面积 Runtime Fork
```

至此，AgentPlatform 的架构边界稳定为：

```text
Upstream Runtime
        +
Enterprise Control Plane
        +
Workflow
        +
Enterprise Extension
        +
Knowledge Governance
        +
User Device Execution Plane
        +
Unified Evidence
        +
Offline Distribution
```

该架构作为后续 AgentPlatform 功能扩展、技术选型、代码评审和版本升级的统一基线。