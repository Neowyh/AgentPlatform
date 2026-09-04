---
status: accepted
---

# Fault-zeroing uses hybrid intake and one shared execution kernel

Every new fault-zeroing Run uses Hybrid Evidence Intake and the same Workflow-backed Fault-zeroing Execution Kernel, whether invoked through a Skill, Expert, or Workflow. The platform expects documentary evidence and a Code Evidence Package: one missing side requires a durable user confirmation before work starts, while both missing sides reject the request. This supersedes ADR-0003's selectable document, code, and hybrid modes so the three invocation forms do not drift into separate analysis implementations.

## Consequences

A non-empty problem description or document-type attachment satisfies the documentary side. Missing material remains explicit in the coverage matrix and residual risks but does not by itself prohibit a confirmed finding; evidence strength still controls Finding Confidence. Skill and Expert invocations route actual analyses through the shared execution kernel, while conceptual questions and limited editing remain ordinary Agent interactions. Each Run pins an immutable Fault-zeroing Result Contract version, and only Artifacts that pass that contract may complete; a disclosed pending-verification result is valid completion. Existing completed Runs remain readable, while queued or paused legacy-mode Runs must pass Hybrid Evidence Intake before continuing or terminate explicitly. Legacy fault-zeroing installation and standalone Workflow seeding paths are removed in the implementation that adopts this decision rather than retained as compatibility adapters.
