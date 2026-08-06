from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.workflow_worker import execute_workflow_task
from ideer.config.paths import Paths
from ideer.persistence.base import Base
from ideer.workflows.v2.adapters import ActionAdapterRegistry
from ideer.workflows.v2.file_roots import make_host_resolver
from ideer.workflows.v2.store import WorkflowV2Store
from ideer.workflows.v2.worker import WorkflowWorker

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / "workflows" / "fault-zeroing.yaml"


@pytest_asyncio.fixture
async def durable_store(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'workflow.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


class RecordingAgent:
    def __init__(self, calls: list[str], *, write_artifacts: bool) -> None:
        self.calls = calls
        self.write_artifacts = write_artifacts

    async def run(self, context, params):
        self.calls.append(context.node_id)
        if self.write_artifacts and context.file_access:
            resolver = make_host_resolver(context.run_id, "user-1")
            for root in context.file_access.get("write", []):
                host = resolver(root)
                assert host is not None, f"unresolvable write root {root}"
                path = Path(host)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.name == "fault_tree.json":
                    path.write_text(
                        '{"top_event": "top", "intermediate_events": [], "bottom_events": [], '
                        '"logic": [], "evidence": [], '
                        '"root_causes": [{"id": "RC-01", "name": "root cause", '
                        '"description": "desc", "evidence_ids": [], '
                        '"status": "confirmed", "confidence": "high"}], '
                        '"verification_plan": []}',
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
) -> None:
    definition = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    version = await durable_store.save_definition("fault-zeroing", definition, "test-hash", "user-1")
    await durable_store.create_run(
        run_id,
        "fault-zeroing",
        version.version,
        {
            "upload_dir": "/mnt/user-data/uploads",
            "problem_description": "top event",
            "output_base_dir": "/mnt/user-data/outputs",
        },
        "user-1",
    )
    registry = ActionAdapterRegistry({("agent", "fault-zeroing"): agent})
    config = _make_config(tmp_path)

    async def execute(task) -> None:
        await execute_workflow_task(
            task,
            store=durable_store,
            config=config,
            registry_factory=lambda _config, _user_id: registry,
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
        lambda: str(REPO_ROOT / "skills"),
    )
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=True),
        run_id="run-worker-real-path",
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
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    definition = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    version = await durable_store.save_definition("fault-zeroing", definition, "test-hash", "user-1")
    await durable_store.create_run(
        "run-worker-host-paths",
        "fault-zeroing",
        version.version,
        {
            "upload_dir": str(tmp_path / "uploads"),
            "problem_description": "top event",
            "output_base_dir": str(tmp_path / "outputs"),
        },
        "user-1",
    )
    calls: list[str] = []
    registry = ActionAdapterRegistry({("agent", "fault-zeroing"): RecordingAgent(calls, write_artifacts=True)})
    config = _make_config(tmp_path)

    async def execute(task) -> None:
        await execute_workflow_task(
            task,
            store=durable_store,
            config=config,
            registry_factory=lambda _config, _user_id: registry,
        )

    assert await WorkflowWorker(durable_store, execute, worker_id="worker-integration").run_once() is True

    run = await durable_store.get_run("run-worker-host-paths")
    assert run is not None and run.status == "failed"
    assert "invalid file_access roots" in (run.error or "")
    assert calls == []
    events = await durable_store.list_events(run.run_id)
    assert [event.event_type for event in events][-1] == "run_failed"


@pytest.mark.asyncio
async def test_missing_artifacts_fail_the_run_instead_of_completing(
    durable_store: WorkflowV2Store,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Missing artifacts are a hard failure by default — the run must not
    complete with a fabricated/stub output and does not pause."""
    monkeypatch.setattr("ideer.workflows.v2.file_roots.get_paths", lambda: Paths(str(tmp_path / "base")))
    calls: list[str] = []
    await _run_worker_once(
        durable_store,
        tmp_path,
        RecordingAgent(calls, write_artifacts=False),
        run_id="run-worker-missing-artifacts",
    )

    run = await durable_store.get_run("run-worker-missing-artifacts")
    assert run is not None and run.status == "failed"
    assert run.error is not None and "artifacts_missing" in run.error
    events = await durable_store.list_events(run.run_id)
    assert "interrupted" not in {event.event_type for event in events}
    assert any(event.event_type == "node_failed" for event in events)
