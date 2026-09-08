"""Unified-chain version-state adoption tests (PATCH-006 closed).

The two formerly independent migration chains (AgentPlatform control-plane,
DeerFlow runtime) are joined by ``20260908_unify_migration_chains`` and track
their state in the single default ``alembic_version`` table. The interim
``deerflow_alembic_version`` table from the dual-chain era is bridged into
``alembic_version`` by ``_chain_meta.adopt_unified_version_state`` before any
migration runs; these tests pin that bridge for every legacy database shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from deerflow.persistence.migrations._chain_meta import (
    CONTROL_PLANE_HEAD,
    DEERFLOW_VERSION_TABLE,
    MERGE_REVISION,
    RUNTIME_HEAD,
    VERSION_TABLE,
    adopt_unified_version_state,
    version_locations,
)

_MIGRATIONS_DIR = str(Path(__file__).resolve().parents[3] / "packages" / "harness" / "deerflow" / "persistence" / "migrations")


def _script_directory() -> ScriptDirectory:
    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("version_locations", version_locations(_MIGRATIONS_DIR))
    return ScriptDirectory.from_config(cfg)


def test_unified_chain_uses_default_version_table(tmp_path: Path) -> None:
    from deerflow.persistence.bootstrap import _get_alembic_config

    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    cfg = _get_alembic_config(engine)  # type: ignore[arg-type]
    # The bootstrap config no longer pins a dedicated table: the unified
    # chain reads the default ``alembic_version`` (env.py configures it).
    assert cfg.get_main_option("version_table") is None
    assert VERSION_TABLE == "alembic_version"


def test_merge_revision_joins_both_heads() -> None:
    script = _script_directory()
    assert script.get_current_head() == MERGE_REVISION
    merge = script.get_revision(MERGE_REVISION)
    assert set(merge._normalized_down_revisions) == {CONTROL_PLANE_HEAD, RUNTIME_HEAD}


def test_runtime_head_is_adopted_into_unified_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('{RUNTIME_HEAD}')"))
        adopt_unified_version_state(conn)
        rows = [r[0] for r in conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()]
        assert rows == [RUNTIME_HEAD]
        assert DEERFLOW_VERSION_TABLE not in inspect(conn).get_table_names()


def test_runtime_head_with_control_plane_ddl_restamps_both_branches(tmp_path: Path) -> None:
    """The pre-unification Gateway steady state: runtime head in the dedicated
    table, enterprise tables created by create_all, no ``alembic_version``.
    The bridge must restamp BOTH branch heads so the upgrade from the merge
    revision does not replay enterprise DDL.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE departments (id VARCHAR PRIMARY KEY)"))
        conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('{RUNTIME_HEAD}')"))
        adopt_unified_version_state(conn)
        rows = {r[0] for r in conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()}
        assert rows == {CONTROL_PLANE_HEAD, RUNTIME_HEAD}
        assert DEERFLOW_VERSION_TABLE not in inspect(conn).get_table_names()


def test_control_plane_head_is_adopted_as_is(tmp_path: Path) -> None:
    """The pre-convergence serve.sh shape: control-plane head in the shared
    table, runtime chain never applied (no dedicated table). The row stays
    put so ``upgrade head`` runs the runtime branch (``0001_baseline`` is
    create_table-guarded) and then the merge revision.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {VERSION_TABLE} VALUES ('{CONTROL_PLANE_HEAD}')"))
        conn.execute(text("CREATE TABLE departments (id VARCHAR PRIMARY KEY)"))
        adopt_unified_version_state(conn)
        rows = [r[0] for r in conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()]
        assert rows == [CONTROL_PLANE_HEAD]


def test_hybrid_dual_recorded_state_restamps_both_branches(tmp_path: Path) -> None:
    """The dual-recorded hybrid: the control-plane head in ``alembic_version``
    AND the runtime chain actually applied (dedicated table at the runtime
    head). The bridge must restamp BOTH branch heads -- dropping the
    dedicated table alone would leave the upgrade replaying the runtime
    branch from base, whose unguarded ``create_table`` revisions crash on
    the existing runtime tables.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE departments (id VARCHAR PRIMARY KEY)"))
        conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {VERSION_TABLE} VALUES ('{CONTROL_PLANE_HEAD}')"))
        conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('{RUNTIME_HEAD}')"))
        adopt_unified_version_state(conn)
        rows = {r[0] for r in conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()}
        assert rows == {CONTROL_PLANE_HEAD, RUNTIME_HEAD}
        assert DEERFLOW_VERSION_TABLE not in inspect(conn).get_table_names()


def test_unified_head_plus_unexpected_runtime_table_fails_loudly(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with pytest.raises(RuntimeError, match="combined version state"):
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text(f"INSERT INTO {VERSION_TABLE} VALUES ('{MERGE_REVISION}')"))
            conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('{RUNTIME_HEAD}')"))
            adopt_unified_version_state(conn)


def test_unified_state_is_left_untouched(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text(f"INSERT INTO {VERSION_TABLE} VALUES ('{MERGE_REVISION}')"))
        adopt_unified_version_state(conn)
        rows = [r[0] for r in conn.execute(text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()]
        assert rows == [MERGE_REVISION]


def test_fresh_database_is_left_untouched(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        adopt_unified_version_state(conn)
        assert inspect(conn).get_table_names() == []


def test_unexpected_runtime_revision_fails_loudly(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with pytest.raises(RuntimeError, match="unexpected revision"):
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {DEERFLOW_VERSION_TABLE} (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(text(f"INSERT INTO {DEERFLOW_VERSION_TABLE} VALUES ('0003_scheduled_tasks')"))
            adopt_unified_version_state(conn)
