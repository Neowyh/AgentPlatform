# M4 Gate 5／6 验收记录 — Knowledge Revision、Publish 与 Run Snapshot

- 候选分支: `feature/m4-knowledge-revisions`
- 验收日期: 2026-09-15
- 依据: `.scratch/m4-knowledge-revisions/`（票 01–06）、总方案 M4 任务卡、知识专项方案 Gate 5/6、双层真源 ADR
- 结论: **当前候选 READY** — 真实 RAGFlow provider 验收 20/20 通过，真实模型 Agent/Workflow A/B/PINNED 各 3/3 通过，且隔离浏览器真实触发 Workflow、持久化 worker 执行并在运行详情展示冻结 KB/Revision/manifest 快照的闭环已通过。适用标准、阻塞 I/O、前端 full、visual、a11y 与真实浏览器 lane 均已留存结果。

## 1. 交付提交

| 票 | 提交 | 内容 |
| --- | --- | --- |
| 01 | `3b2b8fdf` | Revision 候选创建与查看（表/ORM/服务/API/版本页） |
| 02 | `005bffa5` | 发布不可变 Revision（per-revision dataset、门禁、有界重试） |
| 03 | `e1e1321e` | LIVE Run 冻结（闭包解析/快照扩列/队列冻结/投影脱敏） |
| 04 | `2f9ec3b1` | PINNED 选择与固定运行（共享选择器/校验矩阵） |
| 05 | `41e90cdd` | 对账与漂移可见性（check 历史/完整性门禁/admin 视图） |
| 06 | `dddb72d4` | 真实验收暴露的 RAGFlow client 兼容修复 + Patch Ledger 登记 |

## 2. 真实 provider 验收（Gate 5/6 核心）

隔离 RAGFlow v0.27.1 栈（`ideer-ragflow`，127.0.0.1:9380，healthy）+ 真实平台服务层
（ResourceService / KnowledgeDocumentService / KnowledgeRevisionService /
reconciliation）+ 真实 Alembic 迁移 SQLite 库。脚本：`dev-log/m4_gate_acceptance.py`。
当前候选于 2026-09-15 使用本机健康隔离栈重跑，结果 **20/20 PASS**（关键项摘录）：

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| fresh/existing 数据库迁移 | PASS | `upgrade head` 1.3–3.5s；head-1 种子记录（revision 行）在升级后保留 |
| Rev1 真实发布 | PASS | 真实 create_dataset/上传/解析（5–10s），dataset 指纹 `2e1ddcb4…` |
| Run A 冻结 + 检索来源 | PASS | Run A 快照绑定 Rev1 dataset；RAGFlow retrieve 实际返回 GATE-V1 内容 |
| Rev2 发布后版本纪律 | PASS | Run B 用 Rev2；Run A 仍 Rev1；Rev1 dataset 检索仍 GATE-V1（不可变） |
| PINNED Rev1 | PASS | Rev2 active 时 PINNED 新 Run 仍取 Rev1 dataset |
| 发布失败恢复 | PASS | 坏 provider 导致 failed 且指针不切（attempt=1）；真实 provider 重试后 published（attempt=2） |
| 真实漂移注入 | PASS | 删除 active revision 的 provider 文档 → MISSING_DOCUMENT → DRIFTED |
| 漂移阻断 | PASS | LIVE 闭包解析与 PINNED 声明保存均被拒绝（`drifted`） |
| orphan 可见不删除 | PASS | 平台前缀孤立 dataset 被对账报告；验证仍存在、无自动删除 |

真实 provider 验收同时暴露并修复三个既有 client 缺陷（`dddb72d4`，已登记
`UPSTREAM_PATCH_LEDGER.md` PATCH-001）：单文档 parse 404（改批量端点）、单文档
GET 非 JSON（状态改经列表端点）、DELETE query 形式被拒（改 JSON body）。
本次重跑还修正验收脚本对异步文档状态的轮询：每轮调用
`KnowledgeDocumentService.sync_status`，不再只读取本地的 `processing` 状态。

## 3. 测试 lane

| Lane | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| backend-standard（票 01–05 各轮 + 终验） | `bash scripts/run-test-lane.sh backend-standard` | 历史候选 25834→25874 passed, 0 failed；当前候选见 §8 | 1110–1430s/轮 |
| frontend unit（票 01–05 各轮 + 终验） | `pnpm test` | 历史候选 359→361 files, 9988→10000 tests passed；当前候选见 §8 | ~700s |
| pr-standard（M4 终验） | `bash scripts/run-test-lane.sh pr-standard` | 当前候选父 lane incomplete（40 分钟超时）；backend/frontend 子 lane 通过，smoke 既有本候选运行通过，补跑因环境性页面启动失败中止 | 2447s（超时） |
| 聚焦套件 | knowledge / resources / workflows / gateway / persistence 各票 | 当前候选 114 passed（详见 §8） | — |
| inventory / 守卫 | `python3 scripts/test_inventory.py`；迁移单 head + schema 守卫 | 通过（head=`20260915_knowledge_publish_lease`） | — |

一次前端全量出现 1 例 `workflows page.test.tsx` 并行负载超时，单文件复跑 84/84
通过，判定为环境性偶发（非产品代码），已记录。

## 4. 真实／替身／未执行分项

- **真实 RAGFlow**：发布构建、文档摄取/解析、检索来源证明、漂移注入、orphan 探测、对账。
- **替身（FakeProvider）**：单元级门禁矩阵、并发/重试边界、失败注入（真实 provider 无法安全注入的路径）。
- **真实模型（LLM）运行：通过** — DeepSeek v4 pro 上 Agent A／B／PINNED 3/3、Workflow A／B／PINNED 3/3 均通过；输出分别保持 Rev1、Rev2、Rev1，实际工具回执包含对应 RAGFlow 文档来源。Workflow bridge 保留输入、沙箱、安全、工具错误及工具回执中间件，并以显式 `max_turns`/超时限制运行边界。版本冻结证据由平台冻结层（闭包解析 + `run_resource_snapshots` 知识列 + 冻结 dataset 的真实检索）提供，符合"模型最终答案正确率不替代版本冻结证据"的验收纪律。
- **浏览器走查：通过** — 使用生产构建和 auth-disabled 本机全栈运行完整 visual lane，174 项中 173 passed、1 skipped，耗时 470 秒；核心 visual（Agent gallery、Workflow editor、Admin dashboard）3/3 通过，管理员对账页组件回归通过。另在真实 DeepSeek/RAGFlow 配置下隔离启动网关与 Workflow worker，浏览器触发真实 Workflow，运行详情显示冻结 KB、Revision 与 manifest 摘要，测试 1 passed（1.8 分钟）。
- Agent 真实模型脚本 `dev-log/m4_real_model_acceptance.py` 已在 DeepSeek v4 pro 上完成 A-REV1、B-REV2、PINNED-REV1（3/3），输出分别为 `GATE-V1 pineapple`、`GATE-V2 mango`、`GATE-V1 pineapple`。
- 同一脚本的 Workflow A-REV1、B-REV2、PINNED-REV1 也已完成 3/3，工具回执分别指向 Rev1、Rev2、Rev1 的冻结 dataset。
- 本次完整输出保存在 `dev-log/m4-real-model-acceptance-20260915.log`（不含凭据）。
- **GitNexus**：本工作区无 `.gitnexus` 索引且 `npx gitnexus` 无法引导（网络受限）；impact/detect_changes 以人工调用方分析 + 全量 lane 替代（环境限制，已在 dev-log 记录）。

## 5. 隔离验收资产处置

- `dev-log/m4-acceptance-runtime/`（3 个验收 SQLite 库 + 文件存储副本）：验收后删除。
- `dev-log/m4_gate_acceptance.py` 与本记录：保留作为历史证据。
- RAGFlow 冒烟租户内的验收 dataset（每次发布的 per-revision dataset 与 orphan 样本）保留于隔离栈，未自动清理（对账"只读"纪律）；client 未实现 delete_dataset，后续如需回收由运维按 findings 处理。

## 6. 已知差异与评审加固（2026-09-14）

- **HASH_MISMATCH 判定基准（票 05 评审发现，已修复）**：RAGFlow 内部内容摘要不是源文件 SHA-256（HTTP 文档对象亦不承诺返回该字段），因此对账只在 provider 返回 **64 位十六进制摘要且与 manifest 不一致** 时判定 HASH_MISMATCH；缺失或外来格式的摘要一律记为 UNVERIFIED，不误报 HEALTHY 也不误报缺失。真实 RAGFlow 上 content 级篡改因此通常表现为 UNVERIFIED 而非确认漂移——这是"不误报"纪律下的诚实降级；文档集合与存在性检查不受影响。
- **卡死 indexing 的恢复（票 02 评审发现，已修复）**：发布构建由网关进程内后台任务执行，进程重启会留下 `indexing` 状态。`publish_revision` 现在区分"本进程仍在构建"（409）与"执行器已丢失"（进程重启后自动恢复构建，不消耗尝试次数）；发布中标记 `_ACTIVE_PUBLISHES` 由 `execute_publish` 在退出时清理。
- **profile 实际值冻结（票 03 评审发现，已修复）**：`run_resource_snapshots` 新增 `retrieval_profile_json`/`embedding_profile_json` 列，快照同时保存 profile 实际值与摘要；Workflow 运行证据的 `knowledge_scope.revisions` 一并携带实际值。
- **orphan 归属（票 05 评审发现，已修复）**：orphan 检查归一次对账运行所有（`knowledge_revision_checks.knowledge_base_id` 可空，迁移 `20260914_knowledge_orphan_check_scope`），不再按 KB 复制，且无已发布版本时同样可见；admin 查询按 KB 返回时会附带 run 级 orphan 检查。
- **Workflow 终止路由（本轮真实模型探针发现，已修复）**：Workflow bridge 在请求上下文中使用与 `ThreadData`/沙箱条件路由兼容的 middleware 子集；保留输入、文件/沙箱、工具回执、工具错误处理和安全终止，并继续以显式 `max_turns`/超时限制运行边界。真实 Workflow A/B/PINNED 已在 RAGFlow 恢复后重跑并 3/3 通过。
- **评审其余 Standards 项同步修复**：`PUBLISHED_DATASET_NAME_PREFIX` 共享常量、`knowledge/settings.py` 配置读取器、`knowledge/integrity.py` 状态常量复用、`publish_revision` provider 必填 + 路由 503、恒 None 实参移除、`run_reconciliation` 拆分；前端依赖选择器迁移 react-query，四个新组件文案接入 i18n（en-US/zh-CN）。

## 7. pr-standard 历史终验（2026-09-13，评审加固前：`TEST_LANE_DURATION lane=pr-standard seconds=2146 status=0`）

| 子 lane | 结果 | 耗时 |
| --- | --- | --- |
| runtime-boundary | `OK: boundary is not larger than baseline (0)` | — |
| backend-standard | 25878 passed, 145 skipped, 0 failed（`status=0`） | 1293s |
| frontend-standard | 361 files / 10000 tests passed（`status=0`） | 594s |
| frontend-smoke（Playwright @smoke） | 29 passed（`status=0`） | 256s |

各子 lane 均为 `status=0`，父级 `pr-standard` `TEST_LANE_DURATION status=0`。

## 8. 当前候选复核（2026-09-15）

- M4 聚焦套件：114 passed，覆盖发布、PINNED superseded、冻结 profile、对账历史版本、迁移 fresh/existing。
- frontend-standard：最终候选 **362 files / 10061 tests passed**，`TEST_LANE_DURATION status=0`（318s）；frontend-smoke 先前同一候选运行 **29 passed**，后续补跑因页面启动 `ERR_ABORTED` 中止，记录为 incomplete；frontend-a11y：3 passed。
- backend-blocking-io：96 passed（`TEST_LANE_DURATION status=0`）。
- backend-standard：最终候选 **25906 passed、146 skipped、0 failed**，`TEST_LANE_DURATION status=0`（1802s）。
- frontend-visual：173 passed、1 skipped，`TEST_LANE_DURATION lane=frontend-visual seconds=470 status=0`；使用生产构建避免开发服务器冷编译超时。admin dashboard 新增 Knowledge Reconciliation 卡片的 snapshot 已更新并由核心测试验证。
- 当前候选已有 §2 的隔离真实 RAGFlow 20/20 记录、Agent/Workflow 真实模型各 3/3 记录、完整基础 UI visual 证据，以及真实模型浏览器触发的 Workflow Run detail 验证；页面显示冻结 KB、Revision 与 manifest 摘要，运行最终为 completed。
- 隔离真实浏览器 lane 已于当前候选重跑：seed 链路已修正为当前 Resource API 并成功创建、发布 Agent；start 脚本 manifest 指向 DeerFlow 实际使用的 `deerflow.db`，并使用 liveness 检查等待应用启动。RBAC 两项真实浏览器检查通过；可见性申请／审批真实浏览器定向 lane **2/2 passed**，真实模型 Workflow 定向 lane **1/1 passed**（canonical resource ID、英中文案、审批后状态、真实 worker 执行及冻结快照均已验证）。完整基础 lane 为 **6 passed、1 skipped、0 failed**。
- Real E2E 定向命令支持 `REAL_E2E_GREP`，本次可见性证据来自 `REAL_E2E_GREP='real visibility applications' bash backend/scripts/run-real-e2e.sh`，父进程 lane 退出状态为 0。
- 最近一次完整 real lane 在允许本地 socket 的环境中为 **6 passed、1 skipped、0 failed**：RBAC 2/2、可见性 2/2、Workflow Run detail 1/1、memory persistence 1/1；knowledge-center 仍按环境条件 skipped。
- 生产 Workflow Run detail 定向 lane：`REAL_E2E_GREP='real workflow run snapshot' bash backend/scripts/run-real-e2e.sh`，**1 passed**；seed 通过生产 Resource/Workflow Run API 创建记录，再以隔离 SQLite 快照验证页面渲染。
- 运行详情页新增浏览器级快照断言（Workflow run detail mock：KB、版本号、manifest 摘要）；相关前端组件/页面测试本轮 **29 passed**，并由真实模型浏览器 lane 补充端到端验证。
- 真实模型浏览器 Workflow lane：`REAL_E2E_REAL_MODEL=1 REAL_E2E_GREP='real browser model workflow' bash backend/scripts/run-real-e2e.sh`，**1 passed（1.8 分钟）**；使用真实 DeepSeek/RAGFlow，隔离数据库由网关与 Workflow worker 共同执行，浏览器触发运行并验证 completed 与冻结 manifest 摘要。脚本的 real-model 分支会启动对应持久化 worker，默认 lane 不受影响。
