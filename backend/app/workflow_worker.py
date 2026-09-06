"""Process entrypoint for the single durable workflow worker."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, contextmanager
from functools import partial
from typing import Any

import yaml
from langgraph.types import Command

# Canonical runs key their sandboxes on a run-scoped identity; teach the
# runtime's local provider to mount the run's frozen read-only skill view.
from app.agentplatform.resources.canonical_sandbox import install_run_skill_view_resolver as _install_run_skill_view_resolver
from app.agentplatform.workflow_runtime import (
    RunRecordWriter,
    WorkflowCancelled,
    WorkflowGraphCompiler,
    WorkflowInvalidRootsError,
    WorkflowMissingInputRootsError,
    WorkflowPaused,
    WorkflowRunError,
    WorkflowV2Store,
    WorkflowWorker,
    make_host_resolver,
    parse_workflow_v2,
    run_failure_payload,
    validate_read_roots,
    validate_workflow_roots,
    workflow_log_root,
    workflow_snapshot,
)

# Alias legacy IDEER_* deployment env names before any config resolution.
# The alias runs at import time inside compat_env, so importing it here first
# is sufficient (see app/gateway/app.py for the same pattern).
from app.gateway.compat_env import apply_legacy_env_aliases as _apply_legacy_env_aliases  # noqa: F401
from deerflow.config import get_app_config
from deerflow.persistence.engine import close_engine, get_session_factory, init_engine_from_config
from deerflow.persistence.models.workflow_v2 import WorkflowTaskRow
from deerflow.runtime.checkpointer.async_provider import make_checkpointer

# Canonical runs key their sandboxes on a run-scoped identity; teach the
# runtime's local provider to mount the run's frozen read-only skill view.
_install_run_skill_view_resolver()


@contextmanager
def _workflow_run_evidence_context(run: Any):
    """Bind persisted canonical Run Evidence while the graph is executing."""

    from agentplatform_extension.evidence import AuthorizationContext, RunEvidenceBinding, bind_run_evidence

    snapshot = run.snapshot if isinstance(run.snapshot, dict) else {}
    evidence = snapshot.get("run_evidence")
    if not isinstance(evidence, dict):
        yield
        return
    authorization = evidence.get("authorization_context")
    if not isinstance(authorization, dict):
        yield
        return
    binding = RunEvidenceBinding(
        snapshots=tuple(evidence.get("resource_snapshots", ())),
        authorization=AuthorizationContext(
            caller_user_id=str(authorization.get("caller_user_id", run.created_by)),
            effective_agent_id=str(authorization.get("effective_agent_id", run.workflow_resource_id or run.workflow_name)),
            policy_revision=str(authorization.get("policy_revision", evidence.get("policy_revision", "runtime-default"))),
            allowed_tools=tuple(str(value) for value in authorization.get("allowed_tools", ())),
            memory_scope=str(authorization.get("memory_scope", run.created_by)),
        ),
        runtime_assembly_fingerprint=evidence.get("runtime_assembly_fingerprint"),
        trace_id=evidence.get("trace_id"),
    )
    with bind_run_evidence(binding):
        yield


async def load_workflow_definition_for_run(run: Any, store: Any, session_factory: Any, storage: Any) -> dict:
    """Load canonical Runs by frozen UUID; retain name/version for legacy Runs."""

    workflow_resource_id = getattr(run, "workflow_resource_id", None)
    if workflow_resource_id:
        if session_factory is None or storage is None:
            raise RuntimeError("canonical workflow run requires catalog persistence and storage")
        from app.agentplatform.resource_runtime import CanonicalResourceLoader

        async with session_factory() as session:
            frozen = await CanonicalResourceLoader(session, storage).load_workflow(run.run_id, workflow_resource_id)
            return frozen.content
    version = await store.get_definition(run.workflow_name, run.definition_version)
    if version is None:
        raise RuntimeError(f"workflow definition {run.workflow_name}@{run.definition_version} not found")
    return version.definition


async def build_canonical_registry(run: Any, config: Any, session_factory: Any, storage: Any) -> Any:
    """Build adapters only from the Run's frozen UUID closure and runner policy."""

    from sqlalchemy import select

    from app.agentplatform.resource_models import Resource, RunResourceSnapshot
    from app.agentplatform.resource_runtime import CanonicalResourceLoader
    from app.agentplatform.workflow_runtime import ActionAdapterRegistry, _CanonicalAgentAdapter, _ToolAdapter
    from deerflow.tools.tools import get_available_tools

    if session_factory is None:
        raise RuntimeError("canonical workflow run requires catalog persistence")
    raw_groups = run.runner_tool_groups
    allowed_groups = frozenset(raw_groups) if raw_groups is not None else None
    registry = ActionAdapterRegistry()
    for tool in get_available_tools(
        groups=sorted(allowed_groups) if allowed_groups is not None else None,
        app_config=config,
    ):
        registry.register("tool", tool.name, _ToolAdapter(tool, user_id=run.created_by))

    async with session_factory() as session:
        loader = CanonicalResourceLoader(session, storage)
        frozen_skill_versions: dict[str, tuple[int, str]] = {}
        agent_ids = list(
            (
                await session.execute(
                    select(Resource.id)
                    .join(RunResourceSnapshot, RunResourceSnapshot.resource_id == Resource.id)
                    .where(
                        RunResourceSnapshot.run_id == run.run_id,
                        Resource.type == "agent",
                    )
                    .order_by(Resource.id)
                )
            ).scalars()
        )
        for resource_id in agent_ids:
            definition = await loader.load_agent(run.run_id, resource_id)
            skill_definitions = await loader.load_agent_skill_definitions(run.run_id, resource_id)
            skills = [value.skill for value in skill_definitions]
            for value in skill_definitions:
                frozen_skill_versions[value.resource_id] = (value.version, value.content_hash)
            registry.register(
                "agent",
                resource_id,
                _CanonicalAgentAdapter(
                    definition,
                    skills,
                    run.created_by,
                    allowed_tool_groups=allowed_groups,
                ),
            )
        await asyncio.to_thread(
            storage.create_run_skill_view,
            run.run_id,
            [(resource_id, version, content_hash) for resource_id, (version, content_hash) in sorted(frozen_skill_versions.items())],
        )
    return registry


async def execute_workflow_task(
    task: WorkflowTaskRow,
    *,
    store: WorkflowV2Store,
    config: Any,
    checkpointer_factory: Callable[[Any], AbstractAsyncContextManager[Any]] = make_checkpointer,
) -> None:
    """Execute one claimed task through the production graph and event chain."""
    run_id = task.run_id
    run = await store.get_run(run_id)
    if run is None:
        raise RuntimeError(f"workflow run '{run_id}' not found")
    storage = None
    if run.workflow_resource_id:
        from app.agentplatform.resource_runtime import ResourceStorage
        from deerflow.config.paths import get_paths

        storage = ResourceStorage(get_paths().base_dir)
    definition_payload = await load_workflow_definition_for_run(
        run,
        store,
        getattr(store, "session_factory", None),
        storage,
    )
    definition = parse_workflow_v2(yaml.safe_dump(definition_payload))
    adapters = await build_canonical_registry(
        run,
        config,
        getattr(store, "session_factory", None),
        storage,
    )
    if task.resume_command_id is not None:
        command = await store.get_command(task.resume_command_id)
        if command is None:
            raise RuntimeError(f"workflow task '{task.task_id}' has no resume command")
        # LangGraph treats an empty dict as a resume map with no entries, so a
        # payload-less resume would never deliver a value and the interrupt gate
        # would re-raise on every attempt. Normalize to an explicit value.
        resume_value = command.payload if command.payload else {"resumed": True}
        invocation = Command(resume=resume_value)
        # The attempt-budget exemption applies to the immediate resume only;
        # a later crash/take-over must count as a fresh attempt again.
        await store.clear_resume_command(task.task_id)
    else:
        invocation = {"run_id": run_id, "inputs": run.inputs, "state": {}, "outputs": {}, "model_name": run.model_name}

    event_limit = config.workflow_runtime.max_events_per_run

    async def emit_event(event_type: str, payload: dict) -> None:
        event = await store.append_event(
            run_id,
            event_type,
            payload,
            worker_id=task.lease_owner,
            max_events=event_limit - 1,
        )
        if event is None:
            raise WorkflowRunError("event_limit", "工作流执行失败：事件数量已达上限", detail="workflow_event_limit_exceeded")

    async def emit_terminal_event(event_type: str, payload: dict) -> None:
        await store.append_event(
            run_id,
            event_type,
            payload,
            worker_id=task.lease_owner,
            max_events=event_limit,
        )

    runtime_evidence = None
    with _workflow_run_evidence_context(run):
        async with checkpointer_factory(config) as checkpointer:
            graph = WorkflowGraphCompiler(
                definition,
                adapters,
                emit_event=emit_event,
                is_cancelled=lambda: store.is_cancel_requested(run_id),
                node_timeout_seconds=config.workflow_runtime.node_timeout_seconds,
                artifact_resolver=make_host_resolver(run_id, run.created_by),
            ).compile(checkpointer=checkpointer)
            try:
                invalid_roots = validate_workflow_roots(definition.nodes, run.inputs)
                if invalid_roots:
                    raise WorkflowInvalidRootsError(invalid_roots)
                missing_read_roots = validate_read_roots(definition.nodes, run.inputs, make_host_resolver(run_id, run.created_by))
                if missing_read_roots:
                    raise WorkflowMissingInputRootsError(missing_read_roots)
                await emit_event("resumed" if task.resume_command_id is not None else "run_started", {"definition_version": run.definition_version})
                result = await graph.ainvoke(
                    invocation,
                    config={
                        "configurable": {"thread_id": run.checkpoint_thread_id},
                        "max_concurrency": config.workflow_runtime.max_parallel_actions,
                    },
                )
            except WorkflowCancelled as exc:
                await emit_terminal_event("run_cancelled", {"error": str(exc)})
                raise
            except Exception as exc:
                await emit_terminal_event("run_failed", run_failure_payload(exc))
                raise
        from agentplatform_extension.evidence import current_run_evidence

        binding = current_run_evidence()
        if binding is not None:
            runtime_evidence = binding.as_mapping()
    snapshot = workflow_snapshot(result)
    if runtime_evidence is not None:
        snapshot["run_evidence"] = runtime_evidence
    if not await store.update_snapshot(run_id, snapshot, worker_id=task.lease_owner):
        return
    if "__interrupt__" in result:
        await emit_event("interrupted", {"value": snapshot["interrupt"]})
        raise WorkflowPaused
    await emit_terminal_event("run_completed", {})


async def run_worker() -> None:
    config = get_app_config()
    if config.database.backend == "memory":
        raise RuntimeError("workflow-worker requires a durable database backend")
    await init_engine_from_config(config.database)
    sf = get_session_factory()
    if sf is None:
        raise RuntimeError("workflow-worker could not initialize persistence")
    store = WorkflowV2Store(sf)
    writers: dict[str, RunRecordWriter] = {}

    async def record_sink(run, event) -> None:
        writer = writers.get(run.run_id)
        if writer is None:
            writer = RunRecordWriter(make_host_resolver(run.run_id, str(run.created_by)), workflow_log_root())
            writers[run.run_id] = writer
        if event is not None:
            await writer.on_event(event)
        if run.status in {"completed", "failed", "cancelled"}:
            await writer.finalize(store, run)
            writers.pop(run.run_id, None)

    store.event_sink = record_sink

    try:
        runtime = config.workflow_runtime
        # Default to a per-process id: two workers on one machine must never
        # share the default lease owner, or they race to claim the same task.
        await WorkflowWorker(
            store,
            partial(execute_workflow_task, store=store, config=config),
            os.getenv("WORKFLOW_WORKER_ID") or f"workflow-worker-{os.getpid()}",
            lease_seconds=runtime.lease_seconds,
            heartbeat_seconds=runtime.heartbeat_seconds,
            max_attempts=runtime.max_attempts,
        ).run_forever()
    finally:
        await close_engine()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
