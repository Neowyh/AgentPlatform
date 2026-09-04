# AgentPlatform：将 DeerFlow `main` 合并进 `develop` 的完整实施方案

> **目标读者**：Coding Agent、项目维护者、架构评审者  
> **制定日期**：2026-09-04  
> **目标仓库**：`https://github.com/Neowyh/AgentPlatform`，目标分支 `develop`  
> **上游仓库**：`https://github.com/bytedance/deer-flow`，来源分支 `main`  
> **总体目标**：在不回退 AgentPlatform 已形成的企业资源治理、Workflow、业务资源包、内网离线交付等核心能力的前提下，充分吸收 DeerFlow 最新 `main` 的 Runtime、Memory、Sub-Agent、Auth/Authz、Extension、Persistence、MCP、Skill、Sandbox、Frontend 等演进，并把长期 Fork 面积显著收敛。
>
> **重要约束**：DeerFlow `main` 当前是面向 2.1.0 的 Unreleased 开发主线，不是稳定 Release。执行时必须固定到一个明确的 `upstream/main` commit SHA；后续所有测试、问题与回滚都以该 SHA 为准，禁止使用“浮动 main”作为不可复现的升级基线。

---

# 0. 一句话方案

不要把这项工作理解成：

```text
git merge upstream/main
→ 把冲突解决掉
→ 测试
→ 完成
```

应把它理解成：

```text
冻结 develop
    ↓
固定 upstream/main SHA
    ↓
Probe Merge：只测冲突
    ↓
建立差异分类与冲突台账
    ↓
Mechanical Merge：导入上游历史和代码
    ↓
短期 Dual-Runtime Bridge
ideer.* + deerflow.*
    ↓
按模块逐项把 Runtime 切换到 upstream deerflow.*
    ↓
把 AgentPlatform 独有能力上移
Resource / Workflow / Enterprise Policy / Business Package
    ↓
引入 DeerFlow Extension API
    ↓
删除旧 ideer Runtime
    ↓
合并 Frontend / Config / DB / Deployment
    ↓
完整产品验收 + 断网验收
    ↓
develop
```

**本方案的核心不是“如何解决几百个 Git 冲突”，而是“如何借这次升级重建健康的上游边界”。**

---

# 1. 最终目标架构

最终希望得到：

```text
┌────────────────────────────────────────────────────┐
│                AgentPlatform UI                    │
│ Resource Center / Builder / Admin / Workflow UI    │
├────────────────────────────────────────────────────┤
│          AgentPlatform Control Plane               │
│                                                    │
│ Resource Governance V2                             │
│ User / Department / Visibility / Approval          │
│ Version / Draft / Publish / Fork / Transfer        │
│ Run Resource Snapshot / Audit / Business Evals     │
├────────────────────────────────────────────────────┤
│             AgentPlatform Workflow                 │
│ deterministic / semi-agentic orchestration         │
├────────────────────────────────────────────────────┤
│         AgentPlatform Extensions / Adapters        │
│                                                    │
│ Resource Resolver                                  │
│ Enterprise Authorization Adapter                   │
│ Run Evidence / Audit Observer                      │
│ Network Policy                                     │
│ Business Provenance                                │
├────────────────────────────────────────────────────┤
│               DeerFlow Runtime                     │
│                                                    │
│ Lead Agent / Tool / Skills / MCP / Memory           │
│ Sub-Agent / Sandbox / Guardrail / Context           │
│ Authz / Run / Checkpoint / Scheduler / Extensions   │
├────────────────────────────────────────────────────┤
│ Internal vLLM / Qwen / PostgreSQL / Redis(optional)│
├────────────────────────────────────────────────────┤
│              Internal Enterprise Systems           │
└────────────────────────────────────────────────────┘

外围发行层：

┌────────────────────────────────────────────────────┐
│         AgentPlatform Offline Distribution         │
│ images / wheels / office / resource packages       │
│ extensions / config / SBOM / checksums / migration │
└────────────────────────────────────────────────────┘
```

最终代码差异应尽可能满足：

```text
AgentPlatform - DeerFlow
=
Enterprise Resource Governance
+ Workflow
+ Offline Distribution
+ Business Packages
+ Enterprise Extensions
+ Internal Integrations
```

而不是：

```text
AgentPlatform - DeerFlow
=
上述内容
+ Memory Fork
+ Sub-Agent Fork
+ MCP Fork
+ Guardrail Fork
+ vLLM Fork
+ Run/Checkpoint Fork
+ Scheduler Fork
+ 大量通用 Runtime Patch
```

---

# 2. 必须保护的 AgentPlatform 产品不变量

Coding Agent 在任何冲突处理中，都不能只以“哪边代码更新”为依据。以下行为是产品不变量，必须在最终版本中保持。

## 2.1 Resource Governance V2

必须保持：

- Skill / Agent / Workflow 使用稳定 UUID；
- `resources` 为这三类资源的 canonical identity；
- owner / department / visibility / lifecycle 等企业治理信息仍然有效；
- Published Version 不可变；
- `resource_versions` 保存内容 hash；
- `resource_dependencies` 使用 UUID 关联；
- `resource_drafts` 保留 revision / optimistic lock；
- `run_resource_snapshots` 固化完整依赖闭包；
- Worker 只消费已冻结 snapshot，不在执行阶段重新按名称猜资源；
- `/api/resources` 仍为 canonical resource API；
- 资源可见不等于无条件可执行；
- Shared Resource 执行时使用 caller 权限、caller credential、caller memory boundary；
- Bundled Resource 仍通过统一 manifest / seed 流程进入资源目录；
- 已存在的 fault-zeroing / SRS 等业务资源不能因为上游 Skill/Agent 机制而绕过 Resource Catalog。

## 2.2 Workflow

必须保持：

- Workflow 是一等 Resource；
- Workflow 有稳定 UUID、Version、Visibility 和运行快照；
- Workflow Worker 不绕过 Resource Resolver；
- Workflow 调 Agent 时使用已解析资源版本；
- Workflow 可以承担确定性门禁，而不是全部退化为 Lead Agent 自由规划。

## 2.3 Offline / Intranet

必须保持：

- 默认无公网出口；
- 不要求公网搜索服务；
- 内部 vLLM/Qwen 能工作；
- Office 文档链路能工作；
- 完整 air-gapped bundle 能生成；
- 断网机器可完成安装和运行；
- 外部 Web / cloud sandbox / community integration 可以存在于代码，但默认**不可见、不可调用、不可联网**；
- 不能因为合并上游而把公网 API Key 变成内网运行必填项。

## 2.4 Business Packages

必须保持：

- fault-zeroing；
- SRS writing；
- 相关 Skill / Agent / Workflow；
- 验收脚本；
- 输出校验规则；
- bundled resource 初始化。

---

# 3. 这次升级必须吸收的主要上游能力

以执行时锁定的 DeerFlow `main` SHA 为准，当前主线重点包括：

## 3.1 Runtime / Context

- `TokenBudgetMiddleware`
- structured tool result metadata
- tool progress state machine
- durable context across summarization
- goal continuation
- tool receipt
- artifact-delivery receipt
- manual context compaction
- checkpoint delta
- checkpoint cache
- trace id 贯通 Run / checkpoint / trace
- config-declared lead/subagent middleware

## 3.2 Memory

- Pluggable `MemoryManager`
- `memory.manager_class`
- `memory.backend_config`
- per-user memory isolation
- agent-scoped memory
- memory search/tool mode
- consolidation
- staleness review
- durable extraction queue
- FTS5/BM25
- OpenViking / mem0 / Honcho 等可选 backend

## 3.3 Sub-Agent

- Deployment-level Sub-Agent Catalog
- Delegation allowlist
- process-wide concurrency controller
- delegation ledger
- total delegation cap
- durable SQL-backed `batch_task`
- retry / lease / pause / resume / cancel
- subagent acceptance criteria
- tool-receipt-based verification
- `UNVERIFIED` 语义

## 3.4 Authentication / Authorization

- Generic OIDC / SSO
- PAT
- pluggable `AuthorizationProvider`
- Tool assembly-time authorization
- Tool runtime authorization
- Model authorization
- Sandbox authorization
- Gateway route authorization

## 3.5 Extensions

- `deerflow-extension-api`
- out-of-tree extensions
- middleware contribution
- Gateway service / HTTP router
- task lifecycle observer
- system model observer
- provenance
- agent assembly fingerprint
- guardrail decision observation
- MCP origin observation

## 3.6 Skills

- Skill package boundary changes
- managed enabled-only projections
- `/mnt/skills` reserved semantics
- SkillScan
- deferred `describe_skill`
- per-user custom skill isolation
- local `.skill` archive install
- lazy/deferred skill disclosure

## 3.7 MCP

- durable task runtime
- per-server timeout / routing hints
- per-user credentials
- request-scoped secrets
- deny-by-default missing secrets
- MCP origin observability

## 3.8 Persistence / Deployment

- PostgreSQL schema support
- distributed event stream bridge
- checkpoint delta
- multi-worker/multi-instance improvements
- scheduler improvements
- new Docker binding/security defaults
- Helm/Kubernetes assets

---

# 4. 上游 Breaking Changes：合并时必须显式处理

当前 DeerFlow `main` 不是简单新增功能，至少存在以下会直接破坏 AgentPlatform 旧配置/部署语义的变化。

## 4.1 Memory 配置结构变化

旧配置类似：

```yaml
memory:
  enabled: true
  storage_path: memory.json
  debounce_seconds: 30
  max_facts: 100
```

最新主线改为 pluggable memory：

```text
memory
├── enabled
├── mode
├── injection_enabled
├── manager_class
└── backend_config
```

而且 `storage_path` 从“文件路径”变成“根目录”。

**严禁**直接把旧：

```yaml
storage_path: memory.json
```

原样带到新实现。

必须执行显式迁移。

## 4.2 `/mnt/skills` 语义变化

最新主线把：

```text
/mnt/skills
```

保留为 managed enabled-only projection。

因此：

- AgentPlatform 不能再把其他内容挂载到 `/mnt/skills`；
- OfficeCLI、业务文件或其他 operator mounts 不得覆盖它；
- Resource Governance 选择出的 Skill 版本必须通过 projection adapter 投影到 DeerFlow 预期目录；
- Disabled Skill 不得在 Sandbox 内通过文件系统旁路可见。

## 4.3 Docker 默认绑定变化

最新上游 Docker 默认入口绑定 loopback：

```text
127.0.0.1
```

AgentPlatform 的内网服务器通常需要 LAN 可访问。

因此 `deploy-intranet.sh` 必须显式设置正确 `BIND_HOST`，不能依赖过去的 `0.0.0.0` 默认行为。

## 4.4 Trace ID 语义

最新上游每个 Gateway HTTP response 都会带 `X-Trace-Id`，并贯通 Run / checkpoint。

如果 AgentPlatform 有自定义 trace/correlation 机制，必须统一，不要形成两套互相覆盖的 Trace ID。

## 4.5 Config Schema

当前上游 `config.example.yaml` 已有 `config_version`，执行时必须以实际锁定 SHA 的版本为准。

不要继续让 `config.intranet.yaml` 长期脱离上游 schema。

---

# 5. 总体 Git 策略

## 5.1 禁止的做法

Coding Agent **禁止**：

```text
1. 直接在 develop 上 merge upstream/main
2. 全局 git checkout --ours .
3. 全局 git checkout --theirs .
4. 全仓 find/replace ideer → deerflow
5. 冲突文件“能编译就行”
6. 一次性删除 ideer Runtime
7. 一次性替换数据库 migration
8. 为了让测试通过而删除本地 Resource Governance 测试
9. 看到 upstream 新 API 后恢复旧 legacy resource routes
10. 在未固定 SHA 的情况下反复 fetch main 并继续合并
```

---

# 6. 分支模型

建议建立：

```text
develop
  │
  ├── tag: pre-deerflow-main-<SHORT_SHA>
  │
  └── integration/deerflow-main-<SHORT_SHA>
          │
          ├── merge checkpoint
          ├── runtime-foundation
          ├── runtime-memory
          ├── runtime-subagents
          ├── enterprise-control-plane
          ├── frontend
          ├── deployment
          └── acceptance
```

可以再建立一次性：

```text
probe/deerflow-main-<SHORT_SHA>
```

用于冲突探测，完成后删除。

**不要**在 `develop` 上边合并边调试。

---

# 7. Phase 0：读取仓库规则并冻结基线

## 7.1 Coding Agent 必须先读取

至少读取：

```text
AGENTS.md
backend/AGENTS.md
frontend/AGENTS.md
以及每个将要修改目录下更近的 AGENTS.md
```

AgentPlatform 当前规则要求：

- 修改函数/类之前执行 GitNexus impact analysis；
- HIGH / CRITICAL 必须显式报告；
- UNKNOWN 不能视为安全；
- commit 前执行 graph change analysis；
- 高风险路径执行 `pr-standard`；
- Release 执行 `core-full`。

这些规则在合并期间仍然有效。

## 7.2 确认工作区

```bash
git switch develop
git status --short
```

必须为 clean。

禁止使用未提交工作区开始上游融合。

## 7.3 配置 upstream

```bash
git remote -v
```

如果没有：

```bash
git remote add upstream https://github.com/bytedance/deer-flow.git
```

如果已有，确认 URL：

```bash
git remote set-url upstream https://github.com/bytedance/deer-flow.git
```

然后：

```bash
git fetch --prune upstream main
```

## 7.4 固定三个 SHA

```bash
DEVELOP_BASE=$(git rev-parse develop)
UPSTREAM_SHA=$(git rev-parse upstream/main)
MERGE_BASE=$(git merge-base develop upstream/main)

echo "DEVELOP_BASE=$DEVELOP_BASE"
echo "UPSTREAM_SHA=$UPSTREAM_SHA"
echo "MERGE_BASE=$MERGE_BASE"
```

必须持久记录到：

```text
docs/upgrades/deerflow-main-<SHORT_SHA>/UPSTREAM_LOCK.md
```

内容至少包括：

```text
AgentPlatform develop SHA
DeerFlow main SHA
merge-base SHA
date
git remote URL
config_version
```

后续整个融合期间：

> **禁止重新 fetch 后把另一个 main SHA 混入此次集成。**

如果需要新上游能力，另开下一轮 convergence。

## 7.5 建立保护 Tag

```bash
git tag -a pre-deerflow-main-<SHORT_SHA> "$DEVELOP_BASE" \
  -m "AgentPlatform baseline before DeerFlow main <UPSTREAM_SHA>"
```

如有权限，推送：

```bash
git push origin pre-deerflow-main-<SHORT_SHA>
```

## 7.6 冻结数据库 / Resource / Offline 基线

记录：

```text
resources count by type
published resource versions
bundled resource manifest hash
workflow count
resource DB schema
current Alembic head(s)
config hashes
offline bundle manifest
```

如本地有测试 DB：

```bash
cd backend
alembic current
alembic heads
alembic history
```

SQLite 可额外备份：

```bash
cp .ideer/data/ideer.db \
  ../dev-log/ideer-pre-upstream-merge.db
```

该数据库为工作备份，不要提交。

## 7.7 跑完整 baseline

至少：

```bash
bash scripts/run-test-lane.sh core-full
bash scripts/check-intranet.sh
python scripts/run_fault_zeroing_acceptance.py
python scripts/smoke_srs_flow.py
```

如果当前环境能生成离线包：

```bash
bash scripts/package-intranet-offline.sh
```

记录：

```text
command
exit code
test count
skips
known failures
artifact checksum
```

**任何 baseline 本身已经失败的项目，必须先记录，不允许合并后把它误认为 upstream regression。**

### Gate 0

只有以下条件满足才能继续：

- working tree clean；
- SHA 已锁定；
- baseline tag 已创建；
- baseline test report 已保存；
- resource snapshot 已保存；
- DB backup 已完成；
- GitNexus index 可用或明确记录替代方案。

---

# 8. Phase 1：Probe Merge —— 先观察，不修改正式集成分支

## 8.1 建立 Probe Branch

```bash
git switch develop
git switch -c probe/deerflow-main-<SHORT_SHA>
```

启用 rerere：

```bash
git config rerere.enabled true
```

## 8.2 执行 Probe Merge

```bash
git merge --no-commit --no-ff "$UPSTREAM_SHA" || true
```

不要开始修改。

先导出：

```bash
git status --short
git diff --name-only --diff-filter=U
git diff --name-status --merge-base develop "$UPSTREAM_SHA"
```

保存到：

```text
docs/upgrades/deerflow-main-<SHORT_SHA>/
├── UPSTREAM_LOCK.md
├── CONFLICT_LEDGER.md
├── PATH_POLICY.md
└── FEATURE_ADOPTION_MATRIX.md
```

## 8.3 冲突分类

每个冲突必须归入：

| 类型 | 代码 | 含义 |
|---|---|---|
| Upstream-owned | U | 上游为真源，本地改动应改为 adapter/extension |
| Local-owned | L | AgentPlatform 核心产品差异，保留本地语义 |
| Semantic Merge | M | 两边都有必要，人工整合 |
| Adapter | A | 上游 API 保留，本地通过 adapter 接入 |
| Transitional | T | 临时双轨，后续必须删除 |
| Drop | D | 本地旧实现已有上游替代，最终删除 |

`CONFLICT_LEDGER.md` 每项必须记录：

```text
path
classification
upstream intent
local intent
final target
temporary resolution
final resolution phase
tests
owner
status
```

## 8.4 探测后立即 Abort

```bash
git merge --abort
git switch develop
git branch -D probe/deerflow-main-<SHORT_SHA>
```

Probe 的价值是“建立事实”，不是产生代码。

### Gate 1

必须得到：

- 完整 conflict list；
- path ownership matrix；
- feature adoption matrix；
- 至少识别所有高风险冲突：
  - runtime namespace
  - config
  - DB migrations
  - auth
  - resources
  - skills
  - memory
  - subagent
  - frontend
  - docker
  - offline scripts。

---

# 9. Phase 2：建立正式 Integration Branch

```bash
git switch develop
git switch -c integration/deerflow-main-<SHORT_SHA>
```

再次确认：

```bash
test "$(git rev-parse HEAD)" = "$DEVELOP_BASE"
```

执行：

```bash
git merge --no-commit --no-ff "$UPSTREAM_SHA"
```

接下来按照 Path Policy 解决。

---

# 10. Path Policy：路径级解决原则

## 10.1 AgentPlatform 长期拥有的路径

以下原则上以本地语义为主，但需要适配上游接口：

```text
resources/**
workflows/**
vendor/**
bundled-resources.json

docs/decisions/*resource-governance*
docs/testing/**          # AgentPlatform 特有测试规范
scripts/*intranet*
scripts/*fault*
scripts/*srs*
scripts/seed_bundled_resources.py
scripts/intranet_bundle_manifest.py

Resource Governance 相关 Gateway/DB/Frontend
Workflow 相关 Gateway/DB/Frontend
Department / enterprise resource approval
Business package / eval
```

不能简单 `--theirs`。

## 10.2 DeerFlow 上游长期拥有的路径

最终目标应是上游实现为真源：

```text
backend/packages/harness/deerflow/**
backend/packages/extension-api/**
```

以及通用 Runtime：

```text
Memory
Sub-Agent
MCP internals
Guardrail core
Loop detection
Sandbox lifecycle core
Models/vLLM
Run/Checkpoint
Scheduler
Tracing
Generic middleware
```

### 特别注意

AgentPlatform 当前是：

```text
backend/packages/harness/ideer/**
```

不要尝试把 DeerFlow 新代码长期继续翻译到 `ideer.*`。

此次升级要逐步恢复：

```text
deerflow.* = upstream runtime
agentplatform.* = local enterprise layer
```

## 10.3 必须人工 Semantic Merge 的路径

通常包括：

```text
backend/app/**
backend/tests/**
backend/pyproject.toml
backend/uv.lock
backend/alembic/**
config.example.yaml
config.intranet.yaml
.env.example
Makefile
docker/**
scripts/serve.sh
scripts/deploy.sh
scripts/docker.sh
frontend/**
frontend/package.json
frontend/pnpm-lock.yaml
AGENTS.md
backend/AGENTS.md
frontend/AGENTS.md
```

这些路径禁止机械 ours/theirs。

---

# 11. Phase 2 的临时策略：Dual-Runtime Bridge

这是本方案的关键安全机制。

## 11.1 机械合并后的短期状态允许是

```text
backend/packages/harness/
├── ideer/        # 旧 AgentPlatform Runtime，暂时保持现有产品可运行
└── deerflow/     # 新导入的 upstream Runtime
```

同时：

```text
backend/packages/
├── extension-api/
└── harness/
```

## 11.2 目的

先做到：

```text
upstream Runtime 已完整进入仓库
BUT
AgentPlatform 旧运行路径暂时不立即断掉
```

然后每个模块逐项迁移。

这样可以避免：

```text
一次 rename
+ 一次 Runtime 大升级
+ 一次 Resource 重构
+ 一次 DB 迁移
+ 一次 Frontend 升级
```

全部同时发生。

## 11.3 Dual Runtime 的硬性限制

Dual Runtime：

- **只能存在于 integration branch**；
- 不能发布；
- 不能进入最终 `develop`；
- 不允许两套 Runtime 同时处理同一 Run；
- 不允许两套 Memory 同时写；
- 不允许两套 Scheduler 同时启动；
- 不允许同一 Tool 被两个 Runtime 重复注册；
- 每迁移一块，都要删除相应 `ideer` 依赖。

### Gate 2

Mechanical Merge 后至少做到：

```python
import ideer
import deerflow
```

均可 import。

现有 AgentPlatform baseline 仍可通过旧入口运行。

---

# 12. Phase 3：Runtime Foundation 收敛

建议采用“一个模块一个 vertical slice”。

每个 slice：

```text
1. GitNexus impact
2. 写/更新 focused regression test
3. 切换到 upstream implementation
4. focused tests
5. remove local duplicate
6. detect_changes
7. commit
```

---

# 13. Runtime 迁移顺序

推荐顺序不是按目录字母，而是按依赖层级。

## R1. Config / Reflection / Logging / Trace

### Adopt

优先采用上游：

```text
deerflow.config
deerflow.reflection
logging config
trace_context
config versioning / upgrade
```

### Preserve

AgentPlatform 自有：

```text
intranet profile
offline settings
resource/workflow product config
office config
internal endpoint config
```

### 目标

禁止：

```text
上游一套 config parser
本地再维护一套 config parser
```

建议最终：

```text
DeerFlow runtime config schema
+
AgentPlatform product config
```

### 推荐进一步收敛

如果改动可控：

```text
config.yaml              # upstream-compatible DeerFlow runtime
agentplatform.yaml       # resource/workflow/enterprise product config
config.intranet.yaml     # deployment profile / generated effective config
```

如果本轮不拆配置，也至少要求：

- `config.intranet.yaml` 包含当前上游 schema；
- local-only key 有清晰 namespace；
- `make config-upgrade` 可继续工作。

---

## R2. Persistence / Run / Checkpoint

优先吸收：

- RunStore 现有上游语义；
- trace id；
- checkpoint delta；
- checkpoint cache；
- artifact delivery receipts；
- stream bridge；
- Postgres schema support。

### Preserve

AgentPlatform 自有：

```text
run_resource_snapshots
resource version/hash
workflow run linkage
business audit fields
```

### 关键融合点

建议扩展：

```text
Run Evidence Envelope
├── Resource Snapshot
├── Runtime Assembly Fingerprint
├── Tool Receipts
├── Authorization Context
├── Policy Revision
├── Sub-Agent Verification
└── Artifact Receipt
```

而不是让两个 evidence system 平行存在。

---

## R3. Auth / Authz

### 上游负责

```text
AuthorizationProvider
Tool assembly authorization
Tool runtime authorization
Model authorization
Sandbox authorization
Gateway route authorization
OIDC/SSO
PAT
```

### AgentPlatform 负责

```text
resource owner
department
visibility
publish permission
approval
fork/transfer
resource lifecycle
```

### 最终有效能力

```text
Effective Capability
=
Resource declared capability
∩ Caller runtime authorization
∩ Platform policy
∩ Sandbox policy
∩ Network policy
∩ Environment availability
```

### 强制测试

必须验证：

> 无权 Tool 不仅调用失败，而且在 assembly 阶段模型根本看不到。

---

## R4. Models / vLLM / Qwen

### 目标

删除长期维护的本地 Provider Fork。

优先采用：

```text
deerflow.models.*
deerflow.models.vllm_provider
```

AgentPlatform 仅保留：

```text
internal endpoint
auth header
model alias
Qwen profile
intranet default selection
```

只有内部网关协议确实不同，才创建：

```text
agentplatform.adapters.models.*
```

不要修改 DeerFlow provider 核心。

### 验收

至少：

- Qwen thinking；
- reasoning delta；
- tool call；
- streaming；
- structured response；
- timeout/error；
- vision（若内网依赖）。

---

## R5. Guardrail / Loop Detection / Token Budget / Verification

上游负责：

```text
Guardrail runtime
Loop detection
TokenBudgetMiddleware
Tool receipts
Security intervention events
Artifact delivery verification
```

AgentPlatform 保留：

```text
policy values
enterprise thresholds
audit retention
resource-specific restrictions
```

不要继续 fork 算法。

---

## R6. Sandbox

采用上游 sandbox lifecycle/provider abstraction。

保留本地：

```text
OfficeCLI mount
internal filesystem policy
air-gap image
intranet volume mapping
internal security profile
```

### 重要

禁止任何本地 mount 覆盖：

```text
/mnt/skills
```

### 验收

- bash；
- read/write；
- OfficeCLI；
- Resource Skill projection；
- caller isolation；
- unauthorized sandbox denied。

---

## R7. MCP

上游负责：

```text
MCP protocol
durable task
credentials
request-scoped secret
timeout
routing
origin metadata
```

AgentPlatform 保留：

```text
允许哪些 MCP server
internal MCP catalog
network allowlist
department/resource tool policy
credential source policy
```

### 内网原则

代码中可以保留公网 MCP / community provider 支持，但：

```text
config.intranet
+
Authorization
+
Network policy
```

必须保证默认不可调用。

---

## R8. Skill Runtime

这是本次最敏感的融合点之一。

### 不变量

Resource Catalog 仍然是企业身份与版本真源。

但 DeerFlow Runtime 应负责：

```text
SkillScan
Skill parser
Skill progressive disclosure
describe_skill
Sandbox projection
managed /mnt/skills
```

### 正确结构

```text
AgentPlatform Resource Catalog
       │
       │ resolve UUID/version/hash
       ▼
Resolved Skill Set
       │
       ▼
Projection Adapter
       │
       ▼
DeerFlow managed Skill Projection
       │
       ▼
SkillScan / describe_skill / runtime load
```

### 禁止

```text
Resource Catalog
     AND
DeerFlow 自己另一个 public/custom catalog
```

两套身份真源并存。

### 必须做到

Run 开始时：

```text
Resource Resolver
→ 得到 Skill UUID + version + hash
→ 生成 enabled-only projection
→ DeerFlow 只看到 projection
```

从而同时拥有：

```text
企业版本治理
+
上游 Progressive Disclosure
+
SkillScan
+
Sandbox filesystem isolation
```

---

## R9. Memory

优先完整采用上游 `MemoryManager` contract。

AgentPlatform 不再继续维护旧 memory core。

### 迁移要求

旧数据不能直接删除。

必须：

```text
旧 memory.json
     ↓ copy / transform
新 backend storage root
     ↓
验证 per-user isolation
     ↓
验证 facts count/hash
     ↓
保留旧文件直到 upgrade acceptance 完成
```

### Memory Identity

Shared Resource 执行必须绑定：

```text
caller user identity
+
effective agent identity
```

不能错误绑定 resource owner。

### 验收

- 用户 A 不读取用户 B Memory；
- Shared Agent 不读取 owner personal memory；
- Agent-scoped memory 正确；
- summarize/compact 后 memory context 不丢；
- restart 后 memory 保留。

---

## R10. Sub-Agent

优先采用上游：

```text
catalog
allowlist
capacity controller
delegation ledger
batch_task
durable persistence
acceptance criteria
tool receipt verification
```

AgentPlatform 保留：

```text
企业定义的角色/worker resource
Resource governance
business delegation policy
department visibility
```

### 关键理念

AgentPlatform 不应再维护：

```text
“子智能体怎么并发执行”
```

而应维护：

```text
“哪个企业 Agent 有权委派给谁”
```

---

## R11. Scheduler

采用上游 Scheduler 基础设施。

AgentPlatform 仅保留：

```text
resource snapshot
workflow linkage
enterprise ownership
run policy
```

Scheduled run 也必须在 Run 创建时冻结 Resource Snapshot。

---

## R12. Extensions

这一阶段必须真正引入：

```text
deerflow-extension-api
```

而不是把现有：

```text
extensions_config.example.json
```

误认为 Extension System。

建议创建：

```text
backend/packages/agentplatform-extension/
└── agentplatform_extension/
    ├── __init__.py
    ├── resource_snapshot.py
    ├── authorization.py
    ├── audit.py
    ├── provenance.py
    ├── network_policy.py
    └── workflow_observer.py
```

第一批迁出 Harness 的 cross-cutting concern：

1. Run Resource Snapshot binding
2. Audit observer
3. Resource provenance
4. Enterprise policy injection
5. Resource-aware authorization
6. Network policy

### Gate R

完成 Runtime 收敛后：

```bash
git diff "$UPSTREAM_SHA" -- backend/packages/harness/deerflow
```

差异应显著减少。

所有仍存在的差异必须登记：

```text
docs/upgrades/deerflow-main-<SHORT_SHA>/UPSTREAM_PATCH_LEDGER.md
```

每个 patch 必须有：

```text
path
symbol
why upstream extension point is insufficient
test
owner
removal condition
upstream issue/PR（如有）
```

---

# 14. Phase 4：把 AgentPlatform 独有能力移出 `ideer` Runtime

当前：

```text
backend/packages/harness/ideer/
├── fault_zeroing
├── resources
├── workflows
└── ...
```

最终应清理。

## 14.1 建议的目标包

例如：

```text
backend/packages/agentplatform-core/
└── agentplatform/
    ├── resources/
    ├── workflows/
    ├── enterprise/
    └── audit/
```

或者如果这些主要属于 Gateway App：

```text
backend/app/agentplatform/
```

具体位置以依赖方向为准。

核心原则：

> DeerFlow Harness 不依赖 AgentPlatform App。

> AgentPlatform 可以依赖 DeerFlow Runtime / Extension API。

## 14.2 `fault_zeroing`

执行判断：

> 删除 fault-zeroing 业务后，Runtime 是否仍需要该 Python 代码？

如果“不需要”，则不能留在 Harness。

应尽量迁为：

```text
resources/agents/fault-zeroing
resources/skills/...
resources/workflows/...
business eval scripts
```

只有真正通用的 primitive 才提炼到：

```text
agentplatform.workflow primitives
```

### Gate 4

最终：

```text
backend/packages/harness/ideer/
```

应删除或只存在极薄且有明确删除日期的 compatibility shim。

理想状态：完全删除。

---

# 15. Phase 5：数据库与 Migration 融合

数据库是这次升级最大的不可逆风险之一。

## 15.1 原则

禁止：

- 修改已经在线使用过的历史 revision 内容；
- 删除本地 resource tables；
- 为追求“只有一个 migration head”而重写历史；
- 直接拿空数据库测试成功就宣布 migration 成功。

## 15.2 操作流程

记录：

```bash
cd backend
alembic current
alembic heads
alembic history
```

合并上游 migration 文件后再次：

```bash
alembic heads
```

如果出现两个合法分支 head：

```text
local_resource_head
upstream_runtime_head
```

创建新的 Alembic merge revision，而不是重写历史。

示意：

```bash
alembic merge <LOCAL_HEAD> <UPSTREAM_HEAD> \
  -m "merge AgentPlatform resource schema with DeerFlow upstream"
```

以实际工具链为准。

## 15.3 必须测试三类数据库

### A. Fresh DB

```text
空数据库
→ upgrade head
→ seed bundled resources
→ run
```

### B. Existing AgentPlatform DB

```text
develop 真实结构副本
→ upgrade
→ resource/version/snapshot 数量一致
→ 用户/角色一致
→ run history 可读
```

### C. PostgreSQL

如果准备吸收 upstream production persistence：

```text
fresh PostgreSQL
existing-style migrated PostgreSQL test fixture
```

至少验证：

- schema；
- constraints；
- JSON semantics；
- RunStore；
- ResourceService；
- scheduler；
- durable batch。

### Gate 5

所有迁移必须是：

```text
forward-only
repeatable in test
backup-aware
```

---

# 16. Phase 6：Config 融合

## 16.1 目标

以 DeerFlow 当前 `config.example.yaml` 为 Runtime schema source。

AgentPlatform 不应长期自己复制一个完全独立的旧 schema。

## 16.2 必须迁移的内网值

保留：

```text
vLLM endpoint
Qwen model aliases
thinking settings
sandbox
office
no-public-web defaults
internal MCP
resource/workflow
intranet trace endpoint
```

但映射到最新上游字段。

## 16.3 Memory 特别迁移

不能保留：

```yaml
memory:
  storage_path: memory.json
```

必须按锁定 SHA 的最新 schema 改成正确：

```text
manager_class
mode
backend_config
storage root directory
```

具体字段值必须从此次固定 SHA 的 `config.example.yaml` 读取，不允许 Coding Agent 凭印象硬编码。

## 16.4 Config Upgrade

最终必须：

```bash
make config-upgrade
```

对现有内网配置安全运行。

### Gate 6

```text
config.example.yaml
config.intranet.yaml
.env.example
doctor/config validation
```

全部通过。

---

# 17. Phase 7：Frontend 融合

Frontend 不建议整目录 ours/theirs。

## 17.1 Upstream 优先吸收

通用对话体验：

- context usage；
- clarification cards；
- branch/side conversation；
- regenerate；
- workspace change review；
- citation/evidence UI；
- subagent history；
- durable batch panel；
- tool progress；
- auth/SSO settings；
- integrations/tool settings。

## 17.2 AgentPlatform 必须保护

- Resource Center；
- Agent / Skill / Workflow unified resource UX；
- Resource UUID route；
- Owner / Department / Visibility；
- Publish / Draft / Approval；
- Fork / Suspend / Archive；
- Admin；
- business workflow page；
- fault-zeroing / SRS-specific UX（若有）；
- AgentPlatform branding。

## 17.3 API Client

重点检查：

```text
/api/agents
/api/skills
/api/workflows
```

上游可能重新引入自己的 Agent/Skill API。

AgentPlatform canonical rule仍然要求：

```text
/api/resources
```

为企业 Resource API。

不要因为 upstream frontend 引入 old-style API 就重新暴露 local legacy routes。

可以：

```text
upstream runtime APIs
+
AgentPlatform resource APIs
```

但不要让两个 API 同时成为同一种资源的 canonical source。

### Gate 7

```bash
cd frontend
pnpm test
pnpm check
pnpm test:e2e
```

以及：

```bash
bash scripts/run-test-lane.sh pr-standard
```

---

# 18. Phase 8：Docker / Deployment / Offline Bundle

## 18.1 Docker

吸收 upstream：

- Redis stream（需要时）；
- Postgres profile；
- new Gateway；
- Extension package；
- new skill projection；
- current runtime dependencies；
- Docker security defaults。

## 18.2 内网 Profile

继续保持：

```text
external web disabled
public API keys optional/unset
internal vLLM
internal registry
officecli
local/private MCP
```

特别检查：

```text
BIND_HOST
```

避免上游 loopback default 导致内网用户访问不到。

## 18.3 Offline Bundle

必须更新 bundle：

```text
images
Python wheels
Node dependencies / built frontend
extension-api
AgentPlatform extension
resource packages
OfficeCLI
PostgreSQL/Redis image（如果生产 profile 使用）
SBOM
SHA256
config templates
migration
rollback notes
```

## 18.4 网络验收

在真正无公网的环境验证：

```text
DNS 不可访问公网
HTTP/HTTPS 无公网路由
```

仍可以：

```text
启动
登录
资源浏览
Agent Run
Skill
Workflow
Memory
Sub-Agent
Office
vLLM
history/restart
```

### Gate 8

Fresh air-gap install 必须真实通过。

---

# 19. Phase 9：删除 Dual Runtime

只有前述模块全部完成后执行。

## 19.1 查找剩余引用

不要只 grep。

先 GitNexus：

```text
impact / context / detect_changes
```

再文本检索确认：

```bash
rg '\bideer\.' backend frontend scripts tests
rg 'packages/harness/ideer' .
```

## 19.2 删除条件

只有以下全部成立才删除：

- app 已 import `deerflow.*`；
- Resource/Workflow 已移到 AgentPlatform layer；
- fault-zeroing 已业务包化；
- tests 不依赖 ideer；
- scripts 不依赖 ideer；
- config `use:` 路径不依赖 ideer；
- extensions 不依赖 ideer；
- offline bundle 不依赖 ideer。

## 19.3 删除

使用 graph-aware rename/refactor 工具，禁止全局替换。

### Gate 9

```bash
python -c "import deerflow"
```

成功。

```bash
python -c "import ideer"
```

应失败，除非明确保留了短期 compatibility shim。

最终推荐：无 shim。

---

# 20. 上游 Patch Ledger

最终项目允许对：

```text
backend/packages/harness/deerflow/**
```

存在少量本地 Patch。

但每一处必须写进：

```text
UPSTREAM_PATCH_LEDGER.md
```

模板：

```markdown
## PATCH-001

- Path:
- Symbol:
- Classification:
- Local requirement:
- Why Extension/Adapter cannot solve it:
- Test:
- Security impact:
- Upstream issue/PR:
- Removal condition:
- Owner:
```

### Final Gate

执行：

```bash
git diff "$UPSTREAM_SHA" -- backend/packages/harness/deerflow
```

逐项核对 Ledger。

**没有 Ledger 的 Runtime diff 不允许进入 develop。**

---

# 21. Conflict Resolution Rules

Coding Agent 遇到冲突时必须遵守以下决策树。

```text
冲突是否属于 AgentPlatform product invariant？
        │
    ┌───┴───┐
   Yes      No
    │        │
    ▼        ▼
能否通过   是否属于通用 Runtime？
Adapter /        │
Extension？     Yes
 │               │
Yes              ▼
 │           Upstream wins
 ▼               │
保留 upstream    │
+ local adapter  │
 │               │
No               ▼
 │        删除本地重复实现
 ▼
保留 local semantic
但登记 Patch Ledger
```

---

# 22. 常见冲突的具体处理方式

## 22.1 `pyproject.toml`

不要 ours/theirs。

步骤：

1. 采用 upstream dependency baseline；
2. 加回 AgentPlatform 独有 dependency；
3. 删除 upstream 已替代的 local fork dependency；
4. 重新生成 lock；
5. `uv sync`；
6. import smoke；
7. tests。

## 22.2 `uv.lock`

禁止手工逐行解冲突。

解决 `pyproject.toml` 后重新生成。

## 22.3 `pnpm-lock.yaml`

同理：

- 先解决 package.json；
- 再 `pnpm install --lockfile-only` / 项目规范命令重新生成；
- 不手工拼 lockfile。

## 22.4 `AGENTS.md`

应做语义合并。

保留 AgentPlatform：

```text
GitNexus
test lane
resource governance
offline rules
```

吸收 upstream：

```text
new Harness/App boundary
TDD
blocking-I/O
extension rules
new commands
new subsystem AGENTS
```

## 22.5 README / Branding

品牌保持 AgentPlatform / iDeer 产品语义。

技术能力描述更新到最新 Runtime。

不要把 upstream “DeerFlow 官网/产品说明”机械覆盖 AgentPlatform README。

## 22.6 Community Web Tools

不要删除上游源代码。

采用：

```text
code available
+
intranet registration disabled
+
authz denied
+
network denied
```

这样下一轮上游 merge 不需要再次处理“被本地删掉的文件”。

---

# 23. 测试策略

测试采用“Focused → Standard → PR → Release”四层。

## 23.1 每个 vertical slice

先 focused tests。

例如：

```bash
cd backend
uv run pytest tests/.../test_memory_*.py -v
```

然后：

```bash
make test
```

## 23.2 高风险模块

以下每次改动都要：

```bash
bash scripts/run-test-lane.sh pr-standard
```

- auth
- RBAC
- persistence
- memory
- Resource
- Agent
- Skill
- Workflow
- frontend API contract。

## 23.3 Release Final

最终：

```bash
bash scripts/run-test-lane.sh core-full
```

并追加业务验收。

---

# 24. 必须新增的升级回归测试

不能只依赖已有测试。

至少新增以下场景。

## A. Resource Snapshot + New Runtime

```text
Agent Resource A v1
Skill S v2
Workflow W v3
Run
→ snapshot UUID/version/hash
→ 中途发布 A v2
→ 已启动 Run 仍使用 A v1
```

## B. Runtime Authorization

```text
用户无 tool:x 权限
→ Resource 声明 tool:x
→ assembly 后模型 tool list 中不存在 tool:x
→ 强行调用仍被 runtime deny
```

## C. Shared Agent Caller Boundary

```text
Owner 发布共享 Agent
Caller 使用
→ caller credential
→ caller memory
→ caller tool permission
→ 不使用 owner private state
```

## D. Skill Projection

```text
Catalog 解析 Skill UUID/version
→ enabled projection
→ /mnt/skills 只有本次允许的版本
→ disabled/private Skill 不存在
→ SkillScan 正常
```

## E. Memory Migration

```text
旧 memory 数据
→ upgrade
→ per-user facts 保留
→ user isolation
→ agent scoped memory
→ restart
```

## F. Sub-Agent Verification

```text
Subagent 声称创建文件
BUT 没有 receipt
→ UNVERIFIED / fail acceptance

真实 write_file + receipt
→ verified
```

## G. Workflow

```text
Workflow Resource
→ frozen dependency
→ subagent/tool receipt
→ final output
→ run evidence 可追溯
```

## H. Fault Zeroing

现有三类案例全部通过。

## I. SRS

现有 smoke + validation 全部通过。

## J. Offline

```text
no internet
→ fresh install
→ login
→ vLLM
→ file upload
→ Office
→ Resource
→ Workflow
→ Memory
→ Subagent
```

## K. Restart

```text
运行开始
→ gateway restart
→ 可恢复/正确失败
→ history/readability 保证
```

---

# 25. Production Profile 建议

不要强制所有环境都启用最重架构。

## Dev

```text
SQLite
memory/local run events
local sandbox
```

## Enterprise Single Node

```text
PostgreSQL
durable run store
container sandbox
internal vLLM
offline resources
```

## Enterprise HA

```text
PostgreSQL
Redis stream bridge（如需要）
multi Gateway
scheduler lease
durable batch
Kubernetes provisioner
central audit
```

---

# 26. 风险清单

| 风险 | 等级 | 处理 |
|---|---|---|
| `ideer`/`deerflow` 双 Runtime 长期残留 | Critical | Dual Runtime 设为 integration-only + 删除 Gate |
| Resource Catalog 被 upstream Skill/Agent API 绕过 | Critical | canonical API contract tests |
| DB migration 丢失 Resource/Run | Critical | existing DB upgrade acceptance |
| Shared Agent 借 owner 凭据/Memory | Critical | caller-boundary integration test |
| 旧 memory.json 因新 storage_path 语义丢失 | High | copy/migrate/verify，不删除旧数据 |
| `/mnt/skills` 被旧 mount 覆盖 | High | mount audit + sandbox test |
| 上游 Web Tool 意外恢复公网访问 | High | default-deny policy + air-gap test |
| OIDC/RBAC 与 local RBAC 重复判定 | High | 两层职责矩阵 |
| Frontend 重引入 `/api/agents` 等 legacy 资源源 | High | contract tests |
| Docker 127.0.0.1 导致内网不可达 | Medium | BIND_HOST explicit |
| lockfile 手工冲突导致依赖漂移 | Medium | regenerate |
| Fault-zeroing 业务代码继续留 Harness | Medium | Phase 4 cleanup |
| 每个 upstream merge 仍需大范围 rename | High | 最终删除 `ideer` Runtime namespace |

---

# 27. 推荐 Commit 序列

保持 Conventional Commit。

示例：

```text
chore(upstream): lock deer-flow main <sha>
merge(upstream): import deer-flow main <sha>

chore(runtime): add upstream deerflow harness alongside ideer bridge
refactor(config): adopt upstream runtime config schema
refactor(runtime): adopt upstream persistence and checkpoint runtime
refactor(authz): bridge resource policy to upstream authorization provider
refactor(models): adopt upstream vllm provider
refactor(guardrails): adopt upstream verification and runtime guards
refactor(sandbox): adopt upstream sandbox lifecycle
refactor(mcp): adopt upstream mcp runtime
refactor(skills): project canonical resources into deerflow skill runtime
refactor(memory): migrate to upstream memory manager
refactor(subagents): adopt upstream delegated task runtime
feat(extensions): add agentplatform enterprise extension

refactor(resources): move resource governance out of ideer harness
refactor(workflows): move workflow engine out of ideer harness
refactor(business): move fault-zeroing runtime logic into resource package

fix(migrations): merge agentplatform and deerflow schema histories
refactor(frontend): reconcile upstream runtime ui with resource control plane
chore(intranet): update offline distribution for upstream runtime
refactor(runtime): remove legacy ideer harness

test(upgrade): add upstream convergence acceptance coverage
docs(upgrade): record upstream patch ledger and acceptance report
```

不要做成：

```text
fix merge conflicts
```

一个 10000 行、无法审计的 commit。

---

# 28. Integration PR 的交付材料

PR 不能只写：

```text
merge latest DeerFlow
```

必须附：

```text
1. UPSTREAM_LOCK
2. Feature Adoption Matrix
3. Conflict Ledger
4. Upstream Patch Ledger
5. DB Migration Report
6. Resource Governance Regression Report
7. Runtime Acceptance Report
8. Frontend Test Report
9. Fault Zeroing Acceptance
10. SRS Acceptance
11. Offline Fresh Install Report
12. Security / Network Egress Report
13. Remaining Known Differences
```

---

# 29. 最终 Definition of Done

只有以下全部满足，才允许：

```text
integration/... → develop
```

## Git

```bash
git merge-base --is-ancestor "$UPSTREAM_SHA" HEAD
```

exit 0。

## Runtime

- `deerflow.*` 为唯一主 Runtime；
- `ideer.*` Runtime 已删除；
- DeerFlow Harness 与 upstream 差异有完整 Patch Ledger；
- Extension API 生效；
- Memory/SubAgent/MCP/Guardrail/Run 使用上游实现。

## AgentPlatform

- Resource Governance V2 无语义回退；
- Workflow 正常；
- Business Packages 正常；
- Department/Visibility/Approval 正常；
- Run Resource Snapshot 正常。

## Security

- Tool assembly-time auth；
- runtime auth；
- model auth；
- sandbox auth；
- network default deny；
- shared resource caller boundary。

## Data

- fresh DB；
- existing DB；
- resource count/hash；
- migration；
- memory migration；
- history。

## Tests

```text
focused tests green
backend standard green
frontend standard green
pr-standard green
core-full green
fault-zeroing green
SRS green
offline fresh install green
```

## Offline

- 完全断网可安装；
- 不需要公网 API；
- vLLM 可运行；
- Office 可运行；
- resource/workflow/memory/subagent 可运行。

---

# 30. 下一轮上游升级的维护模式

这次融合完成后，不应再回到 Long-lived Runtime Fork。

采用：

```text
upstream DeerFlow
      │
      ▼
thin runtime patch set
      │
      ▼
AgentPlatform Extension
      │
      ▼
Control Plane / Workflow / Distribution
```

建议每次上游升级前：

```bash
git fetch upstream
git log <last_upstream_sha>..upstream/main
git diff --stat <last_upstream_sha>..upstream/main
```

然后更新 Feature Adoption Matrix。

最终目标：

> 新一轮 upstream merge 的主要冲突集中在 Gateway Integration、Extension API compatibility 和 Frontend，而不是 Memory/SubAgent/Sandbox/Models 等整个 Runtime。

---

# 31. Coding Agent Master Instruction

以下内容可以直接作为 Coding Agent 的任务总提示词使用。

---

## TASK

将固定 SHA 的 `bytedance/deer-flow/main` 融合进 `Neowyh/AgentPlatform/develop`，在完整保留 AgentPlatform Resource Governance V2、Workflow、Business Packages 和 Air-Gapped Intranet Distribution 的前提下，使 DeerFlow 最新 Runtime 成为新的基础运行时，并最大限度减少长期 Harness Fork。

## NON-NEGOTIABLE INVARIANTS

1. Skill / Agent / Workflow canonical UUID Resource Governance 不得退化。
2. Run 必须冻结完整 resource UUID/version/hash dependency snapshot。
3. Shared Resource 必须使用 caller identity/credential/memory/tool permission。
4. Workflow 必须继续是一等 Resource。
5. `/api/resources` 不得被旧名称 API 重新替代为 canonical source。
6. Fault Zeroing / SRS / Office / Offline bundle 必须通过现有验收。
7. 内网默认不得产生公网依赖或公网 egress。
8. 不得删除历史 Resource / Run / Memory 数据来规避 migration 问题。
9. 不得用全局 find-replace 把 `ideer` 改成 `deerflow`。
10. 不得把上游新 Runtime 持续人工翻译进 `ideer.*`。
11. 最终 `deerflow.*` 为 Runtime 真源；AgentPlatform 差异移到独立 package / extension / app layer。
12. 每一处最终保留在 `backend/packages/harness/deerflow/**` 的本地 diff 必须登记 Upstream Patch Ledger。

## EXECUTION ORDER

1. Read all applicable `AGENTS.md`.
2. Run baseline + core-full + business acceptance.
3. Lock `DEVELOP_BASE`, `UPSTREAM_SHA`, `MERGE_BASE`.
4. Tag current develop.
5. Probe merge and produce conflict ledger.
6. Create integration branch.
7. Perform mechanical merge.
8. Temporarily keep `ideer.*` + upstream `deerflow.*` dual runtime.
9. Adopt upstream runtime module by module:
   - config/trace
   - persistence/run/checkpoint
   - authz
   - models
   - guardrails/verification
   - sandbox
   - MCP
   - Skill runtime
   - Memory
   - Sub-Agent
   - Scheduler
   - Extensions
10. Move AgentPlatform resources/workflows/business concerns outside `ideer` Harness.
11. Reconcile DB migrations.
12. Reconcile config.
13. Reconcile frontend.
14. Rebuild offline distribution.
15. Remove `ideer` Runtime.
16. Run full acceptance.
17. Verify upstream SHA is ancestor.
18. Audit remaining `deerflow` runtime diff against Patch Ledger.
19. Only then merge integration branch into develop.

## CONFLICT RULE

For each conflict, classify before editing:

```text
U = upstream-owned runtime
L = local product-owned
M = semantic merge
A = adapter
T = transitional
D = delete after replacement
```

Never resolve a conflict without documenting the classification.

## CODING RULE

Before editing a function/class/symbol:

- run GitNexus impact;
- HIGH/CRITICAL: stop and report;
- UNKNOWN: perform supplementary textual/call-path verification;
- write focused regression test;
- make minimal change;
- run focused test;
- run detect_changes before commit.

## TEST RULE

Do not claim a phase complete from unit tests alone.

High-risk changes require:

```bash
bash scripts/run-test-lane.sh pr-standard
```

Final release requires:

```bash
bash scripts/run-test-lane.sh core-full
bash scripts/check-intranet.sh
python scripts/run_fault_zeroing_acceptance.py
python scripts/smoke_srs_flow.py
```

plus fresh air-gap installation acceptance.

## FINAL SUCCESS CRITERIA

```text
deerflow runtime: upstream-first
AgentPlatform control plane: preserved
resource semantics: preserved
workflow semantics: preserved
offline: preserved
business agents: preserved
upstream new capabilities: active or intentionally config-disabled
legacy ideer runtime: removed
untracked upstream kernel patches: zero
full tests: green
```

---

# 32. 参考基线

执行前必须重新打开并以固定 SHA 为准核对：

## AgentPlatform

- Repository  
  `https://github.com/Neowyh/AgentPlatform/tree/develop`
- `AGENTS.md`  
  `https://github.com/Neowyh/AgentPlatform/blob/develop/AGENTS.md`
- Resource Governance V2 ADR  
  `https://github.com/Neowyh/AgentPlatform/blob/develop/docs/decisions/2026-08-14-resource-governance-v2.md`
- Architecture  
  `https://github.com/Neowyh/AgentPlatform/blob/develop/docs/architecture/overview.md`
- Intranet Config  
  `https://github.com/Neowyh/AgentPlatform/blob/develop/config.intranet.yaml`
- Scripts  
  `https://github.com/Neowyh/AgentPlatform/tree/develop/scripts`
- Bundled Resources  
  `https://github.com/Neowyh/AgentPlatform/blob/develop/bundled-resources.json`

## DeerFlow

- Repository  
  `https://github.com/bytedance/deer-flow/tree/main`
- CHANGELOG  
  `https://github.com/bytedance/deer-flow/blob/main/CHANGELOG.md`
- Backend Agent Guide  
  `https://github.com/bytedance/deer-flow/blob/main/backend/AGENTS.md`
- Harness  
  `https://github.com/bytedance/deer-flow/tree/main/backend/packages/harness/deerflow`
- Extension API  
  `https://github.com/bytedance/deer-flow/tree/main/backend/packages/extension-api`
- Config  
  `https://github.com/bytedance/deer-flow/blob/main/config.example.yaml`

---

# 33. 最终原则

这次工作的成功标准不是：

> “所有 Git 冲突都消失了。”

而是：

> **从此以后 AgentPlatform 与 DeerFlow 的差异，主要代表企业产品价值，而不是历史 Fork。**

判断一个本地差异是否应该继续存在，只问三个问题：

1. 这是 AgentPlatform 的企业产品价值吗？
2. 这是内网环境的真实约束吗？
3. 这是上游 Extension/Adapter 无法表达的能力吗？

三个答案都是否定的：

> 删除本地实现，采用 upstream。

只有这样，这次合并才不是一次性的“大升级”，而是把 AgentPlatform 重新带回一条可持续升级的产品线上。
