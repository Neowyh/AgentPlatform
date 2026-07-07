# 全面测试验证与修复计划

> 本文档系统梳理了项目全部 ~543 个测试文件，按模块分批制定验证和修复计划。
> 策略：**模块分批 → 每批运行+修复 → 标记通过 → 下一批**。每批独立，互不阻塞。

---

## 一、测试全景总览

| 分类 | 数量 | 框架 | 位置 |
|------|------|------|------|
| 后端 pytest 单元测试 | 247 个 `.py` 文件 | pytest + pytest-asyncio | `backend/tests/test_*.py` |
| 后端辅助/夹具 | 29 个文件 | conftest / factories / detectors | `backend/tests/{conftest,factories,support}/` |
| 前端 Vitest 单元测试 | 235 个文件 (82 `.test.ts` + 153 `.test.tsx`) | Vitest + jsdom | `frontend/tests/unit/` |
| 前端 Playwright E2E | 32 个 `.spec.ts` 文件 | Playwright | `frontend/tests/e2e/` |
| E2E helper | 4 个文件 | TypeScript | `frontend/tests/e2e/{global-setup,utils,visual}/` |
| CI 工作流 (测试相关) | 10 个 `.yml` | GitHub Actions | `.github/workflows/` |
| **总计测试文件** | **~543 个** | — | — |

---

## 二、分批次执行计划

### 批次说明

- 每批内部可进一步并行：后端用 `-n auto` (pytest-xdist) 或 `--splits N` (pytest-split)
- 每批独立：同一批内的测试失败需要**当场修复**后再走下一批
- 批次间依赖关系：B1→B2→B3→B4，B5/B6 与 B4 可并行，B7 最后

### 依赖图

```
B1(基础层) ──→ B2(核心层) ──→ B3(功能层) ──→ B4(补丁+杂项)
                                                      │
                     B5(后端子目录) ── 并行 ──────────┤
                                                      │
                     B6(前端单元) ──── 并行 ──────────┤
                                                      │
                     B7(前端E2E) ──── 最后 ───────────┘
```

---

### B1: 后端基础层 — 存储/配置/Auth

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B1a** | 存储 / Persistence | 15 | `uv run pytest tests/ -v -k "persistence or checkpointer or store or jsonl or event_store or migrate"` |
| **B1b** | Config / Admin / 启动 | 15 | `uv run pytest tests/ -v -k "app_config or admin_router or setup or ensure or reset or initialize or config_version or extensions or acp or dev_entrypoint"` |
| **B1c** | Auth / 用户权限 | 18 | `uv run pytest tests/ -v -k "auth or authz or password or langgraph_auth or internal_auth or deps_internal or cli_auth"` |

**B1 测试文件清单：**

<details>
<summary>B1a — 存储/Persistence（15 个文件）</summary>

- `test_async_checkpointer.py`
- `test_checkpointer.py`
- `test_checkpointer_async_provider.py`
- `test_checkpointer_none_fix.py`
- `test_persistence_engine.py`
- `test_persistence_run_sql.py`
- `test_persistence_scaffold.py`
- `test_persistence_timezone.py`
- `test_store_async_provider.py`
- `test_store_provider.py`
- `test_store_provider_full.py`
- `test_jsonl_store.py`
- `test_event_store_db_coverage.py`
- `test_event_store_db_coverage2.py`
- `test_migrate_meta_json.py`
</details>

<details>
<summary>B1b — Config/Admin/启动（15 个文件）</summary>

- `test_app_config_coverage.py`
- `test_app_config_extra_coverage.py`
- `test_app_config_reload.py`
- `test_admin_router.py`
- `test_admin_router_e2e.py`
- `test_admin_router_full.py`
- `test_admin_skill_applications_deprecated.py`
- `test_setup_wizard.py`
- `test_ensure_admin.py`
- `test_reset_admin.py`
- `test_initialize_admin.py`
- `test_config_version.py`
- `test_extensions_config.py`
- `test_acp_config.py`
- `test_dev_entrypoint.py`
</details>

<details>
<summary>B1c — Auth/用户权限（18 个文件）</summary>

- `test_auth.py`
- `test_auth_config.py`
- `test_auth_errors.py`
- `test_auth_middleware.py`
- `test_auth_repository_sqlite.py`
- `test_auth_router_cov3.py`
- `test_auth_router_coverage.py`
- `test_auth_router_e2e.py`
- `test_auth_router_gaps.py`
- `test_auth_type_system.py`
- `test_authz.py`
- `test_authz_rbac.py`
- `test_cli_auth_providers.py`
- `test_internal_auth.py`
- `test_internal_auth_coverage.py`
- `test_deps_internal_auth_coverage.py`
- `test_langgraph_auth.py`
- `test_password_validation.py`
</details>

---

### B2: 后端核心层 — Threads/Runs/Workflows/Memory/Middleware/LLM

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B2a** | Threads / Runs / Workflows | 30 | `uv run pytest tests/ -v -k "thread or run or workflow"` |
| **B2b** | Memory | 22 | `uv run pytest tests/test_memory_*.py -v` |
| **B2c** | Middleware | 24 | `uv run pytest tests/ -v -k "middleware"` |
| **B2d** | LLM / Providers | 22 | `uv run pytest tests/ -v -k "provider or model or tracing or converter or patched"` |

<details>
<summary>B2a — Threads/Runs/Workflows（30 个文件）</summary>

- `test_thread_data_middleware.py`
- `test_thread_meta_repo.py`
- `test_thread_run_messages_pagination.py`
- `test_thread_runs_coverage.py`
- `test_thread_runs_router.py`
- `test_thread_state_reducers.py`
- `test_thread_token_usage.py`
- `test_threads_router.py`
- `test_threads_router_e2e.py`
- `test_threads_router_full.py`
- `test_run_event_store.py`
- `test_run_event_store_pagination.py`
- `test_run_journal.py`
- `test_run_manager.py`
- `test_run_naming.py`
- `test_run_repository.py`
- `test_run_worker.py`
- `test_run_worker_rollback.py`
- `test_runs_api_endpoints.py`
- `test_runs_stateless_router.py`
- `test_runs_stateless_router_e2e.py`
- `test_workflow_executor.py`
- `test_workflow_parser_coverage.py`
- `test_workflow_router.py`
- `test_workflow_steps.py`
- `test_workflow_store.py`
- `test_workflows_coverage.py`
- `test_workflows_router.py`
- `test_workflows_router_e2e.py`
- `test_runtime_lifecycle_e2e.py`
</details>

<details>
<summary>B2b — Memory（22 个文件）</summary>

- `test_memory_leak.py`
- `test_memory_middleware.py`
- `test_memory_modules_coverage.py`
- `test_memory_prompt_extra_coverage.py`
- `test_memory_prompt_injection.py`
- `test_memory_queue.py`
- `test_memory_queue_extra_coverage.py`
- `test_memory_queue_user_isolation.py`
- `test_memory_router.py`
- `test_memory_router_coverage.py`
- `test_memory_router_e2e.py`
- `test_memory_storage.py`
- `test_memory_storage_coverage.py`
- `test_memory_storage_extra_coverage.py`
- `test_memory_storage_user_isolation.py`
- `test_memory_thread_meta_coverage.py`
- `test_memory_thread_meta_isolation.py`
- `test_memory_thread_meta_update_metadata.py`
- `test_memory_updater.py`
- `test_memory_updater_coverage.py`
- `test_memory_updater_user_isolation.py`
- `test_memory_upload_filtering.py`
</details>

<details>
<summary>B2c — Middleware（24 个文件）</summary>

- `test_clarification_middleware.py`
- `test_coverage_dangling_middleware_2.py`
- `test_coverage_middleware.py`
- `test_coverage_tool_error_middleware_2.py`
- `test_csrf_middleware.py`
- `test_dangling_tool_call_middleware.py`
- `test_deferred_tool_filter_middleware.py`
- `test_deferred_tool_promotion_real_llm.py`
- `test_deferred_tool_registry_promotion.py`
- `test_dynamic_context_middleware.py`
- `test_guardrail_middleware.py`
- `test_llm_error_handling_middleware.py`
- `test_llm_error_middleware_cov3.py`
- `test_llm_error_middleware_coverage.py`
- `test_middleware_coverage_gaps.py`
- `test_safety_finish_reason_graph_integration.py`
- `test_safety_finish_reason_middleware.py`
- `test_safety_termination_detectors.py`
- `test_summarization_middleware.py`
- `test_title_middleware_core_logic.py`
- `test_todo_middleware.py`
- `test_token_usage_middleware.py`
- `test_uploads_middleware_core_logic.py`
- `test_loop_detection_middleware.py`
</details>

<details>
<summary>B2d — LLM/Providers（22 个文件）</summary>

- `test_claude_provider.py`
- `test_claude_provider_oauth_billing.py`
- `test_claude_provider_prompt_caching.py`
- `test_codex_provider.py`
- `test_mindie_provider.py`
- `test_model_config.py`
- `test_model_factory.py`
- `test_models_router.py`
- `test_models_router_full.py`
- `test_openai_codex_provider.py`
- `test_patched_deepseek.py`
- `test_patched_minimax.py`
- `test_patched_openai.py`
- `test_vllm_provider.py`
- `test_converters.py`
- `test_providers_base_coverage.py`
- `test_tracing_config.py`
- `test_tracing_factory.py`
- `test_tracing_metadata.py`
- `test_local_provider_coverage.py`
- `test_runtime_paths.py`
</details>

---

### B3: 后端功能层 — Agents/Tools/Skills/MCP/Channels/Sandbox/Artifacts

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B3a** | Agents / Subagents | 25 | `uv run pytest tests/ -v -k "agent or subagent or lead_agent or custom_agent"` |
| **B3b** | Tools（不含 MCP） | ~35 | `uv run pytest tests/ -v -k "tool or skill or credential or task_tool or code_interpreter or serper or firecrawl or exa or data_analyzer or image_search or doc_reader or present_file or view_image or local_bash or invoke_acp"` |
| **B3c** | MCP | 9 | `uv run pytest tests/test_mcp_*.py -v` |
| **B3d** | 渠道集成 | 17 | `uv run pytest tests/ -v -k "channel or dingtalk or discord or feishu or slack or telegram or wechat or wecom"` |
| **B3e** | Sandbox | 25 | `uv run pytest tests/ -v -k "sandbox"` |
| **B3f** | Artifacts / Uploads | 10 | `uv run pytest tests/ -v -k "artifact or upload or file_conversion"` |

<details>
<summary>B3a — Agents/Subagents（25 个文件）</summary>

- `test_agents_config_coverage.py`
- `test_agents_router.py`
- `test_agents_router_coverage.py`
- `test_agents_router_coverage2.py`
- `test_agents_router_coverage_boost.py`
- `test_agents_router_e2e.py`
- `test_agents_router_full.py`
- `test_agent_features.py`
- `test_agent_step.py`
- `test_custom_agent.py`
- `test_lead_agent_coverage.py`
- `test_lead_agent_model_resolution.py`
- `test_lead_agent_prompt.py`
- `test_lead_agent_prompt_extra_coverage.py`
- `test_lead_agent_skills.py`
- `test_subagent_executor.py`
- `test_subagent_limit_middleware.py`
- `test_subagent_prompt_security.py`
- `test_subagent_skills_config.py`
- `test_subagent_timeout_config.py`
- `test_subagent_token_collector.py`
- `test_create_ideer_agent.py`
- `test_create_ideer_agent_live.py`
- `test_setup_agent_tool.py`
- `test_update_agent_tool.py`
- `test_update_agent_tool_coverage.py`
</details>

<details>
<summary>B3b — Tools/Skills（~35 个文件）</summary>

- `test_tool_args_schema_no_pydantic_warning.py`
- `test_tool_deduplication.py`
- `test_tool_error_handling_middleware.py`
- `test_tool_output_truncation.py`
- `test_tool_policy.py`
- `test_tool_registry.py`
- `test_tool_search.py`
- `test_tool_step.py`
- `test_tools_coverage.py`
- `test_tools_coverage_boost.py`
- `test_tools_router.py`
- `test_tools_router_e2e.py`
- `test_task_tool_core_logic.py`
- `test_task_tool_coverage.py`
- `test_task_tool_usage_recorder.py`
- `test_serper_tools.py`
- `test_sandbox_search_tools.py`
- `test_exa_tools.py`
- `test_firecrawl_tools.py`
- `test_doc_reader_tools.py`
- `test_doc_reader.py`
- `test_data_analyzer_tools.py`
- `test_data_analyzer.py`
- `test_image_search_tools.py`
- `test_image_search_coverage_fix.py`
- `test_code_interpreter.py`
- `test_skill_manage_tool.py`
- `test_skill_storage.py`
- `test_skills_archive_root.py`
- `test_skills_bundled.py`
- `test_skills_custom_router.py`
- `test_skills_installer.py`
- `test_skills_loader.py`
- `test_skills_parser.py`
- `test_skills_router_coverage.py`
- `test_skills_router_e2e.py`
- `test_skills_router_full.py`
- `test_skills_validation.py`
- `test_present_file_tool_core_logic.py`
- `test_view_image_middleware.py`
- `test_view_image_tool.py`
- `test_local_bash_tool_loading.py`
- `test_credential_file.py`
- `test_credential_loader.py`
- `test_credential_loader_extra_coverage.py`
- `test_invoke_acp_agent_tool.py`
</details>

<details>
<summary>B3c — MCP（9 个文件）</summary>

- `test_mcp_cache.py`
- `test_mcp_cache_extra_coverage.py`
- `test_mcp_client_config.py`
- `test_mcp_config_router_e2e.py`
- `test_mcp_config_secrets.py`
- `test_mcp_custom_interceptors.py`
- `test_mcp_oauth.py`
- `test_mcp_oauth_extra_coverage.py`
- `test_mcp_session_pool.py`
- `test_mcp_sync_wrapper.py`
- `test_mcp_tools.py`
</details>

<details>
<summary>B3d — 渠道集成（17 个文件）</summary>

- `test_channel_base.py`
- `test_channel_commands.py`
- `test_channel_file_attachments.py`
- `test_channel_manager.py`
- `test_channel_manager_coverage.py`
- `test_channel_service.py`
- `test_channel_store.py`
- `test_channels.py`
- `test_channels_coverage.py`
- `test_channels_router_e2e.py`
- `test_dingtalk_channel.py`
- `test_discord_channel.py`
- `test_feishu_channel.py`
- `test_feishu_parser.py`
- `test_slack_channel.py`
- `test_telegram_channel.py`
- `test_wechat_channel.py`
- `test_wecom_channel.py`
</details>

<details>
<summary>B3e — Sandbox（25 个文件）</summary>

- `test_aio_sandbox.py`
- `test_aio_sandbox_coverage.py`
- `test_aio_sandbox_local_backend.py`
- `test_aio_sandbox_provider.py`
- `test_aio_sandbox_provider_coverage_boost.py`
- `test_aio_sandbox_readiness.py`
- `test_coverage_local_sandbox.py`
- `test_coverage_local_sandbox_2.py`
- `test_coverage_local_sandbox_provider.py`
- `test_coverage_sandbox_audit_2.py`
- `test_coverage_sandbox_base.py`
- `test_coverage_sandbox_middleware_2.py`
- `test_coverage_sandbox_tools.py`
- `test_local_sandbox_encoding.py`
- `test_local_sandbox_provider_mounts.py`
- `test_local_sandbox_virtual_path_contract.py`
- `test_remote_sandbox_backend.py`
- `test_sandbox_audit_middleware.py`
- `test_sandbox_exceptions.py`
- `test_sandbox_middleware.py`
- `test_sandbox_middleware_coverage.py`
- `test_sandbox_orphan_reconciliation.py`
- `test_sandbox_orphan_reconciliation_e2e.py`
- `test_sandbox_security.py`
- `test_sandbox_security_helpers.py`
- `test_sandbox_tools.py`
- `test_sandbox_tools_coverage.py`
- `test_sandbox_tools_security.py`
</details>

<details>
<summary>B3f — Artifacts/Uploads（10 个文件）</summary>

- `test_artifacts_router.py`
- `test_artifacts_router_coverage.py`
- `test_artifacts_router_e2e.py`
- `test_uploads_manager.py`
- `test_uploads_manager_coverage.py`
- `test_uploads_router.py`
- `test_uploads_router_e2e.py`
- `test_file_conversion.py`
- `test_file_conversion_coverage.py`
- `test_uploads_middleware_core_logic.py`
</details>

---

### B4: 后端补丁 + 杂项

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B4a** | 覆盖率补丁集 | ~35 | `uv run pytest tests/ -v -k "coverage or worker_cov or parser_cov or prompt_coverage or paths_coverage or resolvers_coverage or services_coverage or search_coverage"` |
| **B4b** | 权限/隔离 | ~10 | `uv run pytest tests/ -v -k "isolation or rbac or visibility or permission or owner"` |
| **B4c** | 杂项 (client/gateway/serial 等) | ~30 | `uv run pytest tests/ -v -k "client or gateway or serial or json or sse or stream or template or error_codes or stress or concurrent or property or doctor or detect or harness or fault_zeroing or install or readability or security_scanner or skill_storage or logging or infoquest or start_local or intranet or local_backend or docker_sandbox or step or guardrail or message_bus or path_utils or user_context or utils_time"` |

<details>
<summary>B4a — 覆盖率补丁集（~35 个文件）</summary>

- `test_coverage_boost.py`
- `test_coverage_boost_2.py`
- `test_coverage_boost_3.py`
- `test_coverage_code_interpreter.py`
- `test_coverage_ddg_search.py`
- `test_coverage_gaps.py`
- `test_coverage_list_dir.py`
- `test_coverage_search.py`
- `test_coverage_tools_2.py`
- `test_worker_cov3.py`
- `test_worker_coverage.py`
- `test_worker_coverage2.py`
- `test_worker_langfuse_metadata.py`
- `test_parser_cov3.py`
- `test_parser_coverage.py`
- `test_prompt_coverage.py`
- `test_paths_coverage.py`
- `test_paths_user_isolation.py`
- `test_resolvers_coverage.py`
- `test_services_coverage_boost.py`
- `test_search_coverage.py`
- `test_network_cov3.py`
- `test_network_utils_coverage.py`
- `test_network_mode.py`
- `test_property_based.py`
- `test_readability.py`
- `test_readability_coverage.py`
- `test_loop_detection_config.py`
- `test_journal_coverage.py`
- `test_journal_coverage2.py`
- `test_detect_uv_extras.py`
- `test_installer_coverage.py`
- `test_schema_parser.py`
</details>

<details>
<summary>B4b — 权限/隔离（~10 个文件）</summary>

- `test_owner_isolation.py`
- `test_migration_user_isolation.py`
- `test_rbac_permission_matrix.py`
- `test_rbac_security.py`
- `test_permission_model_coverage.py`
- `test_visibility_applications.py`
- `test_visibility_applications_e2e.py`
- `test_setup_agent_e2e_user_isolation.py`
- `test_setup_agent_http_e2e_real_server.py`
- `test_update_agent_e2e_user_isolation.py`
</details>

<details>
<summary>B4c — 杂项（~30 个文件）</summary>

- `test_client.py`
- `test_client_e2e.py`
- `test_client_langfuse_metadata.py`
- `test_client_live.py`
- `test_client_message_serialization.py`
- `test_gateway_config_freshness.py`
- `test_gateway_docs_toggle.py`
- `test_gateway_lifespan_shutdown.py`
- `test_gateway_run_recovery.py`
- `test_gateway_runtime_cleanup.py`
- `test_gateway_services.py`
- `test_serialization.py`
- `test_serialize_message_content.py`
- `test_json_compat.py`
- `test_sse_format.py`
- `test_stream_bridge.py`
- `test_template.py`
- `test_template_edge_cases.py`
- `test_error_codes.py`
- `test_stress_concurrent.py`
- `test_concurrent_updates.py`
- `test_doctor.py`
- `test_detect_blocking_io_static.py`
- `test_detect_thread_boundaries.py`
- `test_harness_boundary.py`
- `test_fault_zeroing_visual_outputs.py`
- `test_validate_fault_zeroing_outputs.py`
- `test_install_fault_zeroing_agent.py`
- `test_security_scanner.py`
- `test_local_skill_storage_write.py`
- `test_logging_level_from_config.py`
- `test_infoquest_client.py`
- `test_start_local_script.py`
- `test_intranet_deploy_scripts.py`
- `test_local_backend.py`
- `test_docker_sandbox_mode_detection.py`
- `test_condition_step.py`
- `test_loop_step.py`
- `test_parallel_step.py`
- `test_human_step.py`
- `test_retry_step.py`
- `test_retry_step_gaps.py`
- `test_guardrails.py`
- `test_message_bus.py`
- `test_path_utils.py`
- `test_user_context.py`
- `test_utils_time.py`
- `test_utils_time_coverage.py`
- `test_prompt_coverage.py`
- `test_reflection_resolvers.py`
- `test_timeout_mechanisms.py`
- `test_title_generation.py`
- `test_assistants_compat_full.py`
- `test_assistants_compat_router.py`
- `test_audit_logs_router.py`
- `test_cancel_run_idempotent.py`
- `test_check_script.py`
- `test_file_operation_lock.py`
- `test_feedback.py`
- `test_feedback_persistence.py`
- `test_feedback_router_coverage.py`
- `test_feedback_router_e2e.py`
- `test_suggestions_router.py`
- `test_suggestions_router_e2e.py`
- `test_token_usage.py`
- `test_token_usage_config.py`
- `test_thread_token_usage.py`
- `test_provisioner_kubeconfig.py`
- `test_provisioner_pvc_volumes.py`
</details>

---

### B5: 后端子目录

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B5a** | Blocking IO 回归 | 3 | `make test-blocking-io` |
| **B5b** | QA 子目录 | 3 | `uv run pytest tests/qa/ -v` |

<details>
<summary>B5a — blocking_io/（3 个文件）</summary>

- `blocking_io/test_gate_smoke.py`
- `blocking_io/test_skills_load.py`
- `blocking_io/test_sqlite_lifespan.py`
</details>

<details>
<summary>B5b — qa/（3 个文件）</summary>

- `qa/test_api_qa.py`
- `qa/test_api_qa_multitole.py`
- `qa/test_sse_streaming.py`
</details>

---

### B6: 前端单元测试

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B6a** | `core/` — 领域逻辑 | 118 | `pnpm vitest run tests/unit/core` |
| **B6b** | `components/ai-elements/` | 30 | `pnpm vitest run tests/unit/components/ai-elements` |
| **B6c** | `components/ui/` | 42 | `pnpm vitest run tests/unit/components/ui` |
| **B6d** | `components/workspace/` | 74 | `pnpm vitest run tests/unit/components/workspace` |
| **B6e** | `components/landing/` | 17 | `pnpm vitest run tests/unit/components/landing` |
| **B6f** | `app/` — 页面级 | 52 | `pnpm vitest run tests/unit/app` |
| **B6g** | 根级 (hooks/lib/mdx) | 7 | `pnpm vitest run tests/unit/hooks tests/unit/lib tests/unit/content tests/unit/mdx-components.test.tsx` |

<details>
<summary>B6a — core/（118 个文件）</summary>

- `core/admin/api.test.ts`
- `core/agents/api.test.ts`, `core/agents/hooks.test.ts`, `core/agents/index.test.ts`
- `core/api/api-client.test.ts`, `core/api/errors.test.ts`, `core/api/feedback.test.ts`, `core/api/fetcher.test.ts`, `core/api/stream-mode.test.ts`
- `core/artifacts-utils.test.ts`
- `core/artifacts/fault-tree.test.ts`, `core/artifacts/hooks.test.ts`, `core/artifacts/loader.test.ts`, `core/artifacts/preview.test.ts`, `core/artifacts/utils.test.ts`
- `core/audit-logs/api.test.ts`
- `core/auth/AuthProvider.test.tsx`, `core/auth/gateway-config.test.ts`, `core/auth/proxy-policy.test.ts`, `core/auth/server-extra.test.ts`, `core/auth/server.test.ts`, `core/auth/static-user.test.ts`, `core/auth/types.test.ts`
- `core/blog/index.test.ts`
- `core/clipboard.test.ts`
- `core/config/index.test.ts`
- `core/fault-tree-visualization.test.ts`
- `core/i18n/context.test.tsx`, `core/i18n/cookies-extra.test.ts`, `core/i18n/cookies.test.ts`, `core/i18n/hooks.test.tsx`, `core/i18n/keys.test.ts`, `core/i18n/locale-extra.test.ts`, `core/i18n/locale.test.ts`, `core/i18n/server.test.ts`, `core/i18n/translations.test.ts`
- `core/i18n/locales/en-US-comprehensive.test.ts`, `core/i18n/locales/en-US.test.ts`, `core/i18n/locales/zh-CN.test.ts`
- `core/mcp/api.test.ts`, `core/mcp/hooks.test.ts`, `core/mcp/index.test.ts`
- `core/memory/api.test.ts`, `core/memory/hooks.test.ts`, `core/memory/index.test.ts`
- `core/messages/usage-model.test.ts`, `core/messages/usage.test.ts`, `core/messages/utils-extra.test.ts`, `core/messages/utils.test.ts`
- `core/models/api.test.ts`, `core/models/hooks.test.ts`, `core/models/index.test.ts`
- `core/notification/hooks-extra.test.ts`, `core/notification/hooks.test.ts`
- `core/reasoning-trigger.test.ts`
- `core/rehype/index.test.ts`
- `core/settings/hooks.test.ts`, `core/settings/local.test.ts`, `core/settings/store-extra.test.ts`, `core/settings/store.test.ts`
- `core/skills/api.test.ts`, `core/skills/hooks.test.ts`, `core/skills/index.test.ts`
- `core/static-mode.test.ts`
- `core/streamdown/plugins.test.ts`
- `core/tasks/context.test.tsx`, `core/tasks/index.test.ts`, `core/tasks/subtask-result.test.ts`
- `core/threads/api.test.ts`, `core/threads/export.test.ts`, `core/threads/hooks.test.ts`, `core/threads/message-merge.test.ts`, `core/threads/static-demo.test.ts`, `core/threads/token-usage.test.ts`, `core/threads/utils.test.ts`
- `core/todos/index.test.ts`
- `core/tools/api.test.ts`, `core/tools/index.test.ts`, `core/tools/utils.test.ts`
- `core/uploads/api.test.ts`, `core/uploads/file-validation.test.ts`, `core/uploads/hooks.test.ts`, `core/uploads/index.test.ts`, `core/uploads/prompt-input-files.test.ts`
- `core/utils/datetime.test.ts`, `core/utils/files.test.ts`, `core/utils/json-extra.test.ts`, `core/utils/json.test.ts`, `core/utils/markdown.test.ts`
- `core/visibility-applications/api.test.ts`
- `core/workflows/api.test.ts`, `core/workflows/hooks.test.ts`, `core/workflows/index.test.ts`, `core/workflows/validate.test.ts`
</details>

<details>
<summary>B6b — components/ai-elements/（30 个文件）</summary>

- `artifact.test.tsx`, `canvas.test.tsx`, `chain-of-thought.test.tsx`, `checkpoint.test.tsx`, `code-block.test.tsx`, `connection.test.tsx`, `context.test.tsx`, `controls.test.tsx`, `conversation-scroll-button.test.tsx`, `conversation.test.tsx`, `edge-helpers.test.tsx`, `edge.test.tsx`, `image.test.tsx`, `loader.test.tsx`, `message.test.tsx`, `model-selector.test.tsx`, `node.test.tsx`, `open-in-chat.test.tsx`, `panel.test.tsx`, `plan.test.tsx`, `prompt-input.test.tsx`, `queue.test.tsx`, `reasoning.test.tsx`, `shimmer.test.tsx`, `sources.test.tsx`, `suggestion.test.tsx`, `task.test.tsx`, `toolbar.test.tsx`, `web-preview.test.tsx`, `xyflow-wrappers.test.tsx`
</details>

<details>
<summary>B6c — components/ui/（42 个文件）</summary>

- `alert.test.tsx`, `aurora-text.test.tsx`, `avatar.test.tsx`, `badge.test.tsx`, `breadcrumb.test.tsx`, `button-group.test.tsx`, `button.test.tsx`, `card.test.tsx`, `carousel.test.tsx`, `collapsible.test.tsx`, `command.test.tsx`, `confetti-button.test.tsx`, `dialog.test.tsx`, `dropdown-menu.test.tsx`, `empty.test.tsx`, `flickering-grid.test.tsx`, `hover-card.test.tsx`, `input-group.test.tsx`, `input.test.tsx`, `item.test.tsx`, `label.test.tsx`, `magic-bento.test.tsx`, `number-ticker.test.tsx`, `progress.test.tsx`, `resizable.test.tsx`, `scroll-area.test.tsx`, `select.test.tsx`, `separator.test.tsx`, `sheet.test.tsx`, `shine-border.test.tsx`, `sidebar.test.tsx`, `skeleton.test.tsx`, `sonner.test.tsx`, `spotlight-card.test.tsx`, `switch.test.tsx`, `tabs.test.tsx`, `terminal.test.tsx`, `textarea.test.tsx`, `toggle-group.test.tsx`, `toggle.test.tsx`, `tooltip.test.tsx`, `word-rotate.test.tsx`
</details>

<details>
<summary>B6d — components/workspace/（74 个文件）</summary>

- `agent-welcome.test.tsx`
- `agents/agent-card.test.tsx`, `agents/agent-gallery-enhanced.test.tsx`, `agents/agent-gallery.test.tsx`
- `artifacts/artifact-file-detail.test.tsx`, `artifacts/artifact-file-list.test.tsx`, `artifacts/artifact-trigger.test.tsx`, `artifacts/artifacts-context.test.tsx`, `artifacts/context.test.tsx`, `artifacts/fault-tree-viewer.test.tsx`
- `chats/chat-box.test.tsx`, `chats/use-chat-mode.test.ts`, `chats/use-thread-chat.test.ts`
- `citations/artifact-link.test.tsx`, `citations/citation-link.test.tsx`
- `code-editor.test.tsx`, `command-palette.test.tsx`, `copy-button.test.tsx`, `export-trigger.test.tsx`, `flip-display.test.tsx`, `github-icon.test.tsx`, `input-box.test.tsx`
- `messages/context.test.ts`, `messages/markdown-content.test.tsx`, `messages/message-group.test.tsx`, `messages/message-helpers.test.ts`, `messages/message-list-item.test.tsx`, `messages/message-list.test.tsx`, `messages/message-token-usage.test.tsx`, `messages/skeleton.test.tsx`, `messages/subtask-card.test.tsx`
- `mode-hover-guide.test.tsx`, `overscroll.test.tsx`, `recent-chat-list.test.tsx`
- `settings/about-content.test.ts`, `settings/about-settings-page.test.tsx`, `settings/account-settings-page.test.tsx`, `settings/appearance-settings-page.test.tsx`, `settings/memory-settings-page.test.tsx`, `settings/notification-settings-page.test.tsx`, `settings/settings-dialog.test.tsx`, `settings/settings-section.test.tsx`, `settings/skill-editor.test.tsx`, `settings/skill-settings-page.test.tsx`, `settings/tool-settings-page.test.tsx`
- `streaming-indicator.test.tsx`, `thread-title.test.tsx`, `todo-list.test.tsx`, `token-usage-indicator.test.tsx`, `tooltip.test.tsx`, `welcome.test.tsx`
- `workflows/workflow-card.test.tsx`, `workflows/workflow-gallery.test.tsx`
- `workspace-breadcrumb.test.tsx`, `workspace-container.test.tsx`, `workspace-header.test.tsx`, `workspace-nav-chat-list.test.tsx`, `workspace-nav-menu.test.tsx`, `workspace-sidebar.test.tsx`
</details>

<details>
<summary>B6e — components/landing/（17 个文件）</summary>

- `case-study-section.test.tsx`, `community-section.test.tsx`, `footer.test.tsx`, `header.test.tsx`, `hero.test.tsx`, `post-list.test.tsx`, `progressive-skills-animation.test.tsx`, `sandbox-section.test.tsx`, `section.test.tsx`, `skills-section.test.tsx`, `whats-new-section.test.tsx`
- `sections/case-study-section.test.tsx`, `sections/community-section.test.tsx`, `sections/sandbox-section.test.tsx`, `sections/skills-section.test.tsx`, `sections/whats-new-section.test.tsx`
- `query-client-provider.test.tsx`, `theme-provider.test.tsx`
</details>

<details>
<summary>B6f — app/（52 个文件）</summary>

- `layout.test.tsx`, `page.test.tsx`
- `(auth)/layout.test.tsx`, `(auth)/login/page.test.tsx`, `(auth)/setup/page.test.tsx`
- `[lang]/docs/[[...mdxPath]]/page.test.tsx`, `[lang]/docs/layout.test.tsx`
- `api/memory/[...path]/route.test.ts`, `api/memory/route.test.ts`
- `blog/[[...mdxPath]]/page.test.tsx`, `blog/layout.test.tsx`, `blog/posts/page.test.tsx`, `blog/tags/[tag]/page.test.tsx`
- `mock/api/route.test.ts`, `mock/api/threads/[thread_id]/artifacts/[[...artifact_path]]/route.test.ts`, `mock/api/threads/[thread_id]/history/route.test.ts`, `mock/api/threads/search/route.test.ts`
- `workspace/page.test.tsx`, `workspace/layout.test.tsx`, `workspace/workspace-content.test.tsx`
- `workspace/admin/departments/page.test.tsx`, `workspace/admin/page.test.tsx`, `workspace/admin/tools/page.test.tsx`, `workspace/admin/users/page.test.tsx`, `workspace/admin/visibility-applications/page.test.tsx`
- `workspace/agents/page.test.tsx`, `workspace/agents/gallery-page.test.tsx`, `workspace/agents/new-page.test.tsx`, `workspace/agents/new/page.test.tsx`, `workspace/agents/[agent_name]/page.test.tsx`, `workspace/agents/[agent_name]/edit/page.test.tsx`
- `workspace/agents/[agent_name]/chats/[thread_id]/layout.test.tsx`, `workspace/agents/[agent_name]/chats/[thread_id]/page.test.tsx`
- `workspace/chats/page.test.tsx`, `workspace/chats/providers.test.tsx`, `workspace/chats/thread-page.test.tsx`, `workspace/chats/[thread_id]/layout.test.tsx`, `workspace/chats/[thread_id]/page.test.tsx`, `workspace/chats/[thread_id]/providers.test.tsx`
- `workspace/workflows/page.test.tsx`, `workspace/workflows/gallery-page.test.tsx`, `workspace/workflows/new/page.test.tsx`, `workspace/workflows/[workflow_name]/page.test.tsx`, `workspace/workflows/[workflow_name]/edit/page.test.tsx`
</details>

<details>
<summary>B6g — 根级（7 个文件）</summary>

- `content/meta.test.ts`
- `hooks/use-global-shortcuts.test.ts`, `hooks/use-mobile.test.ts`
- `lib/ime.test.ts`, `lib/utils.test.ts`
- `mdx-components.test.ts`
</details>

---

### B7: 前端 E2E 测试

| 批次 | 模块 | 文件数 | 运行命令 |
|------|------|--------|---------|
| **B7a** | 核心 E2E | 14 | `npx playwright test tests/e2e --project=chromium` |
| **B7b** | QA E2E | 11 | `npx playwright test tests/e2e/qa --project=chromium` |
| **B7c** | Stagehand | 3 | `npx playwright test tests/e2e/stagehand --project=chromium` |
| **B7d** | Visual + A11y | 4 | `npx playwright test tests/e2e/visual --project=visual && npx playwright test tests/e2e/a11y --project=a11y` |

<details>
<summary>B7a — 核心 E2E（14 个文件）</summary>

- `admin-management.spec.ts`
- `agent-chat.spec.ts`
- `agent-management.spec.ts`
- `artifact-preview.spec.ts`
- `artifact-visualization.spec.ts`
- `brand-and-offline.spec.ts`
- `chat.spec.ts`
- `chat-thread-init-ordering.spec.ts`
- `landing.spec.ts`
- `sidebar.spec.ts`
- `skill-management.spec.ts`
- `thread-history.spec.ts`
- `workflow-management.spec.ts`
</details>

<details>
<summary>B7b — QA E2E（11 个文件）</summary>

- `qa/admin-panel.spec.ts`
- `qa/agent-management.spec.ts`
- `qa/auth-flow.spec.ts`
- `qa/chat-flow.spec.ts`
- `qa/file-upload.spec.ts`
- `qa/memory-management.spec.ts`
- `qa/sandbox-management.spec.ts`
- `qa/smoke-landing.spec.ts`
- `qa/smoke-login.spec.ts`
- `qa/visual-screenshot.spec.ts`
- `qa/workflow-management.spec.ts`
</details>

<details>
<summary>B7c — Stagehand（3 个文件）</summary>

- `stagehand/admin-flows.spec.ts`
- `stagehand/chat-interactions.spec.ts`
- `stagehand/workflow-builder.spec.ts`
</details>

<details>
<summary>B7d — Visual + A11y（4 个文件）</summary>

- `visual/landing.visual.spec.ts`
- `visual/login.visual.spec.ts`
- `visual/workspace-layout.visual.spec.ts`
- `a11y/accessibility.spec.ts`
</details>

---

## 三、待办清单

### B1: 后端基础层（3/3）

- [x] **B1a** — 存储/Persistence（15 个文件）
- [x] **B1b** — Config/Admin/启动（15 个文件）
- [x] **B1c** — Auth/用户权限（18 个文件）

### B2: 后端核心层（4/4）

- [x] **B2a** — Threads/Runs/Workflows（30 个文件）
- [x] **B2b** — Memory（22 个文件）
- [x] **B2c** — Middleware（24 个文件）
- [x] **B2d** — LLM/Providers（22 个文件）

### B3: 后端功能层（6/6）

- [x] **B3a** — Agents/Subagents（25 个文件）
- [x] **B3b** — Tools/Skills（~35 个文件）
- [x] **B3c** — MCP（9 个文件）
- [ ] **B3d** — 渠道集成（17 个文件）
- [ ] **B3e** — Sandbox（25 个文件）
- [ ] **B3f** — Artifacts/Uploads（10 个文件）

### B4: 后端补丁 + 杂项（3/3）

- [ ] **B4a** — 覆盖率补丁集（~35 个文件）
- [ ] **B4b** — 权限/隔离（~10 个文件）
- [ ] **B4c** — 杂项（~30 个文件）

### B5: 后端子目录（2/2）— 可与 B4 并行

- [ ] **B5a** — Blocking IO 回归（3 个文件）
- [ ] **B5b** — QA 子目录（3 个文件）

### B6: 前端单元测试（7/7）— 可与 B4/B5 并行

- [ ] **B6a** — core/ 领域逻辑（118 个文件）
- [ ] **B6b** — components/ai-elements（30 个文件）
- [ ] **B6c** — components/ui（42 个文件）
- [ ] **B6d** — components/workspace（74 个文件）
- [ ] **B6e** — components/landing（17 个文件）
- [ ] **B6f** — app/ 页面级（52 个文件）
- [ ] **B6g** — 根级 hooks/lib/mdx（7 个文件）

### B7: 前端 E2E（4/4）— 最后执行

- [ ] **B7a** — 核心 E2E（14 个文件）
- [ ] **B7b** — QA E2E（11 个文件）
- [ ] **B7c** — Stagehand（3 个文件）
- [ ] **B7d** — Visual + A11y（4 个文件）

---

## 四、运行说明

### 环境准备

```bash
# 后端
cd backend
uv sync  # 确保依赖已安装

# 前端
cd frontend
pnpm install
```

### 常用命令速查

| 命令 | 用途 |
|------|------|
| `cd backend && make test` | 后端全部测试 |
| `cd backend && make test-parallel` | 后端并行测试（跳 QA/IO/LLM/serial） |
| `cd backend && make test-coverage` | 后端覆盖率 |
| `cd backend && make test-blocking-io` | 后端 Blocking IO 回归 |
| `cd frontend && pnpm test` | 前端单元测试 |
| `cd frontend && pnpm test:e2e` | 前端 E2E 全部 |
| `cd frontend && pnpm test:e2e:auth` | 前端 E2E 认证专用 |

### 并行加速技巧

```bash
# 后端 - 用 pytest-split 分成 N 份并行运行
cd backend
uv run pytest tests/ --splits 4 --group 1  # 运行第 1/4 份
uv run pytest tests/ --splits 4 --group 2  # 运行第 2/4 份（另一个终端）
uv run pytest tests/ --splits 4 --group 3  # 运行第 3/4 份
uv run pytest tests/ --splits 4 --group 4  # 运行第 4/4 份

# 后端 - 用 xdist 自动并行
cd backend
uv run pytest tests/ -n auto  # 自动使用所有 CPU core
```

### CI 触发条件

| Workflow | 触发条件 |
|----------|----------|
| `backend-unit-tests.yml` | `backend/**` 变更 |
| `backend-qa-tests.yml` | `backend/**` 变更 + PR |
| `backend-blocking-io-tests.yml` | `backend/**` 变更 + PR |
| `frontend-unit-tests.yml` | `frontend/**` 变更 |
| `e2e-tests.yml` | `frontend/**` 变更 + 手动 |
| `lint-check.yml` | 任意变更 |
| `migration-tests.yml` | `backend/**` 变更 + PR |
| `qa-api-tests.yml` | 手动触发 |
