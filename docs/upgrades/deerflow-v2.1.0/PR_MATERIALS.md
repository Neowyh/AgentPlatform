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
| focused suites（authz/PAT 222、threads 167、journal 119、subagents 150、bootstrap 34、migrations 3、frozen inputs、extension contracts） | ✅ |
| `check-frontend-entry-parity.sh` 四层 | ✅ PASSED |
| `npx tsc --noEmit` | ✅ 0 错误 |
| `scripts/run-test-lane.sh pr-standard` | ⏳ 票 11 |
| `scripts/run-test-lane.sh core-full` | ⏳ 票 11 |
| 技能包边界加载 | ⏳ 票 11 |
| 内网 bundle 重建 + `check-intranet.sh` + 容器冒烟 | ⏳ 票 11（沙箱无 docker 则如实 incomplete） |

## High-risk lane 选择（CI 注记）

本 PR 触及 auth / RBAC / persistence / memory / Agent / Skill / Workflow 全部
高危路径。按仓库纪律（AGENTS.md Test Lane Selection），GitHub Actions 将为这些
路径选择 **Real E2E**；本地已执行 pr-standard + core-full（结果见上表），
`core-full` 为交付级验收，历史结果不替代本轮。

## 关联

- 合并计划：`docs/plans/2026-09-30-deerflow-v2.1.0-merge-plan.md`
- 升级档案：`docs/upgrades/deerflow-v2.1.0/`
- 补丁台账：`UPSTREAM_PATCH_LEDGER.md`（PATCH-016..032 本轮补登记 + reassess）
