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

## Required lanes

The implementation lane is the backend standard lane plus the local-runtime
tests. Before handoff, run `bash scripts/run-test-lane.sh pr-standard`; this
ticket changes authentication, persistence, and a new control-plane boundary.
The protected high-risk path should select Real E2E in CI.

本地直接运行 Local Runtime 测试时，工作目录必须是 `local-runtime/`，并显式加入
模块路径：`cd local-runtime && PYTHONPATH=. python3 -m pytest tests -q`。从仓库根目录
调用隔离环境的 pytest 会因为未安装 pytest 或无法导入 `core` 而产生误报；这属于
测试入口问题，不代表 Local Runtime 实现失败。
