---
status: accepted
---

# Fault-zeroing uses hybrid intake and one shared execution kernel

Every new fault-zeroing Run uses Hybrid Evidence Intake and the same Workflow-backed Fault-zeroing Execution Kernel, whether invoked through a Skill, Expert, or Workflow. The platform expects documentary evidence and a Code Evidence Package: one missing side requires a durable user confirmation before work starts, while both missing sides reject the request. This supersedes ADR-0003's selectable document, code, and hybrid modes so the three invocation forms do not drift into separate analysis implementations.

## Consequences

A non-empty problem description or document-type attachment satisfies the documentary side. Missing material remains explicit in the coverage matrix and residual risks but does not by itself prohibit a confirmed finding; evidence strength still controls Finding Confidence. Skill and Expert invocations route actual analyses through the shared execution kernel, while conceptual questions and limited editing remain ordinary Agent interactions. Each Run pins an immutable Fault-zeroing Result Contract version, and only Artifacts that pass that contract may complete; a disclosed pending-verification result is valid completion. Existing completed Runs remain readable, while queued or paused legacy-mode Runs must pass Hybrid Evidence Intake before continuing or terminate explicitly. Legacy fault-zeroing installation and standalone Workflow seeding paths are removed in the implementation that adopts this decision rather than retained as compatibility adapters.

## Implementation status (2026-09-29)

Adopted and wired end to end; the acceptance items below are pinned by tests rather than promised by prose.

- All three invocation entries are wired to the kernel: contract-declared workflow launches route through the kernel's canonical creation path (hybrid intake before any model execution, RBAC via the existing gateway chain), chat entries promote real analyses through the `start_zeroing_run` / `confirm_zeroing_run` / `check_zeroing_run` tools in the fault-zeroing closure, and the engine mounts the declared Result Contract gate while completion judgment is unified through the kernel (kernel contract events land in the run's event log).
- The chat inline end-to-end five-artifact mode is removed — a behavior change: chat no longer produces the five artifacts inline. Skill and Expert texts follow the bisection rule (Q&A and limited edits stay conversation; a real analysis promotes into a formal Run whose artifacts bridge back into the thread).
- Evidence-side judgment follows the glossary in code: a non-empty problem description or any document attachment satisfies the documentary side, the Code Evidence Package is the code side, `evidence_mode` is a derived system result (always `hybrid` for a run that continues) and is no longer a user-supplied input, and the problem description participates in the input snapshot hash.
- A contract violation is a `failed` terminal state with the violation list recorded on the run and the artifacts preserved for inspection; a fully disclosed pending-verification result remains a valid completion.
- The "three entries, one kernel" promise is fixed by an integration test: the same evidence started from the Skill, Expert, and Workflow entries produces identical intake decision, pinned contract version, kernel contract judgment, and five-artifact set.

## Revision record

- 2026-09-29: implementation-status revision. Records the landed three-entry wiring, the removal of the chat inline five-artifact mode (behavior change), the code alignment of evidence-side judgment with the glossary, the failed-terminal semantics for contract violations, and the equivalence acceptance test. The non-canonical workflow agent adapter is removed so no second node-execution implementation survives; the deprecated fault-zeroing subagent declarations never existed in the tracked configuration (they live only in untracked local config files), and the generic custom-subagent mechanism stays for its own live consumers.
