# Feature adoption matrix

| Area | Upstream SHA | Current status | Target owner / seam | Evidence | Blocking closure |
|---|---|---|---|---|---|
| Runtime / context | locked `0f7d8709` | Focused foundation slices green; 183 textual `ideer` imports remain | DeerFlow runtime; AgentPlatform extension for enterprise context | Runtime Foundation focused evidence in `BASELINE_REPORT.md` | Migrate control-plane callers and remove production `ideer` imports |
| Memory | locked `0f7d8709` | Pluggable schema and manager contract adopted; legacy migration path present | DeerFlow `MemoryManager`; AgentPlatform caller/agent scope adapter | 18 config/manager tests; migration tests | Prove old-data copy, per-user isolation, agent scope and restart persistence |
| Sub-agents | locked `0f7d8709` | Receipt and delegation contract is green | DeerFlow delegation runtime; AgentPlatform policy/visibility | 270 passed, 1 skipped | Real receipt verification in a complete workflow run |
| Authz | locked `0f7d8709` | Assembly/runtime deny paths and extension caller context are green | DeerFlow AuthorizationProvider + AgentPlatform policy extension | 43 authz tests; 4 extension-boundary tests | Shared-resource caller credential, memory and tool-permission acceptance |
| Skills | locked `0f7d8709` | Enabled-only defaults and mount contract are green | Resource Resolver → DeerFlow managed `/mnt/skills` projection | Focused skill/mount tests | Run-level UUID/version/hash projection and no competing mount |
| Resources / workflows | locked `0f7d8709` | `/api/resources` remains canonical; workflow DB integration incomplete | AgentPlatform control plane; DeerFlow runtime observer | Resource-version focused tests; SRS smoke passes | Snapshot freeze, workflow receipts and initialized DB integration suite |
| Offline / intranet | locked `0f7d8709` | Default-deny network and DeerFlow runtime paths configured | AgentPlatform deployment overlay | 14 network tests; 1 config contract test | Docker Compose/images, bundle build and fresh air-gapped install |
