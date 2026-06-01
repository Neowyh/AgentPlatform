# Agent 记忆路径遮蔽共享智能体排障复盘

日期：2026-06-01
状态：已修复
相关提交：`5b8331da fix(memory): isolate per-agent memory paths`

## 摘要

本次排障确认了一个用户隔离后的路径命名空间问题：按 Agent 记忆曾写入 `users/<user_id>/agents/<agent_name>/memory.json`，而同一目录树也用于保存用户自定义 Agent 的 `config.yaml` 和 `SOUL.md`。当用户使用共享智能体 `fault-zeroing` 后，memory 写入可能创建 `users/<user_id>/agents/fault-zeroing/` 目录。该目录只有 `memory.json`，没有 Agent 配置文件，但配置加载逻辑会优先检查用户级 Agent 目录，导致共享目录 `agents/fault-zeroing/` 被同名用户目录遮蔽。

修复方案是把按 Agent 记忆迁出 `agents/` 配置命名空间，统一写入 `agent-memory/`：

```text
{base_dir}/users/{user_id}/agent-memory/{agent_name}/memory.json
{base_dir}/agent-memory/{agent_name}/memory.json
```

读取侧保留兼容：新路径不存在时，仍可回退读取旧的 `agents/<agent_name>/memory.json`；写入侧只写新路径，不再自动创建用户级 `agents/<agent_name>/` 目录。

## 影响

- 受影响对象：使用共享自定义 Agent，尤其是离线部署预置的 `fault-zeroing` 智能体。
- 受影响链路：Agent memory 保存、Agent 配置加载、共享 Agent fallback。
- 用户可见表现：共享 Agent 配置存在，但某个用户再次加载同名 Agent 时可能失败，或者被用户目录下只有 `memory.json` 的残缺目录遮蔽。
- 数据损坏：未确认有 memory 数据损坏。旧 memory 文件仍保留并可兼容读取。
- 安全影响：未确认有权限越权；问题本质是路径命名空间混用导致的可用性和配置解析问题。

## 时间线

| 时间 | 事件 |
| --- | --- |
| 2026-06-01 | 根据既定修复计划检查 `Paths` 和 `FileMemoryStorage` 的现状，确认按 Agent memory 仍指向 `agents/<agent>/memory.json`。 |
| 2026-06-01 | 使用 GitNexus 刷新索引并对 `agent_memory_file`、`user_agent_memory_file`、`_get_memory_file_path`、`_load_memory_from_file` 做影响分析，风险为 LOW。 |
| 2026-06-01 | 先补回归测试：保存 `fault-zeroing` 用户级 memory 后，不应创建 `users/alice/agents/fault-zeroing/`，且共享 `agents/fault-zeroing/config.yaml` 仍能被加载。 |
| 2026-06-01 | 首轮验证显示当前实现仍会落到旧路径，符合预期失败方向。 |
| 2026-06-01 | 修改 `Paths`：保留原公开方法名，但将 canonical memory 路径改为 `agent-memory/`；新增 legacy helper 只用于兼容读取。 |
| 2026-06-01 | 修改 `FileMemoryStorage`：读取时新路径优先、旧路径兜底；保存时只写 canonical 新路径。 |
| 2026-06-01 | 更新中文/英文文档，明确 `agents/` 保存配置资产，`agent-memory/` 保存记忆状态。 |
| 2026-06-01 | 运行 focused backend tests：`85 passed`；运行 `ruff check`：通过。 |
| 2026-06-01 | 运行 `gitnexus detect_changes(scope="all")`，风险等级 medium，影响集中在 custom-agent/path 相关链路。 |
| 2026-06-01 | 提交修复：`5b8331da fix(memory): isolate per-agent memory paths`。 |

## 根因分析

### 直接原因

`Paths.user_agent_memory_file(user_id, agent_name)` 和 `Paths.agent_memory_file(agent_name)` 早期返回的是 `agents/<agent_name>/memory.json`。`FileMemoryStorage.save(..., agent_name="fault-zeroing", user_id="alice")` 会创建父目录，因此普通 memory 保存动作就能创建：

```text
{base_dir}/users/alice/agents/fault-zeroing/
```

这个目录名与用户级自定义 Agent 配置目录完全相同。

### 深层原因

用户隔离后，系统把两类不同生命周期的数据放进了同一个命名空间：

- Agent 配置资产：`config.yaml`、`SOUL.md`，用于定义智能体身份、工具组、技能和模型等。
- Agent 记忆状态：`memory.json`，用于保存用户和 Agent 交互后的长期记忆。

配置资产和记忆状态的读写语义不同。配置加载器看到 `users/<user_id>/agents/<agent_name>/` 后，会把它视为用户级 Agent 目录；memory 写入则只关心 `memory.json` 能否落盘。两者共用目录后，memory 写入创建的残缺目录就会被配置加载器误判为用户级 Agent。

### 5 Whys

1. 为什么共享 `fault-zeroing` 会被遮蔽？
   因为用户级 `users/<user_id>/agents/fault-zeroing/` 目录存在后，配置加载优先检查该目录。

2. 为什么该用户级目录会存在？
   因为用户使用 `fault-zeroing` 时，按 Agent memory 保存会创建 `users/<user_id>/agents/fault-zeroing/memory.json`。

3. 为什么 memory 会写到 `agents/`？
   因为旧路径 helper 把按 Agent memory 定义在 `agents/<agent_name>/memory.json` 下。

4. 为什么路径 helper 没有区分配置和记忆？
   因为早期单用户/legacy 布局里，Agent 目录同时承载配置和 memory；迁移到用户隔离后，旧布局语义被沿用。

5. 为什么测试没有提前发现？
   因为已有测试覆盖了用户隔离、memory 文件位置和共享 Agent 读取，但缺少“保存共享 Agent 同名 memory 后，不能创建用户级 Agent 配置目录并遮蔽共享 Agent”的组合回归。

## 解决方案

### 代码修复

路径层：

- `agent_memory_file(name)` 改为返回 `{base_dir}/agent-memory/{name}/memory.json`。
- `user_agent_memory_file(user_id, agent_name)` 改为返回 `{base_dir}/users/{user_id}/agent-memory/{agent_name}/memory.json`。
- 新增 `legacy_agent_memory_file(name)` 和 `legacy_user_agent_memory_file(user_id, agent_name)`，只用于旧路径兼容读取。

存储层：

- `_get_memory_file_path()` 继续返回 canonical 新路径。
- 新增读取路径选择逻辑：新文件存在则读新路径；新文件不存在且是按 Agent memory 时，再回退读旧 `agents/<agent>/memory.json`。
- `save()` 不做旧路径 fallback，始终写 canonical 新路径。
- cache key 保持 `(user_id, agent_name)`，不按物理路径变化。

### 测试补强

新增/更新测试覆盖：

- path helper 返回 `agent-memory/` 路径，并保持 Agent 名小写。
- 旧路径 memory 在新路径缺失时可读取。
- 新旧路径同时存在时，新路径优先。
- 保存用户级 Agent memory 只创建 `agent-memory/`，不创建 `users/<user_id>/agents/<agent_name>/`。
- `fault-zeroing` 共享 Agent 已存在时，保存同名用户级 memory 不影响 `load_agent_config("fault-zeroing", user_id="alice")` 回退读取共享配置。

### 文档修复

已更新相关文档，明确：

- `agents/` 是 Agent 配置资产目录。
- `agent-memory/` 是按 Agent 记忆状态目录。
- 旧 `agents/<agent>/memory.json` 仅作为兼容读取路径，不作为新写入路径。

## 验证记录

执行过的 focused tests：

```bash
env UV_CACHE_DIR=/tmp/uv-cache UV_TOOL_DIR=/tmp/uv-tools \
  PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  uv run pytest \
  tests/test_paths_user_isolation.py \
  tests/test_memory_storage_user_isolation.py \
  tests/test_memory_storage.py \
  tests/test_custom_agent.py::TestPaths \
  tests/test_custom_agent.py::TestMemoryFilePath \
  tests/test_custom_agent.py::TestLoadAgentConfig \
  -q
```

结果：

```text
85 passed, 1 warning
```

执行过的 lint：

```bash
env UV_CACHE_DIR=/tmp/uv-cache UV_TOOL_DIR=/tmp/uv-tools \
  uv run ruff check \
  packages/harness/deerflow/config/paths.py \
  packages/harness/deerflow/agents/memory/storage.py \
  tests/test_paths_user_isolation.py \
  tests/test_memory_storage_user_isolation.py \
  tests/test_memory_storage.py \
  tests/test_custom_agent.py
```

结果：

```text
All checks passed!
```

执行过的 GitNexus 提交前检查：

```text
detect_changes(scope="all", repo="deer-flow")
```

结果摘要：

```text
risk_level: medium
affected_processes: List_custom_agents, Update_agent, Acquire_async
```

影响集中在路径和 custom-agent 相关链路，符合本次改动范围。

## 已知限制

完整请求中的 pytest 命令包含 `tests/test_custom_agent.py` 全文件时，运行到 `TestAgentsAPI::test_list_agents_empty` 后出现长时间挂起。诊断运行显示该文件中前 27 个非 API 测试已经通过，挂起点在 API 测试区域。该挂起未表现为本次 memory/path 断言失败，但仍应作为后续测试稳定性问题单独排查。

## 后续行动项

| 优先级 | 行动项 | 状态 |
| --- | --- | --- |
| P0 | 保持 `agent-memory/` 与 `agents/` 的职责边界，不再把新 memory 写入配置目录 | 已完成 |
| P0 | 保留旧 memory 路径读取兼容，避免旧部署 memory 立即不可读 | 已完成 |
| P1 | 在离线部署复盘文档中记录该故障的现场现象、根因和排查命令 | 已完成 |
| P1 | 单独排查 `tests/test_custom_agent.py::TestAgentsAPI::test_list_agents_empty` 挂起原因 | 待处理 |
| P2 | 后续迁移脚本如处理旧 memory，可明确区分“配置迁移”和“记忆迁移” | 待评估 |

## 经验总结

这次问题不是单个文件路径写错，而是配置资产和运行状态共用命名空间后产生的系统边界问题。修复时应优先让目录结构表达数据语义：`agents/` 放智能体定义，`agent-memory/` 放记忆状态。这样即使某个用户产生新的 memory，也不会让配置加载器误判为用户自定义 Agent，从而避免共享智能体被残缺目录遮蔽。
