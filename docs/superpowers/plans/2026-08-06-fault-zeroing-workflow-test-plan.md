# 归零工作流测试计划（2026-08-06）

## 1. 目标

以 `workflows/fault-zeroing.yaml`（11 节点 DAG：fork 并行证据提取/演绎建树 → join → 审查检漏 → 整合裁决 → 证据评估 → 评估审核 → 评估优化 → 纠正措施(可 skip) → 文档生产）为测试对象，回归 `refactor/workflow-module` 上 3 个近期合并分支引入的功能变更，补齐自动化覆盖缺口，并通过平台真实链路验收。

## 2. 测试范围（聚焦近期 3 个合并分支）

| 合并分支 | 合入日期 | 变更特性 |
|---|---|---|
| `fix/workflow-node-status` (fbd3774e) | 2026-08-05 | fork/join/route 控制节点发出生命周期事件（bare `node_started`/`node_completed`），运行图显示真实状态 |
| `refactor/workflow-run-record` (547ecf40) | 2026-08-05 | ① 运行记录 jsonl+md 持久化 + 下载端点 ② 每轮工具调用进度流(`action_progress`) ③ 缺失产物默认 fail（不再 pause）④ 操作员 resume 免除 attempt 预算 ⑤ 节点输入 precondition 门控（fail/skip） |
| `fix/workflow-run-hygiene` (0cf07dd4) | 2026-08-06 | run 行先于 task 行(FK)、事件上限预留终态事件、空 resume 归一化、工具运行时注入、schema 门控加固（回归为主） |

范围外：validator（按 `2026-08-03-fault-zeroing-workflow-gap-closure.md` 锁定假设，不运行不修改）；其余 Workflow V2 功能只做全量回归不列新用例。

## 3. 分层测试策略

- **L1 后端自动化**：真实 SQLite Store + 真实 Worker/Compiler/Checkpointer + stub adapter（无 LLM），沿用 `backend/tests/integration/workflows/` 既有模式。
- **L2 前端自动化**：Vitest 单测（core + 组件 + 页面）+ Playwright mock E2E。
- **L3 平台级真实链路验收**：真实 LLM + 3 个 eval 案例（`docs/zero_agent_eval_cases/case_01/02/03`，不含 `06_expected_analysis.md`），经 API/UI 人工核对。
- **L4 回归门禁**：后端全量 + 前端 `pnpm test`/`pnpm check`。

## 4. 补测用例清单（自动化）

### 4.1 后端

| ID | 用例 | 优先级 | 落盘位置 |
|---|---|---|---|
| B-T1 | 运行记录下载端点：format 校验 400、未知 run 404、无权限 404、记录缺失 404、jsonl 200（`application/x-ndjson`，文件名 `run_{run_id}.jsonl`）、md 200（`text/markdown`） | P0 | 新增 `backend/tests/integration/api/test_workflow_run_record_download.py` |
| B-T2 | 归零真路径 precondition skip：无 confirmed 根因 → `corrective_actions` 发 `node_skipped`（含 reasons），`generate_outputs` 仍完成并产出 4 文件，run completed | P0 | 扩展 `test_fault_zeroing_worker_runtime.py` |
| B-T3 | fork 分支一成一败：`evidence_collection` 失败 → run failed、`node_failed` 事件、`run_failed` 收尾、join 不完成 | P0 | 同上 |
| B-T4 | 控制节点生命周期事件经 worker 全链路：`fork_start`/`join_review` 的 `node_started`/`node_completed` 出现在事件流，顺序 fork → 分支 → join | P0 | 同上 |
| B-T5 | `RunRecordWriter` 写失败容错：append/finalize 抛 OSError 不冒泡，run 不受影响 | P1 | 扩展 `test_v2_run_record.py` |
| B-T6 | md 记录「节点交互」计数 + payload 2000 字符截断 | P1 | 同上 |
| B-T7 | `_AgentAdapter.astream`：progress_callback 产出 tool_call → `progress` 事件 + 流中 LLM 不可用 → `WorkflowTransientError` | P1 | 扩展 `test_v2_agent_adapter.py` |
| B-T8 | resume 免预算时序：`resume_command_id` 存在期间 claim 不增 attempts，`clear_resume_command` 后恢复计数 | P1 | 扩展 `test_v2_store.py` |

### 4.2 前端

| ID | 用例 | 优先级 | 落盘位置 |
|---|---|---|---|
| F-T1 | run 详情页：MD/JSONL 下载按钮（URL `.../record?format=md|jsonl`、文件名 `run_{run_id}.{fmt}`、非 200 toast）、事件时间线渲染、产物预览(JSON pretty)/下载 | P0 | 扩展 `frontend/tests/unit/app/workspace/workflows/[workflow_name]/runs/[run_id]/page.test.tsx` |
| F-T2 | RunGraph：fork/join 控制节点 completed 状态渲染 | P1 | 扩展 `frontend/tests/unit/components/workspace/workflows/run-graph.test.tsx` |
| F-T3 | E2E：运行详情页（resume/cancel、产物列表、记录下载按钮），扩展 `mockLangGraphAPI` 支持 run events/artifacts/record 路由 | P2 | 新增 `frontend/tests/e2e/workflows/workflow-runs.spec.ts` |

### 4.3 平台级真实链路验收（L3 手动清单）

前置：`make dev` 起全栈；`scripts/install_fault_zeroing_agent.py` 安装 agent；`scripts/seed_fault_zeroing_workflow.py` 播种工作流；worker 随网关自动拉起。

正向（3 个案例各一遍）：
1. 将案例 5 份资料（排除 `06_expected_analysis.md`）放入用户 upload 目录（`/mnt/user-data/uploads/<case>/`）
2. UI 发起运行：填写 `upload_dir` / `problem_description` / `output_base_dir`
3. 运行详情页观察：DAG 实时状态（fork/join 出现 completed）、节点详情、token 流、进度消息（每轮工具调用）、事件时间线
4. 等待完成：9 个 action 节点 completed、运行状态 completed
5. 产物浏览/预览/下载：`fault_tree.json`、`fault_tree.svg`、`bottom_event_assessment.md`、`analysis_process.svg`、`zeroing_report.md` 及 `artifacts/` 下文件，全部非空且可解析
6. 下载 MD/JSONL 运行记录：MD 含节点摘要/交互统计/时间线；JSONL 事件与页面时间线一致
7. 人工核对 `zeroing_report.md` 章节完整、证据引用可追溯

负向：
- 无效 `upload_dir`（host 路径 / 不存在目录）→ API 400（`validate_workflow_roots` / `validate_read_roots`）
- 缺 required input → 400
- 资料不全（缺某类证据）→ 运行完成但覆盖矩阵标注缺失，底事件标 `to_verify`
- kill worker 模拟中断 → 运行 paused → UI resume → 恢复完成（不消耗 attempt 预算）
- cancel 运行 → `cancelled`，部分产物存在
- 跨用户访问运行详情/记录 → 404 隔离
- 同用户并发超限 → 429
- 事件上限：预留终态事件（人为调低 `max_events_per_run` 验证）

## 5. 执行与门禁

```bash
# L1 后端全量
cd backend && UV_CACHE_DIR=/tmp/deer-flow-uv-cache make test
# serial 迁移用例单独跑
cd backend && uv run pytest tests/integration/workflows/test_v2_phase1_runtime.py -v -m serial

# L2 前端
cd frontend && pnpm test && pnpm check

# L4 E2E（P2）
cd frontend && pnpm test:e2e:workflows
```

三条主命令必须退出码 0。任何失败视为未完成，不通过放宽断言或修改门槛通过。

## 6. 风险与约束

- LLM 非确定性：L3 人工判断承担，自动化全部用 stub adapter，不断言 LLM 输出。
- fork 分支取消涉及 LangGraph 调度时序：断言收敛到「run 终态 + 事件集合完整性」，不断言分支内精确事件序。
- `serial` 标记测试默认被 `make test` 排除，需显式 `-m serial`。
- validator 及其测试不运行、不修改（锁定假设）。
- 下载端点测试沿用 `backend/tests/integration/api/` 的 FastAPI TestClient + dependency override 模式。

## 7. 执行结果（2026-08-06）

### 已通过 ✅

| 环节 | 方式 | 结果 |
|------|------|------|
| 后端 workflow 套件 | `pytest tests/integration/workflows tests/unit/workflows` 等 | 222 passed |
| 后端 serial 迁移用例 | `pytest tests/integration/workflows/test_v2_phase1_runtime.py -m serial` | 通过 |
| 前端单元全量 | `pnpm test` | 331 files / 7853 passed |
| 前端静态 | `pnpm check` | 1270 warnings / 0 errors（均为既有 warning） |
| workflow e2e | `playwright test --project=chromium tests/e2e/workflows/` | 125 passed |

补测落地文件：
- 后端：`backend/tests/integration/api/test_workflow_run_record_download.py`（新）、`test_fault_zeroing_worker_runtime.py`、`test_v2_run_record.py`、`backend/tests/unit/workflows/test_v2_agent_adapter.py`、`test_v2_store.py`。
- 前端：`tests/unit/.../runs/[run_id]/page.test.tsx`、`tests/unit/.../run-graph.test.tsx`（完成态 fork/join 控制节点）。
- e2e：`tests/e2e/workflows/workflow-runs.spec.ts`（6 用例）、`tests/e2e/utils/mock-api.ts` 扩展（workflowRuns / artifacts / content / record / events(SSE) / commands；修复 workflow detail 响应缺 `edges` 导致的客户端崩溃）。

### 已知失败（预存在，与本次改动无关）

- `i18n-language-switching.spec.ts:337` "locale cookie zh is normalized to zh-CN"：即使在 stash 掉全部改动后单独重跑仍失败（期望 `zh-CN` 实际 `zh`），属仓库既有问题，不在本计划范围。

### Case 01 真实验收收口记录（2026-08-06）

- 真实 worker run：`fz-01-20260806T125834Z-5172d9`，workflow version `1`，耗时约 `1164.006s`，事件 `114` 条。
- 输入：`00_problem_statement.md`、`01_design方案.md`、`02_test_outline试验大纲.md`、`03_test_summary试验总结报告.md`、`04_test_data.csv`、`05_historical_or_review_notes.md`；未提供 `06_expected_analysis.md`。
- 运行状态：`completed`；9 个 action 节点达到 terminal 状态，其中 8 个 `node_completed`，`corrective_actions` 按前置条件 `node_skipped`；schema feedback 事件 6 条，均含具体 violation。
- 五类产物均已生成、非空，`fault_tree.json` 可解析；验收目录：`backend/.ideer/users/435b5779-61da-408b-8ccc-867c5dcdcc78/threads/fz-01-20260806T125834Z-5172d9/user-data/outputs`。
- validator 已按本轮计划执行，退出码 `1`。失败项为 validator 对报告覆盖表头/待验证项文本的严格匹配：实际报告语义上包含五类资料和 VP-01~VP-06，但未满足 validator 当前匹配规则；未修改 validator，故本轮尚不能报告整体收口完成。
- 当前仅完成 case 01；case 02/03 未执行。
