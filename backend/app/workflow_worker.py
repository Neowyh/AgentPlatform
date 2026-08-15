"""Process entrypoint for the single durable workflow worker."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from functools import partial
from typing import Any

import yaml
from langgraph.types import Command

from ideer.config import get_app_config
from ideer.persistence.engine import close_engine, get_session_factory, init_engine_from_config
from ideer.persistence.models.workflow_v2 import WorkflowTaskRow
from ideer.runtime.checkpointer.async_provider import make_checkpointer
from ideer.workflows.v2.adapters import ActionResolutionError, build_default_registry
from ideer.workflows.v2.compiler import WorkflowCancelled, WorkflowGraphCompiler
from ideer.workflows.v2.file_roots import make_host_resolver, validate_read_roots, validate_workflow_roots, workflow_log_root
from ideer.workflows.v2.parser import parse_workflow_v2
from ideer.workflows.v2.run_record import RunRecordWriter
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowPaused, WorkflowWorker, workflow_snapshot


async def load_workflow_definition_for_run(run: Any, store: Any, session_factory: Any, storage: Any) -> dict:
    """Load canonical Runs by frozen UUID; retain name/version for legacy Runs."""

    workflow_resource_id = getattr(run, "workflow_resource_id", None)
    if workflow_resource_id:
        if session_factory is None or storage is None:
            raise RuntimeError("canonical workflow run requires catalog persistence and storage")
        from ideer.resources.runtime import CanonicalResourceLoader

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

    from ideer.persistence.models.resource_catalog import Resource, RunResourceSnapshot
    from ideer.resources.runtime import CanonicalResourceLoader
    from ideer.tools.tools import get_available_tools
    from ideer.workflows.v2.adapters import ActionAdapterRegistry, _CanonicalAgentAdapter, _ToolAdapter

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


async def resolve_shared_agent_adapters(definition: Any, registry: Any, runner_id: str) -> None:
    """Register shared agents referenced by workflow nodes but owned by another user.

    ``build_default_registry`` registers the runner's own agents from the
    runner's directory. This step adds agents the runner does not own but is
    allowed to use (public / department / super_admin visibility, enforced
    with the same RBAC rules as the agents API). Config and SOUL are loaded
    from the declaring owner's directory by ``_AgentAdapter`` while the run
    context stays with the runner.

    Names the runner already owns (or that the injected registry already
    resolves) are left untouched; unresolvable or inaccessible agents keep the
    existing ``ActionResolutionError`` failure path.
    """
    from app.gateway.authz import check_resource_access
    from app.gateway.utils import ResourceMetadataStore
    from ideer.config.agents_config import validate_agent_name
    from ideer.config.paths import get_paths
    from ideer.persistence.engine import get_session_factory
    from ideer.persistence.models.user import UserModel
    from ideer.workflows.v2.adapters import _AgentAdapter

    agent_names: set[str] = set()
    for node in definition.nodes:
        if getattr(node, "type", None) != "action":
            continue
        action = getattr(node, "action", None)
        if action is None or getattr(action, "kind", None) != "agent":
            continue
        try:
            agent_names.add(validate_agent_name(getattr(action, "name", None)))
        except ValueError:
            continue

    meta_store = ResourceMetadataStore("agent")
    for name in agent_names:
        try:
            registry.resolve("agent", name)
            continue
        except ActionResolutionError:
            pass

        meta = await meta_store.load_meta(name)
        owner_id = meta.get("owner_id")
        if not owner_id or owner_id == runner_id:
            continue
        if not get_paths().user_agent_dir(owner_id, name).exists():
            continue

        sf = get_session_factory()
        user_row = None
        if sf is not None:
            from sqlalchemy import select

            async with sf() as session:
                user_row = (await session.execute(select(UserModel).where(UserModel.id == runner_id))).scalar_one_or_none()
        if user_row is None:
            continue
        if not check_resource_access(user_row, owner_id, meta.get("department_id"), meta.get("visibility", "private")):
            continue
        registry.register("agent", name, _AgentAdapter(name, runner_id, owner_id=owner_id))


async def execute_workflow_task(
    task: WorkflowTaskRow,
    *,
    store: WorkflowV2Store,
    config: Any,
    registry_factory: Callable[[Any, str], Any] = build_default_registry,
    checkpointer_factory: Callable[[Any], AbstractAsyncContextManager[Any]] = make_checkpointer,
) -> None:
    """Execute one claimed task through the production graph and event chain."""
    run_id = task.run_id
    run = await store.get_run(run_id)
    if run is None:
        raise RuntimeError(f"workflow run '{run_id}' not found")
    storage = None
    if run.workflow_resource_id:
        from ideer.config.paths import get_paths
        from ideer.resources.storage import ResourceStorage

        storage = ResourceStorage(get_paths().base_dir)
    definition_payload = await load_workflow_definition_for_run(
        run,
        store,
        getattr(store, "session_factory", None),
        storage,
    )
    definition = parse_workflow_v2(yaml.safe_dump(definition_payload))
    if run.workflow_resource_id:
        adapters = await build_canonical_registry(
            run,
            config,
            getattr(store, "session_factory", None),
            storage,
        )
    else:
        adapters = registry_factory(config, run.created_by)
        await resolve_shared_agent_adapters(definition, adapters, run.created_by)
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
        invocation = {"run_id": run_id, "inputs": run.inputs, "state": {}, "outputs": {}}

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
            raise RuntimeError("workflow_event_limit_exceeded")

    async def emit_terminal_event(event_type: str, payload: dict) -> None:
        await store.append_event(
            run_id,
            event_type,
            payload,
            worker_id=task.lease_owner,
            max_events=event_limit,
        )

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
                raise RuntimeError("invalid file_access roots: " + "; ".join(invalid_roots))
            missing_read_roots = validate_read_roots(definition.nodes, run.inputs, make_host_resolver(run_id, run.created_by))
            if missing_read_roots:
                raise RuntimeError("missing input roots: " + "; ".join(missing_read_roots))
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
            await emit_terminal_event("run_failed", {"error": str(exc)})
            raise
    snapshot = workflow_snapshot(result)
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
