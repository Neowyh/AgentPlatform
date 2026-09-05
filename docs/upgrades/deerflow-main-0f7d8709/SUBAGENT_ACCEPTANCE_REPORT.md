# Sub-agent and receipt acceptance report

| Acceptance | Evidence | Status |
|---|---|---|
| Missing receipt semantics | Task-tool regression marks completed sub-agents without citations as `UNVERIFIED` | passed |
| Real receipt verification | Cited and validated receipts produce `VERIFIED`; failed paths preserve the failure verdict | passed |
| Durable evidence projection | Tool receipts and sub-agent verification records are collected into the shared Run Evidence Envelope | passed |
| Receipt persistence across worker updates | Workflow snapshot merge preserves the immutable envelope and collected receipts | passed |
| Full workflow receipt acceptance | Initialized database workflow with real sub-agent execution and verifiable receipt | open; database-backed worker acceptance remains incomplete |

Focused receipt middleware, task-tool and projection tests passed (32 tests).
