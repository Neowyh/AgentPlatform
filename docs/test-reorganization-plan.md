# Backend Test Directory Reorganization Plan

## 1. Current State

The backend test suite contains **377 test files** in a flat `tests/` directory, with only 3 subdirectories:
- `tests/blocking_io/` (3 test files)
- `tests/qa/` (3 test files)
- `tests/factories/` (1 factory file)

This flat structure makes it difficult to:
- Run specific test categories (unit vs integration vs E2E)
- Understand test scope at a glance
- Maintain test isolation and dependencies
- Configure CI pipelines for different test tiers

## 2. Proposed Directory Structure

```
backend/tests/
├── conftest.py                          # Global fixtures and path setup
├── _agent_e2e_helpers.py                # Shared E2E test helpers
├── _router_auth_helpers.py              # Shared router test auth helpers
│
├── factories/                           # Test data factories (existing)
│   ├── __init__.py
│   └── auth.py
│
├── unit/                                # Unit tests (mock dependencies)
│   ├── __init__.py
│   ├── conftest.py                      # Unit-specific fixtures
│   ├── channels/                        # Channel-related unit tests
│   ├── agents/                          # Agent-related unit tests
│   ├── sandbox/                         # Sandbox-related unit tests
│   ├── workflows/                       # Workflow-related unit tests
│   ├── persistence/                     # Persistence-related unit tests
│   ├── middleware/                      # Middleware unit tests
│   ├── providers/                       # LLM provider unit tests
│   ├── tools/                           # Tool unit tests
│   ├── memory/                          # Memory system unit tests
│   ├── auth/                            # Auth unit tests
│   ├── skills/                          # Skills unit tests
│   ├── workers/                         # Worker unit tests
│   ├── config/                          # Config unit tests
│   └── router/                          # Router unit tests (heavy mock)
│
├── integration/                         # Integration tests (real dependencies)
│   ├── __init__.py
│   ├── conftest.py                      # Integration-specific fixtures
│   ├── api/                             # Router integration tests (TestClient)
│   ├── database/                        # Database integration tests (real SQLite)
│   ├── mcp/                             # MCP integration tests
│   └── safety/                          # Safety/graph integration tests
│
├── e2e/                                 # End-to-end tests
│   ├── __init__.py
│   ├── conftest.py                      # E2E-specific fixtures
│   ├── http/                            # HTTP E2E (real FastAPI, fake LLM)
│   ├── live/                            # Live E2E (real LLM, real API)
│   └── docker/                          # Docker E2E (container lifecycle)
│
├── performance/                         # Performance/stress tests
│   ├── __init__.py
│   └── conftest.py
│
├── blocking_io/                         # Blocking IO detection tests (existing)
│   ├── __init__.py
│   ├── conftest.py
│   └── test_*.py
│
└── qa/                                  # QA tests against running server (existing)
    ├── __init__.py
    ├── conftest.py
    └── test_*.py
```

## 3. File Classification and Target Locations

### 3.1 E2E Tests (11 files)

#### e2e/live/ - Real LLM, Real API (3 files)
| Current File | Notes |
|---|---|
| `tests/test_client_live.py` | Live integration with real API, skipped in CI |
| `tests/test_create_ideer_agent_live.py` | Live LLM integration, requires OPENAI_API_KEY |
| `tests/test_deferred_tool_promotion_real_llm.py` | Real LLM E2E, requires ONEAPI_E2E=1 |

#### e2e/http/ - Real FastAPI App, Fake LLM (5 files)
| Current File | Notes |
|---|---|
| `tests/test_runtime_lifecycle_e2e.py` | Full FastAPI app lifecycle, fake LLM |
| `tests/test_setup_agent_http_e2e_real_server.py` | Real HTTP E2E with real auth chain |
| `tests/test_setup_agent_e2e_user_isolation.py` | User isolation E2E with real HTTP stack |
| `tests/test_update_agent_e2e_user_isolation.py` | User isolation E2E with real HTTP stack |
| `tests/test_safety_finish_reason_graph_integration.py` | Real langchain graph integration |

#### e2e/docker/ - Docker Container Tests (6 files)
| Current File | Notes |
|---|---|
| `tests/test_sandbox_orphan_reconciliation_e2e.py` | Docker container lifecycle |
| `tests/test_sandbox_orphan_reconciliation.py` | Docker container reconciliation |
| `tests/test_docker_sandbox_mode_detection.py` | Docker mode detection |
| `tests/test_aio_sandbox_local_backend.py` | Local sandbox backend |
| `tests/test_local_backend.py` | Local backend tests |
| `tests/test_dev_entrypoint.py` | Dev entrypoint tests |

### 3.2 Integration Tests (39 files)

#### integration/api/ - Router Integration (TestClient + mock auth) (15 files)
| Current File | Notes |
|---|---|
| `tests/test_admin_router_e2e.py` | Admin router E2E with TestClient |
| `tests/test_agents_router_e2e.py` | Agents router E2E with TestClient |
| `tests/test_artifacts_router_e2e.py` | Artifacts router E2E |
| `tests/test_auth_router_e2e.py` | Auth router E2E |
| `tests/test_channels_router_e2e.py` | Channels router E2E |
| `tests/test_feedback_router_e2e.py` | Feedback router E2E |
| `tests/test_mcp_config_router_e2e.py` | MCP config router E2E |
| `tests/test_memory_router_e2e.py` | Memory router E2E |
| `tests/test_runs_stateless_router_e2e.py` | Runs router E2E |
| `tests/test_skills_router_e2e.py` | Skills router E2E |
| `tests/test_suggestions_router_e2e.py` | Suggestions router E2E |
| `tests/test_threads_router_e2e.py` | Threads router E2E |
| `tests/test_tools_router_e2e.py` | Tools router E2E |
| `tests/test_uploads_router_e2e.py` | Uploads router E2E |
| `tests/test_workflows_router_e2e.py` | Workflows router E2E |

#### integration/database/ - Real Database Tests (14 files)
| Current File | Notes |
|---|---|
| `tests/test_owner_isolation.py` | Cross-user isolation (real SQLite) |
| `tests/test_user_context.py` | User context with real DB |
| `tests/test_persistence_timezone.py` | DB timezone tests |
| `tests/test_persistence_scaffold.py` | DB scaffold tests |
| `tests/test_migration_user_isolation.py` | Migration isolation |
| `tests/test_memory_storage_user_isolation.py` | Memory storage isolation |
| `tests/test_memory_queue_user_isolation.py` | Memory queue isolation |
| `tests/test_paths_user_isolation.py` | Paths isolation |
| `tests/test_memory_thread_meta_isolation.py` | Thread meta isolation |
| `tests/test_memory_updater_user_isolation.py` | Memory updater isolation |
| `tests/test_async_checkpointer.py` | Async checkpointer with real DB |
| `tests/test_checkpointer.py` | Checkpointer with real DB |
| `tests/test_checkpointer_async_provider.py` | Async provider with real DB |
| `tests/test_run_event_store.py` | Event store with real DB |

#### integration/mcp/ - MCP Integration (3 files)
| Current File | Notes |
|---|---|
| `tests/test_mcp_session_pool.py` | MCP session pool integration |
| `tests/test_deferred_tool_registry_promotion.py` | Tool promotion with real MCP |
| `tests/test_invoke_acp_agent_tool.py` | ACP agent tool invocation |

#### integration/safety/ - Safety/Graph Integration (2 files)
| Current File | Notes |
|---|---|
| `tests/test_safety_finish_reason_graph_integration.py` | Graph integration (already in e2e/http) |
| `tests/test_run_manager.py` | Run manager with mixed real/mock |

### 3.3 Unit Tests (327 files)

#### unit/router/ - Router Unit Tests (30 files)
| Current File | Notes |
|---|---|
| `tests/test_admin_router.py` | Admin router unit tests |
| `tests/test_admin_router_full.py` | Admin router full coverage |
| `tests/test_agents_router.py` | Agents router unit tests |
| `tests/test_agents_router_coverage.py` | Agents router coverage |
| `tests/test_agents_router_coverage2.py` | Agents router coverage boost |
| `tests/test_agents_router_coverage_boost.py` | Agents router coverage boost |
| `tests/test_agents_router_full.py` | Agents router full coverage |
| `tests/test_artifacts_router.py` | Artifacts router unit tests |
| `tests/test_artifacts_router_coverage.py` | Artifacts router coverage |
| `tests/test_auth_router_cov3.py` | Auth router coverage |
| `tests/test_auth_router_coverage.py` | Auth router coverage |
| `tests/test_auth_router_gaps.py` | Auth router gaps |
| `tests/test_feedback_router_coverage.py` | Feedback router coverage |
| `tests/test_memory_router.py` | Memory router unit tests |
| `tests/test_memory_router_coverage.py` | Memory router coverage |
| `tests/test_models_router.py` | Models router unit tests |
| `tests/test_models_router_full.py` | Models router full coverage |
| `tests/test_runs_stateless_router.py` | Runs router unit tests |
| `tests/test_skills_custom_router.py` | Skills custom router |
| `tests/test_skills_router_coverage.py` | Skills router coverage |
| `tests/test_skills_router_full.py` | Skills router full coverage |
| `tests/test_suggestions_router.py` | Suggestions router unit tests |
| `tests/test_thread_runs_coverage.py` | Thread runs coverage |
| `tests/test_thread_runs_router.py` | Thread runs router |
| `tests/test_threads_router.py` | Threads router unit tests |
| `tests/test_threads_router_full.py` | Threads router full coverage |
| `tests/test_tools_router.py` | Tools router unit tests |
| `tests/test_uploads_router.py` | Uploads router unit tests |
| `tests/test_workflow_router.py` | Workflow router unit tests |
| `tests/test_workflows_router.py` | Workflows router unit tests |

#### unit/channels/ - Channel Unit Tests (12 files)
| Current File | Notes |
|---|---|
| `tests/test_channel_base.py` | Channel base class |
| `tests/test_channel_commands.py` | Channel commands |
| `tests/test_channel_file_attachments.py` | File attachments |
| `tests/test_channel_manager.py` | Channel manager |
| `tests/test_channel_manager_coverage.py` | Channel manager coverage |
| `tests/test_channel_service.py` | Channel service |
| `tests/test_channel_store.py` | Channel store |
| `tests/test_channels.py` | Channels |
| `tests/test_channels_coverage.py` | Channels coverage |
| `tests/test_dingtalk_channel.py` | DingTalk channel |
| `tests/test_discord_channel.py` | Discord channel |
| `tests/test_feishu_channel.py` | Feishu channel |
| `tests/test_feishu_parser.py` | Feishu parser |
| `tests/test_slack_channel.py` | Slack channel |
| `tests/test_telegram_channel.py` | Telegram channel |
| `tests/test_wechat_channel.py` | WeChat channel |
| `tests/test_wecom_channel.py` | WeCom channel |

#### unit/agents/ - Agent Unit Tests (12 files)
| Current File | Notes |
|---|---|
| `tests/test_agent_step.py` | Agent step |
| `tests/test_agents_config_coverage.py` | Agents config |
| `tests/test_create_ideer_agent.py` | Agent creation |
| `tests/test_custom_agent.py` | Custom agent |
| `tests/test_lead_agent_coverage.py` | Lead agent coverage |
| `tests/test_lead_agent_model_resolution.py` | Model resolution |
| `tests/test_lead_agent_prompt.py` | Lead agent prompt |
| `tests/test_lead_agent_prompt_extra_coverage.py` | Prompt extra coverage |
| `tests/test_lead_agent_skills.py` | Lead agent skills |
| `tests/test_subagent_executor.py` | Subagent executor |
| `tests/test_subagent_prompt_security.py` | Subagent prompt security |
| `tests/test_subagent_skills_config.py` | Subagent skills config |
| `tests/test_subagent_timeout_config.py` | Subagent timeout config |
| `tests/test_subagent_token_collector.py` | Subagent token collector |

#### unit/sandbox/ - Sandbox Unit Tests (20 files)
| Current File | Notes |
|---|---|
| `tests/test_aio_sandbox.py` | AIO sandbox |
| `tests/test_aio_sandbox_coverage.py` | AIO sandbox coverage |
| `tests/test_aio_sandbox_provider.py` | AIO sandbox provider |
| `tests/test_aio_sandbox_provider_coverage_boost.py` | Provider coverage boost |
| `tests/test_aio_sandbox_readiness.py` | Sandbox readiness |
| `tests/test_coverage_local_sandbox.py` | Local sandbox coverage |
| `tests/test_coverage_local_sandbox_2.py` | Local sandbox coverage 2 |
| `tests/test_coverage_local_sandbox_provider.py` | Local sandbox provider |
| `tests/test_coverage_sandbox_audit_2.py` | Sandbox audit coverage |
| `tests/test_coverage_sandbox_base.py` | Sandbox base coverage |
| `tests/test_coverage_sandbox_middleware_2.py` | Sandbox middleware coverage |
| `tests/test_coverage_sandbox_tools.py` | Sandbox tools coverage |
| `tests/test_local_sandbox_encoding.py` | Local sandbox encoding |
| `tests/test_local_sandbox_provider_mounts.py` | Local sandbox mounts |
| `tests/test_local_sandbox_virtual_path_contract.py` | Virtual path contract |
| `tests/test_remote_sandbox_backend.py` | Remote sandbox backend |
| `tests/test_sandbox_audit_middleware.py` | Sandbox audit middleware |
| `tests/test_sandbox_exceptions.py` | Sandbox exceptions |
| `tests/test_sandbox_middleware.py` | Sandbox middleware |
| `tests/test_sandbox_middleware_coverage.py` | Sandbox middleware coverage |
| `tests/test_sandbox_search_tools.py` | Sandbox search tools |
| `tests/test_sandbox_security.py` | Sandbox security |
| `tests/test_sandbox_security_helpers.py` | Sandbox security helpers |
| `tests/test_sandbox_tools.py` | Sandbox tools |
| `tests/test_sandbox_tools_coverage.py` | Sandbox tools coverage |
| `tests/test_sandbox_tools_security.py` | Sandbox tools security |

#### unit/workflows/ - Workflow Unit Tests (8 files)
| Current File | Notes |
|---|---|
| `tests/test_condition_step.py` | Condition step |
| `tests/test_human_step.py` | Human step |
| `tests/test_loop_step.py` | Loop step |
| `tests/test_parallel_step.py` | Parallel step |
| `tests/test_retry_step.py` | Retry step |
| `tests/test_retry_step_gaps.py` | Retry step gaps |
| `tests/test_schema_parser.py` | Schema parser |
| `tests/test_template.py` | Template |
| `tests/test_template_edge_cases.py` | Template edge cases |
| `tests/test_tool_step.py` | Tool step |
| `tests/test_workflow_executor.py` | Workflow executor |
| `tests/test_workflow_parser_coverage.py` | Workflow parser coverage |
| `tests/test_workflow_steps.py` | Workflow steps |
| `tests/test_workflow_store.py` | Workflow store |
| `tests/test_workflows_coverage.py` | Workflows coverage |

#### unit/middleware/ - Middleware Unit Tests (20 files)
| Current File | Notes |
|---|---|
| `tests/test_clarification_middleware.py` | Clarification middleware |
| `tests/test_csrf_middleware.py` | CSRF middleware |
| `tests/test_dangling_tool_call_middleware.py` | Dangling tool call |
| `tests/test_dynamic_context_middleware.py` | Dynamic context |
| `tests/test_guardrail_middleware.py` | Guardrail middleware |
| `tests/test_llm_error_handling_middleware.py` | LLM error handling |
| `tests/test_llm_error_middleware_cov3.py` | LLM error coverage |
| `tests/test_llm_error_middleware_coverage.py` | LLM error coverage |
| `tests/test_loop_detection_config.py` | Loop detection config |
| `tests/test_loop_detection_middleware.py` | Loop detection middleware |
| `tests/test_middleware_coverage_gaps.py` | Middleware coverage gaps |
| `tests/test_safety_finish_reason_middleware.py` | Safety finish reason |
| `tests/test_safety_termination_detectors.py` | Safety termination |
| `tests/test_summarization_middleware.py` | Summarization middleware |
| `tests/test_thread_data_middleware.py` | Thread data middleware |
| `tests/test_title_middleware_core_logic.py` | Title middleware |
| `tests/test_todo_middleware.py` | Todo middleware |
| `tests/test_token_usage_middleware.py` | Token usage middleware |
| `tests/test_tool_error_handling_middleware.py` | Tool error handling |
| `tests/test_uploads_middleware_core_logic.py` | Uploads middleware |
| `tests/test_view_image_middleware.py` | View image middleware |

#### unit/providers/ - LLM Provider Unit Tests (10 files)
| Current File | Notes |
|---|---|
| `tests/test_claude_provider.py` | Claude provider |
| `tests/test_claude_provider_oauth_billing.py` | Claude OAuth billing |
| `tests/test_claude_provider_prompt_caching.py` | Claude prompt caching |
| `tests/test_codex_provider.py` | Codex provider |
| `tests/test_mindie_provider.py` | MindIE provider |
| `tests/test_openai_codex_provider.py` | OpenAI Codex provider |
| `tests/test_patched_deepseek.py` | Patched DeepSeek |
| `tests/test_patched_minimax.py` | Patched MiniMax |
| `tests/test_patched_openai.py` | Patched OpenAI |
| `tests/test_vllm_provider.py` | vLLM provider |
| `tests/test_providers_base_coverage.py` | Providers base coverage |

#### unit/tools/ - Tool Unit Tests (25 files)
| Current File | Notes |
|---|---|
| `tests/test_code_interpreter.py` | Code interpreter |
| `tests/test_coverage_code_interpreter.py` | Code interpreter coverage |
| `tests/test_coverage_ddg_search.py` | DDG search coverage |
| `tests/test_coverage_list_dir.py` | List dir coverage |
| `tests/test_coverage_search.py` | Search coverage |
| `tests/test_coverage_tools_2.py` | Tools coverage |
| `tests/test_data_analyzer.py` | Data analyzer |
| `tests/test_data_analyzer_tools.py` | Data analyzer tools |
| `tests/test_doc_reader.py` | Doc reader |
| `tests/test_doc_reader_tools.py` | Doc reader tools |
| `tests/test_exa_tools.py` | Exa tools |
| `tests/test_file_conversion.py` | File conversion |
| `tests/test_file_conversion_coverage.py` | File conversion coverage |
| `tests/test_firecrawl_tools.py` | Firecrawl tools |
| `tests/test_image_search_coverage_fix.py` | Image search coverage |
| `tests/test_image_search_tools.py` | Image search tools |
| `tests/test_present_file_tool_core_logic.py` | Present file tool |
| `tests/test_readability.py` | Readability |
| `tests/test_readability_coverage.py` | Readability coverage |
| `tests/test_search_coverage.py` | Search coverage |
| `tests/test_serper_tools.py` | Serper tools |
| `tests/test_task_tool_core_logic.py` | Task tool core logic |
| `tests/test_task_tool_coverage.py` | Task tool coverage |
| `tests/test_task_tool_usage_recorder.py` | Task tool usage recorder |
| `tests/test_tool_args_schema_no_pydantic_warning.py` | Tool args schema |
| `tests/test_tool_deduplication.py` | Tool deduplication |
| `tests/test_tool_output_truncation.py` | Tool output truncation |
| `tests/test_tool_registry.py` | Tool registry |
| `tests/test_tool_search.py` | Tool search |
| `tests/test_tools_coverage.py` | Tools coverage |
| `tests/test_tools_coverage_boost.py` | Tools coverage boost |
| `tests/test_view_image_tool.py` | View image tool |

#### unit/memory/ - Memory System Unit Tests (20 files)
| Current File | Notes |
|---|---|
| `tests/test_memory_modules_coverage.py` | Memory modules coverage |
| `tests/test_memory_prompt_extra_coverage.py` | Memory prompt coverage |
| `tests/test_memory_prompt_injection.py` | Memory prompt injection |
| `tests/test_memory_queue.py` | Memory queue |
| `tests/test_memory_queue_extra_coverage.py` | Memory queue coverage |
| `tests/test_memory_storage.py` | Memory storage |
| `tests/test_memory_storage_coverage.py` | Memory storage coverage |
| `tests/test_memory_storage_extra_coverage.py` | Memory storage extra |
| `tests/test_memory_thread_meta_coverage.py` | Thread meta coverage |
| `tests/test_memory_thread_meta_update_metadata.py` | Thread meta update |
| `tests/test_memory_updater.py` | Memory updater |
| `tests/test_memory_updater_coverage.py` | Memory updater coverage |
| `tests/test_memory_upload_filtering.py` | Memory upload filtering |

#### unit/auth/ - Auth Unit Tests (15 files)
| Current File | Notes |
|---|---|
| `tests/test_auth_config.py` | Auth config |
| `tests/test_auth_errors.py` | Auth errors |
| `tests/test_auth_middleware.py` | Auth middleware |
| `tests/test_auth_repository_sqlite.py` | Auth repository SQLite |
| `tests/test_auth_type_system.py` | Auth type system |
| `tests/test_authz.py` | Authz |
| `tests/test_authz_rbac.py` | Authz RBAC |
| `tests/test_cli_auth_providers.py` | CLI auth providers |
| `tests/test_credential_file.py` | Credential file |
| `tests/test_credential_loader.py` | Credential loader |
| `tests/test_credential_loader_extra_coverage.py` | Credential loader coverage |
| `tests/test_deps_internal_auth_coverage.py` | Internal auth coverage |
| `tests/test_ensure_admin.py` | Ensure admin |
| `tests/test_initialize_admin.py` | Initialize admin |
| `tests/test_internal_auth.py` | Internal auth |
| `tests/test_internal_auth_coverage.py` | Internal auth coverage |
| `tests/test_langgraph_auth.py` | LangGraph auth |
| `tests/test_reset_admin.py` | Reset admin |

#### unit/skills/ - Skills Unit Tests (12 files)
| Current File | Notes |
|---|---|
| `tests/test_skill_manage_tool.py` | Skill manage tool |
| `tests/test_skill_storage.py` | Skill storage |
| `tests/test_skills_archive_root.py` | Skills archive root |
| `tests/test_skills_bundled.py` | Skills bundled |
| `tests/test_skills_installer.py` | Skills installer |
| `tests/test_skills_loader.py` | Skills loader |
| `tests/test_skills_parser.py` | Skills parser |
| `tests/test_skills_validation.py` | Skills validation |

#### unit/workers/ - Worker Unit Tests (6 files)
| Current File | Notes |
|---|---|
| `tests/test_run_worker.py` | Run worker |
| `tests/test_run_worker_rollback.py` | Run worker rollback |
| `tests/test_worker_cov3.py` | Worker coverage |
| `tests/test_worker_coverage.py` | Worker coverage |
| `tests/test_worker_coverage2.py` | Worker coverage 2 |
| `tests/test_worker_langfuse_metadata.py` | Worker Langfuse metadata |

#### unit/config/ - Config Unit Tests (10 files)
| Current File | Notes |
|---|---|
| `tests/test_app_config_coverage.py` | App config coverage |
| `tests/test_app_config_extra_coverage.py` | App config extra coverage |
| `tests/test_app_config_reload.py` | App config reload |
| `tests/test_config_version.py` | Config version |
| `tests/test_extensions_config.py` | Extensions config |
| `tests/test_gateway_config_freshness.py` | Gateway config freshness |
| `tests/test_logging_level_from_config.py` | Logging level |
| `tests/test_model_config.py` | Model config |
| `tests/test_model_factory.py` | Model factory |
| `tests/test_network_mode.py` | Network mode |

#### unit/persistence/ - Persistence Unit Tests (8 files)
| Current File | Notes |
|---|---|
| `tests/test_persistence_engine.py` | Persistence engine |
| `tests/test_persistence_run_sql.py` | Persistence run SQL |
| `tests/test_run_event_store_pagination.py` | Event store pagination |
| `tests/test_run_journal.py` | Run journal |
| `tests/test_run_naming.py` | Run naming |
| `tests/test_run_repository.py` | Run repository |
| `tests/test_store_async_provider.py` | Store async provider |
| `tests/test_store_provider.py` | Store provider |
| `tests/test_store_provider_full.py` | Store provider full |

#### unit/client/ - Client Unit Tests (6 files)
| Current File | Notes |
|---|---|
| `tests/test_client.py` | Client unit tests |
| `tests/test_client_langfuse_metadata.py` | Client Langfuse metadata |
| `tests/test_client_message_serialization.py` | Client message serialization |
| `tests/test_converters.py` | Converters |
| `tests/test_serialization.py` | Serialization |
| `tests/test_serialize_message_content.py` | Serialize message content |

#### unit/misc/ - Miscellaneous Unit Tests (remaining ~100 files)
All remaining unit test files that don't fit neatly into the above categories, including:
- Coverage boost files (`test_coverage_boost*.py`)
- Gateway tests (`test_gateway_*.py`)
- MCP tests (`test_mcp_*.py`)
- Utility tests (`test_utils_*.py`, `test_path_utils.py`)
- Other tests

### 3.4 Performance Tests (2 files)

| Current File | Notes |
|---|---|
| `tests/test_subagent_limit_middleware.py` | Concurrent subagent limits |
| `tests/test_stream_bridge.py` | Stream bridge performance |

### 3.5 Blocking IO Tests (4 files, existing directory)

| Current File | Notes |
|---|---|
| `tests/blocking_io/test_gate_smoke.py` | Blocking IO gate smoke |
| `tests/blocking_io/test_skills_load.py` | Skills load blocking IO |
| `tests/blocking_io/test_sqlite_lifespan.py` | SQLite lifespan blocking IO |
| `tests/test_detect_blocking_io_static.py` | Static blocking IO detection |

### 3.6 QA Tests (4 files, existing directory)

| Current File | Notes |
|---|---|
| `tests/qa/test_api_qa.py` | API QA against running server |
| `tests/qa/test_api_qa_multitole.py` | Multi-role QA |
| `tests/qa/test_sse_streaming.py` | SSE streaming QA |
| `tests/test_channels.py` | Channels (misclassified, should be unit) |

## 4. Import Path Updates Required

### 4.1 Helper Modules

The following helper modules need to be moved or duplicated:

**`tests/_agent_e2e_helpers.py`**
- Used by: `test_runtime_lifecycle_e2e.py`, `test_setup_agent_http_e2e_real_server.py`, `test_setup_agent_e2e_user_isolation.py`, `test_update_agent_e2e_user_isolation.py`, `test_deferred_tool_registry_promotion.py`
- Action: Move to `tests/e2e/http/_agent_e2e_helpers.py` and update imports

**`tests/_router_auth_helpers.py`**
- Used by: 38 router test files (both unit and integration)
- Action: Keep at `tests/_router_auth_helpers.py` (shared across unit and integration)

### 4.2 conftest.py Files

**`tests/conftest.py`** (global)
- Keep at root level, applies to all tests
- Contains: sys.path setup, circular import breaking, shared fixtures

**`tests/blocking_io/conftest.py`**
- Keep as-is

**`tests/qa/conftest.py`**
- Keep as-is

**New conftest.py files needed:**
- `tests/unit/conftest.py` - Unit-specific fixtures
- `tests/integration/conftest.py` - Integration-specific fixtures (real DB setup)
- `tests/e2e/conftest.py` - E2E-specific fixtures
- `tests/performance/conftest.py` - Performance-specific fixtures

### 4.3 Import Updates by Category

#### Router tests moving to `unit/router/`
Files like `test_admin_router.py` that import from `app.gateway.routers.admin` need:
```python
# Before
from app.gateway.routers.admin import router

# After (same, no change needed - sys.path handles this)
from app.gateway.routers.admin import router
```

#### Router E2E tests moving to `integration/api/`
Files like `test_admin_router_e2e.py` that import `_router_auth_helpers` need:
```python
# Before
from _router_auth_helpers import make_authed_test_app

# After
from _router_auth_helpers import make_authed_test_app  # Still works if helpers stay at root
```

#### E2E tests moving to `e2e/http/`
Files like `test_runtime_lifecycle_e2e.py` that import `_agent_e2e_helpers` need:
```python
# Before
from _agent_e2e_helpers import FakeToolCallingModel

# After (if helpers move)
from tests.e2e.http._agent_e2e_helpers import FakeToolCallingModel
# OR keep at root and import remains the same
```

## 5. Execution Plan

### Phase 1: Create Directory Structure (1 hour)
1. Create all new directories:
   ```bash
   mkdir -p tests/unit/{channels,agents,sandbox,workflows,persistence,middleware,providers,tools,memory,auth,skills,workers,config,client,misc,router}
   mkdir -p tests/integration/{api,database,mcp,safety}
   mkdir -p tests/e2e/{http,live,docker}
   mkdir -p tests/performance
   ```

2. Create `__init__.py` files in each directory

3. Create `conftest.py` files for each major directory

### Phase 2: Move Helper Modules (30 minutes)
1. Copy `_agent_e2e_helpers.py` to `tests/e2e/http/`
2. Keep `_router_auth_helpers.py` at `tests/` root (shared)
3. Update imports in affected files

### Phase 3: Move Unit Tests (2-3 hours)
1. Move router unit tests to `tests/unit/router/`
2. Move channel tests to `tests/unit/channels/`
3. Move agent tests to `tests/unit/agents/`
4. Move sandbox tests to `tests/unit/sandbox/`
5. Move workflow tests to `tests/unit/workflows/`
6. Move middleware tests to `tests/unit/middleware/`
7. Move provider tests to `tests/unit/providers/`
8. Move tool tests to `tests/unit/tools/`
9. Move memory tests to `tests/unit/memory/`
10. Move auth tests to `tests/unit/auth/`
11. Move skills tests to `tests/unit/skills/`
12. Move worker tests to `tests/unit/workers/`
13. Move config tests to `tests/unit/config/`
14. Move persistence tests to `tests/unit/persistence/`
15. Move client tests to `tests/unit/client/`
16. Move remaining tests to `tests/unit/misc/`

### Phase 4: Move Integration Tests (1 hour)
1. Move router E2E tests to `tests/integration/api/`
2. Move database isolation tests to `tests/integration/database/`
3. Move MCP integration tests to `tests/integration/mcp/`

### Phase 5: Move E2E Tests (30 minutes)
1. Move live tests to `tests/e2e/live/`
2. Move HTTP E2E tests to `tests/e2e/http/`
3. Move Docker tests to `tests/e2e/docker/`

### Phase 6: Move Performance Tests (15 minutes)
1. Move performance tests to `tests/performance/`

### Phase 7: Update Configuration (30 minutes)
1. Update `pytest.ini` or `pyproject.toml` testpaths
2. Update CI pipeline test commands
3. Update Makefile test targets
4. Verify all imports work correctly

### Phase 8: Verification (1 hour)
1. Run full test suite to verify no breakage
2. Run each category independently
3. Update documentation

## 6. CI Pipeline Updates

### pytest.ini / pyproject.toml
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "e2e_live: End-to-end tests requiring real API keys",
    "e2e_http: End-to-end tests with real HTTP stack",
    "e2e_docker: End-to-end tests requiring Docker",
    "integration: Integration tests with real dependencies",
    "performance: Performance and stress tests",
    "blocking_io: Blocking IO detection tests",
    "qa: QA tests against running server",
]
```

### Makefile Targets
```makefile
test-unit:
	.venv/bin/python -m pytest tests/unit/ -v

test-integration:
	.venv/bin/python -m pytest tests/integration/ -v

test-e2e:
	.venv/bin/python -m pytest tests/e2e/ -v

test-e2e-live:
	.venv/bin/python -m pytest tests/e2e/live/ -v -s

test-performance:
	.venv/bin/python -m pytest tests/performance/ -v

test-qa:
	.venv/bin/python -m pytest tests/qa/ -v -s

test-all:
	.venv/bin/python -m pytest tests/ -v
```

## 7. Benefits

1. **Clear test organization**: Easy to find and understand test scope
2. **Selective execution**: Run only unit tests in development, full suite in CI
3. **Better CI pipelines**: Different stages for different test types
4. **Reduced confusion**: No more guessing if a test needs external services
5. **Easier maintenance**: Related tests grouped together
6. **Better documentation**: Directory structure serves as documentation

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Import path breakage | Use `sys.path` in conftest.py, verify with full test run |
| CI pipeline breakage | Update CI config in same PR, test thoroughly |
| Merge conflicts | Coordinate with team, do reorganization in one PR |
| Lost tests | Use `git mv` to preserve history, verify file count before/after |

## 9. Statistics Summary

| Category | Count | Percentage |
|---|---|---|
| Unit tests | 294 | 78.0% |
| Integration tests | 39 | 10.3% |
| E2E tests | 11 | 2.9% |
| Performance tests | 2 | 0.5% |
| Blocking IO tests | 4 | 1.1% |
| QA tests | 4 | 1.1% |
| Router unit tests | 30 | 8.0% |
| **Total** | **377** | **100%** |

Note: Router unit tests are a subset of unit tests, counted separately for clarity.
