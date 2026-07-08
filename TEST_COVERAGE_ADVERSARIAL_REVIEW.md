# Deer-Flow / iDeer 测试覆盖对抗式审查报告

> 审查日期: 2026-07-07
> 审查范围: backend/tests/, frontend/tests/unit/, frontend/tests/e2e/
> 对应源码: backend/app/, backend/packages/harness/ideer/, frontend/src/

---

## 一、总体数据

| 指标 | 数值 |
|------|------|
| 后端 Python 源文件 | ~326 |
| 后端测试文件 | ~386 |
| 后端测试用例数 | ~11,323 |
| 前端 TS/TSX 源文件 (不含 content/) | ~284 |
| 前端单元测试文件 | ~220 |
| 前端 E2E 测试文件 | ~35 |

---

## 二、后端测试覆盖清单

### 2.1 路由层 (backend/app/gateway/routers/)

| 路由文件 | 端点数 | 对应测试文件 | 覆盖评级 |
|----------|--------|-------------|----------|
| auth.py | 18 | test_auth.py, test_auth_config.py, test_auth_errors.py, test_auth_middleware.py, test_auth_router_coverage.py, test_auth_router_cov3.py, test_auth_router_e2e.py, test_auth_router_gaps.py, test_auth_type_system.py | **充分** |
| admin.py | 9 | test_admin_router.py (34 tests), test_admin_router_full.py (82 tests), test_admin_router_e2e.py (16 tests) | **充分** |
| agents.py | 20 | test_agents_router.py, test_agents_router_coverage.py, test_agents_router_coverage2.py, test_agents_router_coverage_boost.py, test_agents_router_e2e.py, test_agents_router_full.py | **充分** |
| threads.py | 11 | test_threads_router.py, test_threads_router_e2e.py, test_threads_router_full.py | **充分** |
| thread_runs.py | 14 | test_thread_runs_router.py, test_thread_runs_coverage.py | **充分** |
| skills.py | 19 | test_skills_router_coverage.py, test_skills_router_e2e.py, test_skills_router_full.py, test_skills_custom_router.py | **充分** |
| workflows.py | 12 | test_workflows_router.py, test_workflows_router_e2e.py, test_workflows_coverage.py | **充分** |
| memory.py | 11 | test_memory_router.py, test_memory_router_coverage.py, test_memory_router_e2e.py | **充分** |
| uploads.py | 13 | test_uploads_router.py, test_uploads_router_e2e.py, test_uploads_manager.py, test_uploads_manager_coverage.py | **充分** |
| tools.py | 4 | test_tools_router.py, test_tools_router_e2e.py | **充分** |
| suggestions.py | 5 | test_suggestions_router.py, test_suggestions_router_e2e.py | **充分** |
| feedback.py | 6 | test_feedback.py, test_feedback_router_coverage.py, test_feedback_router_e2e.py | **充分** |
| artifacts.py | 6 | test_artifacts_router.py, test_artifacts_router_coverage.py, test_artifacts_router_e2e.py | **充分** |
| mcp.py | 4 | test_mcp_tools.py, test_mcp_config_router_e2e.py | **充分** |
| assistants_compat.py | 6 | test_assistants_compat_router.py, test_assistants_compat_full.py | **充分** |
| channels.py | 2 | test_channels_router_e2e.py | **一般** |
| models.py | 2 | test_models_router.py, test_models_router_full.py | **一般，缺 E2E** |
| admin_skill_applications.py | 3 | test_admin_skill_applications_deprecated.py | **不足** |
| **audit_logs.py** | **2** | **无专用测试文件** | **缺失** |
| **visibility_applications.py** | **5** | test_visibility_applications.py (仅 mock-based) | **不足，缺 E2E** |

### 2.2 中间件层 (backend/packages/harness/ideer/agents/middlewares/)

| 中间件文件 | 对应测试文件 | 覆盖评级 |
|-----------|-------------|----------|
| clarification_middleware.py | test_clarification_middleware.py | 充分 |
| dangling_tool_call_middleware.py | test_dangling_tool_call_middleware.py, test_coverage_dangling_middleware_2.py | 充分 |
| dynamic_context_middleware.py | test_dynamic_context_middleware.py | 充分 |
| llm_error_handling_middleware.py | test_llm_error_handling_middleware.py, test_llm_error_middleware_coverage.py, test_llm_error_middleware_cov3.py | 充分 |
| loop_detection_middleware.py | test_loop_detection_middleware.py | 充分 |
| safety_finish_reason_middleware.py | test_safety_finish_reason_middleware.py, test_safety_finish_reason_graph_integration.py | 充分 |
| sandbox_audit_middleware.py | test_sandbox_audit_middleware.py, test_coverage_sandbox_audit_2.py | 充分 |
| subagent_limit_middleware.py | test_subagent_limit_middleware.py | 充分 |
| summarization_middleware.py | test_summarization_middleware.py | 充分 |
| title_middleware.py | test_title_middleware_core_logic.py, test_title_generation.py | 充分 |
| todo_middleware.py | test_todo_middleware.py | 充分 |
| token_usage_middleware.py | test_token_usage_middleware.py | 充分 |
| tool_error_handling_middleware.py | test_tool_error_handling_middleware.py, test_coverage_tool_error_middleware_2.py | 充分 |
| uploads_middleware.py | test_uploads_middleware_core_logic.py | 充分 |
| view_image_middleware.py | test_view_image_tool.py, test_view_image_middleware.py | 充分 |
| thread_data_middleware.py | test_thread_data_middleware.py | 充分 |
| memory_middleware.py | 无专用测试文件 | **不足** |
| **deferred_tool_filter_middleware.py** | **无专用测试文件** | **缺失** |
| tool_call_metadata.py | 无专用测试文件 | **不足** |

### 2.3 核心包 (backend/packages/harness/ideer/)

| 模块 | 测试覆盖评级 | 说明 |
|------|-------------|------|
| agents/lead_agent/ | 充分 | test_lead_agent_coverage.py, test_lead_agent_prompt.py, test_lead_agent_skills.py 等 |
| agents/memory/ | 充分 | test_memory_storage.py, test_memory_updater.py, test_memory_queue.py 等 21 个文件 |
| **agents/features.py** | **无测试** | agent 特性标志逻辑无任何测试 |
| config/app_config.py | 充分 | test_app_config_coverage.py, test_app_config_reload.py 等 |
| config/model_config.py | 充分 | test_model_config.py |
| config/skills_config.py | 充分 | test_subagent_skills_config.py |
| config/tracing_config.py | 充分 | test_tracing_config.py |
| **config/skill_evolution_config.py** | **无测试** | |
| **config/checkpointer_config.py** | **无直接测试** | |
| **config/database_config.py** | **无直接测试** | |
| **config/guardrails_config.py** | **无直接测试** | |
| **config/memory_config.py** | **无直接测试** | |
| **config/run_events_config.py** | **无直接测试** | |
| **config/safety_finish_reason_config.py** | **无直接测试** | |
| **config/sandbox_config.py** | **无直接测试** | |
| **config/stream_bridge_config.py** | **无直接测试** | |
| **config/subagents_config.py** | **无直接测试** | |
| **config/summarization_config.py** | **无直接测试** | |
| **config/title_config.py** | **无直接测试** | |
| **config/tool_config.py** | **无直接测试** | |
| **config/tool_search_config.py** | **无直接测试** | |
| guardrails/middleware.py | 充分 | test_guardrail_middleware.py |
| **guardrails/builtin.py** | **无独立测试** | 仅在 middleware 测试中间接使用 |
| **guardrails/provider.py** | **无独立测试** | 基类/数据模型无验证 |
| mcp/ | 充分 | test_mcp_cache.py, test_mcp_tools.py, test_mcp_oauth.py 等 |
| models/ | 较好 | test_model_factory.py, test_patched_*.py, test_claude_provider.py 等 |
| persistence/ | 较好 | test_persistence_engine.py, test_persistence_run_sql.py, test_checkpointer.py 等 |
| **persistence/feedback/** | **无直接测试** | model.py 和 sql.py 无独立验证 |
| **persistence/json_compat.py** | **无测试** | |
| runtime/ | 较好 | test_run_manager.py, test_run_worker.py, test_serialization.py 等 |
| sandbox/ | 充分 | 12 个测试文件全面覆盖 |
| **sandbox/file_operation_lock.py** | **无独立测试** | 并发安全关键逻辑仅在 tools 测试中间接覆盖 |
| skills/ | 较好 | test_skills_parser.py, test_skills_validation.py, test_security_scanner.py 等 |
| **skills/tool_policy.py** | **无直接测试** | 安全关键逻辑 |
| subagents/ | 较好 | test_subagent_executor.py, test_subagent_token_collector.py 等 |
| tools/ | 充分 | test_tool_registry.py, test_tool_search.py, test_task_tool_*.py 等 |
| tracing/ | 充分 | test_tracing_factory.py, test_tracing_config.py, test_tracing_metadata.py |
| uploads/ | 充分 | test_uploads_manager.py, test_uploads_manager_coverage.py |
| utils/ | 较好 | test_utils_time.py, test_file_conversion.py, test_readability.py 等 |
| workflows/ | 充分 | test_workflow_executor.py, test_workflow_parser_coverage.py 等 |
| **scripts/migrate_skill_applications.py** | **无测试** | |

### 2.4 网关层 (backend/app/gateway/)

| 文件 | 测试覆盖 | 评级 |
|------|---------|------|
| app.py | test_gateway_lifespan_shutdown.py, test_gateway_docs_toggle.py | 充分 |
| auth_middleware.py | test_auth_middleware.py | 充分 |
| authz.py | test_authz.py, test_authz_rbac.py | 充分 |
| csrf_middleware.py | test_csrf_middleware.py | 充分 |
| deps.py | test_deps_internal_auth_coverage.py | 一般 |
| **error_codes.py** | **仅在 test_permission_model_coverage.py 中间接引用** | **缺失** |
| internal_auth.py | test_internal_auth.py, test_internal_auth_coverage.py | 充分 |
| langgraph_auth.py | test_langgraph_auth.py | 充分 |
| services.py | test_gateway_services.py, test_services_coverage_boost.py | 充分 |
| audit.py | 无直接测试 | **不足** |

---

## 三、前端测试覆盖清单

### 3.1 Core 模块

| 模块 | 单元测试文件数 | 评级 | 说明 |
|------|-------------|------|------|
| core/agents/ | 3 | 充分 | api + hooks + index 全覆盖 |
| core/api/ | 5 (api-client/errors/feedback/fetcher/stream-mode) | 充分 | |
| core/artifacts/ | 6 (fault-tree/hooks/loader/preview/utils + 顶层) | 充分 | |
| core/auth/ | 7 | 充分 | AuthProvider/gateway-config/proxy-policy/server/static-user/types |
| core/blog/ | 1 | 充分 | |
| core/config/ | 1 | 充分 | |
| core/i18n/ | 9 | 充分 | context/cookies/hooks/keys/locales/server/translations |
| core/memory/ | 3 | 较好 | api/hooks/index |
| core/messages/ | 4 | 充分 | utils/utils-extra/usage/usage-model |
| core/models/ | 3 | 一般 | api/hooks/index，api 仅 4 个测试 |
| core/mcp/ | 3 | **浅** | index 仅验证 re-export，hooks 和 api 测试较少 |
| core/notification/ | 2 | 充分 | hooks + hooks-extra |
| core/settings/ | 4 | 较好 | hooks/local/store/store-extra |
| core/skills/ | 3 | 较好 | api/hooks/index |
| core/streamdown/ | 1 | 一般 | 仅 plugins |
| core/tasks/ | 3 | 较好 | context/index/subtask-result |
| core/threads/ | 7 | 充分 | api/export/hooks/message-merge/static-demo/token-usage/utils |
| core/todos/ | 1 | 较好 | 仅 index |
| core/tools/ | 3 | 较好 | api/index/utils |
| core/uploads/ | 5 | 充分 | api/file-validation/hooks/index/prompt-input-files |
| core/utils/ | 4 (datetime/files/json/json-extra/markdown) | 充分 | |
| core/workflows/ | 4 | 充分 | api/hooks/index/validate |
| **core/audit-logs/** | **0** | **完全缺失** | api.ts 和 types.ts 无任何测试 |
| **core/visibility-applications/** | **0** | **完全缺失** | api.ts 和 types.ts 无任何测试 |
| **core/agents/types.ts** | **0** | 低优先级 | 类型定义通常无需测试 |
| **core/admin/types.ts** | **0** | 低优先级 | |
| **core/utils/uuid.ts** | **0** | 低优先级 | |

### 3.2 页面组件 (app/)

| 页面 | 测试文件 | 评级 |
|------|---------|------|
| (auth)/login/page.tsx | test | 充分 |
| (auth)/setup/page.tsx | test | 充分 |
| (auth)/layout.tsx | test | 充分 |
| workspace/page.tsx | test | 充分 |
| workspace/layout.tsx | test | 充分 |
| workspace/workspace-content.tsx | test | 充分 |
| workspace/admin/page.tsx | test | 充分 |
| workspace/admin/users/page.tsx | test | 充分 |
| workspace/admin/departments/page.tsx | test | 充分 |
| workspace/admin/tools/page.tsx | test | 充分 |
| workspace/admin/visibility-applications/page.tsx | test | 充分 |
| **workspace/admin/audit-logs/page.tsx** | **无测试** | **缺失** |
| **workspace/admin/skill-applications/page.tsx** | **无测试** | **缺失** |
| workspace/agents/* | 多个测试文件 | 充分 |
| workspace/chats/* | 多个测试文件 | 充分 |
| workspace/workflows/* | 多个测试文件 | 充分 |
| blog/* | 多个测试文件 | 充分 |
| [lang]/docs/* | 多个测试文件 | 充分 |

### 3.3 UI/组件层

| 类别 | 测试覆盖 | 评级 |
|------|---------|------|
| components/ui/* | 全部 ~35 个组件均有测试 | 充分 |
| components/ai-elements/* | 全部 ~26 个组件均有测试 | 充分 |
| components/landing/* | 全部有测试 + E2E | 充分 |
| components/workspace/* | 几乎全部有测试 | 充分 |
| **components/workspace/settings/skill-apply-dialog.tsx** | **无测试** | **不足** |
| components/workspace/messages/* | 全部有测试 | 充分 |
| components/workspace/artifacts/* | 全部有测试 | 充分 |
| components/workspace/chats/* | 全部有测试 | 充分 |
| components/workspace/settings/* | 全部有测试 (memory-settings-page 达 160 个用例) | 充分 |

### 3.4 E2E 测试

| E2E 文件 | 覆盖场景 | 评级 |
|----------|---------|------|
| admin-management.spec.ts | 管理面板操作 | 充分 |
| agent-management.spec.ts | Agent CRUD | 充分 |
| agent-chat.spec.ts | Agent 对话 | 充分 |
| artifact-preview.spec.ts | 产物预览 | 充分 |
| artifact-visualization.spec.ts | 产物可视化 | 充分 |
| chat.spec.ts | 基本对话流程 | 充分 |
| chat-thread-init-ordering.spec.ts | 线程初始化顺序 | 充分 |
| skill-management.spec.ts | 技能管理 | 充分 |
| workflow-management.spec.ts | 工作流管理 | 充分 |
| sidebar.spec.ts | 侧边栏导航 | 充分 |
| landing.spec.ts | 首页 | 充分 |
| thread-history.spec.ts | 历史线程 | 充分 |
| brand-and-offline.spec.ts | 品牌/离线 | 充分 |
| qa/auth-flow.spec.ts | 认证流程 | 充分 |
| qa/admin-panel.spec.ts | 管理面板 | 充分 |
| qa/chat-flow.spec.ts | 对话流程 | 充分 |
| qa/file-upload.spec.ts | 文件上传 | 充分 |
| qa/memory-management.spec.ts | 记忆管理 | 充分 |
| qa/sandbox-management.spec.ts | 沙箱管理 | 充分 |
| qa/visual-screenshot.spec.ts | 视觉截图 (91 个用例) | 充分 |
| **缺失: settings 管理 E2E** | | **缺失** |
| **缺失: MCP 配置管理 E2E** | | **缺失** |
| **缺失: 模型管理 E2E** | | **缺失** |
| **缺失: 线程导出 E2E** | | **缺失** |
| **缺失: 反馈/评价 E2E** | | **缺失** |
| **缺失: 审计日志 E2E** | | **缺失** |

---

## 四、缺失分析（按严重程度分级）

### CRITICAL — 安全/数据完整性风险

| # | 缺失项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| C1 | `error_codes.py` 中 `ApiException` 和错误码注册表无直接单元测试。这是全项目统一错误处理的核心，包含 13 个错误码到 HTTP 状态码的映射。未知 code 应抛 `ValueError`，现有代码无验证 | `backend/app/gateway/error_codes.py` | 单元测试: 验证每个错误码映射、构造异常、未知 code 异常 |
| C2 | 密码阻止列表 `_COMMON_PASSWORDS` (约 40 个常见密码) 无系统性验证。auth router 中 `validate_password_strength` 函数是注册流程的唯一防线 | `backend/app/gateway/routers/auth.py` | 安全测试: 常见密码拒绝、长度边界(8字符)、特殊字符密码接受 |
| C3 | RBAC 权限矩阵缺少交叉角色验证。`department_admin` 尝试越权操作 (创建 super_admin、修改其他部门用户、禁用最后 super_admin) 的组合未被系统性覆盖 | `backend/app/gateway/routers/admin.py`, `backend/app/gateway/authz.py` | 集成测试: 每种角色 x 每种操作的权限矩阵 |
| C4 | 乐观锁/并发更新缺少压力测试。admin router 中 `update_user_role` 使用 `with_for_update()` 行锁，但无并发写入冲突的测试 | `backend/app/gateway/routers/admin.py` | 并发测试: 同时修改同一用户角色 |

### HIGH — 重要功能无测试或严重不足

| # | 缺失项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| H1 | `guardrails/builtin.py` (AllowlistProvider) 无独立测试。allow/deny 判定逻辑仅在 middleware 测试中被间接使用 | `backend/packages/harness/ideer/guardrails/builtin.py` | 单元测试: allowlist 匹配、拒绝、空列表、大小写 |
| H2 | `guardrails/provider.py` (GuardrailProvider/GuardrailDecision 基类) 无验证 | `backend/packages/harness/ideer/guardrails/provider.py` | 单元测试: 数据模型构造、字段校验 |
| H3 | `agents/features.py` 完全无测试 | `backend/packages/harness/ideer/agents/features.py` | 单元测试 |
| H4 | `skills/tool_policy.py` 工具策略无直接测试。控制哪些工具可被哪些 agent 使用，是安全关键逻辑 | `backend/packages/harness/ideer/skills/tool_policy.py` | 单元测试: 策略匹配、拒绝、默认行为 |
| H5 | `deferred_tool_filter_middleware.py` 无独立测试文件。`wrap_model_call` 和 `awrap_tool_call` 的工具过滤/拦截逻辑仅在 tool_search 测试中间接覆盖 | `backend/packages/harness/ideer/agents/middlewares/deferred_tool_filter_middleware.py` | 单元测试: 过滤 deferred 工具、拦截未提升工具、async 路径 |
| H6 | `memory_middleware.py` 无直接测试文件 | `backend/packages/harness/ideer/agents/middlewares/memory_middleware.py` | 单元测试 |
| H7 | `persistence/feedback/model.py` 和 `sql.py` 无直接测试 | `backend/packages/harness/ideer/persistence/feedback/` | 集成测试 |
| H8 | `persistence/json_compat.py` 无测试。处理数据迁移中的 JSON 兼容 | `backend/packages/harness/ideer/persistence/json_compat.py` | 单元测试: 序列化/反序列化边界 |
| H9 | `sandbox/file_operation_lock.py` 无独立测试。文件操作锁是并发安全的关键 | `backend/packages/harness/ideer/sandbox/file_operation_lock.py` | 单元测试: 获取/释放、超时、重入 |
| H10 | `audit_logs` 路由无任何测试文件。包含过滤、分页、日期范围查询等复杂逻辑 | `backend/app/gateway/routers/audit_logs.py` | 单元测试 + E2E |
| H11 | `visibility_applications` 路由仅有 mock-based 测试，无 E2E。提交/审批/撤回完整工作流未经过真实 HTTP 栈验证 | `backend/app/gateway/routers/visibility_applications.py` | E2E 测试 |
| H12 | 前端 `core/audit-logs/` (api.ts + types.ts) 完全无测试 | `frontend/src/core/audit-logs/` | 单元测试: API 调用、参数构建、错误处理 |
| H13 | 前端 `core/visibility-applications/` (api.ts + types.ts) 完全无测试 | `frontend/src/core/visibility-applications/` | 单元测试 |
| H14 | 前端 `app/workspace/admin/audit-logs/page.tsx` 无单元测试 | `frontend/src/app/workspace/admin/audit-logs/page.tsx` | 单元测试 |
| H15 | 前端 `app/workspace/admin/skill-applications/page.tsx` 无单元测试 | `frontend/src/app/workspace/admin/skill-applications/page.tsx` | 单元测试 |

### MEDIUM — 覆盖不足或遗漏重要场景

| # | 缺失项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| M1 | 约 15 个 config 模块无直接测试。虽然通过被使用而间接覆盖，但配置解析、默认值、类型校验逻辑未被独立验证 | `backend/packages/harness/ideer/config/*.py` | 参数化单元测试: 验证每个 config 的默认值和边界 |
| M2 | `models` 路由无 E2E 测试。模型列表和 token usage 配置未经真实 HTTP 栈验证 | `backend/app/gateway/routers/models.py` | E2E 测试 |
| M3 | `admin_skill_applications` 路由标记为 deprecated 但仍有端点，测试不足 | `backend/app/gateway/routers/admin_skill_applications.py` | 单元测试或确认完全废弃 |
| M4 | `agents/features.py` (agent 特性标志) 无测试 | `backend/packages/harness/ideer/agents/features.py` | 单元测试 |
| M5 | `scripts/migrate_skill_applications.py` 迁移脚本无测试 | `backend/packages/harness/ideer/scripts/migrate_skill_applications.py` | 集成测试: 迁移前/后数据验证 |
| M6 | `gateway/audit.py` 审计日志记录功能无直接测试 | `backend/app/gateway/audit.py` | 单元测试 |
| M7 | 前端 E2E 缺少以下场景: 设置管理、MCP 配置、模型管理、线程导出、反馈评价、审计日志 | 多个 E2E 文件 | 补充 E2E 测试 |
| M8 | 前端 `core/mcp/index.test.ts` 仅验证 re-export (2 个 test)，是典型的"浅测试" | `frontend/tests/unit/core/mcp/index.test.ts` | 深化测试 |
| M9 | 前端 `core/agents/index.test.ts` 仅验证 re-export (2 个 test) | `frontend/tests/unit/core/agents/index.test.ts` | 深化测试 |
| M10 | 前端 `components/workspace/settings/skill-apply-dialog.tsx` 无测试 | `frontend/src/components/workspace/settings/skill-apply-dialog.tsx` | 单元测试 |

### LOW — 低优先级或类型定义

| # | 缺失项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| L1 | 多个 `types.ts` 文件无测试 (admin/agents/mcp/memory/models/skills/tasks/threads/todos/tools/workflows) | `frontend/src/core/*/types.ts` | 类型定义通常无需单元测试，但可考虑运行时 schema 验证测试 |
| L2 | 前端 `core/api/index.ts` 无测试 | `frontend/src/core/api/index.ts` | 低优先级 |
| L3 | 前端 `core/i18n/index.ts` 无测试 | `frontend/src/core/i18n/index.ts` | 低优先级 |
| L4 | 前端 `core/static-mode.ts` 有测试但覆盖率可能不足 | `frontend/src/core/static-mode.ts` | 检查覆盖率 |
| L5 | 后端 `tool_call_metadata.py` 无独立测试 | `backend/packages/harness/ideer/agents/middlewares/tool_call_metadata.py` | 低优先级 |

---

## 五、测试类型缺失分析

### 5.1 后端缺失的测试类型

| 缺失类型 | 说明 | 涉及范围 |
|----------|------|---------|
| **RBAC 权限矩阵测试** | 没有系统性地测试所有角色 x 所有操作的组合 | admin, authz, 所有需要权限的路由 |
| **并发/竞态测试** | `with_for_update()` 行锁、乐观锁冲突缺少并发压力测试 | admin router, visibility_applications |
| **性能/负载测试** | 无任何性能基线测试 | 全局 |
| **安全扫描测试** | 密码强度、SQL 注入、XSS 防护缺少系统性安全测试 | auth, 所有用户输入端点 |
| **配置热重载测试** | config 模块的动态重载缺少系统性测试 | config/*.py |
| **数据库迁移测试** | Alembic 迁移脚本缺少 forward/backward 测试 | persistence/migrations/ |

### 5.2 前端缺失的测试类型

| 缺失类型 | 说明 | 涉及范围 |
|----------|------|---------|
| **无障碍性 (a11y) 单元测试** | 仅有一个 E2E a11y 测试，缺少组件级别的 a11y 测试 | 所有交互组件 |
| **响应式/移动端测试** | `use-mobile` hook 有测试，但移动端布局/交互缺少单元测试 | workspace 组件 |
| **国际化 (i18n) E2E 测试** | 单元测试充分但缺少多语言切换的 E2E 验证 | 全局 |
| **错误边界测试** | React Error Boundary 场景缺少测试 | 全局 |
| **性能/懒加载测试** | 组件懒加载、代码分割缺少验证 | 全局 |

---

## 六、总体评估

### 覆盖率评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 后端路由层 | **85/100** | 19 个路由中 17 个有充分测试，audit_logs 和 visibility_applications 不足 |
| 后端中间件层 | **90/100** | 21 个中间件中 18 个有充分测试 |
| 后端核心包 | **75/100** | guardrails/builtin, tool_policy, features, file_operation_lock 等缺失 |
| 后端配置层 | **60/100** | 约 15 个 config 模块无直接测试 |
| 前端 core 模块 | **85/100** | audit-logs 和 visibility-applications 完全缺失 |
| 前端组件 | **95/100** | 几乎全部覆盖，仅 skill-apply-dialog 缺失 |
| 前端 E2E | **75/100** | 覆盖主要用户流程，但缺少 settings/MCP/模型/导出/审计日志等场景 |
| 后端 E2E | **80/100** | 21 个 E2E 文件覆盖主要路由，但缺少 models/audit_logs/visibility_applications |
| **综合评分** | **82/100** | 整体测试基础扎实，但在安全验证、RBAC 矩阵、部分新模块方面存在显著缺口 |

### 关键发现

1. **测试数量充足但质量参差不齐**: 后端 11,323 个测试用例、前端约 220 个测试文件提供了广泛的基础覆盖。但部分测试是"浅测试"（仅验证 re-export），对核心逻辑的验证不够深入。

2. **新功能模块存在覆盖盲区**: `audit_logs`、`visibility_applications`、`skill-applications` 等较新的管理功能明显缺乏测试。

3. **安全测试是最大短板**: 密码强度验证、RBAC 权限矩阵、乐观锁并发、工具策略等安全关键路径缺少系统性验证。

4. **前后端 E2E 断层**: 虽然后端有 21 个 E2E 文件、前端有 35 个 E2E 文件，但两者之间缺少端到端的全链路测试（从前端页面操作到后端数据库验证）。

5. **配置模块的测试债务**: 约 15 个配置模块完全无直接测试，仅通过被使用而间接覆盖，配置解析错误可能在运行时才暴露。

---

*报告完成。建议优先处理 CRITICAL 和 HIGH 级别的缺失项。*

---

## 七、测试完善待办清单

> 每项标注优先级（P0=Critical / P1=High / P2=Medium / P3=Low）、状态（TODO / IN_PROGRESS / DONE）、负责人、完成日期。
> 状态更新时请同步修改本表。

### CRITICAL — 安全/数据完整性风险

| # | 待办项 | 涉及文件 | 测试类型 | 状态 | 负责人 | 完成日期 |
|---|--------|---------|---------|------|--------|---------|
| C1 | `error_codes.py` 错误码注册表单元测试：验证每个错误码→HTTP 状态码映射、ApiException 构造、未知 code 抛 ValueError | `backend/app/gateway/error_codes.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| C2 | 密码阻止列表 `_COMMON_PASSWORDS` 系统性验证：常见密码拒绝（大小写不敏感）、长度边界（8字符）、特殊字符密码接受 | `backend/app/gateway/routers/auth.py` | 安全测试 | DONE | MiMoCode | 2026-07-07 |
| C3 | RBAC 权限矩阵交叉角色验证：department_admin 越权操作（创建 super_admin、修改其他部门用户、禁用最后 super_admin）× 所有角色组合 | `backend/app/gateway/routers/admin.py`, `backend/app/gateway/authz.py` | 集成测试 | DONE | MiMoCode | 2026-07-07 |
| C4 | 乐观锁/并发更新压力测试：同时修改同一用户角色、同时审批同一可见性申请 | `backend/app/gateway/routers/admin.py` | 并发测试 | DONE | MiMoCode | 2026-07-07 |

### HIGH — 重要功能无测试或严重不足

| # | 待办项 | 涉及文件 | 测试类型 | 状态 | 负责人 | 完成日期 |
|---|--------|---------|---------|------|--------|---------|
| H1 | `guardrails/builtin.py` AllowlistProvider 独立单元测试：allowlist 匹配、拒绝、空列表、大小写 | `backend/packages/harness/ideer/guardrails/builtin.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H2 | `guardrails/provider.py` 基类/数据模型验证测试 | `backend/packages/harness/ideer/guardrails/provider.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H3 | `agents/features.py` agent 特性标志逻辑单元测试 | `backend/packages/harness/ideer/agents/features.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H4 | `skills/tool_policy.py` 工具策略安全测试：策略匹配、拒绝、默认行为 | `backend/packages/harness/ideer/skills/tool_policy.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H5 | `deferred_tool_filter_middleware.py` 独立单元测试：过滤 deferred 工具、拦截未提升工具、async 路径 | `backend/packages/harness/ideer/agents/middlewares/deferred_tool_filter_middleware.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H6 | `memory_middleware.py` 会话过滤与记忆队列入队单元测试 | `backend/packages/harness/ideer/agents/middlewares/memory_middleware.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H7 | `persistence/feedback/` 模型和 SQL 操作集成测试 | `backend/packages/harness/ideer/persistence/feedback/` | 集成测试 | DONE | MiMoCode | 2026-07-07 |
| H8 | `persistence/json_compat.py` 序列化/反序列化边界单元测试 | `backend/packages/harness/ideer/persistence/json_compat.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H9 | `sandbox/file_operation_lock.py` 并发锁单元测试：获取/释放、超时、重入 | `backend/packages/harness/ideer/sandbox/file_operation_lock.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H10 | `audit_logs` 路由单元测试 + E2E：过滤、分页、日期范围查询、权限验证 | `backend/app/gateway/routers/audit_logs.py` | 单元测试 + E2E | DONE | MiMoCode | 2026-07-07 |
| H11 | `visibility_applications` E2E 测试：提交/审批/撤回完整 HTTP 栈验证 | `backend/app/gateway/routers/visibility_applications.py` | E2E 测试 | DONE | MiMoCode | 2026-07-07 |
| H11-a | visibility_applications dept_admin 同部门审核测试需显式验证部门匹配 | `backend/tests/test_visibility_applications_e2e.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H11-b | visibility_applications 缺少 super_admin 跨部门审核的显式测试 | `backend/tests/test_visibility_applications_e2e.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H11-c | visibility_applications 缺少 `department_id=None` 边界测试 | `backend/tests/test_visibility_applications_e2e.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H11-d | visibility_applications 跨部门测试中用户 dept_id 隐式依赖默认值 | `backend/tests/test_visibility_applications_e2e.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H12 | 前端 `core/audit-logs/` API 调用、参数构建、错误处理单元测试 | `frontend/src/core/audit-logs/` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H13 | 前端 `core/visibility-applications/` API 调用单元测试 | `frontend/src/core/visibility-applications/` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H14 | 前端 `admin/audit-logs/page.tsx` 页面组件单元测试 | `frontend/src/app/workspace/admin/audit-logs/page.tsx` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| H15 | 前端 `admin/skill-applications/page.tsx` 页面组件单元测试 | `frontend/src/app/workspace/admin/skill-applications/page.tsx` | 单元测试 | DONE | MiMoCode | 2026-07-07 |

### MEDIUM — 覆盖不足或遗漏重要场景

| # | 待办项 | 涉及文件 | 测试类型 | 状态 | 负责人 | 完成日期 |
|---|--------|---------|---------|------|--------|---------|
| M1 | ~15 个 config 模块参数化单元测试：验证每个 config 的默认值、类型校验和边界 | `backend/packages/harness/ideer/config/*.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| M2 | `models` 路由 E2E 测试：模型列表和 token usage 配置的 HTTP 栈验证 | `backend/app/gateway/routers/models.py` | E2E 测试 | DONE | MiMoCode | 2026-07-07 |
| M3 | `admin_skill_applications` 路由测试（或确认完全废弃后移除端点） | `backend/app/gateway/routers/admin_skill_applications.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| M4 | `agents/features.py` 补充测试（如 H3 未覆盖全部场景） | `backend/packages/harness/ideer/agents/features.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| M5 | `migrate_skill_applications.py` 迁移脚本集成测试：迁移前/后数据验证 | `backend/packages/harness/ideer/scripts/migrate_skill_applications.py` | 集成测试 | DONE | MiMoCode | 2026-07-07 |
| M6 | `gateway/audit.py` 审计日志记录功能单元测试 | `backend/app/gateway/audit.py` | 单元测试 | DONE | MiMoCode | 2026-07-07 |
| M7 | 前端 E2E 补充：设置管理、MCP 配置、模型管理、线程导出、反馈评价、审计日志场景 | 多个 E2E 文件 | E2E 测试 | DONE | MiMoCode | 2026-07-07 |
| M8 | 前端 `core/mcp/index.test.ts` 深化：从 re-export 验证升级为实际逻辑测试 | `frontend/tests/unit/core/mcp/index.test.ts` | 单元测试 | DONE | opencode | 2026-07-07 |
| M9 | 前端 `core/agents/index.test.ts` 深化：从 re-export 验证升级为实际逻辑测试 | `frontend/tests/unit/core/agents/index.test.ts` | 单元测试 | DONE | opencode | 2026-07-07 |
| M10 | 前端 `skill-apply-dialog.tsx` 组件单元测试 | `frontend/src/components/workspace/settings/skill-apply-dialog.tsx` | 单元测试 | DONE | opencode | 2026-07-07 |

### LOW — 低优先级

| # | 待办项 | 涉及文件 | 测试类型 | 状态 | 负责人 | 完成日期 |
|---|--------|---------|---------|------|--------|---------|
| L1 | 前端 `types.ts` 运行时 schema 验证测试（按需） | `frontend/src/core/*/types.ts` | 单元测试 | DONE | opencode | 2026-07-08 |
| L2 | 前端 `core/api/index.ts` 测试 | `frontend/src/core/api/index.ts` | 单元测试 | DONE | opencode | 2026-07-08 |
| L3 | 前端 `core/i18n/index.ts` 测试 | `frontend/src/core/i18n/index.ts` | 单元测试 | DONE | opencode | 2026-07-08 |
| L4 | 前端 `core/static-mode.ts` 覆盖率检查与补全 | `frontend/src/core/static-mode.ts` | 单元测试 | DONE | opencode | 2026-07-08 |
| L5 | 后端 `tool_call_metadata.py` 独立测试 | `backend/packages/harness/ideer/agents/middlewares/tool_call_metadata.py` | 单元测试 | TODO | | |

### 测试类型缺失专项

| # | 待办项 | 涉及范围 | 测试类型 | 状态 | 负责人 | 完成日期 |
|---|--------|---------|---------|------|--------|---------|
| T1 | RBAC 权限矩阵系统性测试：所有角色 × 所有操作的完整组合 | admin, authz, 所有需权限路由 | 集成测试 | TODO | | |
| T2 | 并发/竞态压力测试：`with_for_update()` 行锁、乐观锁冲突 | admin router, visibility_applications | 并发测试 | TODO | | |
| T3 | 安全专项测试：JWT 伪造、CSRF、路径遍历、XSS、SQL 注入、权限提升 | auth, 所有用户输入端点 | 安全测试 | TODO | | |
| T4 | 配置热重载测试：config 模块的动态重载行为 | `config/*.py` | 集成测试 | TODO | | |
| T5 | 数据库迁移测试：Alembic 迁移脚本 forward/backward 验证 | `persistence/migrations/` | 集成测试 | TODO | | |
| T6 | 前端无障碍性 (a11y) 组件级测试 | 所有交互组件 | 单元测试 | TODO | | |
| T7 | 前端响应式/移动端布局测试 | workspace 组件 | 单元测试 | TODO | | |
| T8 | 前端国际化 (i18n) 多语言切换 E2E 测试 | 全局 | E2E 测试 | TODO | | |
| T9 | 前端 Error Boundary 错误边界测试 | 全局 | 单元测试 | TODO | | |
| T10 | 前端性能/懒加载验证测试 | 全局 | 单元测试 | TODO | | |

---

### 进度统计

| 优先级 | 总数 | TODO | IN_PROGRESS | DONE | 完成率 |
|--------|------|------|-------------|------|--------|
| CRITICAL | 4 | 0 | 0 | 4 | 100% |
| HIGH | 19 | 0 | 0 | 19 | 100% |
| MEDIUM | 10 | 2 | 0 | 8 | 80% |
| LOW | 5 | 1 | 0 | 4 | 80% |
| 类型专项 | 10 | 10 | 0 | 0 | 0% |
| **合计** | **48** | **19** | **0** | **29** | **60%** |
