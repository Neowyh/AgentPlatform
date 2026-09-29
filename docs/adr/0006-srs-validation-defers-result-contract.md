---
status: accepted
---

# SRS output validation defers a platform-level Result Contract

The srs-writing Skill generates GJB438C-2021 software requirement specifications and traceability matrices from a task book. The Fault-zeroing Result Contract defines the platform ideal for output validation: versioned, deterministic rules enforced by the platform at analysis checkpoints and before Run completion, with "Skill text as the validator" named an anti-pattern. The srs-writing Skill does not yet meet that shape, and this ADR records why closing the gap now is deferred rather than built into this round.

## Decision

This round keeps validation inside the srs-writing Skill as the floor. The validator ships as part of the Skill package — provisioned through the Bundled resource seed, so the script stays reachable at the Skill's mount path — and grades errors and warnings, applies requirement-quality rules, and isolates its working state per task book. SKILL.md makes running the validator a mandatory instruction of the review stage, probes officecli availability before generation, and runs a visual self-check on generated documents; the interactive confirmation stage collects per-requirement decisions through structured confirmation cards, and the installer requests minimal permissions. A platform-level SRS Result Contract — the platform enforcing a versioned contract before Run completion, as the Fault-zeroing Result Contract does — is deferred and registered as a backlog initiative pointing to this ADR.

## Trade-offs

The current interactive flow reaches final delivery only through per-item user confirmation, and the shipped validator keeps its rules versioned and evolvable with the Skill package, so the exposure of not enforcing at the platform level today is limited. Platform enforcement, by contrast, extends the Run lifecycle and backend code, and first requires deciding where Run completion is judged and what the enforced artifact semantics are; building it now would couple this Skill round to an unrelated platform change that deserves its own initiative.

## Re-evaluation triggers

Revisit this decision when any of the following becomes true:

- An SRS Run starts non-interactively, through a scheduler or a channel, so the user confirmation gate is unavailable.
- Validation rules must stay strongly consistent across Skill versions, for example a military-standard delivery audit that requires a pinned contract version.
- Same-kind Skills multiply to the point where one validator per Skill becomes duplicated maintenance.
- A real incident delivers output that the validator never ran against.
