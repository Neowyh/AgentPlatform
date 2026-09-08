"""Alembic environment for the unified iDeer migration chain.

Manages the full application schema in one forward-only chain: the
AgentPlatform control-plane tables (resource_metadata, departments,
users_ext, workflow governance, ...) and the DeerFlow runtime tables
(runs, threads_meta, feedback, users, run_events, channel_*, ...).
The runtime-only ``versions/`` directory under this tree and the
control-plane ``versions/`` directory
(``app/agentplatform/persistence/migrations/versions``) are joined by the
merge revision ``20260908_unify_migration_chains``; see ``alembic.ini``
``version_locations`` and ``migrations/_chain_meta.py``.

LangGraph's checkpointer tables (``checkpoints``, ``checkpoint_blobs``,
``checkpoint_writes``, ``checkpoint_migrations``) are managed by LangGraph
itself -- they have their own schema lifecycle and must not be touched by
Alembic. The ``include_object`` filter below explicitly excludes them so a
future ``alembic revision --autogenerate`` will not emit ``drop_table`` for
tables it does not own.
"""

from __future__ import annotations

import asyncio
import logging
import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import unquote

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from deerflow.persistence.base import Base
from deerflow.persistence.migrations._chain_meta import (
    DEERFLOW_VERSION_TABLE,
    VERSION_TABLE,
    adopt_unified_version_state,
)
from deerflow.persistence.migrations._env_filters import (
    LANGGRAPH_OWNED_TABLES,
    include_object,
    register_configured_extension_table_prefixes,
)

# Re-export under the module namespace for any consumer that addresses them
# via ``env.LANGGRAPH_OWNED_TABLES`` / ``env.include_object``.
__all__ = [
    "DEERFLOW_VERSION_TABLE",
    "LANGGRAPH_OWNED_TABLES",
    "VERSION_TABLE",
    "include_object",
]

# Import all models so metadata is populated.
try:
    import deerflow.persistence.models as models  # register ORM models with Base.metadata

    _ = models
except ImportError:
    # Models not available — migration will work with existing metadata only.
    logging.getLogger(__name__).warning("Could not import deerflow.persistence.models; Alembic may not detect all tables")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This process never starts a Gateway, so ``load_extensions()`` has not run and
# ``EXTENSION_TABLE_PREFIXES`` would be empty in the one place ``include_object``
# reads it. Read the declarations straight from config instead; extension code
# is never imported here.
_extension_prefixes = register_configured_extension_table_prefixes()
if _extension_prefixes:
    logging.getLogger(__name__).info("alembic: excluding extension-owned tables with prefixes %s", ", ".join(sorted(_extension_prefixes)))

target_metadata = Base.metadata


def _backend_dir() -> Path:
    """Return the backend/ directory independent of the current CWD."""
    # packages/harness/deerflow/persistence/migrations/env.py -> backend/
    return Path(__file__).resolve().parents[5]


def _sqlite_fs_path(url: str) -> str | None:
    """Filesystem path of a file-backed sqlite URL, else ``None``.

    Distinguishes the raw 4-slash absolute form (``sqlite+aiosqlite:////abs``)
    from the 3-slash driver-relative form (``sqlite+aiosqlite:///./data``),
    which urlparse normalizes to indistinguishable leading-slash paths.
    Relative paths are returned as ``None`` -- callers anchor them first.
    """
    path = url.split("?", 1)[0]
    for prefix in ("sqlite+aiosqlite://", "sqlite://"):
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix) :]
        if not rest or rest == ":memory:":
            return None
        # 4th slash present -> absolute; anything else -> driver-relative.
        if not rest.startswith("//"):
            return None
        return unquote(rest[1:])
    return None


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the parent directory for a SQLite URL so connect() can open it.

    SQLite does not create missing parent directories; without this,
    a fresh checkout (no backend/.deer-flow/data/) fails with
    ``sqlite3.OperationalError: unable to open database file``.
    """
    if not url.startswith("sqlite"):
        return
    fs_path = _sqlite_fs_path(url)
    if not fs_path:
        return
    parent = os.path.dirname(fs_path)
    if parent and parent != os.sep:
        os.makedirs(parent, exist_ok=True)


def _is_project_ini() -> bool:
    """True when alembic is running from this tree's own alembic.ini."""
    ini_path = config.config_file_name
    if not ini_path:
        return False
    try:
        return Path(ini_path).resolve().parent == Path(__file__).resolve().parent
    except OSError:
        return False


def _ini_default_url() -> str | None:
    """Read the raw sqlalchemy.url from the alembic.ini file, if available."""
    ini_path = config.config_file_name
    if not ini_path:
        return None
    try:
        with open(ini_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("sqlalchemy.url"):
                    _, _, value = stripped.partition("=")
                    return value.strip() or None
    except OSError:
        return None
    return None


def _resolve_db_url(fallback: str | None) -> str | None:
    """Resolve the migration DB URL, preferring explicit caller overrides.

    - When the caller explicitly set sqlalchemy.url to something other
      than the alembic.ini default (tests via set_main_option, custom
      -c files, manual overrides), respect it; only ensure the SQLite
      parent dir exists.
    - Otherwise resolve from config.yaml database.backend/sqlite_dir
      (absolute, anchored at backend/ so the CWD does not matter) --
      the same URL the Gateway engine uses, so a CLI ``upgrade head``
      and the Gateway auto-upgrade converge on one database file.
      Returns None for backend=memory (nothing to migrate). Falls back
      to the alembic.ini URL when config is unavailable.
    """
    ini_default = _ini_default_url()
    if not _is_project_ini():
        # Custom -c file outside the migrations dir: the caller chose both
        # the config file and its URL explicitly -- respect it.
        if fallback:
            _ensure_sqlite_parent_dir(fallback)
        return fallback
    if fallback and ini_default and fallback != ini_default:
        _ensure_sqlite_parent_dir(fallback)
        return fallback
    try:
        from deerflow.config.app_config import AppConfig
    except ImportError:
        pass
    else:
        try:
            app_config = AppConfig.from_file()
        except Exception as exc:
            logging.getLogger(__name__).warning("Could not load AppConfig for migrations (%s); using alembic.ini URL", exc)
        else:
            backend = app_config.database.backend
            if backend == "memory":
                return None
            # ``app_sqlalchemy_url`` is the exact URL the Gateway engine
            # resolves (sqlite: sqlite_dir joined with "deerflow.db"; postgres:
            # the asyncpg DSN), so a CLI ``upgrade head`` and the Gateway
            # auto-upgrade converge on one database/server.
            url = app_config.database.app_sqlalchemy_url
            _ensure_sqlite_parent_dir(url)
            config.set_main_option("sqlalchemy.url", url)
            return url
    # Config unavailable: fall back to the ini default, anchored at backend/
    # so a bare CLI run from any CWD lands in the same database file.
    if fallback:
        fs_path = _sqlite_fs_path(fallback)
        if fs_path is None and fallback.startswith("sqlite") and ":memory:" not in fallback:
            scheme, _, rest = fallback.partition("://")
            # The 3rd slash of the 3-slash form reads as a leading "/" here.
            fallback = f"{scheme}:///{_backend_dir() / rest.lstrip('/')}"
        _ensure_sqlite_parent_dir(fallback)
        config.set_main_option("sqlalchemy.url", fallback)
        return fallback
    return fallback


def run_migrations_offline() -> None:
    url = _resolve_db_url(config.get_main_option("sqlalchemy.url"))
    if url is None:
        logging.getLogger(__name__).info("database.backend=memory -- skipping offline migrations")
        return
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        include_object=include_object,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    # Pre-create the version table wide enough for this tree's long
    # date/word-based revision ids (SQLite never enforced Alembic's default
    # VARCHAR(32) ``version_num``, PostgreSQL does). Existing tables are
    # untouched (no-op).
    connection.exec_driver_sql(f"CREATE TABLE IF NOT EXISTS {VERSION_TABLE} (version_num VARCHAR(255) NOT NULL)")
    # Bridge pre-unification version state (dual tables / control-plane-only)
    # before alembic reads the version table.
    adopt_unified_version_state(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
        include_object=include_object,
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sqlite_migrations_online(url: str) -> None:
    """Run SQLite Alembic migrations on a synchronous engine.

    Alembic's command API is synchronous. Using ``asyncio.run`` with an
    ``aiosqlite`` engine here leaves its worker thread alive during repeated
    upgrade/downgrade runs (and can hang process shutdown on Python 3.12).
    The application still uses the async URL at runtime; only this migration
    boundary uses SQLite's synchronous driver.
    """
    sync_url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    connectable = create_engine(sync_url)
    try:
        with connectable.connect() as connection:
            do_run_migrations(connection)
            connection.commit()
    finally:
        connectable.dispose()


def _sqlite_connect_hook(engine) -> None:
    """Attach the cross-process ``busy_timeout`` hook to *engine*'s connections.

    Alembic spawns its OWN engine here -- those connections wouldn't inherit
    the production engine's PRAGMAs (set in ``deerflow.persistence.engine``)
    unless we wire the same hook on this one. Only relevant for the async
    engine (the sync SQLite path wires nothing).
    """
    if not engine.url.drivername.startswith("sqlite"):
        return
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _alembic_sqlite_busy_timeout(dbapi_conn, _record):  # noqa: ARG001
        async def _configure(connection):
            await connection.execute("PRAGMA busy_timeout=30000;")

        dbapi_conn.run_async(_configure)


async def _run_async_migrations_online(url: str) -> None:
    _ensure_sqlite_parent_dir(url)
    pg_schema = config.get_main_option("deerflow_pg_schema")
    connect_args: dict = {}
    # Accept both the canonical ``postgresql`` scheme and libpq's ``postgres``
    # short scheme (with or without a SQLAlchemy ``+driver`` suffix) so a
    # ``postgres://`` DSN still gets its search_path pinned instead of silently
    # writing ``alembic_version`` + migration DDL to the default schema.
    if pg_schema and url.split("+", 1)[0].split(":", 1)[0] in {"postgresql", "postgres"}:
        from deerflow.persistence.postgres_schema import build_asyncpg_connect_args

        connect_args = build_asyncpg_connect_args(pg_schema)

    connectable = create_async_engine(url, connect_args=connect_args)
    _sqlite_connect_hook(connectable)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        # do_run_migrations executes DDL (version-table pre-create, the
        # legacy-state bridge, migrations) on this connection; without an
        # explicit commit the async connection rolls everything back on
        # dispose (alembic's sync path commits inside its transaction
        # manager, the async path does not).
        await connection.commit()
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    url = _resolve_db_url(config.get_main_option("sqlalchemy.url"))
    if url is None:
        logging.getLogger(__name__).info("database.backend=memory -- skipping online migrations")
    elif url.startswith("sqlite+aiosqlite://"):
        # SQLite runs fully synchronously: alembic's command API is
        # synchronous anyway, and a sync engine here avoids leaving an
        # aiosqlite worker thread alive (it can hang process shutdown on
        # Python 3.12). It also lets this env load inside a foreign running
        # event loop (tests), where asyncio.run would raise.
        _run_sqlite_migrations_online(url)
    else:
        asyncio.run(_run_async_migrations_online(url))
