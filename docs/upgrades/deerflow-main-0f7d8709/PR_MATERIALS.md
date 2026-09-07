# Integration PR materials — deerflow-main-0f7d8709

实施方案 §28 要求 Integration PR 附带 13 项交付材料。本文件是材料索引：逐项映射到
本目录的持久化证据文档，并记录最终 lane 状态。PR 描述直接引用本表。

## PR 目标与拓扑

- 分支：`integration/deerflow-main-0f7d8709` → `develop`
- 领先 develop 2623 个提交，落后 0（可干净合入）
- §29 Git DoD：`git merge-base --is-ancestor deerflow/main HEAD` → exit 0（通过）
- Commit 规范：全部 Conventional Commit，无 "fix merge conflicts" 类提交（§27 约束）

## §28 交付材料映射

| # | 材料 | 证据文档 | 状态 |
|---|---|---|---|
| 1 | UPSTREAM_LOCK | `UPSTREAM_LOCK.md`（锁定 deer-flow main `0f7d8709`，harness 差异全部登记） | complete |
| 2 | Feature Adoption Matrix | `FEATURE_ADOPTION_MATRIX.md` | complete |
| 3 | Conflict Ledger | `CONFLICT_LEDGER.md` | complete |
| 4 | Upstream Patch Ledger | `UPSTREAM_PATCH_LEDGER.md`（PATCH-001..013，含证据更新） | complete |
| 5 | DB Migration Report | `MIGRATION_ACCEPTANCE_REPORT.md` + `BASELINE_REPORT.md` 双 migration 树章节 | complete |
| 6 | Resource Governance Regression Report | `AUTHORIZATION_ACCEPTANCE_REPORT.md` | complete |
| 7 | Runtime Acceptance Report | `BASELINE_REPORT.md`（含六轮会话增补） | complete |
| 8 | Frontend Test Report | `BASELINE_REPORT.md` 各增补 + 本文件 lane 记录 | complete |
| 9 | Fault Zeroing Acceptance | `BASELINE_REPORT.md` 最终增补（canonical seam + 端到端脚本结果） | 见 lane 记录 |
| 10 | SRS Acceptance | `BASELINE_REPORT.md`（`smoke_srs_flow.py` ALL CHECKS PASSED） | complete |
| 11 | Offline Fresh Install Report | `BASELINE_REPORT.md` "Not runnable in sandbox"（需隔离环境，如实记录） | honest-record |
| 12 | Security / Network Egress Report | `NETWORK_EGRESS_REPORT.md` | complete |
| 13 | Remaining Known Differences | `FEATURE_ADOPTION_MATRIX.md` 差异列 + `BASELINE_REPORT.md` 各增补的 honest record | complete |

## 收尾轮（2026-09-07）产品修复提交

| Commit | 内容 |
|---|---|
| `aee2bd08` | serial 套件对齐融合后运行时（IDEER_*→DEER_FLOW_* 环境变量、.deer-flow/data 默认目录、双迁移树改写、session pool 断言更新） |
| `781e8bad` | 路由页 header canonicalTitle 接线（thread-title-sync 产品缺口）+ mock 模式下三处 chat surface 的 metadata GET |
| `7d9eb137` | workbench 路由页四处融合丢失接线恢复（displayThreadId、handleSubmit options、goal 集成、分支接线） |
| `08f525ad` | Settings dialog 三 tab 恢复、sidecar/browser 接线、docs 仓库 base 双段路径修复、移动端溢出修复 |
| `98b3816e` | Workflows 侧栏入口恢复 + thread-page/docs 单测镜像同步 |
| `e0348684` | composer slash 建议层 testid 恢复（chat-input / slash-overlay / slash-option-*） |

## 收尾轮（2026-09-07）Lane 记录

| Lane | 结果 | 证据 |
|---|---|---|
| pr-standard | passed（2026-09-06，首次全绿） | `BASELINE_REPORT.md` P8 增补 |
| check-runtime-boundary | passed（0 ideer 直连导入文件） | 本轮 core-full 第 1 阶段 |
| backend-full standard | passed：11916 passed / 18 skipped（2 个负载抖动用例单跑复验通过） | 本轮 core-full |
| backend-full serial | passed：75 passed / 1 skipped（merge-head 设计性跳过） | commit `aee2bd08` 后全绿 |
| frontend-core vitest coverage | passed：356 文件 / 9913 tests（coverage 半区经补装 `@vitest/coverage-v8@5` 后首次真正运行） | 本轮 core-full |
| frontend-core pnpm check | passed（exit 0，0 errors） | 本轮 core-full |
| frontend-mock-e2e（全量） | partial：历史功能语料 270 passed / 68 failed / 1 flaky；本轮 handoff 残留聚焦验证 13/13；required full rerun completed 348 collected tests: 311 passed / 14 failed / 3 flaky / 20 skipped, with residual failures concentrated in legacy fixtures and unwired admin/audit mocks | `BASELINE_REPORT.md` 收尾增补 |
| core-full（整链） | boundary ✓、backend-full ✓、frontend-core ✓、mock-e2e partial（handoff 残留聚焦验证完成；全量已完成但仍有环境/历史 fixture 残余失败） | 本表 + 收尾增补 |
| check-intranet | not runnable（无 Docker，如实记录） | — |
| fault-zeroing 端到端 | incomplete（环境性）：DeepSeek 端点可达且 canonical seam 全链路真实执行（bundle seed → intake 暂停 → 操作员确认 → 多轮 subagent 产出），但 `deductive_tree` 节点在 900s/1800s/3600s 三档节点预算下均超时——瓶颈为沙箱到外部模型的推理往返延迟；worker 链路由 8/8 集成测试守护 | `BASELINE_REPORT.md` 收尾增补 |
| offline fresh install | not runnable（需隔离环境，如实记录） | — |

## Mock-e2e final verification note (2026-09-07)

The focused thread-history/sidebar regression cases passed after the pagination and missing-thread route fixes. A required fresh full rerun was started with `--workers=2 --retries=2`, but is recorded as **incomplete**: the local dev server exited around test 85/348 after 3.8 minutes (28 passed, 1 flaky, 296 did not run), and the remaining attempts reported `ERR_CONNECTION_REFUSED`. The prior completed full-run result remains the comparable corpus result above: 311 passed / 14 failed / 3 flaky / 20 skipped.

The subsequent final run used a rebuilt production bundle/server and completed the full 348-test corpus with **328 passed / 20 skipped / 0 failed / 0 flaky** under `--workers=2 --retries=2`. The earlier incomplete run is retained above as historical environment evidence; this final result is authoritative for handoff completion.
