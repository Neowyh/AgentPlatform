---
status: accepted
---

# Code-level vocabulary unifies on "agent"; 专家 survives only as a display word

Upstream deer-flow names the conversational-expert concept "agent" everywhere: `/workspace/agents` routes, `agent-card` / `agent-settings-dialog` / `agent-welcome` components, the `/api/agents` router, and every test and mock. iDeer renamed the user-facing surface to "experts" — `/workspace/capabilities/experts/*` routes, `ExpertList`, expert edit and chat pages — while the backend domain object stayed "agent" (resource type `agent`, agent metadata reconciliation, frozen agent inputs). The rename is skin-deep: routes and component names only.

Each upstream convergence round pays the same tax for this split. Upstream tests hard-code agents paths and get rewritten to experts paths by hand (the v2.1.0 round rewrote `agent-chat.spec.ts` end to end). Upstream improvements to management components we deleted (`agent-welcome`, `agent-settings-dialog`) land as delete/modify conflicts needing manual transplant triage. Every conflict classifier must re-derive the mapping "agents(上游) = experts(本地) = resource type `agent`" before touching a hunk, and a mistake in that mapping is silent breakage, not a test failure.

## Decision

Code and route vocabulary unifies on "agent". Expert-named routes move to agent-named paths (the merged tree keeps `/workspace/agents` reachable through redirects in both directions during transition), components named for the same concept drop the expert prefix, and tests stop rewriting upstream paths. The display word 专家 is a presentation concern: it lives in the `zh-CN` locale strings and nowhere else; the `en-US` locale shows "Agent". The data source does not move — `/api/agents` stays unmounted and `/api/resources` stays the canonical source; this decision renames surfaces, it does not re-open the data-source question settled by Resource Governance V2 (2026-08-14).

## Trade-offs

The unification is a one-time migration of roughly 30-60 files (expert routes, components, unit tests, e2e) plus permanent redirects so existing bookmarks and chat history links keep working, and it concedes the differentiated word in code — 专家 remains visible to users but greps for it stop finding routes. Keeping the split was the alternative: it would preserve today's naming and instead tax every future convergence with rewrites, transplants, and a human-maintained terminology map (CONTEXT.md glossary entry plus a merge-playbook check). That map is still recorded as the transition-period safety net, but the mapping it documents should stop growing once the rename lands.

## Re-evaluation triggers

Revisit this decision when any of the following becomes true:

- Product packaging requires "experts" as a marketed, versioned concept (for example an 专家市场 storefront) strong enough to justify a brand word in code, not only in copy.
- Upstream renames the concept itself, which would reset the mapping cost and warrant a fresh comparison.
- The rename migration stalls past half-done (some routes renamed, some not): a partially applied vocabulary is worse than either consistent form, so the unfinished remainder either completes or reverts within the same convergence round it started in.
