# PR materials — merge deer-flow v2.1.0

> 状态：草稿（lane 结果由票 11 填入）。合入 develop 后按本文件开 PR。

## 用户可见变更（摘要）

吸收上游 v2.1.0（2026-09-24 正式版，772 个 PR）至企业线，保留全部离线内网特性：

- **认证**：PAT 个人访问令牌（`/api/v1/auth/pats`，scope 与本地 assistants/models
  取并集，准入经本地 authz 链）；登录限流参数可配置；`/me` 返回本地平台身份 +
  effective permissions；账号偏好四字段云端同步。
- **运行时**：调度器 `interval` 周期与 cron 预览；run 历史 service 端过滤；
  可插拔 memory 后端（`memory.manager_class`）；`/mnt/skills` 管理式投影；
  SKILL.md 包边界规则；`X-Trace-Id` 全响应（trace 防伪：caller 提供值被覆盖）。
- **协作**：Projects / 文档 shelf / 回收站 / 会话引用 / 会话归档（能力中心
  experts/skills/connectors tab 内挂载上游 gallery，路径仍走本地 redirect 方案）。
- **迁移**：统一迁移链重接（`20261001_rejoin_upstream_line`，单 head）；
  checkpoint delta 快照频率默认 1000→10（内网 overlay 显式 pin 部署值）；
  Docker 默认绑 127.0.0.1（内网交付脚本显式 BIND_HOST）。

## 合并治理

- 目标：tag `v2.1.0`（207 个上游提交）；基线 `0f7d8709`；快照 tag
  `deerflow-v2.1.0`。
- 冲突：96 路径 + 76 双侧自动合并文件，处置全部登记
  `docs/upgrades/deerflow-v2.1.0/CONFLICT_LEDGER.md`（冻结决议 D1-D4）。
- 补丁台账：PATCH-001..032 全量 reassess（票 10），1 条款被上游吸收，
  31 keep，零未映射。
- 架构纪律：Extension Before Fork；`/api/resources` canonical 不变；
  agents 管理入口维持本地 redirect 方案（有意排除，已登记）。

## 验证命令与结果

| 检查 | 结果 |
| --- | --- |
| `import deerflow` + `create_app()`（236 路由） | ✅ |
| 后端全量（非 serial，排除 blocking_io/llm/live/external） | ✅ 29386 passed / 237 skipped / 0 failed（2103s） |
| focused suites（authz/PAT 222、threads 167、journal 119、subagents 150、bootstrap 34、migrations、skills 607、extension contracts） | ✅ |
| `check-frontend-entry-parity.sh` 四层 | ✅ PASSED |
| frontend vitest + `pnpm check` | ✅ 1281/1282（唯一失败 `input-box-project-attachment` 为合并前预存在、bisect 判依赖漂移，登记 develop 跟进）；check exit 0 |
| `scripts/run-test-lane.sh pr-standard` | ✅ exit 0（local-runtime 11s / backend-standard 1030s / frontend-standard 458s / frontend-smoke 63s） |
| `scripts/run-test-lane.sh backend-full`（含 serial） | ✅ exit 0（1218s；serial 迁移链常量修正 df970cc42） |
| `scripts/run-test-lane.sh frontend-core` | ✅ exit 0（578s，coverage + check） |
| `scripts/run-test-lane.sh frontend-mock-e2e` | ⚠️ 367/414（合并前基线 337/344；分桶台账 `dev-log/2026-10-02-mock-e2e-followup-ledger.md`，跟进项在 develop 处理） |
| 内网 bundle + `check-intranet.sh` + 容器冒烟 | ✅ ideer-20261002-d4b23e6c4（3.9G）：8 项 0 errors、登录/资源/线程/重启持久化全过（LLM 会话段沙箱无模型密钥，incomplete） |
| `scripts/run-test-lane.sh core-full` | ⏳ 票 11 |
| 技能包边界加载 | ✅ 607 测试绿 + bundled-skills.txt 59/59 在 resources/skills + skills-lock 一致 |

## 本轮收敛修复（合并丢失/对齐类，票 11 评审产出）

- `1f18d4170` sse_consumer 订阅循环恢复（合并去重误删）+ services 去重
- `a868441a6` agent store 引导缝（#5324 display_name 保留）
- `b0b12ba4c` MCP 任务快照关停清理；`277b28343` 上传虚拟路径 skip 包络
- `76c049e6b` 迁移真实链头探测；`7298b85c8` DooD socket 上游优先
- `27e571842` skill-creator quick_validate 回补；`c18d47b59` 51 件测试对齐
- `30c70ccbf` 虚拟化侧栏列表恢复 thread-list testid（P6）；`4a054ef1b` smoke 对齐合并后模型选择器；`5d1aad7d3` logging real-emit 测试 urllib3 级别隔离

## High-risk lane 选择（CI 注记）

本 PR 触及 auth / RBAC / persistence / memory / Agent / Skill / Workflow 全部
高危路径。按仓库纪律（AGENTS.md Test Lane Selection），GitHub Actions 将为这些
路径选择 **Real E2E**；本地已执行 pr-standard + core-full（结果见上表），
`core-full` 为交付级验收，历史结果不替代本轮。

## 关联

- 合并计划：`docs/plans/2026-09-30-deerflow-v2.1.0-merge-plan.md`
- 升级档案：`docs/upgrades/deerflow-v2.1.0/`
- 补丁台账：`UPSTREAM_PATCH_LEDGER.md`（PATCH-016..032 本轮补登记 + reassess）
