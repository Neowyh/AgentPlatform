# Local Runtime test matrix

The matrix maps the M7 Device and Protocol Security groups to concrete test
files. Tests are intentionally separated from the existing Resource tests so a
Device can never be accidentally covered as a Resource.

## Device control-plane tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| Device key registration and owner binding | `backend/tests/unit/device_control/test_devices.py` | Public key is stored; owner is required; private key never crosses the API |
| Lifecycle transitions | `backend/tests/unit/device_control/test_devices.py` | PENDING → ONLINE/OFFLINE and REVOKED/BLOCKED/OUTDATED guards are deterministic |
| Pairing code and URL | `backend/tests/unit/device_control/test_pairing.py` | Code is random, expires, single-use, and returns no permanent token |
| Browser confirmation | `backend/tests/integration/api/test_device_pairing.py` | Owner succeeds; non-owner and unauthenticated users receive explicit rejection |
| Duplicate/expired pairing | `backend/tests/unit/device_control/test_pairing.py` | Replay and expiry are terminal and do not bind a second user/device |
| Admin list/status/revoke | `backend/tests/integration/api/test_devices_router.py` | Authorized admin sees status/capabilities and revoke fences reconnection |
| Heartbeat and last_seen | `backend/tests/unit/device_control/test_lifecycle.py` | Heartbeat updates last_seen only for the current authenticated session |
| Device is not a Resource | `backend/tests/contracts/test_device_resource_boundary.py` | No Device enum/API/permission is accepted by Resource handlers |
| Demonstration gate | `backend/tests/integration/api/test_device_lifecycle_e2e.py` | install → pair → online → disconnect → offline → revoke → denied reconnect |

## Protocol security tests

| Scenario | Test file | Required assertion |
| --- | --- | --- |
| Outbound-only WSS handshake | `backend/tests/unit/device_control/test_broker.py` | Device initiates; server has no device-dial path |
| Envelope schema and message families | `backend/tests/unit/device_control/test_protocol.py` | All M7 message types validate and unknown critical types fail closed |
| Signed echo task lifecycle | `backend/tests/integration/api/test_device_broker_e2e.py` | task → ack → progress → result produces structured receipt |
| Cancel and timeout | `backend/tests/unit/device_control/test_tasks.py` | Cancel is idempotent; expiry becomes DEVICE_OFFLINE when delivery is impossible |
| Replay protection | `backend/tests/unit/device_control/test_protocol_security.py` | Duplicate task IDs and expired envelopes are rejected |
| Tamper protection | `backend/tests/unit/device_control/test_protocol_security.py` | Signature/hash changes are rejected before echo execution |
| Session binding | `backend/tests/unit/device_control/test_protocol_security.py` | Envelope from another session is rejected |
| Version negotiation | `backend/tests/unit/device_control/test_protocol.py` | Critical mismatch BLOCKED; compatible old runtime OUTDATED |
| Local DENY precedence | `local-runtime/tests/test_policy.py` | Local DENY wins over server ALLOW and yields a receipt/rejection |
| Local receipt shape | `local-runtime/tests/test_receipts.py` | Receipt binds task/run IDs, policy decision, status, and hashes |

## Required lanes

The implementation lane is the backend standard lane plus the local-runtime
tests. Before handoff, run `bash scripts/run-test-lane.sh pr-standard`; this
ticket changes authentication, persistence, and a new control-plane boundary.
The protected high-risk path should select Real E2E in CI.
