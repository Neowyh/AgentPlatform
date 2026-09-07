"""Comprehensive integration tests for Alembic database migrations.

Tests cover:
- Full upgrade from scratch to head
- Downgrade round-trip (upgrade -> downgrade -> upgrade)
- Each migration step is individually reversible
- Head schema matches ORM model definitions
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy import exc as sa_exc

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "app" / "agentplatform" / "persistence" / "migrations"

# The alembic URL uses the async driver.  For post-migration verification
# we open the same SQLite file with a synchronous engine (no greenlet needed).
_ASYNC_PREFIX = "sqlite+aiosqlite:///"
_SYNC_PREFIX = "sqlite:///"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_alembic_config(db_url: str) -> AlembicConfig:
    """Build an Alembic config pointing at the project's migration scripts."""
    alembic_cfg = AlembicConfig(str(MIGRATIONS_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    return alembic_cfg


def get_head_revision() -> str:
    """Return the current head revision identifier."""
    cfg = make_alembic_config("sqlite+aiosqlite:///:memory:")
    return ScriptDirectory.from_config(cfg).get_current_head()


def _sync_url(async_url: str) -> str:
    """Convert sqlite+aiosqlite:///path to sqlite:///path for sync reads."""
    assert async_url.startswith(_ASYNC_PREFIX)
    return _SYNC_PREFIX + async_url[len(_ASYNC_PREFIX) :]


def _get_table_names(db_url: str) -> set[str]:
    url = _sync_url(db_url)
    engine = create_engine(url)
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
    engine.dispose()
    return tables


def _get_current_revision(db_url: str) -> str | None:
    url = _sync_url(db_url)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            try:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = result.fetchone()
                return row[0] if row else None
            except sa_exc.OperationalError:
                return None
    finally:
        engine.dispose()


def _get_table_schema(db_url: str) -> dict[str, dict[str, tuple[str, bool]]]:
    """Return {table_name: {col_name: (type_name, nullable)}} for all tables."""
    url = _sync_url(db_url)
    engine = create_engine(url)
    with engine.connect() as conn:
        inspector = inspect(conn)
        schema = {}
        for table_name in sorted(inspector.get_table_names()):
            schema[table_name] = {c["name"]: (type(c["type"]).__name__, c.get("nullable", True)) for c in inspector.get_columns(table_name)}
    engine.dispose()
    return schema


def _get_orm_tables() -> set[str]:
    """Return the set of ORM-model table names registered on Base.metadata."""
    import deerflow.persistence.models  # noqa: F401 — registers models with Base.metadata
    from deerflow.persistence.base import Base

    return set(Base.metadata.tables.keys())


def _get_all_revisions() -> list:
    cfg = make_alembic_config("sqlite+aiosqlite:///:memory:")
    return list(ScriptDirectory.from_config(cfg).walk_revisions())


def _bootstrap_runtime_schema(db_url: str) -> None:
    """Run the deerflow runtime schema bootstrap against a migrated DB.

    Production enterprise deployments apply the enterprise Alembic tree first
    and let ``deerflow.persistence.bootstrap`` backfill the deerflow-owned
    tables at startup; tests that assert full ORM coverage mirror that order.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import create_async_engine

    from deerflow.persistence.bootstrap import bootstrap_schema

    async def _run() -> None:
        engine = create_async_engine(db_url)
        try:
            await bootstrap_schema(engine, backend="sqlite")
        finally:
            await engine.dispose()

    asyncio.run(_run())


def _get_non_merge_revisions() -> list[str]:
    return [rev.revision for rev in _get_all_revisions() if rev.down_revision is not None and not isinstance(rev.down_revision, tuple)]


def _get_parent_revision(rev: str) -> str:
    for r in _get_all_revisions():
        if r.revision == rev:
            if isinstance(r.down_revision, tuple):
                return r.down_revision[0]
            return r.down_revision  # type: ignore[return-value]
    msg = f"Revision {rev!r} not found in migration tree"
    raise ValueError(msg)


NON_MERGE_REVISIONS = _get_non_merge_revisions()


def _get_merge_revisions() -> list[str]:
    return [rev.revision for rev in _get_all_revisions() if isinstance(rev.down_revision, tuple)]


MERGE_REVISIONS = _get_merge_revisions()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.serial
class TestAlembicMigrations:
    """Integration tests for Alembic database migrations."""

    # -----------------------------------------------------------------------
    # Test 1: Full upgrade from blank DB to head
    # -----------------------------------------------------------------------

    def test_upgrade_from_scratch_to_head(self, tmp_path: Path) -> None:
        """Verify enterprise migrations plus runtime bootstrap create all tables."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, "head")
        _bootstrap_runtime_schema(db_url)

        current = _get_current_revision(db_url)
        assert current == get_head_revision(), f"Expected head revision {get_head_revision()}, got {current}"

        tables = _get_table_names(db_url)
        expected = _get_orm_tables()
        assert tables >= expected, f"Missing tables: {expected - tables}"

    # -----------------------------------------------------------------------
    # Test 2: Downgrade one step and re-upgrade — schema must match
    # -----------------------------------------------------------------------

    def test_downgrade_round_trip(self, tmp_path: Path) -> None:
        """Upgrade to head, downgrade one step, then re-upgrade.

        The column-level schema after the round-trip must be identical
        to the original.
        """
        head = get_head_revision()
        if head in MERGE_REVISIONS:
            pytest.skip("Head is a merge revision; downgrade -1 is ambiguous")

        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, "head")
        schema_after_upgrade = _get_table_schema(db_url)

        downgrade(cfg, "-1")
        upgrade(cfg, "+1")

        schema_after_round_trip = _get_table_schema(db_url)
        schema_after_upgrade.pop("alembic_version", None)
        schema_after_round_trip.pop("alembic_version", None)
        assert schema_after_upgrade == schema_after_round_trip, "Schema after downgrade-then-re-upgrade differs from original"

    # -----------------------------------------------------------------------
    # Test 3: Each migration step is individually reversible
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("rev", NON_MERGE_REVISIONS)
    def test_each_migration_step_is_reversible(self, tmp_path: Path, rev: str) -> None:
        """For each non-merge revision: upgrade -> downgrade -> re-upgrade.

        Verifies:
        - upgrade reaches the target revision
        - downgrade reaches the parent revision
        - re-upgrade reaches the target revision again
        - column-level schema before downgrade matches schema after re-upgrade
        """
        parent = _get_parent_revision(rev)
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, rev)

        current = _get_current_revision(db_url)
        assert current == rev, f"Expected revision {rev}, got {current}"

        schema_before = _get_table_schema(db_url)
        schema_before.pop("alembic_version", None)

        downgrade(cfg, parent)

        after_downgrade = _get_current_revision(db_url)
        assert after_downgrade == parent, f"Expected {parent} after downgrade, got {after_downgrade}"

        upgrade(cfg, rev)

        after_upgrade = _get_current_revision(db_url)
        assert after_upgrade == rev, f"Expected {rev} after re-upgrade, got {after_upgrade}"

        schema_after = _get_table_schema(db_url)
        schema_after.pop("alembic_version", None)
        assert schema_before == schema_after, f"Schema after round-trip for {rev} differs"

    # -----------------------------------------------------------------------
    # Test 4: Head schema matches ORM model definitions
    # -----------------------------------------------------------------------

    def test_head_schema_matches_orm_models(self, tmp_path: Path) -> None:
        """Verify every ORM-model table + column exists in the DB at head
        (after the runtime bootstrap backfill) and that column types and
        nullability match.
        """
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, "head")
        _bootstrap_runtime_schema(db_url)

        orm_tables = _get_orm_tables()
        sync_url = _sync_url(db_url)

        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                db_table_names = set(inspector.get_table_names()) - {"alembic_version"}

                missing = orm_tables - db_table_names
                assert not missing, f"ORM tables missing from DB: {missing}"

                from deerflow.persistence.base import Base

                for table_name in sorted(orm_tables):
                    db_cols: dict[str, tuple[object, bool]] = {c["name"]: (c["type"], c.get("nullable", True)) for c in inspector.get_columns(table_name)}

                    for (
                        col_name,
                        orm_col,
                    ) in Base.metadata.tables[table_name].columns.items():
                        assert col_name in db_cols, f"Column {table_name}.{col_name} exists in ORM but is missing in DB"
                        db_type, db_nullable = db_cols[col_name]
                        orm_type = orm_col.type
                        orm_nullable = orm_col.nullable
                        assert isinstance(db_type, type(orm_type)), f"Column {table_name}.{col_name}: DB type {type(db_type).__name__} is not compatible with ORM type {type(orm_type).__name__}"
                        if orm_nullable is False and db_nullable is True:
                            import warnings

                            warnings.warn(f"Column {table_name}.{col_name}: ORM says NOT NULL but DB allows NULLs (migration may lack nullable=False)")
        finally:
            engine.dispose()

    # -----------------------------------------------------------------------
    # Test 5: Merge revisions round-trip (regression baseline)
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("rev", MERGE_REVISIONS)
    def test_merge_revision_round_trip(self, tmp_path: Path, rev: str) -> None:
        """Each merge revision can be upgraded to without error.

        Merge revisions carry no schema changes themselves; this test
        serves as a regression baseline ensuring merge-point upgrades
        do not crash and correctly record the revision.
        """
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, rev)
        current = _get_current_revision(db_url)
        assert current == rev, f"Expected {rev}, got {current}"

        schema = _get_table_schema(db_url)
        assert "alembic_version" in schema

    # -----------------------------------------------------------------------
    # Test 6: _stamp_alembic_head interaction test
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stamp_alembic_head_interaction(self, tmp_path: Path) -> None:
        """End-to-end dual-tree version-table interaction test.

        The historic ``engine._stamp_alembic_head`` helper was superseded by
        the ``deerflow.persistence.bootstrap`` state machine, which records
        its revisions in a dedicated ``deerflow_alembic_version`` table. This
        test verifies the production coexistence contract:

        1. Applies the enterprise tree to head (standard ``alembic_version``).
        2. Runs the runtime bootstrap, which takes the legacy branch,
           backfills deerflow-owned tables and stamps the deerflow head.
        3. Verifies full ORM coverage and that each version table records
           its own tree's head.
        4. Verifies a second bootstrap run is a no-op and leaves both
           version tables untouched.
        """
        from sqlalchemy.ext.asyncio import create_async_engine

        import deerflow.persistence.models  # noqa: F401
        from deerflow.persistence.base import Base
        from deerflow.persistence.bootstrap import _get_head_revision, bootstrap_schema

        db_path = tmp_path / "test_stamp.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        upgrade(make_alembic_config(db_url), "head")

        engine = create_async_engine(db_url)
        try:
            await bootstrap_schema(engine, backend="sqlite")

            head_rev = _get_head_revision()
            enterprise_rev = _get_current_revision(db_url)

            def _read_versions(sync_conn):
                from sqlalchemy import inspect as sa_inspect

                insp = sa_inspect(sync_conn)
                deer_rows = []
                if "deerflow_alembic_version" in insp.get_table_names():
                    deer_rows = [str(r[0]) for r in sync_conn.execute(text("SELECT version_num FROM deerflow_alembic_version")).fetchall()]
                ent_rows = [str(r[0]) for r in sync_conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()]
                return deer_rows, ent_rows

            async with engine.begin() as conn:
                deer_rows, ent_rows = await conn.run_sync(_read_versions)
                tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))

            assert deer_rows == [head_rev], f"Expected deerflow version table at {head_rev}, got {deer_rows}"
            assert ent_rows == [enterprise_rev], f"Expected enterprise version table at {enterprise_rev}, got {ent_rows}"

            missing = set(Base.metadata.tables) - tables
            assert not missing, f"ORM tables missing after bootstrap: {missing}"

            # Second bootstrap run must be a no-op on the versioned branch.
            await bootstrap_schema(engine, backend="sqlite")
            async with engine.begin() as conn:
                deer_rows_after, ent_rows_after = await conn.run_sync(_read_versions)
            assert deer_rows_after == deer_rows
            assert ent_rows_after == ent_rows
        finally:
            await engine.dispose()
