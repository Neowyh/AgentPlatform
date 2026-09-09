# M7 patch ledger

The M7 control plane does not modify the shared harness package.

| Change | Reason | Scope | Validation |
| --- | --- | --- | --- |
| `7ae6b5907 fix(testing): make backend and smoke lanes hermetic` | Prevent the backend lane and frontend smoke lane from depending on pre-existing runtime state; create required sandbox paths before Uvicorn starts | Test harness and lane scripts only | Backend standard lane and frontend smoke lane passed before M7 implementation |
| `fix(subagents): preserve runtime overrides during managed-store lookup` | Prevent `list_subagents()` from losing a caller-provided global timeout/max-turns override when resolving the default managed-subagent store reloads AppConfig | `backend/packages/harness/deerflow/subagents/registry.py` | Timeout/config regression tests and backend-standard lane passed |

Device control-plane code remains under `backend/app/device_control/`, its
router and migration, and `local-runtime/`. Future edits to shared harness code
must add a row here before implementation.
