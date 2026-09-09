# M7 patch ledger

The M7 control plane does not modify the shared harness package.

| Change | Reason | Scope | Validation |
| --- | --- | --- | --- |
| `7ae6b5907 fix(testing): make backend and smoke lanes hermetic` | Prevent the backend lane and frontend smoke lane from depending on pre-existing runtime state; create required sandbox paths before Uvicorn starts | Test harness and lane scripts only | Backend standard lane and frontend smoke lane passed before M7 implementation |

Device control-plane code remains under `backend/app/device_control/`, its
router and migration, and `local-runtime/`. Future edits to shared harness code
must add a row here before implementation.
