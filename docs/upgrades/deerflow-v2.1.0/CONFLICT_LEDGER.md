# DeerFlow v2.1.0 conflict ledger

- 锁定上游目标：tag `v2.1.0`（commit `345f08be00c8a9495079b732a39b46aa9af1584e`）
- 当前锁定基线：`0f7d8709d3bbf0be26460b6277fbad9329302243`
- probe 实测冲突：**96 个路径**（两轮试合并一致，分布见合并计划 §1）
- 状态：**空白模板** —— 由票 02 在机械合并（probe 分支）后按六个片区登记语义台账。

登记纪律：沿用 `deerflow-main-0f7d8709/CONFLICT_LEDGER.md` 的"语义台账替代
机械行"做法 —— 每个片区一行一族路径，逐行填 Target owner / 处置分类 /
验收证据 / 关闭条件；任何行不得在没有指名报告或 focused test 的情况下移入
`closed`。完整冲突路径清单可用下式复现：

```bash
git diff --name-only 0f7d8709d3bbf0be26460b6277fbad9329302243 v2.1.0
```

## Semantic ledger

| Area / path family | Final classification | Target owner | Acceptance evidence | Close condition | Status |
|---|---|---|---|---|---|

## A. harness 补丁重放

_待票 02 填充（22 个补丁×上游交集文件，逐条对照 PATCH 台账行的移除条件）_

## B. gateway + auth

_待票 02 填充（auth.py 三方语义、PAT 路由策略与本地 RBAC 矩阵统一、auth/pat.py 落位）_

## C. 持久化迁移

_待票 02 填充（bootstrap、统一迁移链、上游新增 migrations 与本地链合并）_

## D. memory + config

_待票 02 填充（插件化 schema、backend_config、storage_path 目录化、intranet overlay）_

## E. frontend

_待票 02 填充（workspace 组件、i18n 三件套、model-selector、playwright）_

## F. CI + 部署 + 文档

_待票 02 填充（workflows、Makefile、deploy.sh、docker、backend/docs）_

## Closure record

_尚未开始。所有行保持 `open`，直至每行及合并计划中的最终门禁全部关闭。_
