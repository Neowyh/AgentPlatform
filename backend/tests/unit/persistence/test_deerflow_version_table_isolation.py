from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from deerflow.persistence.bootstrap import (
    _VERSION_TABLE,
    _adopt_legacy_version_table,
    _get_alembic_config,
    _reflect_state,
)


def test_deerflow_alembic_chain_uses_dedicated_version_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    cfg = _get_alembic_config(engine.sync_engine if hasattr(engine, "sync_engine") else engine)  # type: ignore[arg-type]
    assert cfg.get_main_option("version_table") == _VERSION_TABLE


def test_legacy_control_plane_head_is_not_adopted(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('20260828_run_snapshot_selection_role')"))
        _adopt_legacy_version_table(conn)
        assert _VERSION_TABLE not in inspect(conn).get_table_names()
        assert _reflect_state(conn)["has_alembic_version"] is False


def test_legacy_deerflow_head_is_adopted(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('0018_oauth_identity_pg_partial')"))
        _adopt_legacy_version_table(conn)
        assert conn.scalar(text(f"SELECT version_num FROM {_VERSION_TABLE}")) == "0018_oauth_identity_pg_partial"
        assert _reflect_state(conn)["has_alembic_version"] is True
