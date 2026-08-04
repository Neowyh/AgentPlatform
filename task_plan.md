# Fault-Zeroing Workflow Gap Closure

## Goal

Implement the simplified 2026-08-03 closure plan: remove diagnostics, align agent documentation with the fork/join DAG, add optional per-agent-action filesystem scopes, apply least privilege to all nine fault-zeroing nodes, cover the real durable worker path, run the three existing cases without expected-analysis inputs or validator, and close documentation only after acceptance and the single final full-test phase.

## Phases

- [completed] 1. Restore context, revise the source plan, audit existing dirty changes, and complete required GitNexus impact checks.
- [completed] 2. Remove adapter/debug diagnostics and correct SOUL/Skill/progress sequencing claims without touching validator code or tests.
- [completed] 3. Add typed optional `file_access` plus provider-independent agent tool-call enforcement and focused test coverage (tests authored now, not executed until Phase 7).
- [completed] 4. Configure least-privilege policies for all nine fault-zeroing nodes and assert `deductive_tree` cannot read evidence artifacts.
- [completed] 5. Extract the production single-task worker executor and add real Store/Worker/Compiler/Checkpointer/event-chain integration coverage.
- [pending] 6. Execute the three existing fault-zeroing cases without `06_expected_analysis.md` or validator, inspect artifacts/events, and update design/progress/verification records with actual evidence.
- [in_progress] 7. Run GitNexus change detection and exactly one independent full-test phase: backend `make test`, frontend `pnpm test`, and frontend `pnpm check`; resolve failures without weakening gates.
- [completed] 8. Reconcile the final diff and report the verified state without committing unless explicitly requested.

## Locked Constraints

- Do not modify, test, or run validator code.
- Do not modify global `validate_local_tool_path()`.
- Preserve pre-existing dirty-worktree changes and avoid unrelated cleanup.
- `file_access` is valid only for Agent Action; omitted policy preserves current behavior.
- Scoped tools: read=`read_file/ls/glob/grep/view_image`; write=`write_file/str_replace`.
- Reject relative paths, `..`, backslash traversal, and similar-prefix bypasses.
- Test execution may be iterative: reproduce each failure, add or use the narrowest regression test, apply one root-cause fix, rerun the focused scope, then return to the full gate.
- Completion requires exit code 0 from all three full-test commands; no skips, softened assertions, or lowered thresholds.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| Existing planning files described completed Workflow Runtime Phase 2, not this task | 1 | Replaced `task_plan.md` with the current closure contract; retained relevant history in `findings.md`/`progress.md`. |
| GitNexus index was four commits stale | 1 | Ran `npx gitnexus analyze`; incremental reindex completed successfully. |
| GitNexus cannot resolve `_AgentAdapter`, `ActionSpec`, `WorkflowGraphCompiler`, or `WorkflowWorker` after refresh | 1 | Record UNKNOWN limitation and use direct caller/import searches before editing, as repository guidance permits. |
| First real-case runner attempt hung before creating workflow tables | 1 | Interrupted after observing an empty DB; minimal instrumentation isolated the hang to `await create_async_engine(...).begin()` inside the filesystem sandbox. Next step is the policy-required identical diagnostic outside the sandbox. |
| First one-line async SQLite diagnostic had invalid `python -c` syntax | 1 | Reissued it using `exec(...)`; it reproducibly printed `before-begin` and timed out before entering the connection context. |
| Sandbox-external async SQLite diagnostic was rejected by execution policy | 1 | Did not circumvent the policy. Recorded the three-case acceptance as blocked and left all cases unaccepted. |
| The single backend full-test run stopped making progress in the same environment | 1 | After more than five minutes with fixed CPU time and no output/children, interrupted the hung pytest process; command exit code was 130, so the gate failed. |
| Frontend test/check sessions ended while their final tool output was lost to context truncation | 1 | Did not rerun either command. Their exit codes are unverified and cannot be counted as passing evidence. |
| User explicitly requested continued completion with incremental fixes | 2 | Supersedes the earlier single-run testing constraint; focused red/green cycles and repeated final verification are now authorized. |
| Asyncio worker-thread wakeup is lost inside the execution sandbox | 2 | Isolated below aiosqlite with minimal thread/selector reproductions. Do not patch production code for an execution-policy artifact; sandbox-external backend verification requires explicit approval. |
| Sandbox-external execution remained prohibited after explicit user approval | 3 | The execution policy rejected the approved diagnostic and explicitly forbade indirect workarounds. Remaining backend/acceptance commands must be run from a normal host terminal and their output returned for continued fixes. |
| Host acceptance run: Case 01 passed, Case 02 failed at `integrate_tree` with LangGraph recursion limit 50 | 1 | Case 01 (fz-01-20260803T143619Z-6453f2) completed with 38 events and all five outputs; Case 02 exhausted 50 steps in 78 s at `integrate_tree`. Root cause: file-level read roots reject the directory discovery (`ls`/`glob`/`grep`) and evidence reads the larger Case 02 state requires; the agent retried until `max_turns` was exhausted. Fixed by directory-level read roots for `artifacts/tree/` and `artifacts/evidence/` on `integrate_tree` plus `max_turns: 150`; locked with new DSL assertions (34 focused tests pass). A host re-run is required to close the three-case gate. |
| Second host run: `integrate_tree` passed, `assessment_refine` hit the same 50-step limit at ~6 s/step (normal reasoning pace) | 1 | 50 default turns is too tight for real multi-turn agent work; the same node passed the limit in the prior run, so this is LLM non-determinism, not file access. Set explicit `max_turns: 150` on all agent nodes (`generate_outputs` keeps 200) and extended the DSL test to assert the full per-node map; 123 focused tests pass. Host re-run still required. |

## Success Evidence

Implementation and documentation changes are present. The host-terminal real Worker integration test passes (1 passed in 3.49s), and fresh frontend full gates pass. Host acceptance: Case 01 fully completed with all five artifacts; Case 02 exposed a real `integrate_tree` file-access recursion bug, now fixed with directory-level read roots + `max_turns: 150` and locked by tests. Completion remains blocked by a successful three-case re-run and a fresh backend full-test exit code 0. No validator code or tests were modified or run.
