# Bug List — Issue Analysis & Fix Tracking

> Generated: 2026-06-09
> Source: `known-issues.md` (103 issues) + `backend-unflashed-issues.md` (17 items)
> Branch: `offline_feature` vs `main`

---

## Summary

| 状态 | 数量 |
|------|------|
| 已修复（代码确认） | 30 |
| 仍然存在 — 本轮已修复 | 22 |
| 后续已修复 | 6 |
| 仍然存在 — 后续处理 | 37 |
| 设计决策/无需修改 | 12 |
| 新功能（不在本轮范围） | 1 |
| 测试覆盖（不在本轮范围） | 6 |

---

## 一、已修复的问题（代码确认）

| # | 问题 | 确认依据 |
|---|------|----------|
| 2 | code_interpreter 无沙箱隔离 | `tools.py` 使用 `ensure_sandbox_initialized(runtime)` |
| 5/80 | 条件步骤 goto 为死代码 | `executor.py:52-61` 已实现 goto 跳转逻辑 |
| 9 | 前端 Admin API 缺少分页参数 | `admin.py:65-66` 有 `limit`/`offset` 参数 |
| 10 | updateUserRole 返回类型不匹配 | 已修复 |
| 12 | StepDef 接口缺少字段 | 已添加所有字段 |
| 18 | 工作流读取端点无认证 | `workflows.py:51,62` 使用 `get_current_rbac_user` |
| 19 | _read_file 缺少 pandas 检查 | `data_analyzer/tools.py:53` 有 `if pd is None` |
| 20 | 前端角色变更缺少确认对话框 | 已修复 |
| 22 | submitReview 返回类型不匹配 | 已修复 |
| 30 | _is_visible_to_user 缺少 department_admin | `agents.py:206` 和 `skills.py:82` 已添加 |
| 31 | code_interpreter 环境变量过滤过严 | 白名单已扩展 |
| 32 | loop_step 静默处理 None 迭代项 | `loop_step.py:28-34` 返回空列表并记录警告 |
| 35 | 取消的运行状态被覆盖为 FAILED | `executor.py:75` 检查 `state.status != RunStatus.CANCELLED` |
| 37 | Agent 写端点使用可选认证 | `agents.py:395,496,667,814` 使用 `get_current_rbac_user` |
| 40 | get_current_rbac_user 不检查禁用状态 | `authz.py:497-498` 检查 `rbac_user.disabled` |
| 43 | useSubmitReview 不刷新运行状态 | 已修复 |
| 54 | Skill.visibility 使用未类型化字符串 | `types.py` 使用 `ResourceVisibility` StrEnum |
| 55 | listUsers getBackendBaseURL 回退不一致 | 已修复 |
| 57 | submit_review dict 解包覆盖 approved | `workflows.py:279` 过滤 `body.data` 中的 `approved` |
| 69 | test_tool 返回完整错误堆栈 | `tools.py:149` 返回通用错误消息 |
| 79 | tools 页面直接使用 fetch | 已迁移到 `admin/api.ts` |
| 93 | 并行子步骤嵌套 ID 相同 | `parallel_step.py:33` 使用 `f"{parent_id}.{sub_id}"` |
| 94 | save_run_state 不处理非 JSON 可序列化 | `store.py:261-277` 使用 `_json_safe` |
| 95 | 条件步骤缺少 expression 默认 always-true | `parser.py:93-94` 要求 `expression` 字段 |
| 96 | 循环变量模板路径变更为破坏性更改 | 新语法 `{{_loop.index}}`/`{{_loop.item}}` 已实现 |
| 15 | list_users 不支持过滤已禁用用户 | `admin.py:109` 返回 `disabled` 字段 |
| 34 | Agent 写端点缺少可见性检查 | 已改为强制认证 |
| P2-API-01 | 装饰器顺序不一致 | 代码确认顺序正确 |
| P2-API-02 | agents.py 注释误导 | 注释与代码一致 |
| P2-API-03 | run_workflow 角色枚举脆弱 | 当前枚举正确 |

---

## 二、本轮已修复的问题（22 项）

### CRITICAL（1 项）

#### BUG-01: human_review 步骤嵌套在 loop/parallel 中时崩溃
- **原编号**: #87
- **当前状态**: ✅ 仍然存在
- **紧急程度**: CRITICAL
- **引入阶段**: Phase 4（工作流引擎）
- **文件**: `backend/packages/harness/ideer/workflows/parser.py`
- **原因**: `execute_step` 没有 `HUMAN_REVIEW` 分支，嵌套调用时抛出 `ValueError`
- **修复状态**: ✅ 已完成
- **修复方案**: 在 parser 中验证 `human_review` 不能嵌套在 depth > 0 的位置

### HIGH（7 项）

#### BUG-02: Agent 写端点缺少认证
- **原编号**: #70 (check_agent_name)
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 3
- **文件**: `backend/app/gateway/routers/agents.py:303`
- **修复状态**: ✅ 已完成
- **修复方案**: 添加 `get_optional_rbac_user` 依赖

#### BUG-03: 工作流条件表达式永远为真
- **原编号**: #1
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 4
- **文件**: `executor.py:151`
- **原因**: `bool(render_value("42 > 80", ctx))` 对非空字符串永远为 True
- **修复状态**: ✅ 已完成
- **修复方案**: 实现 `_evaluate_expression` 支持比较运算符（>, <, >=, <=, ==, !=）和逻辑运算符（and, or, not）

#### BUG-04: 条件步骤嵌套分支不支持列表类型
- **原编号**: #29
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH（与 BUG-03 关联）
- **引入阶段**: Phase 4
- **文件**: `condition_step.py:37`
- **修复状态**: ✅ 已完成
- **修复方案**: 添加 `isinstance(branch, list)` 处理，依次执行列表中的子步骤

#### BUG-05: submit_review 缺少授权检查
- **原编号**: #13
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 4
- **文件**: `workflows.py:264`
- **修复状态**: ✅ 已完成
- **修复方案**: 加载工作流 YAML 验证 approvers 列表，非 approver 且非 super_admin 拒绝

#### BUG-06: _authenticate 向所有用户授予全部权限
- **原编号**: #17
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 3
- **文件**: `authz.py:157`
- **修复状态**: ✅ 已完成
- **修复方案**: viewer 角色只获得读权限（threads:read, runs:read）

#### BUG-07: 共享 Agent 在 list_agents 中对非 super_admin 不可见
- **原编号**: #98
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 3
- **文件**: `agents.py:267-269`
- **修复状态**: ✅ 已完成
- **修复方案**: 共享 agent（仅在 template dir 中）视为 public 可见性，同步修复 get_agent/export_agent/get_agent_stats

#### BUG-08: _check_resource_modify 多个实现不一致
- **原编号**: #51
- **当前状态**: ✅ 仍然存在
- **紧急程度**: HIGH
- **引入阶段**: Phase 3
- **文件**: `authz.py`, `agents.py`, `skills.py`
- **修复状态**: ✅ 已完成
- **修复方案**: agents.py 和 skills.py 的 `_check_resource_modify` 改为委托 `authz.check_resource_modify`

### MEDIUM（14 项）

#### BUG-09: _authenticate 权限映射（与 BUG-06 合并修复）

#### BUG-10: extensions_config 环境变量未设置时静默替换为空字符串
- **原编号**: #100
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `extensions_config.py:165-168`
- **修复状态**: ✅ 已完成
- **修复方案**: 改为 raise ValueError，与 app_config.py 行为一致

#### BUG-11: 并行子步骤无超时强制执行
- **原编号**: #45
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `parallel_step.py`
- **修复状态**: ✅ 已完成
- **修复方案**: 从 step_def 读取 timeout，用 `asyncio.wait_for` 包装 gather 调用

#### BUG-12: loop 步骤静默吞掉子步骤失败
- **原编号**: #46
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `loop_step.py`, `schema.py`, `parser.py`
- **修复状态**: ✅ 已完成
- **修复方案**: 添加 `fail_fast` 布尔字段到 StepDef schema，parser 透传，loop_step 在 fail_fast=True 时首个子步骤失败立即抛出 RuntimeError

#### BUG-13: 并行子步骤失败返回 dict 而非 None
- **原编号**: #28/#47/#65/#81
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `parallel_step.py:42`
- **修复状态**: ✅ 已完成
- **修复方案**: 使用 `_ERROR_SENTINEL` 哨兵键区分错误结果和正常工具输出

#### BUG-14: 条件步骤重试导致内联子步骤重复执行
- **原编号**: #41
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `executor.py:105`
- **修复状态**: ✅ 已完成
- **修复方案**: 条件步骤含内联子步骤时禁用外层重试（子步骤自有重试策略）

#### BUG-15: loop_vars 未持久化到数据库
- **原编号**: #27
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `store.py:120-151`
- **修复状态**: ✅ 已完成
- **修复方案**: 添加 `loop_vars` JSON 列到 workflow_runs 表，save/load 同步持久化

#### BUG-16: render_params 不递归处理嵌套列表
- **原编号**: #64
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `template.py:65`
- **修复状态**: ✅ 已完成
- **修复方案**: 提取 `_render_item` 递归处理嵌套 list/dict/str

#### BUG-17: loop_vars 浅拷贝导致嵌套循环数据泄漏
- **原编号**: #62
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `loop_step.py:64`
- **修复状态**: ✅ 已完成
- **修复方案**: 使用 `copy.deepcopy(state.loop_vars)` 替代 `dict(state.loop_vars)`

#### BUG-18: update_config 只验证键不验证值
- **原编号**: #68
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `registry.py:51`
- **修复状态**: ✅ 已完成
- **修复方案**: 根据 config_schema 验证值类型和 enum 约束

#### BUG-19: test_tool 端点无执行超时
- **原编号**: #83
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `tools.py:132`
- **修复状态**: ✅ 已完成
- **修复方案**: 使用 `asyncio.wait_for` 包装，300 秒超时

#### BUG-20: Agent 元数据从错误用户目录加载
- **原编号**: #71
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `agents.py:267`
- **修复状态**: ✅ 已完成
- **修复方案**: 共享 agent（`_is_shared_only`）跳过用户目录元数据加载，直接视为 public

#### BUG-21: update_skill 并发修改竞态条件
- **原编号**: #88
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `skills.py`
- **修复状态**: ✅ 已完成
- **修复方案**: 使用 `threading.Lock` 序列化 extensions_config.json 的读-改-写周期

#### BUG-22: Agent 写端点缺少可见性/所有权检查（update_agent）
- **原编号**: #34（update_agent 部分）
- **当前状态**: ✅ 仍然存在
- **紧急程度**: MEDIUM
- **文件**: `agents.py:487`
- **修复状态**: ✅ 已完成
- **修复方案**: 添加 `visibility` 字段到 `AgentUpdateRequest`，更新时验证 `_can_set_visibility`

---

## 三、后续已修复的问题（6 项）

| # | 问题 | 紧急程度 | 修复方案 |
|---|------|----------|----------|
| 7 | 工作流存储 DB 未初始化处理不一致 | LOW | 所有 sf is None 路径添加 logger.warning |
| 23 | extractError 代码重复 | LOW | 提取为 `frontend/src/core/api/errors.ts` 共享模块 |
| 49 | 条件步骤返回类型不一致 | LOW | condition_step goto 返回格式统一为 `f"goto:{branch}"` |
| 76 | list_tools/get_tool_detail 不一致 | LOW | get_tool_detail 响应添加 `config` 字段 |
| 77 | _MAX_ROWS 未执行 | LOW | 添加 post-load 行数截断安全网 |
| 82 | require_role 硬编码参数名 | LOW | 通过 inspect.signature 动态查找 UserModel 参数 |

---

## 四、后续处理的问题（37 项）

| # | 问题 | 紧急程度 | 不修复理由 |
|---|------|----------|-----------|
| 4 | Community Tools 代码重复 | MEDIUM | 需要大规模重构，单独 PR |
| 6 | 并行步骤共享可变状态 | MEDIUM | asyncio 单线程，实际风险低 |
| 8 | update_user_role 缺少行锁 | LOW | 已有 with_for_update，SQLite 不支持 |
| 11 | 前端 YAML 验证过于简单 | LOW | 前端优化，非阻塞 |
| 14 | disable_user 竞态条件 | LOW | 已有 with_for_update |
| 16 | 重试机制覆盖历史步骤结果 | MEDIUM | 需要架构调整 |
| 21 | on_error 仅支持 "skip" | LOW | 功能扩展 |
| 24 | tool_step 超时无法终止线程 | MEDIUM | Python 线程模型限制 |
| 25 | ToolRegistry.update_config 无实际效果 | HIGH | 需要统一工具实例化路径 |
| 26 | render_value 返回 None | LOW | 设计决策 |
| 33 | submit_review TOCTOU | MEDIUM | 需要事务合并 |
| 36 | list_tools 暴露 config | MEDIUM | 需要决定策略 |
| 38 | SQLite 首次用户竞态 | MEDIUM | SQLite 限制 |
| 39 | 工具注册表每步重建 | LOW | 性能优化 |
| 42 | 条件内联子步骤绕过 _should_run | LOW | 边缘场景 |
| 44 | 工作流 API 返回类型不匹配 | LOW | 前后端对齐 |
| 48 | save_run_state 无重试 | MEDIUM | 需要重试层 |
| 50 | Agent 步骤调用私有方法 | LOW | API 设计 |
| 52 | _ideer_test_bypass_auth | MEDIUM | 已有 Request 检查 |
| 53 | require_permission TOCTOU | MEDIUM | 需要事务合并 |
| 56 | _dispatch 类型不一致 | LOW | 维护风险 |
| 58 | read_document async 改造 | MEDIUM | 需要审查调用方 |
| 59 | ProgrammingError 捕获过宽 | MEDIUM | 需要方言检测 |
| 60 | get_optional_rbac_user 重抛 403 | MEDIUM | 设计决策 |
| 61 | list_workflows total 包含错误 | LOW | 前端处理 |
| 63 | save_workflow 并发竞态 | MEDIUM | 需要 upsert |
| 66 | 条件步骤两套实现 | MEDIUM | 需要统一 |
| 67 | save_run_state 无事务隔离 | MEDIUM | 需要乐观锁 |
| 72 | 无管理员路径管理共享模板 | LOW | 功能缺失 |
| 73 | submit_review 不验证执行器存活性 | MEDIUM | 需要心跳机制 |
| 74 | _can_set_visibility 允许无部门用户 | LOW | 边缘场景 |
| 75 | Agent 统计信息泄露 | LOW | 运营元数据 |
| 78 | list_departments 缺少角色限制 | LOW | 设计决策 |
| 84 | save_run_state 未持久化 review_result | MEDIUM | 当前不触发 |
| 85 | update_agent 未验证可见性变更 | LOW | 当前无 visibility 字段 |
| 86 | WorkflowDef.name max_length | LOW | DB 约束 |
| 89 | 后台任务孤立运行 | MEDIUM | 需要恢复机制 |
| 90 | _should_run falsy 值 | LOW | 行为文档化 |
| 91 | 运行记录不快照 YAML | MEDIUM | 需要快照机制 |
| 92 | LocalSettings 类型过于宽松 | LOW | 前端类型 |
| 97 | update_skill 移除自动创建 | LOW | 设计决策 |
| 99 | Admin 页面未使用 React Query | LOW | 前端优化 |
| 100 | extensions_config 环境变量 | MEDIUM | 同 BUG-10 |
| 101 | 前端工作流 API 缺少分页 | LOW | 前端优化 |
| 102 | 前端未类型化请求体 | LOW | 前端优化 |
| 103 | _check_resource_modify 允许 dept_admin | LOW | 可能是设计意图 |

---

## 五、设计决策/无需修改（12 项）

| # | 问题 | 理由 |
|---|------|------|
| P2-RUNTIME-03 | Claude 同步重试阻塞 | 同步 API 固有特性 |
| P2-RUNTIME-05 | 摘要忙等待 | langchain 基类，无法修改 |
| P2-RUNTIME-07 | 子 agent 沙箱共享 | 设计决策 |
| P2-API-01 | 装饰器顺序不一致 | 代码确认正确 |
| P2-API-02 | agents.py 注释误导 | 注释已修正 |
| P2-API-03 | run_workflow 角色枚举 | 当前正确 |
| P2-BUILD-01 | duckdb/markitdown 主依赖 | 安装优化 |
| P2-BUILD-03 | 测试导入路径非标准 | 一致性 |
| P2-RUNTIME-08 | 内存队列跨用户干扰 | 已部分修复 |
| 78 | list_departments 无角色限制 | 设计决策：允许所有用户查看部门列表 |
| 86 | WorkflowDef.name max_length | DB 约束决定 |
| 90 | _should_run falsy 值 | 设计决策 |

---

## 六、新功能（不在本轮范围）

| 编号 | 问题 | 理由 |
|------|------|------|
| P2-WF-05 | 工作流取消 API | 新功能，需单独 PR |

---

## 七、测试覆盖（不在本轮范围）

| 编号 | 问题 | 理由 |
|------|------|------|
| P2-TEST-01 | tools 路由零测试 | 需要单独 PR |
| P2-TEST-02 | admin 路由零测试 | 需要单独 PR |
| P2-TEST-03 | agents 路由零测试 | 需要单独 PR |
| P2-TEST-04 | workflow 路由无 RBAC 测试 | 需要单独 PR |
| P2-TEST-05 | asyncio.sleep monkey-patch | 测试质量 |
| P2-TEST-06 | doc_reader 缺 async 标记 | 测试质量 |
