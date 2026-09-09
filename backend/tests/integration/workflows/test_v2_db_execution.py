"""Ticket 02: Workflow V2 six-table family, full DB execution verification.

PATCH-009's debt: the six Workflow V2 tables (definition versions, runs,
tasks, lease audit, events, commands) were model- and contract-checked but
never proven against real databases. These tests prove, per backend, that:

1. ``alembic upgrade head`` on an EMPTY database creates the six-table
   family (the unified chain -- the same command serve.sh runs);
2. ``WorkflowV2Store`` drives a full lifecycle over those migrated tables
   (definition -> run -> lease claim/renew -> events -> snapshot recovery ->
   resume command -> cancel request -> consume), the same call pattern the
   Gateway (deps.py), Worker (workflow_worker.py) and canonical run
   preparation use;
3. ``RunRepository`` reads the shared ``runs`` table state that a canonical
   Workflow V2 run participates in (RunRecord's evidence projection reads
   the same rows);
4. the Gateway's canonical-run preparation over the MIGRATED schema:
   ``ResourceService`` publish flow -> ``create_canonical_run`` ->
   ``run_resource_snapshots`` rows carrying the 20260828
   ``selection_role`` column (its real write path), then the Worker
   lease claim / expiry-takeover / stale-worker-blocked cycle audited in
   ``workflow_lease_audit``;
5. an EXISTING database parked at the 20260715 workflow-v2 shape upgrades to
   head with its rows intact and readable -- the 20260825/20260828 column
   additions (``workflow_v2_runs.model_name``,
   ``run_resource_snapshots.selection_role``) land as NULL/default backfills.

Backends: sqlite (aiosqlite) and postgresql (asyncpg). The postgres URL
comes from ``WORKFLOW_V2_TEST_POSTGRES_URL``; when unset (CI without a PG
service) the postgres variants are reported as skipped, never silently
absent.

Seams (pre-agreed): ``WorkflowV2Store`` and ``RunRepository`` public methods
-- the same boundaries the Gateway/Worker/RunRecord callers use. No store
internals are mocked.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

import pytest
import pytest_asyncio
from _resource_catalog import publish_resource
from alembic import command
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agentplatform.resources.service import (
    ResourceAction,
    ResourceActor,
    ResourceService,
)
from app.agentplatform.workflows.v2.store import WorkflowV2Store
from deerflow.persistence.migrations._chain_meta import MERGE_REVISION
from deerflow.persistence.models.workflow_v2 import WorkflowLeaseAuditRow
from deerflow.persistence.run import RunRepository
from tests._migration_test_support import unified_alembic_config

POSTGRES_URL = os.getenv("WORKFLOW_V2_TEST_POSTGRES_URL", "")
if POSTGRES_URL.startswith(("postgresql://", "postgres://")):
    # Normalize to the asyncpg SQLAlchemy driver, mirroring
    # ``database_config.app_sqlalchemy_url``.
    POSTGRES_URL = POSTGRES_URL.replace("postgres://", "postgresql://", 1).replace("postgresql://", "postgresql+asyncpg://", 1)
# Raw DSN for asyncpg scratch-database administration (no driver suffix).
POSTGRES_ADMIN_URL = POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

pytestmark = pytest.mark.asyncio

# The postgres variant stays visible in every run: without the URL it is
# reported as skipped (with the reason), never silently absent.
BACKENDS = [
    "sqlite",
    pytest.param(
        "postgres",
        marks=pytest.mark.skipif(not POSTGRES_URL, reason="set WORKFLOW_V2_TEST_POSTGRES_URL to exercise the PostgreSQL variants"),
    ),
]


async def _upgrade_to(url: str, revision: str) -> None:
    """Run one alembic upgrade on a worker thread.

    Mirrors production, where ``bootstrap_schema`` wraps the synchronous
    ``command.upgrade`` in ``asyncio.to_thread``: the async-backend
    migration path drives its own event loop and must not run on the
    caller's running loop.
    """
    await asyncio.get_running_loop().run_in_executor(None, partial(command.upgrade, unified_alembic_config(url), revision))


def _async_url(backend: str, tmp_path: Path) -> str:
    if backend == "sqlite":
        return f"sqlite+aiosqlite:///{tmp_path / 't02.db'}"
    return POSTGRES_URL


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=BACKENDS)
def backend(request) -> str:
    return request.param


class _ScratchPostgres:
    """Per-test scratch database inside the configured PG instance."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.dbname = f"wfv2_{uuid.uuid4().hex[:12]}"
        self.admin_url = POSTGRES_ADMIN_URL  # raw DSN for asyncpg.connect

    async def create(self) -> str:
        import asyncpg

        conn = await asyncpg.connect(self.admin_url)
        try:
            await conn.execute(f"DROP DATABASE IF EXISTS {self.dbname} WITH (FORCE)")
            await conn.execute(f"CREATE DATABASE {self.dbname}")
        finally:
            await conn.close()
        base = self.url.rsplit("/", 1)[0]
        return f"{base}/{self.dbname}"

    async def drop(self) -> None:
        import asyncpg

        conn = await asyncpg.connect(self.admin_url)
        try:
            await conn.execute(f"DROP DATABASE IF EXISTS {self.dbname} WITH (FORCE)")
        finally:
            await conn.close()


@pytest_asyncio.fixture
async def backend_url(backend: str, tmp_path: Path):
    """A fresh, EMPTY database URL (no migrations applied yet)."""
    if backend == "postgres":
        scratch = _ScratchPostgres(POSTGRES_URL)
        url = await scratch.create()
    else:
        scratch = None
        url = _async_url(backend, tmp_path)
    yield url
    if scratch is not None:
        await scratch.drop()


@pytest_asyncio.fixture
async def engine(backend_url: str):
    eng = create_async_engine(backend_url)
    yield eng
    await eng.dispose()


# ---------------------------------------------------------------------------
# Shared lifecycle driver -- the Gateway/Worker call pattern, unmocked
# ---------------------------------------------------------------------------


async def _drive_full_lifecycle(store: WorkflowV2Store, run_repo: RunRepository, engine) -> None:
    """Drive the six-table family through its full write/read surface."""
    # 1. definition versions (workflow_definition_versions)
    saved = await store.save_definition("verify-flow", {"name": "verify-flow", "version": 2}, "hash-abc", "admin")
    latest = await store.get_latest_definition("verify-flow")
    assert latest is not None and latest.version == saved.version
    fetched = await store.get_definition("verify-flow", saved.version)
    assert fetched is not None and fetched.content_hash == "hash-abc"
    rows, total = await store.list_latest_definitions()
    assert total >= 1 and any(r.workflow_name == "verify-flow" for r in rows)

    # 2. run + task rows (workflow_v2_runs, workflow_tasks)
    run = await store.create_run("t02-run-1", "verify-flow", saved.version, {"n": 1}, "admin")
    assert run.status == "queued"

    # 3. lease claim (workflow_tasks update + workflow_lease_audit append)
    claimed = await store.claim_next_task("worker-a", lease_seconds=60)
    assert claimed is not None and claimed.run_id == "t02-run-1"
    assert claimed.lease_owner == "worker-a" and claimed.status == "running"
    renewed = await store.renew_lease(claimed.task_id, "worker-a", lease_seconds=90)
    assert renewed is True

    # 4. events (workflow_v2_events, per-seq unique)
    await store.append_event("t02-run-1", "run_started", {"step": 0})
    await store.append_event("t02-run-1", "node_completed", {"node": "prepare"})
    events = await store.list_events("t02-run-1")
    assert [e.seq for e in events] == [1, 2]
    assert {e.event_type for e in events} == {"run_started", "node_completed"}

    # 5. snapshot recovery (workflow_v2_runs.snapshot) -- the worker's
    #    restart-recovery write path (update_snapshot with worker lease check)
    snapshot = {"run_evidence": {"resource_snapshots": [{"resource_id": "wf", "version": 1, "content_hash": "h", "selection_role": "root"}]}}
    assert await store.update_snapshot("t02-run-1", snapshot, worker_id="worker-a") is True
    reread = await store.get_run("t02-run-1")
    assert reread is not None and reread.snapshot["run_evidence"]["resource_snapshots"][0]["selection_role"] == "root"

    # 6. resume + cancel commands (workflow_commands); a cancel on a RUNNING
    #    task raises the cancel flag the worker consumes.
    cmd = await store.submit_command("t02-cmd-1", "t02-run-1", "resume", {"node": "review"}, "admin")
    assert cmd is not None
    got = await store.get_command("t02-cmd-1")
    assert got is not None and got.payload == {"node": "review"}
    assert await store.latest_command("t02-run-1", "resume") is not None

    cancel = await store.submit_command("t02-cmd-2", "t02-run-1", "cancel", {}, "admin")
    assert cancel is not None
    assert await store.is_cancel_requested("t02-run-1") is True
    assert await store.consume_cancel_request("t02-run-1") is True
    cancelled = await store.get_run("t02-run-1")
    assert cancelled is not None and cancelled.status == "cancelled"
    assert await store.is_cancel_requested("t02-run-1") is False

    # 7. lease audit rows recorded the claim (and its renew takeover)
    async with engine.begin() as conn:
        audit = (await conn.execute(select(WorkflowLeaseAuditRow))).all()
        assert {r.event_type for r in audit} >= {"claimed"}
        assert {r.worker_id for r in audit} == {"worker-a"}

    # 8. RunRepository over the shared runs table (Run history readable)
    await run_repo.put("t02-shared-run", thread_id="t02-thread", status="completed")
    shared = await run_repo.get("t02-shared-run")
    assert shared is not None and shared["status"] == "completed"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkflowV2SixTableFamily:
    async def test_fresh_upgrade_creates_and_drives_six_tables(self, backend: str, backend_url: str, engine) -> None:
        """Empty DB -> unified-chain upgrade -> full lifecycle on both backends."""
        await _upgrade_to(backend_url, "head")

        async with engine.begin() as conn:
            rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
            assert MERGE_REVISION in {r[0] for r in rows}
            for table in ("workflow_definition_versions", "workflow_v2_runs", "workflow_tasks", "workflow_lease_audit", "workflow_v2_events", "workflow_commands", "runs"):
                exists = (
                    await conn.execute(
                        text("SELECT count(*) FROM information_schema.tables WHERE table_name = :t" if backend == "postgres" else "SELECT count(*) FROM sqlite_master WHERE type='table' AND name = :t"),
                        {"t": table},
                    )
                ).scalar_one()
                assert exists == 1, f"{table} missing after upgrade on {backend}"

        store = WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
        run_repo = RunRepository(async_sessionmaker(engine, expire_on_commit=False))
        await _drive_full_lifecycle(store, run_repo, engine)

    async def test_existing_workflow_v2_shape_upgrade_keeps_data_readable(self, backend: str, backend_url: str, engine) -> None:
        """Existing-DB path: a database parked at the 20260715 workflow-v2
        shape upgrades to head with its rows intact and readable -- the
        20260825 (``workflow_v2_runs.model_name``) and 20260828
        (``run_resource_snapshots.selection_role``) additions land as
        NULL/default backfills and the store keeps working on top.

        Every table that exists at the 20260715 shape carries a seeded
        legacy row (definitions, runs, tasks, events, commands) plus a
        shared-``runs`` row, and each is read back through its public seam
        after the upgrade. ``workflow_lease_audit`` cannot be seeded here:
        the 20260715 revision does not create it yet (later revisions do),
        so its upgrade path is covered by the fresh-DB test.
        """
        # Park the database at the 20260715 revision (workflow-v2 tables at
        # their initial shape; run_resource_snapshots does not exist yet).
        await _upgrade_to(backend_url, "20260715_workflow_v2")

        seed_session = async_sessionmaker(engine, expire_on_commit=False)()
        async with seed_session.begin():
            await seed_session.execute(
                text("INSERT INTO workflow_definition_versions (id, workflow_name, version, definition, content_hash, created_by, created_at) VALUES ('def-1', 'verify-flow', 1, '{}', 'hash-old', 'admin', CURRENT_TIMESTAMP)")
            )
            await seed_session.execute(
                text(
                    "INSERT INTO workflow_v2_runs (run_id, workflow_name, definition_version, checkpoint_thread_id, status, inputs, snapshot, created_by, created_at, updated_at) "
                    "VALUES ('t02-legacy-run', 'verify-flow', 1, 'wf-t02-legacy-run', 'completed', '{}', '{}', 'admin', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            await seed_session.execute(
                text("INSERT INTO workflow_tasks (task_id, run_id, status, attempts, cancel_requested) VALUES ('task-1', 't02-legacy-run', 'completed', 1, :false)"),
                {"false": False},
            )
            await seed_session.execute(text("INSERT INTO workflow_v2_events (id, run_id, seq, event_type, payload, created_at) VALUES ('ev-1', 't02-legacy-run', 1, 'run_started', '{}', CURRENT_TIMESTAMP)"))
            await seed_session.execute(text("INSERT INTO workflow_commands (command_id, run_id, command_type, payload, created_by, created_at) VALUES ('cmd-legacy-1', 't02-legacy-run', 'resume', '{}', 'admin', CURRENT_TIMESTAMP)"))
            await seed_session.execute(
                text(
                    "INSERT INTO runs (run_id, thread_id, user_id, status, multitask_strategy, metadata_json, kwargs_json, message_count, "
                    "total_input_tokens, total_output_tokens, total_tokens, llm_call_count, lead_agent_tokens, subagent_tokens, middleware_tokens, created_at, updated_at) "
                    "VALUES ('t02-legacy-shared-run', 'wf-t02-legacy-run', 'legacy-admin', 'error', 'reject', '{}', '{}', 0, 0, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
        await seed_session.close()

        # Bring the database to head: 20260814/20260825/20260828 run.
        await _upgrade_to(backend_url, "head")

        async with engine.begin() as conn:
            head_rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).fetchall()
            assert {r[0] for r in head_rows} == {MERGE_REVISION}

        store = WorkflowV2Store(async_sessionmaker(engine, expire_on_commit=False))
        run = await store.get_run("t02-legacy-run")
        assert run is not None
        assert run.status == "completed"
        assert run.model_name is None  # the 20260825 column backfilled NULL
        definition = await store.get_definition("verify-flow", 1)
        assert definition is not None and definition.content_hash == "hash-old"
        events = await store.list_events("t02-legacy-run")
        assert [e.event_type for e in events] == ["run_started"]
        legacy_command = await store.get_command("cmd-legacy-1")
        assert legacy_command is not None and legacy_command.command_type == "resume"
        assert await store.latest_command("t02-legacy-run", "resume") is not None
        shared = await RunRepository(async_sessionmaker(engine, expire_on_commit=False)).get("t02-legacy-shared-run", user_id="legacy-admin")
        assert shared is not None and shared["status"] == "error"

        # New writes work alongside the upgraded rows. The event counter on
        # the run row (event_seq) mirrors what the 20260715-era store had
        # recorded: one event appended, so the counter must be at 1.
        seed_session = async_sessionmaker(engine, expire_on_commit=False)()
        async with seed_session.begin():
            await seed_session.execute(text("UPDATE workflow_v2_runs SET event_seq = 1 WHERE run_id = 't02-legacy-run'"))
        await seed_session.close()
        await store.append_event("t02-legacy-run", "run_completed", {})
        assert len(await store.list_events("t02-legacy-run")) == 2


# ---------------------------------------------------------------------------
# Gateway canonical-run path over the migrated schema
# ---------------------------------------------------------------------------

MINIMAL_DEFINITION = {
    "schema_version": 2,
    "name": "t02-canonical-flow",
    "description": "Minimal canonical workflow for the DB-execution ticket",
    "inputs": {},
    "state": {},
    "entrypoint": "work",
    "nodes": [
        {
            "id": "work",
            "type": "action",
            "action": {"kind": "agent", "name": "t02-agent"},
        }
    ],
    "edges": [],
}


class TestCanonicalRunGatewayPathOnMigratedSchema:
    async def test_canonical_run_freezes_closure_and_worker_takes_over_lease(self, backend: str, backend_url: str, engine) -> None:
        """The Gateway's canonical preparation over the MIGRATED schema (not
        create_all): ResourceService publish flow -> ``create_canonical_run``
        -> ``run_resource_snapshots`` rows carrying the 20260828
        ``selection_role`` column -- its real write path -- then the Worker
        lease claim / expiry takeover / stale-worker-blocked cycle audited in
        ``workflow_lease_audit``.
        """
        await _upgrade_to(backend_url, "head")
        factory = async_sessionmaker(engine, expire_on_commit=False)

        # The migrated schema enforces resources.owner_id -> users_ext (the
        # SQLite create_all suites never see this), so seed the owner first.
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO users_ext (id, username, role, disabled) VALUES ('owner-1', 'owner-1', 'super_admin', :false)"),
                {"false": False},
            )

        # Publish workflow -> agent -> skill through ResourceService and wire
        # the dependency closure, exactly as the catalog admin flow does.
        admin = ResourceActor(
            user_id="owner-1",
            department_id=None,
            role="super_admin",
            permissions=frozenset({ResourceAction.READ, ResourceAction.WRITE, ResourceAction.USE}),
            tool_groups=None,
        )
        async with factory() as session:
            service = ResourceService(session, admin)
            skill, _ = await publish_resource(service, resource_type="skill", slug="t02-skill", storage_kind="filesystem", content={"name": "t02-skill", "description": "skill"})
            agent, _ = await publish_resource(service, resource_type="agent", slug="t02-agent", storage_kind="filesystem", content={"name": "t02-agent", "description": "agent"})
            workflow, _ = await publish_resource(service, resource_type="workflow", slug="t02-canonical-flow", storage_kind="database", content=MINIMAL_DEFINITION)
            await service.replace_dependencies(agent.id, [skill.id])
            await service.replace_dependencies(workflow.id, [agent.id])
            await session.commit()
            catalog = {"workflow": workflow.id, "agent": agent.id, "skill": skill.id}

        store = WorkflowV2Store(factory)
        owner = ResourceActor(
            user_id="owner-1",
            department_id=None,
            role="super_admin",
            permissions=frozenset({ResourceAction.READ, ResourceAction.USE}),
            tool_groups=None,
        )
        run = await store.create_canonical_run("t02-canonical-1", catalog["workflow"], {}, owner, model_name="t02-model")
        assert run.status == "queued" and run.model_name == "t02-model"

        # run_resource_snapshots: three frozen rows, root workflow plus the
        # resolved agent/skill closure, all at the published version.
        async with engine.begin() as conn:
            snapshot_rows = (await conn.execute(text("SELECT resource_id, version, selection_role FROM run_resource_snapshots WHERE run_id = 't02-canonical-1'"))).fetchall()
        assert len(snapshot_rows) == 3
        assert {r[2] for r in snapshot_rows} == {"root", "resolved"}
        assert next(r for r in snapshot_rows if r[0] == catalog["workflow"])[2] == "root"
        assert all(r[1] == 1 for r in snapshot_rows)

        # Worker lifecycle on the canonical run: worker-a claims, its lease
        # expires, worker-b takes the same task over, and the stale worker is
        # blocked from finishing while worker-b finalizes the run.
        started = datetime.now(UTC)
        first = await store.claim_next_task("worker-a", now=started, lease_seconds=1)
        assert first is not None and first.run_id == "t02-canonical-1"
        second = await store.claim_next_task("worker-b", now=started + timedelta(seconds=2), lease_seconds=30)
        assert second is not None and second.task_id == first.task_id
        assert await store.finish_task(first.task_id, "completed", None, "worker-a") is False
        assert await store.finish_task(second.task_id, "completed", None, "worker-b") is True
        finished = await store.get_run("t02-canonical-1")
        assert finished is not None and finished.status == "completed"

        async with engine.begin() as conn:
            audit = (await conn.execute(text("SELECT event_type, worker_id FROM workflow_lease_audit WHERE run_id = 't02-canonical-1' ORDER BY created_at, id"))).fetchall()
        assert audit == [
            ("claimed", "worker-a"),
            ("taken_over", "worker-b"),
            ("released", "worker-b"),
        ]
