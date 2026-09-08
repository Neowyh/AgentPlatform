# ExecutionTarget 作为一等运行维度

> audience: developers, architects, reviewers
> status: accepted
> owner: engineering maintainers
> last-verified: 2026-09-08
> canonical-path: `docs/decisions/2026-09-08-execution-target-first-class-dimension.md`

## 决策摘要

「在哪里执行」提升为正式的一等运行维度 `ExecutionTarget`，第一阶段枚举统一为 `SERVER` 与 `USER_DEVICE` 两个值。执行位置必须显式声明，禁止同一个 Server Tool 根据运行环境悄悄切换为本地执行。

## 背景与备选

引入 Local Runtime 后，同一业务操作存在两个真实执行位置。若执行位置隐式化（按环境自动切换），运行证据无法回答「这件事在哪里发生的」，授权与审计也会出现两套隐含语义。

备选一是沿用 Local Runtime 实施方案早期文本中的 `SERVER_SANDBOX` 命名；备选二是让模型在工具名层面选择位置（如 `local.*` 与 server 工具并列自选）。前者与总体基线 §10 的 `SERVER` 命名冲突，按「基线 > 专项」裁决统一为 `SERVER`；后者违反「模型不感知基础设施细节」原则，被否决——模型只见能力，位置由 Workflow Step 声明与平台路由决定。

## 决策

- 枚举值：`SERVER` | `USER_DEVICE`；未来可扩展 `EDGE_NODE`、`GPU_WORKSTATION`、`LAB_DEVICE`、`SERVER_INTERNAL`。
- Workflow Step 可声明 `execution_target` 及 `requires_device_online`、`requires_user_consent`、`timeout`、`retry`、`fallback`。
- Run 创建时冻结 device_id 等执行定位信息，运行中不漂移。
- `local.knowledge.search` 等 `local.*` 名称只是内部 capability / routing key，不构成模型可见的第二执行语义。

## 后果

- 所有涉及执行的证据必须携带执行目标，缺失即证据不完整。
- 后续新增执行位置（如边缘节点）只需扩展枚举与路由，不需新增工具命名空间。
- 若上游 DeerFlow 未来引入等价的执行位置抽象，应迁移至上游语义并撤销本决策的本地枚举。
