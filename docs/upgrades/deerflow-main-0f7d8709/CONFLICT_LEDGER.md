# DeerFlow main conflict ledger

- Probe branch: `probe/deerflow-main-0f7d8709`
- Locked upstream: `0f7d8709d3bbf0be26460b6277fbad9329302243`
- Probe conflicts observed: **515 paths**
- Probe disposition: aborted before resolution; the mechanical merge is now
  represented by `integration/deerflow-main-0f7d8709`.

The original probe produced one mechanically generated row per path, all with
the same unresolved `M/open/TBD` values. This ledger replaces that noise with
the semantic ownership and closure gates used for convergence. The complete
path list remains reproducible with:

```bash
git diff --name-only develop...0f7d8709d3bbf0be26460b6277fbad9329302243
```

## Semantic ledger

| Area / path family | Final classification | Target owner | Acceptance evidence | Close condition | Status |
|---|---|---|---|---|---|
| `backend/packages/harness/deerflow/**`, `backend/src/**` | Upstream runtime | DeerFlow | Runtime focused tests; zero unregistered local patches | Runtime Foundation, authz, skills, memory, sub-agent and persistence slices pass | open |
| `backend/packages/harness/ideer/**` | Temporary compatibility runtime | AgentPlatform control plane during bridge | Import/use inventory; focused regression for each migrated seam | No production `ideer` imports; package removed | open |
| `backend/app/agentplatform/**` and `backend/packages/agentplatform-extension/**` | AgentPlatform enterprise extension | AgentPlatform | Resource snapshot, authorization, audit/provenance and network-policy tests | Extension owns all enterprise-only behavior | open |
| Resource APIs and governance migrations | AgentPlatform product invariant | AgentPlatform control plane | `/api/resources` canonical, UUID/version/hash snapshots, workflow linkage | Resource/Workflow acceptance suite passes | open |
| `config*.yaml`, memory configuration | Semantic merge | DeerFlow schema + AgentPlatform intranet overlay | Config validation, old-data migration, restart persistence | No legacy `storage_path: memory.json` semantics remain | open |
| Skill projection and mounts | Semantic merge | DeerFlow `/mnt/skills` + resolver adapter | Enabled-only projection and mount-isolation test | Exactly one managed `/mnt/skills` projection | open |
| Auth/Authz, MCP, sandbox, community integrations | Upstream runtime with intranet policy | DeerFlow runtime; AgentPlatform policy | Assembly/runtime deny, caller credential boundary, egress checks | Community paths present but invisible/un-callable by default | open |
| Frontend | Semantic merge | AgentPlatform Resource Center + DeerFlow generic UI | `pnpm test`, `pnpm check`, E2E | `/api/resources` remains canonical; no legacy resource source | open |
| Docker, offline package and migration docs | Semantic merge | AgentPlatform delivery layer | Intranet check, offline package, fresh air-gapped install | Bundle installs/runs without network | open |

## Boundary decisions (locked)

1. `/api/resources` is the only canonical enterprise resource API.
2. DeerFlow owns generic Runtime; AgentPlatform owns governance, Workflow,
   intranet policy and business packages.
3. Enterprise behavior crosses the runtime boundary through the extension or
   adapter seam; it is not added to the DeerFlow harness fork.

## Closure record

No row may move to `closed` without naming a report or focused test in the
acceptance-evidence column. The ledger is intentionally still open: this
branch is not eligible for `develop` or release until every row and the final
gates in the implementation plan are closed.
