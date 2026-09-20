# M7 patch ledger

The M7 control plane does not modify the shared harness package.

| Change | Reason | Scope | Validation |
| --- | --- | --- | --- |
| `7ae6b5907 fix(testing): make backend and smoke lanes hermetic` | Prevent the backend lane and frontend smoke lane from depending on pre-existing runtime state; create required sandbox paths before Uvicorn starts | Test harness and lane scripts only | Backend standard lane and frontend smoke lane passed before M7 implementation |
| `fix(subagents): preserve runtime overrides during managed-store lookup` | Prevent `list_subagents()` from losing a caller-provided global timeout/max-turns override when resolving the default managed-subagent store reloads AppConfig | `backend/packages/harness/deerflow/subagents/registry.py` | Timeout/config regression tests and backend-standard lane passed |

Device control-plane code remains under `backend/app/device_control/`, its
router and migration, and `local-runtime/`. Future edits to shared harness code
must add a row here before implementation.

M8 local file and Python hardening remains outside the shared harness. The
runtime changes use only local-runtime seams and the existing broker protocol;
no new harness patch is required.

M9 local secrets (OS store, `local:` references, redaction gate) also remains
inside `local-runtime/` plus its tests; the broker protocol is unchanged and no
harness patch is required.

M9 `local.mcp.*` model-side integration lives in `local-runtime/core/mcp.py`,
the `agentplatform-extension` local_runtime tools, and their tests; the harness
package is untouched and no harness patch is required.

M9 production closure adds the tray/pairing CLI, secure session references,
policy-hash capability updates, HTTP MCP session-header replay, Windows Job
Object handle correction, and the canonical Agent assembly seam. These edits
remain outside `backend/packages/harness/deerflow/`; the only shared test
surface change is the bounded frontend lane (`--no-file-parallelism`) and the
independent `local-runtime` lane.

The shared extension notifier also now stops immediately when one hook consumes
the shared timeout budget. This preserves the existing timeout contract by
preventing later extensions from starting after the budget has expired; it is
covered by `tests/test_extension_task_lifecycle.py`.

M9 security closure also binds production local-tool assembly to the signed
broker connection. Device online state, owner, announced capabilities, MCP
descriptions, and schema hashes now come from the authenticated websocket;
request context cannot forge them, and unannounced `local.*` operations are
rejected before dispatch.

M9 session invalidation now closes live broker sockets and marks pending tasks
offline when an owner disconnects or revokes a device. The tray treats server
close codes for revoked or superseded sessions as `pairing_required` and stops
automatic reconnects, preventing an expired credential from dialing forever.

M9 configuration closure now creates file/Python services when the first root
is added, removes them when the last root is removed, and swaps the MCP
supervisor when its config path changes; active sessions receive the resulting
capability update immediately.

M9 Streamable HTTP handling validates the negotiated protocol version, preserves
`Mcp-Session-Id` across requests, and clears an invalid session without
replaying the failed request. Regression tests cover JSON responses and session
expiry without replaying a side-effecting call.

On Windows, the device signing key now uses the same Credential Manager seam as
session credentials. A legacy adjacent key file is migrated only after the
secure write succeeds; Linux development keeps the restricted file fallback.
