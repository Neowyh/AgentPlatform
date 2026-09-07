# Authorization and shared-resource acceptance report

This report records the current evidence for the DeerFlow AuthorizationProvider
boundary and the AgentPlatform caller-scoped extension projection. It is an
open acceptance artifact, not a release sign-off.

| Acceptance | Evidence | Status |
|---|---|---|
| Assembly-time tool filtering | `backend/tests/test_authorization_enforcement.py` and `backend/tests/test_authorization_tool_filter.py`: denied tools are removed before model assembly; fail-closed provider errors remove all tools | passed (15 + 17 focused tests) |
| Runtime forced-call denial | Authorization middleware test sends a denied `bash` tool call directly and verifies the handler is not invoked and returns `authz.denied` | passed |
| Shared Agent caller identity | Tool-filter test verifies an `owner_user_id` hint cannot replace the authenticated caller principal | passed |
| Caller-only credential projection | Extension boundary tests verify owner credential fields never enter the durable authorization projection | passed |
| Caller memory isolation | `AuthorizationContext` rejects owner-scoped memory and projects `memory_scope` to the caller | passed |
| Sandbox authorization | RBAC allow/deny, reused-sandbox recheck, fail-closed provider errors and internal caller role handling are covered | 13 core cases passed; the full file remained incomplete after the upload-router cases produced no output within the guard window |
| End-to-end shared-resource run | Full authenticated shared Agent run with caller credential, memory, and tool permission isolation | open; requires initialized DB/runtime acceptance |

The direct file invocation initially exposed a test-path issue
(`_router_auth_helpers` was not importable); rerunning with `PYTHONPATH=backend/tests`
passed the core cases but still timed out in the upload-router portion. This is
recorded as incomplete rather than a production authorization regression and
must be rerun through the repository's standard test lane.
