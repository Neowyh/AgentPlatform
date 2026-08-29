# Gap Spec — Scenario Binding Deep Module (supplement to #2/#6, not overlapping)

> audience: developers, maintainers
> status: ready-for-agent — gap supplement, does not duplicate #2–#7 feature scope
> parent: Neowyh/AgentPlatform#2 (static binding epic), complements #6
> created: 2026-08-29
> scope: architecture deepening only — no bundling, no freeze, no config content

---

## Problem Statement

The feature behavior for Scenario Tab / Agent Pill / Task Chip / Selected Task is already specified in #2 and #6 (selection, clearing, template injection, Chinese labels, Agent-filtered skill discovery, submission with single skill). The gap is architectural: the current implementation spreads one domain concept across seven shallow modules with duplicated registries and interfaces. Understanding one selection requires bouncing between `types`, `config`, `hooks`, `prompt-templates`, three cloned bars, and page-level coercion. Template, tags, and submit context diverge after a Task Chip click, and skill identity is dropped after `onInjectPrompt`. Tests cover pure leaves but not the composition where bugs hide, so fixing keyboard or template races requires patching multiple places.

## Solution

Deepen the existing behavior behind a single Scenario Binding module whose interface is the only seam callers and tests need to learn. The module owns the single registry, the invariant `pill.scenarioId === scenario`, the binding `{Agent, single Skill, prompt, tags}`, and the shared `ChipBar` keyboard logic. Existing feature contracts (#4 submission with single `skill_name`, #5 static 43-chip inventory, #6 visible interactions) remain unchanged; this spec only changes how the same contracts are implemented and tested, and removes two dead modules. Database-backed configuration, admin UI, cache, audit, and scenario-scoped visibility remain out of scope per #2.

## User Stories

1. As a developer, I want one Scenario Binding module to own Scenario Tab / Agent Pill / Task Chip selection, so that I change one label or icon in one place.
2. As a developer, I want the registry to be a single source with derived `ScenarioId` and `SCENARIO_IDS`, so that adding a Scenario Tab cannot drift from its type.
3. As a developer, I want pill and chip labels to use `labelKey` (not Chinese literals mixed with i18n), so that Agent display names align with Pill labels without duplication.
4. As a developer, I want `togglePill` to auto-correct the Scenario Tab when the pill belongs to another tab, so that no invalid `pill.scenarioId !== scenario` combination is observable.
5. As a developer, I want `selectedScenario` to be non-nullable with `initialScenario = creative` and non-cancellable (clicking the active tab is a no-op), so that the welcome page never renders an empty pill area per the chosen product invariant.
6. As a developer, I want selecting a Task Chip to yield `{skillName, promptTemplate}` together, so that skill identity is not discarded after prompt injection.
7. As a developer, I want the module to expose `activeBinding {agentSlug, agentName, skillName | null, promptTemplate | null, tags}` as the single submission source, so that Task selection travels structurally to the runtime contract.
8. As a developer, I want the module to derive both tags (Agent Pill tag + Selected Task tag whose text equals the Skill display name) in one place, so that pages do not re-derive labels.
9. As a developer, I want template queue, tag, and submit context to share one state machine `idle | pending | confirming` inside the module, so that toggling the same Task Chip twice does not leave a stale template.
10. As a developer, I want a single `ChipBar<T>` with `useRovingTabIndex` to replace the three cloned bars, so that keyboard and a11y fixes apply once.
11. As a developer, I want the exclusive `ScenarioCascadeBar` to remain the sole orchestrator and the dead `FeatureChipBar` and `AgentOrSkillBar` removed, so that two competing layouts do not coexist.
12. As a developer, I want old `useScenarioSelection` / `getPillsByScenario` / `getTemplateForChip` retained as thin deprecated adapters to the new module for one release, so that existing tests stay green during migration.
13. As a tester, I want the module interface to be the test surface, so that interaction tests cover selection → tags → binding without mocking leaves, and `two adapters (new + old) justify the seam`.

## Implementation Decisions

- **Module and seam**: Introduce one deep module — Scenario Binding — with seam at `useScenarioBinding()` return shape. Existing seams atChipBar, selectors, and prompt helpers become internal implementation; highest seam is the hook, ideal count is one. Two adapters (new interface + thin legacy wrappers) justify the seam for one release.
- **Registry single source**: Scenario Tab, Agent Pill, Task Chip inventory remains static, version-controlled, frontend-owned per #2. Single registry object holds `id, labelKey, iconName, agentPills {agentSlug, labelKey, chips {taskId, labelKey, skillName, promptTemplate}}`. Derived types and ID lists are computed, not duplicated. Chinese literals are removed; Pill display name derives from `labelKey`.
- **Variant inventory alignment**: The eight code-development Task Chips per #5 are the canonical visible set (`grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `code-review`, `improve-codebase-architecture`, `diagnosing-bugs`, `srs-writing`); only eight shortcuts are visible while the code-development Agent closure retains its full 26-skill set per #2 — this spec does not change that inventory.
- **Binding shape**: Task Chip binding is single Skill. Module exposes `activeBinding.skillName` singular (nullable) and `promptTemplate` together; `tags` includes Agent Pill tag and, when present, Selected Task tag with `text == Skill display name`. Submission mapping to #4 `skill_name` singular remains unchanged; array form is not introduced in this gap.
- **Invariants (Q4/Q6)**: `selectedScenario` is non-nullable, initial `creative`, non-cancellable. `togglePill` auto-switches Scenario Tab on mismatch. `selectScenario` with same id is a no-op and never clears to null. `toggleChip` validates membership in `selectedPill.chips`.
- **ChipBar convergence (Q5)**: Unified `ChipBar<T>` with `variant: pill | chip` and extracted `useRovingTabIndex` for ArrowLeft/Right/Home/End handling. Exclusive cascade (pill xor chip) is retained; parallel layout is removed with its dead modules.
- **State co-location (Q7)**: Dual tags, pending template, and confirm branching are co-located behind the seam with explicit `idle | pending | confirming` handling for deselect symmetry; highlight is via forwarded ref, not DOM query.
- **Legacy adapters (Q8)**: Deprecated wrappers re-export old names for one release; deletion is a follow-up ticket.

## Testing Decisions

- Only test externally observable behavior through the new seam; do not test internal registry layout or ChipBar internals beyond the seam.
- Cover via the existing welcome cascade E2E seam but driving it through the new module: selection, cross-Scenario clearing (now auto-correct), template injection, re-click deselect symmetry, and Tag text == Skill name.
- Add unit tests at the module interface level for invariant enforcement, single-source derivation, and `activeBinding` mapping for Agent-only vs Agent+Task.
- Verify that two adapters (new hook + legacy wrappers) produce identical observable behavior.
- Reuse #6 submission contract tests for Agent-only / Agent+Task / unselected paths; this gap only adds the upstream binding correctness that feeds them.

## Out of Scope

- Bundled resource inventory and Matt skill import (#3) — already specified.
- Run snapshot freezing and closure validation (#4) — already specified, single-skill contract unchanged.
- Static entry content and Agent closure alignment (#5) — already specified, eight-chip set unchanged.
- Database-backed binding, admin CRUD, audit, cache invalidation, live editing, scenario-scoped visibility filtering — explicitly out per #2, deferred.
- Offline package verification and full E2E offline suite (#7) — already specified.
- Guaranteed tool invocation for a selected Skill — out per #2.

## Further Notes

- This gap spec contradicts the earlier draft `docs/plans/2026-08-28-scenario-binding-agent-skill-prd.md` sections that proposed DB + admin + 30s cache + `skill_names[]` array and 22+2+1 inventory; those sections are superseded by #2 static-config decision and #3 56+15+1 inventory. Deferred parts are intentionally not carried into this gap.
- Implementation is a refactor tracer-bullet: no new user-visible feature beyond #6, but deepens for leverage (one interface, N callers) and locality (one place to fix cascade bugs).
- Depends on #5 config shape and #6 interaction expectations; does not block #3/#4.

