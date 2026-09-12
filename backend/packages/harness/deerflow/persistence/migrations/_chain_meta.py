"""Single source of truth for the unified migration chain's identity.

Shared by three consumers that must never disagree:

- ``migrations/env.py`` (the alembic environment: CLI ``upgrade head`` and
  every ``command.stamp`` / ``command.upgrade`` the bootstrap issues),
- ``deerflow.persistence.bootstrap`` (the Gateway auto-upgrade path), and
- the guard tests under ``backend/tests``.

The unified chain joins the AgentPlatform control-plane chain (rooted at
``16147afec43b``) and the DeerFlow runtime chain (rooted at
``0001_baseline``) with the merge revision :data:`MERGE_REVISION`, tracked
in the single :data:`VERSION_TABLE`. Databases stamped by the pre-unification
bootstrap keep their runtime head in the dedicated
:data:`DEERFLOW_VERSION_TABLE`; :func:`adopt_unified_version_state` bridges
that state into :data:`VERSION_TABLE` so one ``alembic upgrade head``
converges both chains.

This module must stay import-light (no alembic runtime machinery): env.py
imports it during ``alembic`` command startup, and importing alembic's
``context`` there is only legal inside a running environment.
"""

from __future__ import annotations

import logging
import pathlib

# The unified chain keeps its revision state in the default
# ``alembic_version`` table -- the table the AgentPlatform control-plane
# chain has always used.
VERSION_TABLE = "alembic_version"

# Dedicated version table from the dual-chain era (the PATCH-006 isolation).
# Read-only after the bridge: databases carrying it are adopted, then the
# table is dropped.
DEERFLOW_VERSION_TABLE = "deerflow_alembic_version"

# Heads of the two chains joined by the merge revision.
CONTROL_PLANE_HEAD = "20260828_run_snapshot_selection_role"
RUNTIME_HEAD = "0018_oauth_identity_pg_partial"

# The join point: ``alembic heads`` must report exactly this revision.
MERGE_REVISION = "20260908_unify_migration_chains"

#: Revisions that mean "already inside the unified chain".
_UNIFIED_REVISIONS = frozenset({CONTROL_PLANE_HEAD, RUNTIME_HEAD, MERGE_REVISION})

#: Marker table for "the control-plane chain's DDL is applied". The root
#: revision ``16147afec43b`` creates ``departments``; every deployment that
#: ever ran the enterprise chain (or the Gateway's create_all, which renders
#: the unified metadata) has it.
_CONTROL_PLANE_MARKER_TABLE = "departments"
# The pre-convergence deployment path stamped only the original control-plane
# root. Intermediate revisions are still live Alembic positions and must be
# allowed to advance normally; treating them as already-at-head creates an
# overlapping upgrade range.
_LEGACY_CONTROL_PLANE_HEADS = frozenset({"16147afec43b"})


def version_locations(migrations_dir: str | pathlib.Path) -> str:
    """Render the alembic ``version_locations`` value for *migrations_dir*.

    The unified ScriptDirectory scans this tree's own ``versions/`` plus the
    control-plane ``versions/`` directory. Kept next to the chain constants
    because every bare-``Config()`` builder (bootstrap, autogen script) must
    repeat it -- an ini-file-only setting would silently hide the
    control-plane revisions from them.
    """
    root = pathlib.Path(migrations_dir).resolve()
    control_plane = root.parents[4] / "app" / "agentplatform" / "persistence" / "migrations" / "versions"
    return f"{root / 'versions'} {control_plane}"


def adopt_unified_version_state(sync_conn) -> None:
    """Bridge a pre-unification database into the single version table.

    The version table is allowed to carry **one row per merged branch** --
    alembic's native representation for a database sitting on multiple
    branches of a merge-enabled chain (exactly what
    ``alembic stamp <head1> <head2>`` produces). The bridge uses that to
    restate each legacy database's true position declaratively instead of
    re-running DDL that the pre-unification stack already applied:

    Legacy states handled (all produced by the pre-unification stack):

    - unified state: :data:`VERSION_TABLE` carries revision(s) from the
      unified chain. The dedicated table, if still present, is retired --
      the merge revision subsumes both old heads.

    - runtime-recorded state (the pre-unification Gateway's steady state):
      the runtime head sits in the dedicated :data:`DEERFLOW_VERSION_TABLE`.
      The control-plane DDL may or may not also be present (created by the
      Gateway's ``create_all``, which renders the unified metadata, or by
      ``serve.sh``'s enterprise-side upgrade). Restamp as
      ``stamp(CONTROL_PLANE_HEAD, RUNTIME_HEAD)`` when the control-plane
      DDL is detectable (via :data:`_CONTROL_PLANE_MARKER_TABLE`), else
      ``stamp(RUNTIME_HEAD)`` -- then drop the dedicated table. From that
      position ``upgrade head`` runs only the merge revision itself.

    - control-plane-only state (the pre-convergence ``serve.sh`` shape):
      :data:`VERSION_TABLE` carries the control-plane head and the runtime
      chain has NO record anywhere (its revisions were never applied -- the
      core tables came from the control-plane chain's own
      ``c4d5e6f7a8b9``). The row stays put: from that position
      ``upgrade head`` runs the runtime branch (``0001_baseline`` is
      create_table-guarded, the post-baseline revisions idempotent) and then
      the merge revision.

    - pre-alembic state (enterprise DDL present, no version rows anywhere):
      leave untouched. The caller (``bootstrap_schema``'s create_all
      branches) stamps before upgrading; the CLI path fails loudly on the
      first ``create_table`` instead of guessing.

    A fresh database (no rows anywhere) is left untouched; alembic's own
    handling applies. Unknown rows fail loudly rather than being silently
    restamped here.
    """
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    insp = sa_inspect(sync_conn)
    tables = set(insp.get_table_names())

    def _rows(table: str) -> list[str]:
        return [str(row[0]) for row in sync_conn.execute(text(f"SELECT version_num FROM {table}")).fetchall()]

    unified_rows: list[str] = _rows(VERSION_TABLE) if VERSION_TABLE in tables else []
    if any(revision in _UNIFIED_REVISIONS for revision in unified_rows):
        if DEERFLOW_VERSION_TABLE in tables:
            runtime_rows = [str(row[0]) for row in sync_conn.execute(text(f"SELECT version_num FROM {DEERFLOW_VERSION_TABLE}")).fetchall()]
            if runtime_rows and set(runtime_rows) != {RUNTIME_HEAD}:
                raise RuntimeError(f"chain-meta: unexpected revision(s) {runtime_rows!r} in {DEERFLOW_VERSION_TABLE}; expected [{RUNTIME_HEAD!r}]. Upgrade to the pre-unification head first.")
            if runtime_rows:
                # Hybrid dual-recorded state: the control-plane head is
                # recorded AND the runtime chain was actually applied
                # (dedicated table). Declare both branch heads so
                # ``upgrade head`` runs only the merge revision -- replaying
                # the runtime branch from base would hit unguarded
                # ``create_table`` revisions for tables that already exist.
                if set(unified_rows) != {CONTROL_PLANE_HEAD}:
                    # Some other unified row (merge or newer) plus a
                    # dedicated table: the shared-table subsumption already
                    # covers it, but a runtime row contradicting the
                    # unified row is unexpected -- refuse rather than guess.
                    raise RuntimeError(f"chain-meta: unexpected combined version state {sorted(set(unified_rows))!r} + {runtime_rows!r}; expected [{CONTROL_PLANE_HEAD!r}] or the unified head.")
                sync_conn.execute(text(f"DELETE FROM {VERSION_TABLE}"))
                sync_conn.execute(text(f"INSERT INTO {VERSION_TABLE} (version_num) VALUES (:revision)"), {"revision": RUNTIME_HEAD})
                sync_conn.execute(text(f"INSERT INTO {VERSION_TABLE} (version_num) VALUES (:revision)"), {"revision": CONTROL_PLANE_HEAD})
                logging.getLogger(__name__).info("chain-meta: hybrid dual-recorded state restamped to [%s, %s]", CONTROL_PLANE_HEAD, RUNTIME_HEAD)
            sync_conn.execute(text(f"DROP TABLE {DEERFLOW_VERSION_TABLE}"))
            logging.getLogger(__name__).info("chain-meta: retired legacy table %s", DEERFLOW_VERSION_TABLE)
        return

    runtime_rows: list[str] = _rows(DEERFLOW_VERSION_TABLE) if DEERFLOW_VERSION_TABLE in tables else []
    if runtime_rows != [RUNTIME_HEAD] and runtime_rows:
        raise RuntimeError(f"chain-meta: unexpected revision(s) {runtime_rows!r} in {DEERFLOW_VERSION_TABLE}; expected [{RUNTIME_HEAD!r}]. Upgrade to the pre-unification head first.")

    has_control_plane_ddl = _CONTROL_PLANE_MARKER_TABLE in tables
    if unified_rows and set(unified_rows).issubset(_LEGACY_CONTROL_PLANE_HEADS) and has_control_plane_ddl and CONTROL_PLANE_HEAD not in unified_rows:
        # Some pre-unification databases stamped only the runtime revision
        # after creating the complete control-plane schema via ``create_all``.
        # Declare that branch applied before ``upgrade head`` so its DDL is not
        # replayed (the runtime branch still advances from its recorded row).
        sync_conn.execute(
            text(f"INSERT INTO {VERSION_TABLE} (version_num) VALUES (:revision)"),
            {"revision": CONTROL_PLANE_HEAD},
        )
        logging.getLogger(__name__).info("chain-meta: adopted existing control-plane schema at %s", CONTROL_PLANE_HEAD)
        unified_rows.append(CONTROL_PLANE_HEAD)
    if runtime_rows:
        # Runtime chain applied and recorded in the dedicated table; the
        # control-plane half may or may not have its DDL present (created by
        # the Gateway's ``create_all``, which renders the unified metadata).
        # Restamp the true position; from there ``upgrade head`` only runs
        # the merge revision.
        if VERSION_TABLE not in tables:
            sync_conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(255) NOT NULL)"))
        desired = [RUNTIME_HEAD]
        if has_control_plane_ddl:
            desired.insert(0, CONTROL_PLANE_HEAD)
        sync_conn.execute(text(f"DELETE FROM {VERSION_TABLE}"))
        for revision in desired:
            sync_conn.execute(text(f"INSERT INTO {VERSION_TABLE} (version_num) VALUES (:revision)"), {"revision": revision})
        if DEERFLOW_VERSION_TABLE in tables:
            sync_conn.execute(text(f"DROP TABLE {DEERFLOW_VERSION_TABLE}"))
        logging.getLogger(__name__).info("chain-meta: restamped unified position %s", desired)
        return

    if not unified_rows and not runtime_rows and _is_create_all_current(sync_conn, tables):
        # create_all-current state (no version rows anywhere, but every
        # runtime-metadata table and column exists): the schema is at head
        # by construction -- the same invariant the bootstrap's empty branch
        # relies on (``create_all`` + ``stamp head``). This is the
        # crash-recovery shape of an interrupted empty branch, and stamping
        # the merge position avoids replaying the whole chain against
        # already-current tables (unguarded ``create_table`` /
        # batch-``add_column`` revisions would crash). Drifted databases
        # fail the column check and fall through to a full replay, where the
        # idempotent helpers repair them.
        if VERSION_TABLE not in tables:
            sync_conn.execute(text(f"CREATE TABLE {VERSION_TABLE} (version_num VARCHAR(255) NOT NULL)"))
        sync_conn.execute(text(f"INSERT INTO {VERSION_TABLE} (version_num) VALUES (:revision)"), {"revision": MERGE_REVISION})
        logging.getLogger(__name__).info("chain-meta: create_all-current state stamped to %s", MERGE_REVISION)
        return

    if has_control_plane_ddl and not unified_rows:
        # Enterprise DDL without a version row: pre-alembic enterprise DB.
        # Leave the (absent) version state to the caller's stamp branch.
        logging.getLogger(__name__).info("chain-meta: control-plane DDL present without version row; caller must stamp")
        return
    # Anything else (fresh DB, unknown rows) is left to alembic's own
    # handling; unknown rows fail loudly in ScriptDirectory rather than
    # being silently restamped here.


def _is_create_all_current(sync_conn, tables: set[str]) -> bool:
    """True when *sync_conn*'s schema matches ``Base.metadata`` exactly.

    Every runtime-metadata table must exist and carry every model column.
    This is the signature of a database produced by
    ``Base.metadata.create_all`` against the current models (the empty
    branch's fast path), as opposed to a drifted legacy database that needs
    the chain's idempotent repairs. ``deerflow.persistence.models`` is
    imported lazily so this module stays import-light.
    """
    from sqlalchemy import inspect as sa_inspect

    try:
        import deerflow.persistence.models  # noqa: F401  -- registers runtime models
        from deerflow.persistence.base import Base
    except ImportError:
        # Models unavailable: the create_all-current check cannot be
        # answered -- fall through to the chain's own handling (same
        # tolerance as the bootstrap/env model imports).
        return False

    metadata_tables = Base.metadata.tables
    if not metadata_tables or not tables:
        return False
    if not set(metadata_tables).issubset(tables):
        return False
    insp = sa_inspect(sync_conn)
    for table_name, table in metadata_tables.items():
        reflected_columns = {c["name"]: c for c in insp.get_columns(table_name)}
        if not set(table.columns).issubset(reflected_columns):
            return False
        # A name-only check mistakes hand-applied ALTERs for a fresh
        # ``create_all`` schema.  Compare the same shape dimensions used by
        # ``safe_add_column`` so drifted legacy databases continue through
        # the idempotent migration revisions and emit diagnostics.
        for desired in table.columns:
            actual = reflected_columns[desired.name]
            desired_nullable = True if desired.nullable is None else bool(desired.nullable)
            if bool(actual.get("nullable", True)) != desired_nullable:
                return False
            from deerflow.persistence.migrations._helpers import _normalize_default, _type_equivalent

            if _normalize_default(actual.get("default")) != _normalize_default(desired.server_default):
                return False
            if not _type_equivalent(actual.get("type"), desired.type):
                return False
    return True
