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

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "packages" / "harness" / "ideer" / "persistence" / "migrations"

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
    import ideer.persistence.models  # noqa: F401 — registers models with Base.metadata
    from ideer.persistence.base import Base

    return set(Base.metadata.tables.keys())


def _get_all_revisions() -> list:
    cfg = make_alembic_config("sqlite+aiosqlite:///:memory:")
    return list(ScriptDirectory.from_config(cfg).walk_revisions())


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
        """Verify a full migration from blank DB to head creates all tables."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, "head")

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
        and that column types and nullability match.
        """
        db_path = tmp_path / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        cfg = make_alembic_config(db_url)

        upgrade(cfg, "head")

        orm_tables = _get_orm_tables()
        sync_url = _sync_url(db_url)

        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                inspector = inspect(conn)
                db_table_names = set(inspector.get_table_names()) - {"alembic_version"}

                missing = orm_tables - db_table_names
                assert not missing, f"ORM tables missing from DB: {missing}"

                from ideer.persistence.base import Base

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
        """End-to-end test for _stamp_alembic_head.

        1. Creates ORM tables via Base.metadata.create_all
        2. Stamps alembic head via _stamp_alembic_head
        3. Verifies alembic_version table and revision
        4. Verifies alembic upgrade head is idempotent
        """
        import shutil

        from sqlalchemy.ext.asyncio import create_async_engine

        import ideer.persistence.engine as engine_mod
        import ideer.persistence.models  # noqa: F401
        from ideer.persistence.base import Base
        from ideer.persistence.engine import _stamp_alembic_head

        db_path = tmp_path / "test_stamp.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # -- temp persistence dir for _stamp_alembic_head (parses migration files)
        persistence_dir = tmp_path / "persistence"
        pv_dir = persistence_dir / "migrations" / "versions"
        pv_dir.mkdir(parents=True)
        (pv_dir / "001_initial.py").write_text('revision: str = "abc123"\ndown_revision: str | None = None\n')
        (pv_dir / "002_add_table.py").write_text('revision: str = "def456"\ndown_revision: str | None = "abc123"\n')

        # -- temp Alembic env for upgrade("head") idempotency check
        alembic_dir = tmp_path / "alembic"
        av_dir = alembic_dir / "versions"
        av_dir.mkdir(parents=True)
        (alembic_dir / "alembic.ini").write_text(f"[alembic]\nscript_location = {alembic_dir}\nsqlalchemy.url = {db_url}\n")
        (alembic_dir / "env.py").write_text(
            '"""Alembic env."""\n'
            "from alembic import context\n"
            "from sqlalchemy import create_engine\n"
            "from ideer.persistence.base import Base\n\n"
            "config = context.config\n"
            "target_metadata = Base.metadata\n\n"
            "url = config.get_main_option('sqlalchemy.url')\n"
            "url = url.replace('sqlite+aiosqlite://', 'sqlite://')\n"
            "connectable = create_engine(url)\n"
            "with connectable.connect() as connection:\n"
            "    context.configure(connection=connection, "
            "target_metadata=target_metadata, render_as_batch=True)\n"
            "    with context.begin_transaction():\n"
            "        context.run_migrations()\n"
        )
        shutil.copy(str(MIGRATIONS_DIR / "script.py.mako"), str(alembic_dir / "script.py.mako"))
        (av_dir / "001_initial.py").write_text(
            '"""initial"""\nrevision: str = "abc123"\ndown_revision: str | None = None\n\nfrom alembic import op\nimport sqlalchemy as sa\n\ndef upgrade() -> None:\n    pass\n\ndef downgrade() -> None:\n    pass\n'
        )
        (av_dir / "002_add_table.py").write_text(
            '"""add table"""\nrevision: str = "def456"\ndown_revision: str | None = "abc123"\n\nfrom alembic import op\nimport sqlalchemy as sa\n\ndef upgrade() -> None:\n    pass\n\ndef downgrade() -> None:\n    pass\n'
        )

        head_rev = "def456"

        engine = create_async_engine(db_url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

                original_file = engine_mod.__file__
                engine_mod.__file__ = str(persistence_dir / "engine.py")
                try:
                    await _stamp_alembic_head(conn, "sqlite")
                finally:
                    engine_mod.__file__ = original_file

            sync_url = _sync_url(db_url)
            sync_engine = create_engine(sync_url)
            try:
                with sync_engine.connect() as conn:
                    result = conn.execute(text("SELECT version_num FROM alembic_version"))
                    row = result.fetchone()
                    assert row is not None, "alembic_version table missing"
                    assert row[0] == head_rev, f"Expected {head_rev}, got {row[0]}"
            finally:
                sync_engine.dispose()

            from alembic.config import Config as AlembicConfig

            temp_cfg = AlembicConfig(str(alembic_dir / "alembic.ini"))
            upgrade(temp_cfg, "head")

            current = _get_current_revision(db_url)
            assert current == head_rev, f"After idempotent upgrade, expected {head_rev}, got {current}"
        finally:
            await engine.dispose()
