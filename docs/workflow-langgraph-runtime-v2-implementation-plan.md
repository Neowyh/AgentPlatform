# YAML Workflow v2 → LangGraph 两阶段实施计划

## 目标

将 YAML workflow 重定义为受治理的声明式图 DSL，由 LangGraph 负责编译执行、checkpoint、并行、条件路由、重试和人工中断；平台负责版本、权限、worker、事件、审计和前端体验。

首期支持：`action`、`route`、静态 `fork/join`、节点 retry、`interrupt`、带 `max_iterations` 的有界回边。不支持动态 fan-out、子工作流和补偿事务。

## 固定接口与状态边界

- YAML v2 固定包含 `schema_version: 2`、`inputs`、`state`、`entrypoint`、具唯一 ID 的 `nodes` 与 `edges`；`action` 仅允许受控的 `agent` 或 `tool` 适配器，禁止嵌入任意 Python 或 LangGraph 配置。
- 保留 `POST /api/workflows/{name}/run` 创建运行；新增：
  - `GET /api/workflows/{name}/runs/{run_id}/events?after_seq=N`：SSE，支持断线后从序号补发。
  - `POST /api/workflows/{name}/runs/{run_id}/commands`：提交唯一 `command_id` 的 `resume` 或 `cancel` 命令；审批是 `resume` 的受权限约束变体。
- 将定义、运行、任务和事件解耦：workflow 版本不可变；每个 run 固定引用其定义版本和 checkpoint namespace；任务表保存状态、租约、心跳、尝试次数与取消请求；事件按 run 递增序号持久化。
- 运行图使用 `thread_id = wf:{run_id}`；不得复用会话 agent 的 thread/checkpoint 命名空间。

## Phase 1：DSL v2 与单实例 durable worker 闭环

- 新建 v2 schema、解析器和静态校验：拒绝重复节点、悬空边、不可达终点、非法状态写入、无 `max_iterations` 的回边、不匹配的 fork/join、未知 action，以及未声明的模板变量。
- 实现 `WorkflowGraphCompiler`：将 v2 YAML 编译为 `StateGraph`；以显式 reducer 合并并行分支的 `data` 与 `outputs`，以节点级 retry 映射重试策略，以 `interrupt()`/`Command(resume=...)` 实现人工审批。每个 action 必须产生结构化结果、幂等键和节点生命周期事件。
- 用新的不可变定义版本、workflow run、任务与事件模型替代当前将定义和可变执行状态混在 `workflow_runs` 中的模式；保留旧数据只读可查。
- Gateway 只做鉴权、输入校验、创建 run/task、读取快照和提交命令；新增独立 worker 进程循环领取待执行任务，在单实例部署下执行或恢复对应 LangGraph checkpoint，并原子写入终态/下一任务状态。
- 第一阶段 SSE 发送 `run_started`、`node_started`、`node_completed`、`node_failed`、`interrupted`、`resumed`、`run_completed`、`run_failed`、`run_cancelled`；事件先持久化再推送，查询接口作为 SSE 断线补偿。
- 切换发布：先停止旧 workflow 接单；将所有 legacy 非终态 run 标记为 `failed`，错误码为 `workflow_runtime_replaced`；归档 v1 YAML 和历史快照为只读，标记 `migration_required`；移除旧执行器的路由调用，不做 YAML 自动转换。
- 先为 schema、编译器、action adapter、interrupt/resume、任务领取、API/SSE 写失败测试，再实现最小代码；每个可独立验证单元单独提交。

### Phase 1 验收

- 顺序、条件、静态并行汇合、重试、有界循环及审批流程均可从 checkpoint 恢复，且同一 `command_id` 重复提交不重复推进图。
- worker 重启后，待执行或暂停的 run 能被重新领取；已终态 run 绝不再次执行。
- SSE 连接中断后，以 `after_seq` 能无缺口补齐生命周期事件；事件顺序与 run 快照一致。
- v1 定义不可再运行，遗留运行记录仍可查询，且切换期间没有新旧执行器并行处理同一 run。

## Phase 2：多 worker 接管、完整流与运营治理

- 将任务领取升级为数据库 compare-and-set 租约：任务有 `lease_owner`、`lease_expires_at`、心跳和递增 attempt；仅持有有效租约的 worker 可写执行状态。过期租约可由其他 worker 接管，达到最大 attempt 后进入失败终态并保留诊断。
- 建立取消协议：Gateway 原子写 `cancel_requested`，worker 在节点边界和 LangGraph 流迭代边界消费该请求并写入 `cancelled`；不把取消等同于直接杀进程。
- 扩展 action adapter 的流式接口：agent token、tool 进度和自定义节点进度写入同一 workflow event 序列；SSE 统一输出，不把 LangGraph 原始事件类型泄漏为公共 API。
- 前端从 2 秒轮询迁至 SSE 驱动的运行详情；初始化加载 run 快照与历史事件，收到事件后更新节点图、agent 输出和审批面板；轮询仅保留为连接恢复失败时的只读兜底。
- 加入运行治理：按用户/部门限制并发 run 与并行 action 数；限制循环次数、单节点超时、最大事件量；记录 workflow 版本、触发者、审批者、租约变更、取消与失败原因。
- 在现有 workflow router、持久化模型、runtime event store 和 workflow 前端 hooks 旁新增 v2 专属模块；不要继续扩张旧 `WorkflowExecutor`、`WorkflowStore` 或轮询式 `human_step`。

### Phase 2 验收

- 两个 worker 并发运行时，同一 run 在任何时刻只有一个有效执行租约；故意终止持有者后，另一 worker 从最后 checkpoint 接管，已完成的 action 不重复产生副作用。
- agent token、节点状态、审批和终态在同一 SSE 序列中可重放；权限不足的用户不能订阅、查询、取消或恢复他人的 private workflow run。
- 并发、超时、循环和事件量上限均产生明确、可审计的失败事件，而不是卡住或无限运行。
- 后端覆盖 compiler、租约竞争、接管、重复 command、取消、SSE 补发和 RBAC；前端覆盖断线恢复、审批恢复和终态渲染；完成真实双 worker 的端到端验收。

## 实施假设

- 采用一次性切换：不维护旧 YAML 的可运行兼容层，也不自动转换 v1 定义。
- Phase 1 的 worker 是独立持久化进程，但只部署一个副本；Phase 2 才承诺多副本接管与租约竞争。
- 数据库 checkpoint/event 后端是生产必选；内存和 JSONL 仅可用于本地开发，不能作为 durable worker 的生产后端。
- 外部 action 的“恰好一次”不可凭运行时保证；平台以稳定幂等键、checkpoint 后恢复和审计实现至少一次执行下的业务幂等。
