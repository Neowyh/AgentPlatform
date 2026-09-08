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
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from deerflow.persistence.migrations._chain_meta import (
    CONTROL_PLANE_HEAD,
    DEERFLOW_VERSION_TABLE,
    MERGE_REVISION,
    RUNTIME_HEAD,
    VERSION_TABLE,
    version_locations,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "packages" / "harness" / "deerflow" / "persistence" / "migrations"

# The alembic URL uses the async driver.  For post-migration verification
# we open the same SQLite file with a synchronous engine (no greenlet needed).
_ASYNC_PREFIX = "sqlite+aiosqlite:///"
_SYNC_PREFIX = "sqlite:///"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_alembic_config(db_url: str) -> AlembicConfig:
    """Build an Alembic config pointing at the unified migration scripts.

    Built as a bare config (not from ``alembic.ini``) with an explicit URL so
    the tests never touch a real deployment database, and with
    ``version_locations`` mirroring the ini so both version directories are
    visible.
    """
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("path_separator", "space")
    cfg.set_main_option("version_locations", version_locations(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


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
        assert list(script.get_heads()) == [MERGE_REVISION]
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
        assert versions.get(VERSION_TABLE) == [MERGE_REVISION]
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

        assert _get_version_rows(db_url).get(VERSION_TABLE) == [MERGE_REVISION]

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
            assert _get_version_rows(db_url).get(VERSION_TABLE) == [MERGE_REVISION]
            assert DEERFLOW_VERSION_TABLE not in _get_version_rows(db_url)

            # Second bootstrap run: still a no-op.
            await _bootstrap_schema(db_url)
            assert _get_version_rows(db_url).get(VERSION_TABLE) == [MERGE_REVISION]
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
        assert versions.get(VERSION_TABLE) == [MERGE_REVISION]
        assert DEERFLOW_VERSION_TABLE not in versions
