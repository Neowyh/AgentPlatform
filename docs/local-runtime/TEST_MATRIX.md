# Local Runtime test matrix

The matrix maps the M7 Device and Protocol Security groups to concrete test
files. Tests are intentionally separated from the existing Resource tests so a
Device can never be accidentally covered as a Resource.

## Device control-plane tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| Device key registration and owner binding | `backend/tests/unit/device_control/test_service.py` | Public key is stored; owner is required; private key never crosses the API |
| Lifecycle transitions | `backend/tests/unit/device_control/test_service.py` | PENDING → ONLINE/OFFLINE and REVOKED/BLOCKED/OUTDATED guards are deterministic |
| Pairing code and URL | `backend/tests/unit/device_control/test_pairing.py`, `backend/tests/integration/api/test_devices_router.py` | Code is random, expires, and registration returns a short-lived claim rather than a session |
| Browser confirmation | `backend/tests/unit/device_control/test_service.py`, `backend/tests/integration/api/test_devices_router.py`, `frontend/tests/unit/core/devices/api.test.ts` | Only the owner confirms; completion requires the confirmed claim |
| Duplicate/expired pairing | `backend/tests/unit/device_control/test_pairing.py`, `backend/tests/unit/device_control/test_service.py` | Replay and expiry are terminal and do not bind a second user/device |
| Admin list/status/revoke | `backend/tests/integration/api/test_devices_router.py` | Authorized admin sees status/capabilities and revoke fences reconnection |
| Heartbeat and last_seen | `backend/tests/unit/device_control/test_service.py`, `backend/tests/integration/api/test_devices_router.py` | Heartbeat updates last_seen only for the current authenticated session |
| Device is not a Resource | `backend/tests/unit/device_control/test_service.py` | Device operations remain in the device router and model boundary |
| Demonstration gate | `backend/tests/integration/api/test_devices_router.py` | pair → confirm → complete → online → disconnect → offline → revoke → denied reconnect |

## Protocol security tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| Outbound-only WSS handshake | `backend/tests/unit/device_control/test_broker.py` | Device initiates; server has no device-dial path |
| Envelope schema and message families | `backend/tests/unit/device_control/test_protocol.py` | All M7 message types validate and unknown critical types fail closed |
| Signed echo task lifecycle | `backend/tests/integration/api/test_devices_router.py` | task → ack → progress → result produces structured receipt |
| Real Local Runtime service gate | `backend/tests/integration/api/test_devices_router.py` | Temporary uvicorn service and `LocalRuntimeClient` complete an echo task |
| Cancel and timeout | `backend/tests/unit/device_control/test_tasks.py` | Cancel is idempotent; expiry becomes DEVICE_OFFLINE when delivery is impossible |
| Replay protection | `backend/tests/unit/device_control/test_protocol_security.py` | Duplicate task IDs and expired envelopes are rejected |
| Tamper protection | `backend/tests/unit/device_control/test_protocol_security.py` | Signature/hash changes are rejected before echo execution |
| Session binding | `backend/tests/unit/device_control/test_protocol_security.py` | Envelope from another session is rejected |
| Version negotiation | `backend/tests/unit/device_control/test_protocol.py` | Critical mismatch BLOCKED; compatible old runtime OUTDATED |
| Local DENY precedence | `local-runtime/tests/test_policy.py` | Local DENY wins over server ALLOW and yields a receipt/rejection |
| Local receipt shape | `local-runtime/tests/test_receipts.py` | Receipt binds task/run IDs, policy decision, status, and hashes |
| Root link and handle safety | `local-runtime/tests/test_files.py` | In-root symlink/junctions are rejected; reads and writes use a verified directory handle |
| Streaming output safety | `local-runtime/tests/test_python.py` | Split credentials are redacted, previews are bounded, and hashes are computed incrementally |
| Consent cancellation race | `local-runtime/tests/test_transport.py` | Cancellation removes pending consent and late approval cannot revive the task |
| Consent restart/replay | `local-runtime/tests/test_consent.py` | SQLite audit survives restart while approvals remain one-time and payload-bound |
| Artifact upload grant binding | `local-runtime/tests/test_python.py` | Upload grant is bound to run/task/thread/name and cannot be replayed |
| Server artifact intake | `backend/tests/unit/device_control/test_artifacts.py` | Streaming upload enforces grant expiry, size/hash limits, traversal safety, and one-time consumption |
| Local receipt to Run Evidence | `backend/tests/test_local_runtime_extension.py` | Local tool executor forwards device receipts into the active run evidence binding |
| Revocation/offline recheck | `backend/tests/test_local_runtime_extension.py` | Frozen routes revalidate the six-factor authorization before dispatch and refuse revoked/offline capabilities |
| Run authorization snapshot | `backend/tests/test_local_runtime_extension.py` | Run identity, device, policy version and six-factor intersection are frozen; child snapshots can only narrow |
| Broker snapshot enforcement | `backend/tests/unit/device_control/test_broker.py` | Broker rejects a task when its frozen device or effective capability snapshot no longer matches |
| Broker receipt evidence bridge | `backend/tests/unit/device_control/test_broker.py`, `backend/tests/test_local_runtime_extension.py` | Terminal device receipts are forwarded once into the active Run Evidence ledger |

## Local MCP host tests (M9)

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| stdio transport lifecycle | `local-runtime/tests/test_mcp.py` | Newline-delimited JSON-RPC initialize/tools list/tool call run against a real child process |
| localhost HTTP transport | `local-runtime/tests/test_mcp.py` | JSON-RPC over HTTP POST reaches a loopback MCP endpoint and returns structured results |
| Call containment | `local-runtime/tests/test_mcp.py` | Tool timeouts and JSON-RPC errors are structured; the connection stays usable for later calls |
| Config and transport validation | `local-runtime/tests/test_mcp.py` | Specs require consistent transport fields and safe server names; duplicate names are rejected |
| Local network policy | `local-runtime/tests/test_mcp.py` | Loopback is allowed; public internet and unapproved intranet are denied; DNS resolution cannot bypass the policy |
| Lifecycle and restart policy | `local-runtime/tests/test_mcp.py` | Crash restarts back off within the configured budget, then mark the server failed; manual stops never restart |
| Single-server fault isolation | `local-runtime/tests/test_mcp.py` | A crash or in-flight failure on one server never affects another server or the runtime |
| Schema change containment | `local-runtime/tests/test_mcp.py` | `tools/list_changed` refreshes the projection; a failed refresh keeps the last known tools |
| Disabled servers are invisible | `local-runtime/tests/test_mcp.py` | Disabled servers refuse start and project no `local.mcp.*` capabilities |
| Secret reference seam | `local-runtime/tests/test_mcp.py` | `local:<name>` env/header placeholders resolve through the injected resolver; unresolved references fail closed without starting the server |
| Capability projection | `local-runtime/tests/test_mcp.py` | Enabled servers project `local.mcp.<server>.<tool>` capabilities; the runtime publishes them in hello/CAPABILITY_UPDATE and republishes on change |
| MCP consent default | `local-runtime/tests/test_mcp.py` | Projected MCP tools are risk level 1: consent is required unless local policy says otherwise |
| MCP task round trip | `local-runtime/tests/test_mcp.py` | Server task → consent round trip → completed receipt bound to run/task with tool content |
| Broker MCP gate | `backend/tests/integration/api/test_devices_router.py` | Temporary service plus real Local Runtime and real stdio MCP complete a task via the broker with consent and a structured receipt |

## Local secret tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| OS-backed store abstraction | `local-runtime/tests/test_secrets.py` | Memory backend covers set/rotate/delete/list; Windows Credential Manager backend exists behind the same protocol and fails closed on other platforms |
| `local:<name>` reference validity | `local-runtime/tests/test_secrets.py` | Only well-formed references parse; names never expose values |
| Injection seam | `local-runtime/tests/test_secrets.py` | Task payload `secrets` slots resolve references into the process environment only; literal values in secret slots are rejected |
| Redaction gate | `local-runtime/tests/test_secrets.py`, `backend/tests/unit/device_control/test_secrets_gate.py` | Stream output, previews, receipts, and every broker-recorded field are free of plaintext while the script printed it |
| Missing reference / backend down | `local-runtime/tests/test_secrets.py`, `backend/tests/unit/device_control/test_secrets_gate.py` | Structured `SECRET_REF_NOT_FOUND` / `SECRET_BACKEND_UNAVAILABLE` task failure; no plaintext fallback |
| No model-callable secrets capability | `local-runtime/tests/test_secrets.py` | `local.secrets.*` operations are rejected as unsupported |
| Secret CLI surface | `local-runtime/tests/test_secrets.py` | Write/rotate/delete/list work; listing prints names only and no command output contains the value |

## Local MCP integration tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| `local.mcp.*` projection under the six factors | `backend/tests/test_local_runtime_mcp_integration.py` | Projected tools appear in `assemble_local_tools`/`local_tool_names` only when the device announced them and every factor allows; offline projects nothing |
| Disabled/crashed server withdrawal | `backend/tests/test_local_runtime_mcp_integration.py` | Withdrawing the capability name from `device_capabilities` removes the tool from the model list; re-announcing restores it |
| Frozen-route dispatch and receipt recording | `backend/tests/test_local_runtime_mcp_integration.py` | `LocalToolExecutor.invoke` routes `local.mcp.*` through the frozen route, records the receipt (server/tool name, result hash), and never exposes the device id |
| Structured MCP failure semantics | `backend/tests/test_local_runtime_mcp_integration.py` | `MCP_TIMEOUT`, `SERVER_CRASHED`, `TOOL_NOT_FOUND`, and `SECRET_UNAVAILABLE` return distinguishable structured values with their receipts; no fake success |
| Shared caller and Sub-Agent boundaries | `backend/tests/test_local_runtime_mcp_integration.py` | `child_authorization` and `RunAuthorizationSnapshot` narrowing apply to MCP capabilities |
| Authorization matrix (MCP items) | `backend/tests/test_local_runtime_mcp_integration.py` | Unauthorized caller / offline device / policy deny / withdrawn server: tool invisible and invocation rejected before routing |
| MCP secret reference composition | `local-runtime/tests/test_mcp_secrets.py` | `SecretResolver` feeds the supervisor seam; references resolve into the server process env only; missing references fail closed; tool output echoing a resolved value is redacted |

## Required lanes

The implementation lane is the backend standard lane plus the local-runtime
tests. Before handoff, run `bash scripts/run-test-lane.sh pr-standard`; this
ticket changes authentication, persistence, and a new control-plane boundary.
The protected high-risk path should select Real E2E in CI.

本地直接运行 Local Runtime 测试时，工作目录必须是 `local-runtime/`，并显式加入
模块路径：`cd local-runtime && PYTHONPATH=. python3 -m pytest tests -q`。从仓库根目录
调用隔离环境的 pytest 会因为未安装 pytest 或无法导入 `core` 而产生误报；这属于
测试入口问题，不代表 Local Runtime 实现失败。
