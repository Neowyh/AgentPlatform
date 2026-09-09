# Local Runtime architecture

This document fixes the M7 boundary for the Local Runtime line. It describes the
current AgentPlatform host and the seams where device control-plane code belongs.

## Layers and dependency direction

```text
Browser / administrator
        |
        v
Gateway API (app.gateway) ---- server database / audit log
        |
        +-- Device control plane: identity, pairing, lifecycle, sessions
        |
        +-- Broker: outbound device sessions and signed task envelopes
        |
        v
Extension API / runtime assembly (deerflow_extension_api)
        |
        v
Local Runtime on the user's device
        +-- transport: outbound WSS only
        +-- policy: local DENY can veto server ALLOW
        +-- core: safe, explicitly registered local capabilities
        +-- receipts: immutable execution evidence
```

The dependency direction is server control plane → extension contract → Local
Runtime. The runtime never becomes a second Agent runtime and the server never
opens a connection to a user's device. A Device is a control-plane identity;
it is not a `Resource`, is not included in the resource type enum, and is not
selected or addressed by the model.

The existing application split remains a hard boundary: `app.*` may import
`deerflow.*`, while the harness must not import `app.*`. Device routes and
persistence therefore live under `backend/app/`; reusable extension contracts
live under `backend/packages/extension-api/`.

## Main objects

| Object | Owner | Responsibility | Lifetime |
| --- | --- | --- | --- |
| Device | Control plane | Stable user-bound public-key identity and lifecycle state | Until revoked/deleted |
| Pairing session | Gateway | Short-lived browser confirmation and device credential exchange | Minutes |
| Device session | Broker | Authenticated connection registered by an outbound device connection | Connection |
| Local capability | Device + policy | What this runtime can do, subject to effective authorization | Heartbeat/registration revision |
| Local task | Run/tool call + device | One delegated, bounded operation | Until result, cancel, expiry, or offline |
| Local execution receipt | Runtime/evidence | What ran, policy/consent, status, and hashes | Bound to the parent run |

## Integration seams

- Gateway startup and route mounting are owned by `backend/app/gateway/app.py`.
- Route authentication and authorization are centralized in
  `backend/app/gateway/authz.py`; device routes must use the existing auth
  context and must not invent a parallel user model.
- SQLAlchemy models share `deerflow.persistence.base.Base`, as shown by
  `backend/app/agentplatform/rbac_models.py` and
  `backend/app/agentplatform/resource_models.py`.
- The extension contract already provides `RunEvidenceEnvelope`, task
  lifecycle hooks, runtime dependencies, and an extension registry in
  `backend/packages/extension-api/deerflow_extension_api/contracts.py`.
- Model-visible tools are assembled through the pure
  `backend/app/agentplatform/tools/assembly.py:assemble_tools` seam. Device
  capabilities must be intersected before this seam; the model must only see
  authorized tools.

## Invariants

1. Device identity is public-key based; bearer credentials are short-lived and
   scoped to a pairing or session.
2. Device connections are outbound-only and are rejected unless the device is
   active and the session matches the current identity.
3. Local policy is authoritative at execution time. Local DENY overrides a
   server ALLOW, and consent binds to the exact task content.
4. Every local task belongs to a legitimate Run and Tool Call and produces a
   structured receipt or a structured rejection.
5. Protocol and runtime versions are negotiated before task delivery.
