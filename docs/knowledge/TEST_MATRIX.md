# Test Matrix — 知识方案 §95–99 到测试文件的映射（M2 Ticket 01 产出）

> audience: developers, testers<br>
> status: current<br>
> owner: engineering maintainers<br>
> last-verified: 2026-09-11<br>
> canonical-path: `docs/knowledge/TEST_MATRIX.md`

把知识方案 §95–99 测试矩阵逐条映射到本仓库测试文件（现有文件给出锚点，新文件给出建议路径）。路径与命名遵循仓库规约：后端 `backend/tests/unit|integration|contracts/` 的 `test_*.py`；前端 `frontend/tests/unit/` 镜像 `src/` 树。Lane 定义见 `scripts/run-test-lane.sh`。

实施票归属：**票 02** = KB 资源治理；**票 03** = LIVE/PINNED 依赖；**票 04** = Effective Scope + 运行时适配；M4/M5 为后续里程碑占位。现状勘察锚点见 `IMPLEMENTATION_INVENTORY.md`。

## 1. §95 Unit

### 1.1 Knowledge Service（票 02 为主）

| 矩阵项 | 落点 | 要点 |
| --- | --- | --- |
| create | 新建 `backend/tests/unit/knowledge/test_knowledge_base_service.py`；风格参照 `backend/tests/unit/resources/test_resource_service_access.py`、`test_resource_service_governance.py` | `ResourceType.KNOWLEDGE_BASE` 创建走 `ResourceService.create_resource`；storage 规则 KB⇒database；`(type, owner, slug)` 唯一 |
| update | 同上 | 声明式 Content 草稿/发布走 database draft 路径（`ResourcePublisher.save_database_draft/publish_database`，`resources/publisher.py:190/216`）；Content 不含 provider_dataset_id/api key（知识方案 §75） |
| permission | 同上 + 既有 `test_resource_service_access.py` 扩展 | `_visible_query` 对 KB 生效：private/department/public × owner/部门/超管（`IMPLEMENTATION_INVENTORY.md` §1.3） |
| provider mapping | 同上 | 绑定/换绑 dataset：`provider_dataset_id` opaque、唯一约束、可空（SCHEMA_PLAN §2）；dataset ID 不入导出（`GET /export`，`resources.py:913`） |
| revision | M4：`backend/tests/unit/knowledge/test_knowledge_revision_service.py` | revision_no 自增、status 机、manifest_hash、发布不可变 |
| manifest hash | M4 同上 | manifest → hash 稳定性 |

### 1.2 Provider（M2 已有 + M3 扩展）

| 矩阵项 | 落点 | 要点 |
| --- | --- | --- |
| search | 既有 `backend/tests/test_ragflow_tools.py`（~34 例）、`backend/tests/test_ragflow_client.py` | 已覆盖：分组并行（≤4）、空 dataset 跳过、rank 交错、分页 |
| upload / status | M3：新建 `backend/tests/unit/knowledge/test_knowledge_provider.py` | 管理侧 Provider（复用 harness client 共享 base_url/auth/timeout/error mapping/redaction，知识方案 §18） |
| timeout | 既有 client 测试错误归一化锚点（`test_ragflow_client.py:170-246`）扩展超时分支 | `RAGFlowConnectionError` 归一 |
| redaction | 既有 `test_ragflow_tools.py:496-602`（API key 永不泄漏、dataset ID 仅错误路径、base_url 永不外发 `:574-600`） | M2 新增断言：绑定/解绑 API 的错误同样脱敏 |

### 1.3 Scope（票 03/04 为主）

| 矩阵项 | 落点 | 要点 |
| --- | --- | --- |
| dependency | 新建 `backend/tests/unit/knowledge/test_knowledge_dependency.py`；类型矩阵锚点 `_assert_dependency_type`（`resources/service.py:1067`） | agent/workflow→knowledge_base 合法；KB→∅；pinned 无 revision 拒绝 |
| visibility | 既有 `test_resource_service_governance.py` 可见性闭合用例扩展到 KB | public 源→KB 目标可见性闭合规则不变 |
| caller | 新建 `backend/tests/unit/knowledge/test_effective_knowledge_scope.py` | caller 无权 KB 被交集剔除（§96 B/C 的 unit 前置） |
| workflow | 既有 `backend/tests/unit/workflows/test_v2_canonical_run.py` 旁新建 workflow-scope 用例 | workflow 声明的 KB 范围不被 agent 步骤扩大（§96 D unit 前置） |
| live/pinned | `test_knowledge_dependency.py` | mode 持久化、字段校验、展示 payload（票 03 focused 三件套） |

## 2. §96 Integration

落点建议：`backend/tests/integration/knowledge/`，复用共享 fixture 模式 `backend/tests/integration/workflows/_resource_catalog.py`（canonical 目录 + 快照基建）。

| 场景 | 矩阵定义 | 落点与要点 |
| --- | --- | --- |
| A. Agent Dependency | Agent A→KB1、Agent B→KB2，A 搜不到 KB2 | 票 04：canonical agent run 装配后 scope 只含 KB1（`canonical_agent_run_preparation.py:33` 路径，参照 `tests/unit/gateway/test_canonical_agent_run.py` 提升） |
| B. User Permission | Agent 声明 KB1 但 caller 无权 → KB 不进 Effective Scope | 票 04：caller 权限交集剔除，且 KB 对模型不可见（装配期裁剪） |
| C. Shared Agent | 公开 Agent，caller 执行用 caller KB 权限而非 owner 的 | 票 04：caller–owner 交叉；锚定基线不变量 16 |
| D. Workflow | Workflow 指定 KB，agent 步骤不能越过 workflow scope | 票 04：workflow run 快照闭包 + 子图加载（`workflow_worker.py:82-183`） |
| E. Sub-Agent | Sub-Agent 不因 delegation 获得新 KB | 票 04：scope 交集 `Parent ∩ SubAgent dependency ∩ caller`（知识方案 §79）；锚定基线不变量 17 |

既有可参照的 integration 基建：`tests/integration/workflows/test_v2_snapshot_receipts_initialized_db.py`、`test_v2_db_execution.py`、`test_v2_subagent_receipt_executed_workflow.py`、`tests/integration/api/test_canonical_run_skill_projection_e2e.py`、`test_shared_resource_run_e2e.py`。

## 3. §97 Revision Tests（M4，票 03 先落声明半）

| 场景 | 落点 | 要点 |
| --- | --- | --- |
| LIVE：Run A 于 Rev1 创建 → 发布 Rev2 → Run A 仍 Rev1、Run B 用 Rev2 | M4：`backend/tests/unit/knowledge/test_knowledge_run_freeze.py`；冻结机制锚点 `ResourceService.create_run_snapshot`（`service.py:1250`）+ `CanonicalResourceLoader._frozen_version`（`runtime.py:107`） | LIVE = 启动时最新，非中途漂移（知识方案 §36）；快照唯一约束 `(run_id, resource_id)` 幂等 |
| PINNED：pinned Rev1 → 发布 Rev2 → 新 Run 仍 Rev1 | M4 同上 | pinned 解析固定 revision；票 03 先测 pinned 声明持久化与校验拒绝路径 |

## 4. §98 Retrieval Receipt Tests（M5，票 04 预留接口断言）

| 要点 | 落点 |
| --- | --- |
| run_id / KB UUID / revision / query hash / document / chunk / scores / tool receipt 完整关联 | M5：新建 `backend/tests/unit/knowledge/test_knowledge_retrieval_receipt.py`；receipt 现状（工具级哈希账本，无 KB 维度）见 `IMPLEMENTATION_INVENTORY.md` §6 |
| tool receipt 链路不回归 | 既有 `backend/tests/test_tool_receipt.py`、`test_receipt_verification.py`、`backend/tests/unit/agentplatform/test_receipt_projection.py`；票 04 保证 knowledge_search receipt 仍进 Run Evidence（`tool_receipt_middleware.py:76-81` → `agentplatform_extension/evidence.py:148-151`） |
| KNOWLEDGE_ACCESS_DENIED 可观测 | 票 04：与空结果 `"No relevant content found."`（`formatting.py:54`）可区分；receipt/错误串不含 dataset ID |

## 5. §99 Security Tests

| 矩阵项 | 落点 | 要点 |
| --- | --- | --- |
| raw dataset id injection | 票 04：`test_effective_knowledge_scope.py` + `test_ragflow_tools.py` 扩展 | 模型传 logical selector 之外任何值拒绝；KNOWLEDGE_ACCESS_DENIED 不回显 ID |
| provider id guessing | 票 04 | 猜 dataset ID 无法扩大 scope；scope 外 dataset 不发起检索 |
| unauthorized logical KB / hidden KB enumeration | 票 02 + 04 | 无权用户 `GET /api/resources` 不可见（`_visible_query`）、详情/绑定/管理 403/404；列表响应不泄漏存在性 |
| API key leakage | 既有 `test_ragflow_tools.py:496-602` | 已覆盖，票 02/04 新增路径（绑定 API、scope 拒绝错误）沿用 `_redact` |
| provider exception leakage | 既有 `:574-600`（base_url 不外发） | 新错误语义沿用 |
| path traversal upload / oversized / unsupported file | M3：`test_knowledge_provider.py` | 上传管线（知识方案 §54） |
| shared-resource privilege escalation | 票 04（§96 C 的安全断言面） | caller 权限而非 owner |
| subagent privilege escalation | 票 04（§96 E 的安全断言面） | delegation 不扩权 |

## 6. Lane 与前端映射

- **票 02**（resources 高风险）：focused（`test_knowledge_base_service.py` + `unit/persistence/test_migration_versions.py`）→ `cd backend && make test` → `bash scripts/run-test-lane.sh pr-standard`（含 `check-runtime-boundary.sh`，守住 harness 零 diff）。
- **票 03**：focused 三件套（声明/拒绝路径/持久化）→ `make test` → `pr-standard`。
- **票 04**（resources/authz 双高风险）：scope unit + integration 矩阵全量 → `make test` → `pr-standard`；如涉异步 I/O 改动另跑 `backend-blocking-io`；收尾按总方案可跑 `core-full`（仅显式验收请求）。
- 越权实测（票 04）：dev RAGFlow（`docker/ragflow/` profile，M1 交接物见 `IMPLEMENTATION_INVENTORY.md` §8）上两 KB × 两用户正反用例——手动/验收报告形式，参照 `docs/testing/knowledge-gate1-acceptance-report.md` 格式归档。
- 前端（票 03 最小 UI）：`frontend/tests/unit/app/workspace/capabilities/experts/[agent_name]/edit/page.test.tsx` 扩展 KB checkbox；API mock 约定参照 `frontend/tests/e2e/workflows/admin-management.spec.ts` 的 `/api/resources` route 拦截；运行 `cd frontend && pnpm test`。
