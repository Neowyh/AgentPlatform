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
| Local Runtime client | `local-runtime/core/transport.py` | `LocalRuntimeClient` | Outbound WebSocket HELLO and signed echo execution |
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
