# 归零智能体子智能体不可用修复计划

**目标：** 修复归零智能体在启用子智能体时的运行中断问题，保证子智能体可正常完成任务、主流程可稳定返回结果，并保留用量统计能力。

**结论：** 当前问题不在归零案例资料本身，而在 `task_tool` 对运行时 callbacks 形态的假设过强。实际运行中 `runtime.config["callbacks"]` 可能是 `AsyncCallbackManager`，而现有代码直接按可迭代对象处理，导致子智能体完成后回传用量统计时抛出 `TypeError: 'AsyncCallbackManager' object is not iterable`。修复重点应放在 `task_tool` 的兼容性加固，而不是改 agent 配置或关闭子智能体能力。

**影响面：** GitNexus 影响分析为 LOW。直接受影响的是 `_report_subagent_usage` 和 `_find_usage_recorder`，间接影响 `task_tool` 的终止事件处理。无需变更外部 API。

---

## 1. 诊断结论

1. 子智能体“可见、可启动、可执行”这一层已经成立。
2. 崩溃发生在子智能体结束后，`task_tool` 试图从 runtime callbacks 中寻找用量记录器时。
3. 运行时 callbacks 在真实框架里不一定是列表，可能是 `AsyncCallbackManager`。
4. 当前实现把“可迭代 callbacks”当成前提，因此在回传统计阶段失败。

---

## 2. 修复方案

### 2.1 加入 callbacks 归一化逻辑

在 `backend/packages/harness/deerflow/tools/builtins/task_tool.py` 中增加一个轻量归一化函数，例如 `_iter_runtime_callbacks(callbacks)`，让它支持：

- `None` -> 空
- `list / tuple / set` -> 直接遍历
- `AsyncCallbackManager` 或类似对象 -> 从 `.handlers`、`.inheritable_handlers`、`.local_handlers` 中提取 handler
- 非可迭代对象 -> 如果对象本身带 `record_external_llm_usage_records`，允许直接作为 recorder；否则忽略

### 2.2 加固 `_find_usage_recorder()`

把 `_find_usage_recorder()` 改成只依赖归一化后的 callback 序列，不再直接对 `runtime.config["callbacks"]` 做 `for cb in callbacks`。

要求：

- 不因 callbacks 形态异常抛错
- 找到带 `record_external_llm_usage_records` 的对象后立即返回
- 找不到 recorder 时返回 `None`

### 2.3 加固 `_report_subagent_usage()`

让用量统计变成“尽力而为”的附加能力，不得影响任务主流程。

要求：

- `_find_usage_recorder()` 的异常也要被兜住
- 没有 recorder 时直接跳过
- 只有统计成功时才标记 `usage_reported=True`

---

## 3. 测试方案

### 3.1 单元测试

在 `backend/tests/test_task_tool_core_logic.py` 或等价测试文件中补覆盖：

- callbacks 为普通列表时能找到 recorder
- callbacks 为 `AsyncCallbackManager` 形态时能找到 recorder
- callbacks 为带 `.handlers` 的对象时能找到 recorder
- callbacks 为非可迭代对象时不抛错
- `_report_subagent_usage()` 在 recorder 可用时正常记录，在 recorder 不可用时安静降级

### 3.2 回归测试

补一个真实路径测试，避免继续用过度 mock 掩盖问题：

- 让 `task_tool` 走到终止事件处理
- runtime callbacks 传入 manager 形态
- 验证子智能体任务能正常完成，不再因为统计逻辑中断

### 3.3 现场验证

修复后使用现有 `fault-zeroing` 智能体跑一次小样例：

- 启用 `context.subagent_enabled=true`
- 触发一次子智能体委托
- 验证日志中不再出现 `AsyncCallbackManager object is not iterable`
- 验证子智能体结果文件能正常产出

---

## 4. 实施顺序

1. 先改 `task_tool` 的 callbacks 兼容性。
2. 再补 `task_tool` 单元测试和回归测试。
3. 最后做一次本地端到端验证，确认子智能体不再中断。

---

## 5. 备选方案与取舍

1. **推荐方案：修 `task_tool` 兼容性**
   - 保留用量统计
   - 风险最小
   - 对运行形态最稳

2. **临时绕过：关闭子智能体用量统计**
   - 可以快速止血
   - 但会丢失审计和统计能力
   - 只能作为临时兜底，不适合作为最终方案

3. **改 worker 维持 callbacks 为 list**
   - 不推荐
   - 真实运行时会继续经过 LangGraph/LangChain 的包装
   - 不是根因修复

---

## 6. 验收标准

- 子智能体任务可正常完成
- 主流程不再因 callbacks 形态报错中断
- 用量统计可用时正常记录，不可用时安静跳过
- 新增测试覆盖 `AsyncCallbackManager` 形态
