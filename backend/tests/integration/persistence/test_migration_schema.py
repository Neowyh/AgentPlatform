"""Integration tests for the unified Alembic migration chain.

One forward-only chain joins the AgentPlatform control-plane revisions and
the DeerFlow runtime revisions (merge revision
``20260908_unify_migration_chains``), tracked in the single default
``alembic_version`` table. Tests cover:

- Full upgrade from an empty database to the single head
- Head identity: ``alembic heads`` reports exactly the merge revision
- Head schema covers the full ORM metadata (both table families)
- Idempotent re-upgrade (``upgrade head`` at head is a no-op)
- Gateway bootstrap after the CLI upgrade is a no-op and vice versa

Downgrade round-trips are deliberately absent: the convergence plan pins
migrations as forward-only (收敛方案 Gate 5), and the two branches share
table names (runs/threads_meta/run_events/feedback/users), so downgrade past
the merge revision is not a supported operation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from deerflow.persistence.migrations._chain_meta import (
    CONTROL_PLANE_HEAD,
    DEERFLOW_VERSION_TABLE,
    MERGE_REVISION,
    RUNTIME_HEAD,
    VERSION_TABLE,
)
from tests._migration_test_support import unified_alembic_config

CURRENT_HEAD = "20260916_knowledge_evaluation"

# The alembic URL uses the async driver.  For post-migration verification
# we open the same SQLite file with a synchronous engine (no greenlet needed).
_ASYNC_PREFIX = "sqlite+aiosqlite:///"
_SYNC_PREFIX = "sqlite:///"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_alembic_config(db_url: str):
    """Alembic config pointing at the unified migration scripts (shared helper)."""
    return unified_alembic_config(db_url)


def get_head_revision() -> str:
    """Return the unified chain's head revision identifier."""
    return ScriptDirectory.from_config(make_alembic_config("sqlite+aiosqlite:///:memory:")).get_current_head()


def _sync_url(async_url: str) -> str:
    """Convert sqlite+aiosqlite:///path to sqlite:///path for sync reads."""
    assert async_url.startswith(_ASYNC_PREFIX)
    return _SYNC_PREFIX + async_url[len(_ASYNC_PREFIX) :]


def _get_table_names(db_url: str) -> set[str]:
    engine = create_engine(_sync_url(db_url))
    try:
        with engine.connect() as conn:
            return set(inspect(conn).get_table_names())
    finally:
        engine.dispose()


def _get_version_rows(db_url: str) -> dict[str, list[str]]:
    """Return {version_table: rows} for both the unified and legacy tables."""
    engine = create_engine(_sync_url(db_url))
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            rows: dict[str, list[str]] = {}
            for table in (VERSION_TABLE, DEERFLOW_VERSION_TABLE):
                if table in tables:
                    rows[table] = [str(r[0]) for r in conn.execute(text(f"SELECT version_num FROM {table}")).fetchall()]
            return rows
    finally:
        engine.dispose()


async def _bootstrap_schema(db_url: str) -> None:
    """Run the Gateway bootstrap (init_engine's schema step) against *db_url*."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from deerflow.persistence.bootstrap import bootstrap_schema

    engine = create_async_engine(db_url)
    try:
        await bootstrap_schema(engine, backend="sqlite")
    finally:
        await engine.dispose()


def _full_orm_tables() -> set[str]:
    """All ORM tables the Gateway registers: runtime + enterprise models."""
    import app.gateway.app  # noqa: F401  -- registers enterprise models
    import deerflow.persistence.models  # noqa: F401  -- registers runtime models
    from deerflow.persistence.base import Base

    return set(Base.metadata.tables.keys())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.serial
class TestUnifiedMigrationChain:
    """Integration tests for the unified Alembic migration chain."""

    def test_single_head_is_the_merge_revision(self) -> None:
        script = ScriptDirectory.from_config(make_alembic_config("sqlite+aiosqlite:///:memory:"))
        assert list(script.get_heads()) == [CURRENT_HEAD]
        merge = script.get_revision(MERGE_REVISION)
        assert set(merge._normalized_down_revisions) == {CONTROL_PLANE_HEAD, RUNTIME_HEAD}

    def test_upgrade_from_scratch_to_head(self, tmp_path: Path) -> None:
        """One ``alembic upgrade head`` takes an empty DB to the single head."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        command.upgrade(make_alembic_config(db_url), "head")

        tables = _get_table_names(db_url)
        expected = _full_orm_tables()
        assert tables >= expected, f"Missing tables: {expected - tables}"

        versions = _get_version_rows(db_url)
        assert versions.get(VERSION_TABLE) == [CURRENT_HEAD]
        # The dual-chain era's dedicated table must not come back.
        assert DEERFLOW_VERSION_TABLE not in versions

    def test_head_schema_matches_full_orm_metadata(self, tmp_path: Path) -> None:
        """Every ORM table + column (both families) exists in the DB at head."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        command.upgrade(make_alembic_config(db_url), "head")

        engine = create_engine(_sync_url(db_url))
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                db_table_names = set(inspector.get_table_names()) - {VERSION_TABLE}
                from deerflow.persistence.base import Base

                for table_name in sorted(_full_orm_tables()):
                    assert table_name in db_table_names, f"ORM table {table_name} missing from DB"
                    db_cols = {c["name"] for c in inspector.get_columns(table_name)}
                    orm_cols = set(Base.metadata.tables[table_name].columns.keys())
                    missing = orm_cols - db_cols
                    assert not missing, f"Columns of {table_name} missing from DB: {missing}"
        finally:
            engine.dispose()

    def test_re_upgrade_at_head_is_a_noop(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")

        assert _get_version_rows(db_url).get(VERSION_TABLE) == [CURRENT_HEAD]

    @pytest.mark.asyncio
    async def test_gateway_bootstrap_after_cli_upgrade_is_a_noop(self, tmp_path: Path) -> None:
        """serve.sh upgrades first, then the Gateway's bootstrap must observe
        the unified head and do nothing (versioned branch).
        """
        from sqlalchemy.ext.asyncio import create_async_engine

        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        command.upgrade(make_alembic_config(db_url), "head")

        engine = create_async_engine(db_url)
        try:
            await _bootstrap_schema(db_url)
            assert _get_version_rows(db_url).get(VERSION_TABLE) == [CURRENT_HEAD]
            assert DEERFLOW_VERSION_TABLE not in _get_version_rows(db_url)

            # Second bootstrap run: still a no-op.
            await _bootstrap_schema(db_url)
            assert _get_version_rows(db_url).get(VERSION_TABLE) == [CURRENT_HEAD]
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_gateway_bootstrap_on_runtime_head_database(self, tmp_path: Path) -> None:
        """A pre-unification Gateway DB (runtime head in the dedicated table,
        enterprise tables from create_all) is restamped to both branch heads
        by the bridge; the upgrade then runs only the merge revision.
        """
        from sqlalchemy import text

        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # Shape the legacy state directly: full ORM tables via create_all
        # (mirrors the Gateway's empty branch) + a dedicated runtime version
        # table at the runtime head, no unified version table.
        import deerflow.persistence.models  # noqa: F401
        from deerflow.persistence.base import Base

        sync_engine = create_engine(_sync_url(db_url))
        try:
            Base.metadata.create_all(sync_engine)
            with sync_engine.begin() as conn:
                conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
                conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('{RUNTIME_HEAD}')"))
        finally:
            sync_engine.dispose()

        await _bootstrap_schema(db_url)

        versions = _get_version_rows(db_url)
        assert versions.get(VERSION_TABLE) == [CURRENT_HEAD]
        assert DEERFLOW_VERSION_TABLE not in versions

    def test_create_all_current_database_stamps_merge(self, tmp_path: Path) -> None:
        """Crash-recovery pin: a database whose tables carry *current* model
        shapes but no version rows (an interrupted empty-branch bootstrap)
        must be stamped to the merge position, not replayed.

        Replaying the chain against create_all-shaped tables crashes on the
        unguarded ``create_table`` revisions and on SQLite batch
        ``add_column`` (alembic assumes the column is new and builds a
        contradictory column-order dependency -- the
        ``CircularDependencyError`` seen on ``f3a2b1c4d5e6`` against
        ``users_ext``). The bridge's create_all-current check recognizes the
        shape and stamps ``MERGE_REVISION`` directly.
        """
        import deerflow.persistence.models  # noqa: F401  -- registers runtime models
        from deerflow.persistence.base import Base

        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        sync_engine = create_engine(_sync_url(db_url))
        try:
            Base.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        command.upgrade(make_alembic_config(db_url), "head")

        assert _get_version_rows(db_url).get(VERSION_TABLE) == [CURRENT_HEAD]
        # The stamp must not have created anything new: table set unchanged.
        engine = create_engine(_sync_url(db_url))
        try:
            with engine.connect() as conn:
                assert set(Base.metadata.tables).issubset({r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()})
        finally:
            engine.dispose()

    def test_pre_alembic_enterprise_database_upgrades_to_head(self, tmp_path: Path) -> None:
        """The earliest enterprise deployments (pre-2026-06-03, before the
        control-plane chain started recording versions) carry only the
        hand-provisioned core tables -- departments, users_ext (without the
        later ``disabled`` column), and the runtime core five -- and no
        ``alembic_version`` row. A single CLI ``upgrade head`` must take
        that database to the merge head.

        The runtime branch replays from base (``0001_baseline`` is
        create_table-guarded, the post-baseline column revisions idempotent
        via ``safe_add_column``) and the control-plane branch creates the
        resource/workflow/audit families from scratch.
        """
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        sync_engine = create_engine(_sync_url(db_url))
        try:
            with sync_engine.begin() as conn:
                # The control-plane core family (16147afec43b's DDL) at its
                # pre-2026-06-03 shape.
                conn.execute(text("CREATE TABLE departments (id VARCHAR(36) NOT NULL PRIMARY KEY, name VARCHAR(128) NOT NULL UNIQUE, description VARCHAR(512), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"))
                conn.execute(
                    text(
                        "CREATE TABLE users_ext ("
                        "id VARCHAR(36) NOT NULL PRIMARY KEY, "
                        "username VARCHAR(128) NOT NULL UNIQUE, "
                        "role VARCHAR(32), "
                        "department_id VARCHAR(36) REFERENCES departments(id), "
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                        "last_login DATETIME)"
                    )
                )
                # The runtime core five as the era's create_all produced them
                # (pre-#3658: no token_usage_by_model; nullable columns).
                conn.execute(
                    text(
                        "CREATE TABLE users ("
                        "id VARCHAR(36) NOT NULL PRIMARY KEY, "
                        "email VARCHAR(320) NOT NULL, "
                        "password_hash VARCHAR(128), "
                        "system_role VARCHAR(16) NOT NULL, "
                        "created_at DATETIME NOT NULL, "
                        "oauth_provider VARCHAR(32), "
                        "oauth_id VARCHAR(128), "
                        "needs_setup BOOLEAN NOT NULL, "
                        "token_version INTEGER NOT NULL)"
                    )
                )
                conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
                conn.execute(
                    text(
                        "CREATE TABLE runs ("
                        "run_id VARCHAR(64) NOT NULL PRIMARY KEY, "
                        "thread_id VARCHAR(64) NOT NULL, "
                        "assistant_id VARCHAR(128), "
                        "user_id VARCHAR(64), "
                        "status VARCHAR(20), "
                        "model_name VARCHAR(128), "
                        "multitask_strategy VARCHAR(20), "
                        "metadata_json JSON, "
                        "kwargs_json JSON, "
                        "error TEXT, "
                        "message_count INTEGER, "
                        "first_human_message TEXT, "
                        "last_ai_message TEXT, "
                        "total_input_tokens INTEGER, "
                        "total_output_tokens INTEGER, "
                        "total_tokens INTEGER, "
                        "llm_call_count INTEGER, "
                        "lead_agent_tokens INTEGER, "
                        "subagent_tokens INTEGER, "
                        "middleware_tokens INTEGER, "
                        "follow_up_to_run_id VARCHAR(64), "
                        "created_at DATETIME, "
                        "updated_at DATETIME)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TABLE threads_meta ("
                        "thread_id VARCHAR(64) NOT NULL PRIMARY KEY, "
                        "assistant_id VARCHAR(128), "
                        "user_id VARCHAR(64), "
                        "display_name VARCHAR(256), "
                        "status VARCHAR(20), "
                        "metadata_json JSON, "
                        "created_at DATETIME, "
                        "updated_at DATETIME)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TABLE run_events ("
                        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
                        "thread_id VARCHAR(64) NOT NULL, "
                        "run_id VARCHAR(64) NOT NULL, "
                        "user_id VARCHAR(64), "
                        "event_type VARCHAR(32) NOT NULL, "
                        "category VARCHAR(16) NOT NULL, "
                        "content TEXT, "
                        "event_metadata JSON, "
                        "seq INTEGER NOT NULL, "
                        "created_at DATETIME, "
                        "CONSTRAINT uq_events_thread_seq UNIQUE (thread_id, seq))"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TABLE feedback ("
                        "feedback_id VARCHAR(64) NOT NULL PRIMARY KEY, "
                        "run_id VARCHAR(64) NOT NULL, "
                        "thread_id VARCHAR(64) NOT NULL, "
                        "user_id VARCHAR(64), "
                        "message_id VARCHAR(64), "
                        "rating INTEGER NOT NULL, "
                        "comment TEXT, "
                        "created_at DATETIME, "
                        "CONSTRAINT uq_feedback_thread_run_user UNIQUE (thread_id, run_id, user_id))"
                    )
                )
        finally:
            sync_engine.dispose()

        command.upgrade(make_alembic_config(db_url), "head")

        assert _get_version_rows(db_url).get(VERSION_TABLE) == [CURRENT_HEAD]
        engine = create_engine(_sync_url(db_url))
        try:
            with engine.connect() as conn:
                tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
                # The control-plane family landed...
                for expected in ("resource_metadata", "resources", "resource_versions", "workflow_v2_runs", "run_resource_snapshots", "audit_logs", "skill_applications"):
                    assert expected in tables, f"{expected} missing after upgrade"
                # ...the runtime family landed (its post-baseline revisions
                # replayed over the pre-#3658 core five)...
                for expected in ("channel_connections", "agents", "mcp_tasks", "scheduled_tasks", "personal_access_tokens", "subagent_batches"):
                    assert expected in tables, f"{expected} missing after upgrade"
                # ...and the drifted core shapes were repaired, not duplicated.
                runs_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(runs)")).fetchall()]
                assert runs_cols.count("token_usage_by_model") == 1
                assert runs_cols.count("stop_reason") == 1
                users_ext_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users_ext)")).fetchall()]
                assert users_ext_cols.count("disabled") == 1
        finally:
            engine.dispose()
