# Local Runtime implementation inventory

This inventory records the current code seams used by the M7 implementation.
Paths and symbols below are implemented on the M7 branch.

| Concern | Current location | Symbol / evidence | M7 use |
| --- | --- | --- | --- |
| Gateway application lifecycle | `backend/app/gateway/app.py` | `_configure_extensions`, `create_app`, router includes around the `app.include_router` block | Register device routes and broker lifecycle without changing the harness |
| Route authentication | `backend/app/gateway/authz.py` | `AuthContext`, `get_auth_context`, `require_auth`, `require_permission`, `get_current_rbac_user` | Browser/admin identity and owner checks |
| RBAC users | `backend/app/agentplatform/rbac_models.py` | `UserModel`, `UserRole`, shared `Base` | Foreign key for device ownership and admin actions |
| Persistence engine | `backend/packages/harness/deerflow/persistence/` | `Base`, `get_session_factory`, migration environment | Device tables and indexes |
| Resource boundary | `backend/app/agentplatform/resource_models.py` | `ResourceType` and `Resource` check constraints | Explicitly keep `device` out of Resource APIs and enums |
| Resource HTTP API | `backend/app/gateway/routers/resources.py` | resource request models and route handlers | Negative boundary tests: device operations must not be resource operations |
| Audit trail | `backend/app/agentplatform/audit_model.py` and `backend/app/gateway/routers/audit_logs.py` | `AuditLog`, audit route models | Pair, revoke, block, and task security events |
| Tool assembly | `backend/app/agentplatform/tools/assembly.py` | `ToolSet`, `assemble_tools` | Apply server authorization and registered device capabilities before model exposure |
| Extension contract | `backend/packages/extension-api/deerflow_extension_api/contracts.py` | `RunEvidenceEnvelope`, `TaskInfo`, `TaskOutcome`, `ExtensionService`, `ExtensionRegistry` | Additive integration point for receipts and runtime services |
| Evidence implementation | `backend/packages/agentplatform-extension/agentplatform_extension/evidence.py` | `RunEvidenceBinding`, `build_run_evidence_envelope` | Attach local execution receipts to the canonical run evidence |
| Workflow evidence | `backend/app/agentplatform/workflows/v2/store.py` and `backend/app/workflow_worker.py` | `_canonical_run_evidence`, `_workflow_run_evidence_context` | Preserve run ownership and receipt lineage |
| Existing run cancellation | `backend/app/gateway/routers/thread_runs.py`, `backend/app/gateway/routers/runs.py` | run lifecycle request/response models and handlers | Parent semantics for local task cancel/expiry |
| Extension loading | `backend/packages/harness/deerflow/extensions/` and `backend/app/gateway/app.py` | extension loader plus `_configure_extensions` | Keep Local Runtime integration outside harness patches |
| Device control plane | `backend/app/device_control/` | `models.py`, `pairing.py`, `protocol.py`, `broker.py`, `service.py` | Pairing, owner confirmation, sessions, signed broker, and lifecycle |
| Device HTTP API | `backend/app/gateway/routers/devices.py` | pairing, register/complete, lifecycle, task, and WebSocket routes | Browser and runtime control plane boundary |
| Device persistence | `backend/app/agentplatform/persistence/migrations/versions/20260909_device_control_plane.py` | device, pairing, and session tables | Durable ownership and one-time claims |
| Device artifact intake | `backend/app/device_control/artifacts.py` | `DeviceArtifactStore`, `ArtifactUploadGrant` | Session/task-bound single-use grants, streaming size/hash checks, and atomic workspace handles |
| Local Runtime client | `local-runtime/core/transport.py` | `LocalRuntimeClient` | Outbound WebSocket HELLO, capability updates, signed echo/file execution, and hash-bound consent round trips |
| Allowed-root file store | `local-runtime/core/files.py` | `RootConfig`, `LocalFileStore` | Logical `/root` paths, link rejection, verified directory-handle operations, atomic writes, and safe errors |
| Local Python executor | `local-runtime/core/python.py` | `PythonExecutor`, `LocalPythonService` | Isolated interpreter, stream redaction/rate limits, incremental log hashes, process-group cleanup, and artifact reads |
| Local consent persistence | `local-runtime/core/consent.py` | `ConsentStore(db_path=...)` | SQLite-backed one-time approvals and auditable actor/time/hash decisions across restart |
| Local secret store | `local-runtime/core/secrets.py` | `SecretStore`, `WindowsCredentialStore`, `InMemorySecretStore`, `create_default_secret_store` | OS-backed (Windows Credential Manager) device-local credential storage behind a replaceable backend; values never leave the device |
| Device identity key storage | `local-runtime/core/tray.py`, `local-runtime/core/settings.py` | `_load_or_create_key`, `RuntimeSettings.device_key_ref` | Uses the OS secure store on Windows and migrates legacy key files only after a successful secure write; restricted file fallback is retained for non-Windows development |
| Secret references and injection | `local-runtime/core/secrets.py` | `SecretResolver`, `ResolvedSecrets`, `is_secret_ref` | `local:<name>` references in task payloads and MCP configs resolve locally to process environments only; literal values in secret slots are rejected |
| Secret redaction gate | `local-runtime/core/python.py`, `local-runtime/core/secrets.py` | `_StreamingRedactor`, `SecretRedactor` | Stream output, bounded previews, and receipts are scrubbed against resolved values; split-across-chunk values are held back until safe to emit |
| Local administration CLI | `local-runtime/core/cli.py` | `ideer-local-runtime` | Configure logical root, set capability policy, list pending/audited decisions, approve or deny by hash, and write/rotate/delete/list local secrets |
| Tray and pairing entry point | `local-runtime/core/tray.py`, `local-runtime/core/cli.py` | `TrayApplication`, `TrayController`, `pair-start`, `pair-complete` | Native status/settings/audit surface; owner-confirmed pairing persists the server session identity and stores claim/session credentials by secure-store reference |
| Local artifact staging | `local-runtime/core/artifacts.py` | `FileArtifactUploader`, `SingleUseUploadGrant` | Durable hash-addressed handles with bounded, idempotent, traversal-safe writes and run/task/thread-bound one-time grants |
| Local MCP host | `local-runtime/core/mcp.py` | `MCPSupervisor`, `LocalMCPService` | stdio/localhost MCP lifecycle, fault isolation, `local.mcp.<server>.<tool>` projection, and result redaction against resolved credentials |
| MCP model-side projection | `backend/packages/agentplatform-extension/agentplatform_extension/local_runtime/tools.py` | `assemble_local_tools`, `is_local_mcp_capability`, `LocalToolExecutor` | Projected MCP tools pass the same six-factor trim, frozen-route dispatch, and receipt chain as the static local tools |
| Production Agent MCP assembly | `backend/app/agentplatform/runtime_adapter.py`, `backend/app/gateway/canonical_agent_run_preparation.py` | `build_canonical_agent_factory`, `prepare_canonical_agent_run` | Converts the frozen run authorization and device route into executable LangChain tools; model receives capability names and schemas, never a device selector |
| Authenticated MCP capability registry | `backend/app/device_control/broker.py`, `backend/app/gateway/routers/devices.py`, `backend/app/gateway/run_preparation.py` | `DeviceConnection.tool_descriptors`, `_bind_local_runtime_context` | Binds online status, owner, capabilities, schema descriptors, and schema hashes from the signed device session before Agent assembly; request context cannot forge device facts |
| Session invalidation and re-pair gate | `backend/app/device_control/broker.py`, `backend/app/gateway/routers/devices.py`, `local-runtime/core/transport.py`, `local-runtime/core/tray.py` | `DeviceBroker.invalidate`, `RePairRequired`, `TrayController._supervise` | Owner disconnect/revoke closes active sockets and fails pending tasks; rejected or expired sessions stop reconnecting and require pairing again |
| Runtime configuration application | `local-runtime/core/tray.py` | `TrayController.save_settings`, `_rebuild_file_services`, `set_mcp_config_path` | First/last root and MCP config changes update live services and publish the new signed capability/policy state |
| Local Runtime protocol | `local-runtime/core/protocol.py` | envelope signing and verification | Wire-compatible signed messages |
| Test helpers | `backend/tests/conftest.py`, `backend/tests/_gateway_e2e_env.py`, `backend/tests/_router_auth_helpers.py` | database, app, and authenticated-client fixtures | Device and protocol test setup |

The M7 implementation keeps the control plane outside
`backend/packages/harness/deerflow/`. The only shared harness changes are the
test-lane hardening recorded in [PATCH_LEDGER.md](PATCH_LEDGER.md).

## Reusable behavior

- User identity and route authorization already have a fail-closed provider
  path in `authz.py`; device owner checks should compose with it.
- Resource versions and run snapshots demonstrate immutable, hash-addressed
  evidence. Local receipts should follow the same content-hash and parent-run
  approach rather than adding a second audit source.
- `assemble_tools` is deliberately pure and immutable. Capability filtering
  belongs before it, so unauthorized device actions are absent from the model's
  tool list rather than rejected only after model selection.
- The extension API is additive by design: optional fields and default protocol
  methods preserve compatibility for existing extensions.
