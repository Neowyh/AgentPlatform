# AgentPlatform Local Runtime / 桌面执行代理建设实施方案（Coding Agent 版）

> 制定日期：2026-09-04  
> 前置条件：已完成 **DeerFlow `main` → AgentPlatform `develop` 收敛**，`deerflow.*` 已成为唯一 Runtime 真源；AgentPlatform 独有能力位于 Control Plane / Workflow / Extension / Business Package 层。  
> 目标：在不改变 AgentPlatform B/S 主架构的前提下，引入运行在用户终端 PC 上的 **AgentPlatform Local Runtime**，使服务端 Agent 能够安全、受控、可审计地执行本地脚本、访问本地文件、调用本机 MCP、使用本地工具和本地知识库。

---

## 1. 总体结论

当前 AgentPlatform / DeerFlow 的核心限制不是 B/S 架构本身，而是：

> **Agent Runtime 只存在于服务端，缺少 User Device Execution Plane。**

因此不建议把 AgentPlatform 整体改成 Electron/Tauri 桌面应用，也不建议在浏览器中直接开放 localhost 远程执行接口。

推荐新增独立子系统：

```text
AgentPlatform Local Runtime
```

其定位是：

> **面向终端设备的可信 Agent 执行节点。**

职责分工：

```text
Server
├── LLM / Lead Agent
├── Resource Governance
├── Workflow
├── Authorization
├── Run / Audit / Evidence
└── Local Runtime Broker

User Device
└── Local Runtime
    ├── Device Identity
    ├── Local Policy
    ├── User Consent
    ├── Local Files
    ├── Script Execution
    ├── Local MCP
    ├── Local Secrets
    ├── Local Knowledge
    └── Execution Receipt
```

核心安全原则：

> **服务端决定“是否允许委派”，本地端决定“是否允许真正执行”。**

两层授权必须同时通过。

---

## 2. 最终架构

```text
┌─────────────────────────────────────────────┐
│           AgentPlatform Server              │
│                                             │
│ Web / Gateway / DeerFlow Runtime            │
│ Resource / Workflow / Knowledge             │
│ Authorization / Run / Evidence              │
│                                             │
│          Local Runtime Broker               │
└────────────────────┬────────────────────────┘
                     │
              outbound WSS
                     │
                     ▼
┌─────────────────────────────────────────────┐
│        AgentPlatform Local Runtime          │
│                                             │
│ Device Identity / Session / Heartbeat       │
│ Capability Registry / Local Policy          │
│ User Consent / Local Sandbox                │
│                                             │
│ Local Files                                 │
│ Local Script / Python / PowerShell          │
│ Local MCP                                   │
│ Local Secrets                               │
│ Local Knowledge                             │
│ Local Execution Receipt                     │
└─────────────────────────────────────────────┘
```

Local Runtime 是**可选终端组件**：

```text
普通用户
→ 纯 Web

需要本地能力的用户
→ Web + Local Runtime
```

---

## 3. 新增三个核心概念

### 3.1 Device

Device 属于 Control Plane Entity，不与 Agent/Skill/Workflow/KnowledgeBase 混为同类 Resource。

建议：

```text
Identity / Control Plane
├── User
├── Department
└── Device

Resource
├── Agent
├── Skill
├── Workflow
└── KnowledgeBase
```

建议字段：

```text
devices
---------------------------------
id
user_id
device_name
os
os_version
architecture
runtime_version
status
last_seen_at
public_key
device_fingerprint
capabilities_json
policy_version
paired_at
revoked_at
created_at
updated_at
```

状态：

```text
PENDING
ONLINE
OFFLINE
REVOKED
BLOCKED
OUTDATED
```

### 3.2 ExecutionTarget

将“在哪里执行”显式化。

第一版：

```text
SERVER_SANDBOX
USER_DEVICE
```

未来：

```text
SERVER_INTERNAL
EDGE_NODE
GPU_WORKSTATION
LAB_DEVICE
```

模型不得指定 raw `device_id`、IP、端口。

模型只看到：

```text
local.files.read
local.python
local.git
local.mcp.*
local.knowledge.search
```

AgentPlatform 根据当前用户、Run 和已绑定设备进行路由。

### 3.3 Local Capability

Device 向 Server 报告可用能力，例如：

```json
{
  "capabilities": [
    "local.files.read",
    "local.files.write",
    "local.python",
    "local.powershell",
    "local.git",
    "local.office",
    "local.mcp",
    "local.knowledge"
  ]
}
```

最终可用能力：

```text
Effective Local Capability
=
Agent declared capability
∩ Caller authorization
∩ Device capability
∩ Device local policy
∩ Workflow policy
∩ Platform policy
```

只有最终交集进入 DeerFlow Tool Assembly。

---

## 4. 通信架构

禁止：

```text
Server → 用户 PC IP:Port
```

推荐：

```text
Local Runtime → AgentPlatform Server
```

使用终端主动发起的安全长连接。

MVP 推荐：

```text
WSS
```

未来如二进制流、大规模设备和双向 streaming 需求明显，再评估 gRPC bidirectional stream。

连接流程：

```text
Local Runtime Start
→ Load Device Identity
→ Authenticate
→ WSS Connect
→ Register Session
→ Capability Report
→ Heartbeat
→ Receive Task
```

---

## 5. Device Pairing

首次启动：

```text
Local Runtime
→ Generate device key pair
→ Request pairing session
→ Show pair code / browser URL
→ User logs into AgentPlatform
→ Confirm device
→ Server binds Device ↔ User
→ Device obtains short-lived session credential
```

不要使用永久明文 API Token。

推荐：

```text
device private key
+
server challenge
+
short-lived session token
```

高安全环境后续支持 mTLS / 企业 PKI。

---

## 6. Local Runtime Broker

服务端新增：

```text
Local Runtime Broker
```

职责：

```text
connection registry
device authentication
heartbeat
task routing
task lifecycle
cancel
timeout
streaming
receipt collection
offline handling
```

禁止 Broker 直接拥有：

```text
任意远程 shell
用户文件系统权限
用户 secret
```

---

## 7. Local Task Model

建议：

```text
local_tasks
---------------------------------
id
run_id
thread_id
tool_call_id
user_id
device_id
capability
task_type
payload_json
status
timeout_at
created_at
accepted_at
started_at
finished_at
result_summary
receipt_id
```

状态：

```text
QUEUED
DELIVERED
AWAITING_CONSENT
ACCEPTED
RUNNING
SUCCEEDED
FAILED
DENIED
CANCELLED
TIMED_OUT
DEVICE_OFFLINE
```

任何 Local Task 必须属于合法：

```text
Run + Tool Call + Caller + Device
```

不允许存在“后台管理员任意下发命令”的旁路。

---

## 8. 双重授权模型

### Server Authorization

检查：

```text
Caller permission
Agent declared capability
Workflow policy
Device ownership
Device online
Resource policy
Platform policy
```

无权能力在 Agent Assembly 阶段直接移除，使模型看不到。

### Local Authorization

终端收到任务后再次检查：

```text
trusted server
valid task/session
capability
allowed root
command policy
network policy
local consent
local secret policy
```

本地 DENY 永远优先。

---

## 9. User Consent 风险分级

### Level 0 — Safe Read

```text
list directory
read allowed file
git status
local knowledge search
```

默认可自动执行。

### Level 1 — Modify

```text
write file
run script
git checkout
Office edit
```

用户可配置：

```text
always allow
ask first
deny
```

### Level 2 — Dangerous

```text
arbitrary delete
registry
system config
network config
install software
service control
```

默认 DENY。

Consent 必须绑定本次 `request_hash`，不能用同一个授权批准被篡改后的任务。

---

## 10. Allowed Roots

禁止 Local Runtime 默认访问整块磁盘。

用户显式授权：

```text
D:\Projects
D:\Documents\Quality
C:\Users\Me\Downloads
```

对 Agent 暴露逻辑 Root：

```text
/projects
/quality
/downloads
```

每次访问必须基于 canonical resolved path 验证，防止：

```text
../
symlink escape
junction escape
UNC bypass
case/path normalization trick
```

---

## 11. Local File Tools

MVP：

```text
local.files.list
local.files.read
local.files.write
local.files.info
```

后续：

```text
local.files.copy
local.files.move
local.files.delete
```

删除类默认高风险。

不要让现有 Server `read_file` / `bash` 根据环境偷偷切换本地执行。

执行位置必须体现在 Tool 名称和 UI 中。

---

## 12. Local Script Execution

第一版优先：

```text
local.python
```

而不是直接开放任意 Shell。

建议 Payload：

```text
runtime
working_root
script / args
environment_refs
timeout
expected_outputs
```

Server 不传 secret 明文。

后续按需要增加：

```text
local.powershell
local.shell
```

并使用更严格 Policy。

---

## 13. Local Sandbox

MVP 不要求每台 Windows PC 安装 Docker。

先实现：

```text
allowed roots
working directory isolation
process timeout
child process cleanup
environment filtering
command allowlist/policy
network policy
```

高安全版本再考虑：

```text
restricted token
Windows Job Object
Windows Sandbox
WSL/container
```

---

## 14. Local MCP

Local Runtime 应成为本机 MCP Host / MCP Client Manager：

```text
Local Runtime
├── stdio MCP
└── localhost HTTP MCP
```

本地 MCP 示例：

```text
Git
Filesystem
MATLAB
CAD
Office
Database
```

正确链路：

```text
Server
→ Local Task
→ Local Runtime
→ stdio / localhost MCP
```

禁止：

```text
Server → 用户 PC:3000/mcp
```

Local Runtime 上报 Tool 能力：

```text
local.mcp.git.status
local.mcp.git.log
local.mcp.matlab.run
```

Server 再做 Resource/User/Device/Policy 裁剪。

---

## 15. Local Secret Store

本机凭据不应上传 Server，例如：

```text
Git token
SSH key
本地数据库密码
MATLAB/CAD credential
```

Resource/Tool 只引用：

```text
local:git.company
local:ssh.projectA
```

Secret 值保留在 OS 安全存储。

Windows 第一版优先：

```text
Credential Manager / DPAPI
```

禁止 `secrets.json` 明文保存。

---

## 16. Local Knowledge

在 KnowledgeBase 基础能力已经建设的前提下，增加：

```text
KnowledgeBase.location
=
SERVER
USER_DEVICE
```

Provider：

```text
KnowledgeProvider
├── RAGFlowProvider          location=SERVER
└── LocalKnowledgeProvider   location=USER_DEVICE
```

不要在每台 PC 部署完整 RAGFlow。

本地知识库推荐轻量：

```text
File Watcher
Parser
Chunker
Local Embedding
SQLite FTS / lightweight vector index
Retriever
```

第一版具体向量方案单独选型，不在架构层写死。

数据流：

```text
Local Documents
→ Local Index
→ local.knowledge.search
→ Top Evidence Only
→ Central Agent
```

原始文档不上传 Server。

仍复用：

```text
KnowledgeBase UUID
Revision
Manifest Hash
Run Snapshot
Retrieval Receipt
```

不要另建第二套个人知识库治理体系。

---

## 17. Local Execution Receipt

每次本地执行生成：

```text
LocalExecutionReceipt
---------------------------------
id
run_id
tool_call_id
device_id
capability
task_type
request_hash
policy_version
consent_decision
started_at
finished_at
exit_code
stdout_hash
stderr_hash
artifact_refs
artifact_hashes
runtime_version
local_tool_version
status
```

与 DeerFlow Tool Receipt 建立父子关联：

```text
DeerFlow Tool Receipt
→ Local Execution Receipt
→ Run Evidence
```

---

## 18. Artifact

本地运行产生：

```text
report.docx
chart.png
result.csv
```

支持两种模式：

### Upload

经用户 Policy 允许：

```text
Local → Server Workspace
```

### Keep Local

保留本机，仅返回逻辑 handle：

```text
local://.../artifact/...
```

模型不得看到真实 `C:\...` 路径。

第一版优先实现显式 Upload，Keep Local 后续完善。

---

## 19. 与 DeerFlow 的边界

原则上不修改：

```text
backend/packages/harness/deerflow/**
```

通过 AgentPlatform Extension 注册：

```text
local.* tools
device-aware authorization
task routing
receipt/provenance
```

建议：

```text
agentplatform_extension/
└── local_runtime/
    ├── tools.py
    ├── authorization.py
    ├── routing.py
    ├── receipts.py
    └── provenance.py
```

如果确实必须修改 DeerFlow Harness：

1. 先证明 Extension/Adapter 无法实现；
2. 写 focused regression test；
3. 登记 Upstream Patch Ledger；
4. 评估向 upstream 提交通用扩展点。

---

## 20. Server 目录建议

```text
backend/app/
├── devices/
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   ├── router.py
│   └── pairing.py
│
└── local_runtime/
    ├── broker.py
    ├── connection.py
    ├── tasks.py
    ├── service.py
    ├── receipts.py
    └── errors.py
```

实际位置以收敛后的仓库 `AGENTS.md` 和依赖方向为准。

---

## 21. Local Runtime 客户端建议

独立顶层模块：

```text
local-runtime/
├── core/
├── transport/
├── policy/
├── receipts/
├── storage/
├── capabilities/
│   ├── files/
│   ├── exec/
│   ├── mcp/
│   ├── secrets/
│   └── knowledge/
├── tray/
└── tests/
```

不要放进 Web frontend。

---

## 22. 客户端技术路线

### MVP 推荐

```text
Python Core
+
轻量 Tray
```

优势：

```text
与现有 Python/MCP 工具链一致
快速实现
脚本执行方便
```

### 长期可评估

```text
Rust Core + Tauri Tray
```

适合加强：

```text
进程控制
本地安全
单文件发行
资源占用
```

但不要为了技术栈升级阻塞 V0/V1。

---

## 23. Tray 最小功能

显示：

```text
连接状态
Server
当前 User
Device Name
Runtime Version
Allowed Roots
Capabilities
Local MCP
最近执行
```

控制：

```text
Pause
Disconnect
Open Settings
View Local Audit
```

Consent 由 Tray 完成，而不是依赖 Browser localhost API。

---

## 24. Multiple Devices

一个 User 可绑定：

```text
Laptop
Desktop
Workstation
```

模型不选设备。

聊天/UI 中提供：

```text
本地执行设备：[我的工作站 ▼]
```

Run 开始时冻结：

```text
device_id
```

避免运行中漂移。

---

## 25. Workflow Integration

Workflow step 支持：

```text
execution_target = USER_DEVICE
```

示例：

```text
Step 1 Server Knowledge Search
Step 2 Local Python Analyze
Step 3 Server Agent Interpret
Step 4 Local Office Generate
```

可配置：

```text
requires_device_online
requires_user_consent
timeout
fallback
```

---

## 26. Sub-Agent

V1：

```text
Sub-Agent 仍运行在 Server
```

但可以调用 Local Tool。

V3 才支持真正：

```text
Local Worker / Local Sub-Agent
```

适用于：

```text
50GB 数据
大型代码仓
敏感本地资料
专业软件
```

不要 V1 就复制一套 Local DeerFlow。

---

## 27. Network Policy

Local Runtime 不能成为绕过企业内网限制的旁路。

建议：

```text
LOCAL_NETWORK =
DENY
INTRANET_ONLY
ALLOW
```

内网默认：

```text
INTRANET_ONLY
```

允许：

```text
AgentPlatform Server
localhost MCP
批准的内网地址
```

默认禁止公网。

---

## 28. Protocol Version

WSS 握手必须包含：

```text
protocol_version
runtime_version
capabilities_version
policy_hash
```

Server 配置：

```text
minimum_supported_version
recommended_version
```

严重不兼容：

```text
BLOCKED
```

普通旧版：

```text
OUTDATED
```

---

## 29. Message Envelope

建议统一：

```json
{
  "protocol_version": 1,
  "type": "task",
  "message_id": "...",
  "device_id": "...",
  "session_id": "...",
  "timestamp": "...",
  "payload": {}
}
```

类型：

```text
hello
heartbeat
capability_update
task
task_ack
task_progress
task_result
task_cancel
consent_required
error
```

高安全环境给 task 加 payload hash / signature / expiry。

---

## 30. Replay Protection

Local Runtime 必须拒绝：

```text
重复 task id
过期 task
payload hash 不一致
session 不匹配
```

用户 Consent 也绑定 request hash。

---

## 31. Offline Handling

设备离线：

```text
local Tool 在新 Run assembly 中不出现
```

Run 中途掉线：

```text
DEVICE_OFFLINE
```

Workflow 可：

```text
retry / wait / fallback / fail
```

高风险本地任务不要无限 Queue。

Local Task 必须有：

```text
expires_at
```

避免用户第二天开机突然执行昨日写文件/删除任务。

---

## 32. Task Cancellation

Run cancel 必须传播：

```text
Server Run
→ Local Task
→ terminate process
→ cleanup
→ receipt
```

---

## 33. Output / Context

stdout/stderr 可 streaming，但必须：

```text
size limit
rate limit
redaction
```

不要把完整日志全部塞进 LLM Context。

应：

```text
Local Result
→ structured summary
→ selected stdout
→ artifact refs
```

完整日志留 Run Evidence / debug。

---

## 34. Privacy

Server 默认不采集：

```text
完整目录树
全部安装软件
环境变量
secret values
个人文件清单
```

只采集：

```text
用户授权 Roots
明确公开 Capability
必要 Runtime/OS 版本
```

---

## 35. Audit

Server 至少记录：

```text
Device paired/revoked
Capability changed
Local task requested
Local task denied
Consent
Execution
MCP call
Secret ref used
Local knowledge retrieval
```

Local Runtime 也保留最近本地 Audit，让用户知道 Agent 在 PC 做过什么。

---

# 36. 分阶段实施

## Phase 0 — Repository Reconnaissance

Coding Agent 先读取：

```text
AGENTS.md
backend/AGENTS.md
frontend/AGENTS.md
Extension API
AuthorizationProvider
Tool Assembly
Run / Tool Receipt
Workflow
KnowledgeBase
```

创建：

```text
docs/local-runtime/
├── ARCHITECTURE.md
├── IMPLEMENTATION_INVENTORY.md
├── SECURITY_MODEL.md
└── TEST_MATRIX.md
```

未完成 Inventory 前不进行大规模编码。

---

## Phase 1 — Device Control Plane

实现：

```text
Device model
Pairing
Revoke
Online/offline
Heartbeat
Runtime version
Capability registry
```

Gate：

```text
install
→ pair
→ online
→ disconnect
→ offline
→ revoke
→ reconnect denied
```

---

## Phase 2 — Secure WSS Broker

实现：

```text
authenticated WSS
session
heartbeat
protocol version
task envelope
ack
timeout
cancel
replay protection
```

Gate：

```text
Server → signed test task → Device → receipt
```

此阶段不执行系统命令。

---

## Phase 3 — Local Files

实现：

```text
Allowed Roots
local.files.list
local.files.read
local.files.write
```

Gate：

```text
allowed root success
outside root denied
../ denied
symlink/junction escape denied
write follows consent policy
```

---

## Phase 4 — Local Python

实现：

```text
local.python
working root
timeout
cancel
stdout/stderr
artifact
consent
receipt
```

Gate：成功、非零退出、超时、取消、子进程清理均有测试。

---

## Phase 5 — DeerFlow Tool Integration

通过 AgentPlatform Extension 注册 `local.*`。

Tool 出现条件：

```text
device online
∩ device capability
∩ caller permission
∩ agent declaration
∩ local policy compatibility
```

Gate：

> 无可用设备时，模型看不到 `local.python`。

---

## Phase 6 — Local MCP

实现：

```text
MCP supervisor
stdio MCP
localhost HTTP MCP
tool discovery
tool projection
```

至少用一个 test MCP / Git MCP 完成 E2E。

---

## Phase 7 — Local Secrets

实现：

```text
OS-backed secret store
logical secret refs
tool binding
```

Gate：

> Server DB、日志、Tool args、Receipt 中不存在 secret plaintext。

---

## Phase 8 — Tray UX

实现：

```text
connection
capabilities
roots
MCP
consent
audit
pause
```

---

## Phase 9 — Workflow USER_DEVICE

增加：

```text
ExecutionTarget.USER_DEVICE
```

并支持：

```text
requires_device_online
consent
timeout
fallback
```

---

## Phase 10 — Local Knowledge

KnowledgeBase 基础完成后加入：

```text
location=USER_DEVICE
LocalKnowledgeProvider
local index
retrieval receipt
```

Gate：

> 原始文件不上传 Server，但 Server Agent 可以获得授权的最小检索证据。

---

## Phase 11 — Offline Distribution

发行：

```text
Windows installer
runtime package
trusted server config
version manifest
SHA256
SBOM
internal upgrade package
```

不得访问：

```text
GitHub / PyPI / npm public registry
```

完成真正断网安装验收。

---

# 37. 测试矩阵

## Device

```text
pair
connect
heartbeat
offline
reconnect
revoke
wrong user
invalid credential
outdated runtime
```

## Authorization

```text
Agent 有 / User 无
User 有 / Device 无
Device 有 / Local Policy deny
全部有
Shared Agent caller/owner separation
```

## File Security

```text
outside root
../
symlink
junction
UNC
case/path trick
large file
locked file
```

## Execute

```text
success
non-zero
timeout
cancel
huge stdout
stderr
artifact
child cleanup
```

## MCP

```text
stdio
localhost
server crash
timeout
schema change
disabled server
secret redaction
```

## Protocol Security

```text
revoked device
expired session
replay task
modified payload
wrong device
wrong user
expired task
```

## Network

```text
AgentPlatform Server allowed
localhost MCP allowed
approved intranet allowed
public Internet denied
```

## Offline

```text
install
pair
execute
MCP
local knowledge
upgrade
```

---

# 38. Business E2E

建议使用故障归零场景：

```text
Server:
企业规范 KB
历史故障 KB

Local:
20GB 测试数据
Python
MATLAB/分析工具
项目文件
```

执行：

```text
Server Retrieval
→ Local Data Analysis
→ Server Reasoning
→ Workflow Gate
→ Report
→ Run Evidence
```

验收重点：

```text
执行目标正确
权限正确
本地数据未越界
知识证据正确
本地执行 Receipt 完整
最终报告可追溯
```

---

# 39. MVP Definition of Done

```text
[ ] Device 可配对/撤销
[ ] Local Runtime 主动 WSS 连接
[ ] Capability 注册
[ ] Assembly-time local capability filtering
[ ] Local Policy 二次授权
[ ] Allowed Roots
[ ] local.files.read/write
[ ] local.python
[ ] timeout/cancel
[ ] Consent
[ ] Execution Receipt
[ ] Run Evidence
[ ] Windows 内网离线安装
[ ] 默认无公网依赖
```

---

# 40. V1 Definition of Done

```text
[ ] Local MCP
[ ] Local Secret Store
[ ] Tray
[ ] Multiple Devices
[ ] Device Selector
[ ] Workflow USER_DEVICE
[ ] Protocol Version
[ ] Internal Update Distribution
[ ] Security Regression Suite
```

---

# 41. V2 Definition of Done

```text
[ ] Local Knowledge Provider
[ ] KnowledgeBase location=USER_DEVICE
[ ] Local Retrieval Receipt
[ ] Local-only document policy
[ ] Local KB Eval
```

---

# 42. V3 Definition of Done

```text
[ ] Local Worker / Sub-Agent
[ ] Durable long-running local task
[ ] Large local data processing
[ ] Optional Local Model
```

---

# 43. V1 明确不做

```text
Remote Desktop
键鼠控制
全功能 RPA
任意远程系统管理
默认全盘访问
Mandatory Local LLM
Local full DeerFlow Runtime
每台 PC 部署完整 RAGFlow
多人共享 Device
无人确认的高危命令
```

---

# 44. 推荐 Commit 序列

```text
docs(local-runtime): add architecture and security model
feat(devices): add device pairing and lifecycle
feat(local-runtime): add authenticated websocket broker
feat(local-runtime): add task lifecycle and heartbeat
feat(local-runtime): add capability registry

feat(local-files): add allowed roots and read tools
feat(local-files): add policy-gated write tools

feat(local-exec): add python execution
feat(local-exec): add timeout cancel consent and receipts

feat(extensions): register device-aware local tools
feat(authz): filter local capabilities during agent assembly

feat(local-mcp): add local mcp supervisor
feat(local-secrets): add os-backed secret references

feat(frontend): add device management
feat(local-runtime): add tray and local audit

feat(workflows): add user-device execution target

feat(knowledge): add local knowledge provider
feat(knowledge): add device-scoped retrieval receipts

chore(intranet): package local runtime for offline windows
test(local-runtime): add security and e2e acceptance
docs(local-runtime): add operations runbook
```

---

# 45. Coding Agent Master Instruction

## TASK

在已经完成 DeerFlow `main` → AgentPlatform `develop` 收敛的代码基础上实现 AgentPlatform Local Runtime。

Local Runtime 是独立的 User Device Execution Plane，不是第二套 DeerFlow。

目标是在保留 B/S 主架构的前提下，使 Server-side DeerFlow Agent 能安全调用当前用户设备上的本地文件、Python/脚本、MCP、Secrets 和后续本地知识库。

## NON-NEGOTIABLE INVARIANTS

1. `deerflow.*` 仍是唯一 Agent Runtime 真源。
2. Local Runtime 不运行第二套 Lead Agent / Memory / Workflow。
3. Server 不主动连接用户 PC；Device 主动建立认证连接。
4. 模型不得指定 raw device ID、IP 或本地端口。
5. 所有 Local Task 必须属于合法 Run + Tool Call。
6. Server Authorization 与 Local Authorization 必须双重通过。
7. Local DENY 永远优先。
8. 高风险操作默认 DENY。
9. 文件只访问显式 Allowed Roots。
10. 不提供隐藏的任意远程 shell。
11. Local Secret plaintext 不离开 Device。
12. Local MCP 不直接暴露给中心 Server。
13. Local Capability 在 Agent Assembly 时裁剪。
14. Device 离线时不可向模型暴露不可执行 Tool。
15. Shared Agent 使用 Caller Device/Permission，不使用 Owner Device。
16. Sub-Agent delegation 不得扩权。
17. Local Execution Receipt 必须进入 DeerFlow Tool Receipt / Run Evidence。
18. Local Knowledge 复用 AgentPlatform KnowledgeBase Governance。
19. 内网默认禁止公网 egress。
20. 不在 DeerFlow Harness 中实现 AgentPlatform 本地执行产品逻辑。

## EXECUTION ORDER

```text
Repository Inventory
→ Device Control Plane
→ Secure WSS
→ Local Files
→ Local Python
→ DeerFlow Tool Integration
→ Local MCP
→ Local Secrets
→ Tray
→ Workflow USER_DEVICE
→ Local Knowledge
→ Offline Distribution
```

## AUTHORIZATION

```text
Effective Local Capability
=
Agent declared capability
∩ Caller authorization
∩ Device capability
∩ Local policy
∩ Workflow policy
∩ Platform policy
```

Server 与 Device 均重新验证。

## DEVICE ROUTING

模型只调用：

```text
local.python
local.files.*
local.mcp.*
```

模型永远不选 Device。

AgentPlatform 使用当前 Run 冻结的 ExecutionTarget 路由。

## FILE RULE

- logical roots only；
- canonical path verification；
- reject traversal/symlink/junction escape；
- no whole-disk default access。

## EXECUTION RULE

V1 从 `local.python` 开始。

PowerShell/Shell 后续单独受控加入。

不要用 unrestricted remote shell 作为基础 API。

## CONSENT RULE

- Read-safe 可自动；
- Modify 根据本地策略；
- Dangerous 默认 DENY；
- Consent 必须绑定 request hash。

## MCP RULE

```text
Server → Local Runtime → Local MCP
```

优先 stdio / localhost-only。

## SECRET RULE

Secret 存 OS secure store。

Server 只持有 logical reference。

## RECEIPT RULE

每次执行必须关联：

```text
Run
Tool Call
Caller
Device
Capability
Policy Revision
Consent
Result
Artifacts
```

## KNOWLEDGE RULE

Local KB 仍是：

```text
KnowledgeBase Resource
location=USER_DEVICE
```

保持 UUID / Revision / Snapshot / Retrieval Receipt。

原始文档默认不上传。

## TEST RULE

必须覆盖：

```text
unauthorized user
wrong/revoked/offline device
replay
payload tamper
path traversal
symlink escape
consent rejection
timeout
cancel
MCP crash
secret leakage
public network denial
shared Agent caller/owner
Sub-Agent no privilege expansion
air-gap install
```

## FINAL SUCCESS CRITERIA

```text
Device pairing/revoke works
Secure outbound channel works
Capabilities are governed
Local tools appear only when authorized and executable
Local file scope is safe
Local Python works with timeout/cancel
Local Policy can veto Server
Consent works
Execution Receipt is traceable
Local MCP works
Secrets remain local
Workflow can target USER_DEVICE
Windows offline deployment works
Server-side AgentPlatform has no regression
```

---

# 46. 最终产品模型

```text
                         AgentPlatform

      Skill            Knowledge            Tool
      怎么做              知道什么             能做什么
        \                  |                 /
         \                 |                /
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
                   /              \
                  /                \
         Server Runtime        Local Runtime
               │                    │
               ▼                    ▼
      Server Knowledge        Local Knowledge
      Server MCP              Local MCP
      Server Sandbox          Local Files/Tools
               \                    /
                \                  /
                    Run Evidence
                    凭什么可信
```

Local Runtime 的价值不是“给浏览器加一个脚本执行按钮”，而是把 **执行位置** 正式提升为 AgentPlatform 的一等运行维度。

最终应始终保持：

```text
Server 编排
Local 执行

Server 授权
Local 再授权

模型看到能力
模型不知道设备细节

数据尽量不动
计算按需下沉

执行可证明
权限可治理
内网可交付
```
