from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.workflow_worker import execute_workflow_task
from ideer.config.paths import Paths
from ideer.persistence.base import Base
from ideer.resources.runtime import _json_hash
from ideer.resources.service import ResourceAction, ResourceActor
from ideer.workflows.v2.adapters import ActionAdapterRegistry, _ToolAdapter
from ideer.workflows.v2.errors import WorkflowInvalidRootsError
from ideer.workflows.v2.file_roots import make_host_resolver
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowWorker

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / "resources" / "workflows" / "fault-zeroing.yaml"


@pytest_asyncio.fixture
async def durable_store(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


async def _make_canonical_run(
    store: WorkflowV2Store,
    run_id: str,
    definition: dict,
    inputs: dict,
    *,
    name: str = "fault-zeroing",
    owner: str = "user-1",
) -> None:
    """Freeze a canonical workflow run whose dependency closure is a single workflow root."""
    from uuid import uuid4

    from ideer.persistence.models.resource_catalog import Resource, ResourceVersion

    workflow_id = str(uuid4())
    async with store.session_factory() as session:
        session.add(
            Resource(
                id=workflow_id,
                type="workflow",
                slug=name,
                display_name=name,
                owner_id=owner,
                visibility="public",
                scope_department_id=None,
                lifecycle_status="active",
                latest_version=1,
                draft_revision=0,
                storage_kind="database",
                storage_key=f"workflows/{workflow_id}",
                system_owned=False,
                authz_revision=1,
            )
        )
        session.add(
            ResourceVersion(
                id=f"wv-{run_id}",
                resource_id=workflow_id,
                version=1,
                content_hash=_json_hash(definition),
                storage_key=f"workflows/{workflow_id}/versions/1",
                scan_result={},
                content=definition,
                created_by=owner,
            )
        )
        await session.commit()
    actor = ResourceActor(
        user_id=owner,
        department_id=None,
        role="user",
        permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
        tool_groups=None,
    )
    await store.create_canonical_run(run_id, workflow_id, inputs, actor)


class RecordingAgent:
    def __init__(
        self,
        calls: list[str],
        *,
        write_artifacts: bool,
        fail_nodes: set[str] | None = None,
        confirmed_root_causes: bool = True,
    ) -> None:
        self.calls = calls
        self.write_artifacts = write_artifacts
        self.fail_nodes = fail_nodes or set()
        self.confirmed_root_causes = confirmed_root_causes

    async def run(self, context, params):
        self.calls.append(context.node_id)
        if context.node_id in self.fail_nodes:
            raise RuntimeError(f"agent failed for node {context.node_id}")
        if self.write_artifacts and context.file_access:
            resolver = make_host_resolver(context.run_id, "user-1")
            for root in context.file_access.get("write", []):
                host = resolver(root)
                assert host is not None, f"unresolvable write root {root}"
                path = Path(host)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name == "fault_tree.json":
                    path.write_text(
                        f'{{"top_event": "top", "intermediate_events": [], "bottom_events": [], '
                        f'"logic": [], "evidence": [], '
                        f'"root_causes": [{{"id": "RC-01", "name": "root cause", '
                        f'"description": "desc", "evidence_ids": [], '
                        f'"status": "{("confirmed" if self.confirmed_root_causes else "to_verify")}", "confidence": "high"}}], '
                        f'"verification_plan": []}}',
                        encoding="utf-8",
                    )
                elif path.name == "fault_tree_structure.json":
                    path.write_text(
                        '{"top_event": "top", "intermediate_events": [], "bottom_events": [], "logic": [], "evidence": [], "root_causes": [], "verification_plan": []}',
                        encoding="utf-8",
                    )
                elif path.name == "corrective_actions.json":
                    path.write_text(
                        '{"corrective_actions": [{"id": "CA-01", "name": "fix", "description": "desc", "target_root_cause_id": "RC-01", "completion_criteria": "done"}]}',
                        encoding="utf-8",
                    )
                else:
                    path.write_text("{}", encoding="utf-8")
        return {"node_id": context.node_id}


def _make_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        checkpointer=SimpleNamespace(type="sqlite", connection_string=str(tmp_path / "checkpoints.db")),
        database=SimpleNamespace(backend="memory"),
        workflow_runtime=SimpleNamespace(
            max_events_per_run=1000,
            node_timeout_seconds=30,
            max_parallel_actions=3,
        ),
    )


async def _run_worker_once(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    agent: RecordingAgent,
    *,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    await _make_canonical_run(
        durable_store,
        run_id,
        definition,
        {
            "upload_dir": "/mnt/user-data/uploads",
            "problem_description": "top event",
            "output_base_dir": "/mnt/user-data/outputs",
        },
    )
    registry = ActionAdapterRegistry({("agent", "fault-zeroing"): agent})
    config = _make_config(tmp_path)
    monkeypatch.setattr("app.workflow_worker.build_canonical_registry", AsyncMock(return_value=registry))

    async def execute(task) -> None:
        await execute_workflow_task(
            task,
            store=durable_store,
            config=config,
        )

    assert await WorkflowWorker(durable_store, execute, worker_id="worker-integration").run_once() is True


@pytest.mark.asyncio
async def test_production_worker_task_path_persists_all_fault_zeroing_events(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    monkeypatch.setattr(
        "ideer.workflows.v2.file_roots._get_skills_host_path",
        lambda: str(REPO_ROOT / "resources" / "skills"),
    )
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=True),
        run_id="run-worker-real-path",
        monkeypatch=monkeypatch,
    )

    run = await durable_store.get_run("run-worker-real-path")
    assert run is not None and run.status == "completed"
    assert len(calls) == 9
    assert set(calls[:2]) == {"evidence_collection", "deductive_tree"}
    assert set(run.snapshot["outputs"]) == set(calls)
    events = await durable_store.list_events(run.run_id)
    assert events[0].event_type == "run_started"
    assert events[-1].event_type == "run_completed"
    assert [event.event_type for event in events].count("node_completed") == 11
    assert (tmp_path / "checkpoints.db").is_file()


@pytest.mark.asyncio
async def test_host_path_inputs_fail_the_run_instead_of_completing(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Host paths are rejected when the canonical run is created — a run can
    never reach the worker with invalid file_access roots."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    definition = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    with pytest.raises(WorkflowInvalidRootsError) as exc_info:
        await _make_canonical_run(
            durable_store,
            "run-worker-host-paths",
            definition,
            {
                "upload_dir": str(tmp_path / "uploads"),
                "problem_description": "top event",
                "output_base_dir": str(tmp_path / "outputs"),
            },
        )

    assert exc_info.value.code == "invalid_file_roots"
    assert exc_info.value.violations and all({"node_id", "access", "path"} <= set(v) for v in exc_info.value.violations)

    run = await durable_store.get_run("run-worker-host-paths")
    assert run is None


@pytest.mark.asyncio
async def test_missing_artifacts_pause_the_run_for_manual_resume(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The bundled workflow opts into ``on_missing_artifact: pause`` — a node
    whose declared write roots produced no usable data must park the run as
    ``paused`` with an ``artifacts_missing`` interrupt instead of failing it,
    so an operator can fix the files and resume from the checkpoint."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=False),
        run_id="run-worker-missing-artifacts",
        monkeypatch=monkeypatch,
    )

    run = await durable_store.get_run("run-worker-missing-artifacts")
    assert run is not None and run.status == "paused"
    events = await durable_store.list_events(run.run_id)
    assert not any(event.event_type == "node_failed" for event in events)

    interrupts = run.snapshot.get("interrupt", [])
    assert interrupts and interrupts[0]["type"] == "artifacts_missing"
    # both fork branches race without artifacts; whichever pauses first wins
    assert interrupts[0]["node_id"] in {"evidence_collection", "deductive_tree"}
    assert interrupts[0]["missing"]


@pytest.mark.asyncio
async def test_precondition_skip_skips_corrective_actions_and_still_generates_outputs(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The real workflow's corrective_actions gate must skip when no root cause
    is confirmed (fault_tree.json `root_causes[*].status` has no `confirmed`),
    and generate_outputs must still complete the run with all 4 files."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=True, confirmed_root_causes=False),
        run_id="run-worker-precondition-skip",
        monkeypatch=monkeypatch,
    )

    run = await durable_store.get_run("run-worker-precondition-skip")
    assert run is not None and run.status == "completed"
    events = await durable_store.list_events(run.run_id)

    skipped = [event for event in events if event.event_type == "node_skipped"]
    assert len(skipped) == 1
    assert skipped[0].payload["node_id"] == "corrective_actions"
    assert any("precondition" in (reason or "") for reason in skipped[0].payload.get("reasons", []))

    assert "corrective_actions" not in calls
    assert "generate_outputs" in calls
    assert [event.event_type for event in events].count("node_completed") == 10


@pytest.mark.asyncio
async def test_fork_branch_failure_fails_run_and_persists_node_failure(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A failing fork branch must fail the run (default missing-artifact/failure
    semantics), persist the node_failed event, and never mark the join completed."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=True, fail_nodes={"evidence_collection"}),
        run_id="run-worker-fork-branch-failure",
        monkeypatch=monkeypatch,
    )

    run = await durable_store.get_run("run-worker-fork-branch-failure")
    assert run is not None and run.status == "failed"
    events = await durable_store.list_events(run.run_id)

    failed = [event for event in events if event.event_type == "node_failed"]
    assert any(event.payload.get("node_id") == "evidence_collection" for event in failed)
    completed_nodes = {event.payload.get("node_id") for event in events if event.event_type == "node_completed"}
    assert "join_review" not in completed_nodes
    assert events[-1].event_type == "run_failed"
    assert "evidence_collection" in calls


@pytest.mark.asyncio
async def test_control_node_lifecycle_events_reach_the_event_stream(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """fork_start and join_review must emit node_started/node_completed so the
    run graph shows real status for control nodes (fix/workflow-node-status)."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=True),
        run_id="run-worker-control-node-events",
        monkeypatch=monkeypatch,
    )

    run = await durable_store.get_run("run-worker-control-node-events")
    assert run is not None and run.status == "completed"
    events = await durable_store.list_events(run.run_id)

    def node_events(event_type: str, node_id: str):
        return [event for event in events if event.event_type == event_type and event.payload.get("node_id") == node_id]

    for node_id in ("fork_start", "join_review"):
        started = node_events("node_started", node_id)
        completed = node_events("node_completed", node_id)
        assert len(started) == 1, f"{node_id} must emit exactly one node_started"
        assert len(completed) == 1, f"{node_id} must emit exactly one node_completed"
        assert started[0].payload.get("started_at")
        assert completed[0].payload.get("finished_at")

    seqs = {(event.event_type, event.payload.get("node_id")): event.seq for event in events}
    assert seqs[("node_started", "fork_start")] < seqs[("node_started", "evidence_collection")]
    assert seqs[("node_started", "evidence_collection")] < seqs[("node_started", "join_review")]
    assert seqs[("node_started", "join_review")] < seqs[("node_started", "review_and_crosscheck")]


GATED_WORKFLOW = """
schema_version: 2
name: gated
inputs: {}
state: {}
entrypoint: gate_1
nodes:
  - id: gate_1
    type: interrupt
    roles: [super_admin]
  - id: gate_2
    type: interrupt
    roles: [super_admin]
  - id: finish
    type: action
    action: {kind: tool, name: finish}
edges:
  - {from: gate_1, to: gate_2}
  - {from: gate_2, to: finish}
"""


class FinishAgent:
    async def run(self, context, params):
        return {"node_id": context.node_id}


@pytest.mark.asyncio
async def test_empty_payload_resume_advances_past_interrupt_gates(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A resume command with an empty payload must still advance the run.

    LangGraph treats ``Command(resume={})`` as a resume map with zero entries,
    which would make the interrupt gate re-raise and the run stay paused
    forever. The production worker normalizes the empty payload.
    """
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    definition = yaml.safe_load(GATED_WORKFLOW)
    await _make_canonical_run(durable_store, "run-gate-resume-empty", definition, {}, name="gated")
    registry = ActionAdapterRegistry({("tool", "finish"): FinishAgent()})
    config = _make_config(tmp_path)
    monkeypatch.setattr("app.workflow_worker.build_canonical_registry", AsyncMock(return_value=registry))

    async def execute(task) -> None:
        await execute_workflow_task(
            task,
            store=durable_store,
            config=config,
        )

    worker = WorkflowWorker(durable_store, execute, worker_id="worker-integration")
    assert await worker.run_once() is True
    paused = await durable_store.get_run("run-gate-resume-empty")
    assert paused is not None and paused.status == "paused"

    await durable_store.submit_command("resume-empty-1", "run-gate-resume-empty", "resume", {}, "user-1")
    assert await worker.run_once() is True
    advanced = await durable_store.get_run("run-gate-resume-empty")
    assert advanced is not None and advanced.status == "paused"

    await durable_store.submit_command("resume-empty-2", "run-gate-resume-empty", "resume", {}, "user-1")
    assert await worker.run_once() is True
    completed = await durable_store.get_run("run-gate-resume-empty")
    assert completed is not None and completed.status == "completed"


@pytest.mark.asyncio
async def test_tool_adapter_injects_sandbox_runtime(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Workflow `kind: tool` nodes must get a ToolRuntime like agent nodes do.

    Without runtime injection, sandbox tools (write_file/read_file) fail with
    "runtime Field required" because LangGraph only injects the runtime for
    agent nodes. The adapter must mirror the thread-scoped state/context the
    local sandbox derives (thread_id == run_id).
    """
    monkeypatch.setattr("ideer.config.paths.get_paths", lambda: Paths(str(tmp_path / "base")))

    from ideer.sandbox.sandbox_provider import reset_sandbox_provider
    from ideer.sandbox.tools import read_file_tool, write_file_tool

    reset_sandbox_provider()

    WRITE_WORKFLOW = """
schema_version: 2
name: gated-tool
inputs: {}
state:
  note_done:
    type: boolean
    default: false
  content:
    type: string
    default: ""
entrypoint: write
nodes:
  - id: write
    type: action
    action:
      kind: tool
      name: write_file
      params:
        description: verify
        path: /mnt/user-data/workspace/note.txt
        content: hello
    writes:
      - $.state.note_done
  - id: read
    type: action
    action:
      kind: tool
      name: read_file
      params:
        description: verify
        path: /mnt/user-data/workspace/note.txt
        offset: 0
        limit: 100
    writes:
      - $.state.content
edges:
  - {from: write, to: read}
"""
    definition = yaml.safe_load(WRITE_WORKFLOW)
    await _make_canonical_run(durable_store, "run-tool-runtime", definition, {}, name="gated-tool")
    registry = ActionAdapterRegistry(
        {
            ("tool", "write_file"): _ToolAdapter(write_file_tool, user_id="user-1"),
            ("tool", "read_file"): _ToolAdapter(read_file_tool, user_id="user-1"),
        }
    )
    config = _make_config(tmp_path)
    monkeypatch.setattr("app.workflow_worker.build_canonical_registry", AsyncMock(return_value=registry))

    async def execute(task) -> None:
        await execute_workflow_task(
            task,
            store=durable_store,
            config=config,
        )

    worker = WorkflowWorker(durable_store, execute, worker_id="worker-integration")
    assert await worker.run_once() is True
    completed = await durable_store.get_run("run-tool-runtime")
    assert completed is not None and completed.status == "completed"
    assert completed.snapshot["outputs"]["read"] == "hello"
    assert (tmp_path / "base/users/user-1/threads/run-tool-runtime/user-data/workspace/note.txt").exists()
