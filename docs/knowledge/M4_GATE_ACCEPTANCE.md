# M4 Gate 5／6 验收记录 — Knowledge Revision、Publish 与 Run Snapshot

- 候选分支: `feature/m4-knowledge-revisions`
- 验收日期: 2026-09-13
- 依据: `.scratch/m4-knowledge-revisions/`（票 01–06）、总方案 M4 任务卡、知识专项方案 Gate 5/6、双层真源 ADR
- 结论: **通过（含明确记录的未执行项）** — 票 01–05 交付完成；票 06 真实 provider 验收 20/20 通过、迁移与 lane 全绿；真实 LLM 运行与浏览器走查因环境无模型凭据未执行（见 §5）。

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
结果 **20/20 PASS**（关键项摘录）：

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

## 3. 测试 lane

| Lane | 命令 | 结果 | 耗时 |
| --- | --- | --- | --- |
| backend-standard（票 01–05 各轮 + 终验） | `bash scripts/run-test-lane.sh backend-standard` | 25834→25874 passed, 0 failed；`TEST_LANE_DURATION status=0` | 1110–1430s/轮 |
| frontend unit（票 01–05 各轮 + 终验） | `pnpm test` | 359→361 files, 9988→10000 tests passed | ~700s |
| pr-standard（M4 终验） | `bash scripts/run-test-lane.sh pr-standard` | 见 §6 追加记录 | — |
| 聚焦套件 | knowledge / resources / workflows / gateway / persistence 各票 | 全绿（178–2502 passed/轮） | — |
| inventory / 守卫 | `python3 scripts/test_inventory.py`；迁移单 head + schema 守卫 | 通过（head=`20260913_knowledge_revision_integrity`） | — |

一次前端全量出现 1 例 `workflows page.test.tsx` 并行负载超时，单文件复跑 84/84
通过，判定为环境性偶发（非产品代码），已记录。

## 4. 真实／替身／未执行分项

- **真实 RAGFlow**：发布构建、文档摄取/解析、检索来源证明、漂移注入、orphan 探测、对账。
- **替身（FakeProvider）**：单元级门禁矩阵、并发/重试边界、失败注入（真实 provider 无法安全注入的路径）。
- **真实模型（LLM）运行：未执行** — 本环境无任何模型凭据（无 `config.yaml`/`.env`，环境变量无 API key），Agent/Workflow Run 无法完成模型调用。版本冻结证据由平台冻结层（闭包解析 + `run_resource_snapshots` 知识列 + 冻结 dataset 的真实检索）提供，符合"模型最终答案正确率不替代版本冻结证据"的验收纪律。
- **浏览器走查：部分未执行** — 候选查看/发布/版本选择已有组件单测（25+ 个 library/selector 用例）覆盖交互与状态；浏览器端完整走查及"Run 版本查看"页面因需全栈 + 真实模型运行未执行。
- **GitNexus**：本工作区无 `.gitnexus` 索引且 `npx gitnexus` 无法引导（网络受限）；impact/detect_changes 以人工调用方分析 + 全量 lane 替代（环境限制，已在 dev-log 记录）。

## 5. 隔离验收资产处置

- `dev-log/m4-acceptance-runtime/`（3 个验收 SQLite 库 + 文件存储副本）：验收后删除。
- `dev-log/m4_gate_acceptance.py` 与本记录：保留作为历史证据。
- RAGFlow 冒烟租户内的验收 dataset（每次发布的 per-revision dataset 与 orphan 样本）保留于隔离栈，未自动清理（对账"只读"纪律）；client 未实现 delete_dataset，后续如需回收由运维按 findings 处理。

## 6. pr-standard 终验（2026-09-13，`TEST_LANE_DURATION lane=pr-standard seconds=2146 status=0`）

| 子 lane | 结果 | 耗时 |
| --- | --- | --- |
| runtime-boundary | `OK: boundary is not larger than baseline (0)` | — |
| backend-standard | 25878 passed, 145 skipped, 0 failed（`status=0`） | 1293s |
| frontend-standard | 361 files / 10000 tests passed（`status=0`） | 594s |
| frontend-smoke（Playwright @smoke） | 29 passed（`status=0`） | 256s |

各子 lane 均为 `status=0`，父级 `pr-standard` `TEST_LANE_DURATION status=0`。
