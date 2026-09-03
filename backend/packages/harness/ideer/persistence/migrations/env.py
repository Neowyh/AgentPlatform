"""Alembic environment for iDeer application tables.

ONLY manages iDeer's tables (runs, threads_meta, cron_jobs, users).
LangGraph's checkpointer tables are managed by LangGraph itself -- they
have their own schema lifecycle and must not be touched by Alembic.
"""

from __future__ import annotations

import asyncio
import logging
import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import unquote, urlparse

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from ideer.persistence.base import Base

# Import all models so metadata is populated.
try:
    import ideer.persistence.models as models  # register ORM models with Base.metadata

    _ = models
except ImportError:
    # Models not available — migration will work with existing metadata only.
    logging.getLogger(__name__).warning("Could not import ideer.persistence.models; Alembic may not detect all tables")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _backend_dir() -> Path:
    """Return the backend/ directory independent of the current CWD."""
    return Path(__file__).resolve().parents[5]


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the parent directory for a SQLite URL so connect() can open it.

    SQLite does not create missing parent directories; without this,
    a fresh checkout (no backend/.ideer/data/) fails with
    ``sqlite3.OperationalError: unable to open database file``.
    """
    if not url.startswith("sqlite"):
        return
    # Strip query string, handle sqlite+aiosqlite:////abs/path and
    # sqlite+aiosqlite:///.ideer/relative/path forms.
    path = url.split("?", 1)[0]
    parsed = urlparse(path)
    fs_path = unquote(parsed.path or "")
    if not fs_path or fs_path == "/:memory:":
        return
    # urlparse keeps the leading slash for absolute paths (////abs -> /abs);
    # for driver-relative URLs the path is already relative.
    parent = os.path.dirname(fs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _migrations_dir() -> Path:
    """Return the directory containing this env.py (script_location)."""
    return Path(__file__).resolve().parent


def _is_project_ini() -> bool:
    """True when alembic is running from the project's own alembic.ini."""
    ini_path = config.config_file_name
    if not ini_path:
        return False
    try:
        return Path(ini_path).resolve().parent == _migrations_dir()
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
      (absolute, anchored at backend/ so the CWD does not matter) and
      override alembic.ini. Returns None for backend=memory (nothing
      to migrate). Falls back to the alembic.ini URL when config is
      unavailable.
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
        from ideer.config.app_config import AppConfig
    except ImportError:
        if fallback:
            _ensure_sqlite_parent_dir(fallback)
        return fallback
    try:
        app_config = AppConfig.from_file()
    except Exception as exc:
        logging.getLogger(__name__).warning("Could not load AppConfig for migrations (%s); using alembic.ini URL", exc)
        if fallback:
            _ensure_sqlite_parent_dir(fallback)
        return fallback
    backend = app_config.database.backend
    if backend == "memory":
        return None
    if backend == "sqlite":
        sqlite_dir = app_config.database.sqlite_dir
        if not os.path.isabs(sqlite_dir):
            # Match Gateway startup (CWD=backend/): resolve relative
            # sqlite_dir against backend/ so migrations and the gateway
            # share backend/.ideer/data/ideer.db regardless of the
            # caller's CWD (serve.sh historically ran alembic from the
            # migrations directory).
            sqlite_dir = str(_backend_dir() / sqlite_dir)
        os.makedirs(sqlite_dir, exist_ok=True)
        url = f"sqlite+aiosqlite:///{os.path.join(sqlite_dir, 'ideer.db')}"
        config.set_main_option("sqlalchemy.url", url)
        return url
    # postgres and future backends: use the configured URL as-is.
    url = app_config.database.app_sqlalchemy_url
    config.set_main_option("sqlalchemy.url", url)
    return url


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
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = _resolve_db_url(config.get_main_option("sqlalchemy.url"))
    if url is None:
        logging.getLogger(__name__).info("database.backend=memory -- skipping online migrations")
        return
    _ensure_sqlite_parent_dir(url)
    connectable = create_async_engine(url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
