# Local Runtime security model

The server authorizes delegation; the device authorizes execution. These are
separate decisions and both must succeed.

## Two-layer authorization

| Decision | Server control plane | Device Local Runtime |
| --- | --- | --- |
| Who is acting? | Authenticated AgentPlatform user and bound Device public key | Authenticated device session and local operator context |
| What is requested? | Run/tool-call identity, task type, payload hash, target device identity | Exact task payload, local capability, allowed roots, consent level |
| Allow condition | User may delegate, Device is owned/active, capability is registered, session is current | Capability is locally enabled, roots/policy match, consent is present when required |
| Deny rule | Missing/expired/revoked identity or authorization rejects delivery | Local DENY always wins, even when the server allowed delegation |
| Evidence | Audit event and server-side task state | Local execution receipt with policy, consent, status, and hashes |

The effective capability is the intersection of agent declaration, caller
authorization, registered device capability, Local Policy, and platform policy.
Filtering occurs before model tool assembly. The model receives no hidden or
unauthorized device capability.

## Required security controls

- Device keys are generated on the device; the server stores only the public
  key and key metadata. Permanent plaintext device tokens are never returned.
- Pairing codes are random, short-lived, single-use, owner-scoped, and consumed
  atomically. Browser confirmation requires the authenticated owner; an
  arbitrary logged-in user cannot confirm another user's device.
- WSS sessions are initiated by the device. The server maintains a registry but
  never dials a user device.
- Each task envelope has a unique task ID, protocol version, issued time,
  `expires_at`, session ID, payload hash, and signature. The receiver rejects
  duplicate IDs, expired envelopes, session mismatches, invalid signatures, and
  hash mismatches before execution.
- Revoke and block are checked on every handshake and task transition. An
  already-open session is closed or fenced when the identity changes state.
- Protocol incompatibility is explicit: a critical mismatch becomes BLOCKED;
  an older but understood runtime becomes OUTDATED and cannot receive tasks
  until its compatibility policy permits it.
- Task cancellation is idempotent and propagates to the device. Offline tasks
  carry an expiry and become `DEVICE_OFFLINE` after the delivery deadline.
- Only the harmless echo task is used by the M7 gate. No system command or
  arbitrary shell execution is part of this ticket.

## Threat register

| Threat | Control | Observable rejection/evidence |
| --- | --- | --- |
| Pairing code guessing | High-entropy code, expiry, attempts/rate limit, single use | `PAIRING_INVALID` / audit event |
| Non-owner confirmation | Authenticated owner comparison | `PAIRING_NOT_OWNER` |
| Pairing replay | Atomic consume and terminal session state | `PAIRING_ALREADY_USED` |
| Stolen/revoked device key | State check on handshake and session fencing | `DEVICE_REVOKED` |
| Session hijack | Device-key proof plus session binding and WSS transport | `SESSION_MISMATCH` |
| Task replay | Seen task IDs scoped to device/session and expiry | `TASK_REPLAYED` |
| Task tampering | Signature verification and payload hash | `TASK_SIGNATURE_INVALID` / `TASK_HASH_MISMATCH` |
| Cross-session delivery | Envelope session ID must equal active session | `SESSION_MISMATCH` |
| Server overreach | Local policy and consent gate before execution | `LOCAL_POLICY_DENIED` |
| Capability drift | Versioned capability registration and intersection at assembly | Capability omission / receipt |
| Offline ambiguity | `expires_at` plus explicit `DEVICE_OFFLINE` state | Task terminal state |
