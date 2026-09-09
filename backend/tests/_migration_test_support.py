"""Shared helpers for migration-adjacent integration tests.

``tests`` is a package, so tests anywhere under it can import this module
as ``from tests._migration_test_support import ...`` without relying on
``PYTHONPATH``.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config as AlembicConfig

from deerflow.persistence.migrations._chain_meta import version_locations

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "packages" / "harness" / "deerflow" / "persistence" / "migrations"


def unified_alembic_config(db_url: str) -> AlembicConfig:
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
