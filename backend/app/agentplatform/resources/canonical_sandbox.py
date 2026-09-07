"""Canonical Run sandbox identity and exact Skill mount paths."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from deerflow.config.paths import get_paths, join_host_path

# Canonical Runs replace the generic projection at the same managed DeerFlow
# mount. Keeping one container path prevents a second skill namespace from
# bypassing the enabled-only `/mnt/skills` projection contract.
CANONICAL_SKILLS_CONTAINER_PATH = "/mnt/skills"
_SCOPE_PREFIX = "canonical_run_"
_THREAD_KEY_LENGTH = 16
_RUN_NAMESPACE = uuid.UUID("3ea44ca0-e819-5064-91b7-224484411da3")


def canonical_run_key(run_id: str) -> str:
    try:
        return str(uuid.UUID(run_id))
    except ValueError:
        return str(uuid.uuid5(_RUN_NAMESPACE, run_id))


def canonical_sandbox_scope(thread_id: str, run_id: str) -> str:
    """Return a filesystem-safe sandbox key unique to one frozen Run.

    The scope has to pass DeerFlow's 64-character thread-id budget
    (``utils.thread_id.validate_thread_id``), so the per-thread component is a
    short digest of ``(run, thread)`` instead of an encoded id. Uniqueness per
    frozen Run and thread is preserved; the digest is deterministic, so host
    directories stay stable across retries of the same run.
    """

    canonical_run_id = canonical_run_key(run_id)
    digest = hashlib.sha256(f"{canonical_run_id}:{thread_id}".encode()).hexdigest()[:16]
    return f"{_SCOPE_PREFIX}{canonical_run_id.replace('-', '')}_{digest}"


def parse_canonical_sandbox_scope(scope: str | None) -> tuple[str, str] | None:
    if not scope or not scope.startswith(_SCOPE_PREFIX):
        return None
    payload = scope[len(_SCOPE_PREFIX) :]
    run_hex, separator, thread_key = payload.partition("_")
    if not separator or len(run_hex) != 32 or len(thread_key) != _THREAD_KEY_LENGTH:
        return None
    try:
        bytes.fromhex(run_hex)
        int(thread_key, 16)
        run_id = str(uuid.UUID(hex=run_hex))
    except ValueError:
        return None
    return thread_key, run_id


def canonical_run_skill_view_path(run_id: str) -> Path:
    canonical_run_id = canonical_run_key(run_id)
    return get_paths().base_dir / "resources" / "run-skill-views" / canonical_run_id


def canonical_run_skill_view_host_path(run_id: str) -> str:
    canonical_run_id = canonical_run_key(run_id)
    # IDEER_HOST_BASE_DIR keeps pre-existing deployments working; DEER_FLOW_HOST_BASE_DIR
    # is the upstream name deerflow.config.paths resolves, honored as fallback.
    host_base = os.environ.get("IDEER_HOST_BASE_DIR") or os.environ.get("DEER_FLOW_HOST_BASE_DIR") or str(get_paths().base_dir)
    return join_host_path(host_base, "resources", "run-skill-views", canonical_run_id)


def _resolve_run_skill_view(sandbox_identity: str) -> tuple[str, Path] | None:
    """Resolver hook for DeerFlow's local sandbox provider.

    Returns ``(run_id, run_skill_view)`` for canonical run identities so the
    provider maps ``/mnt/skills`` to the frozen read-only view and keys
    user-data directories on the run workspace — the same ``thread_dir(run_id)``
    layout the workflow file-roots resolver and the artifact gate use.
    ``None`` for ordinary identities (the managed skills projection applies).
    """
    scope = parse_canonical_sandbox_scope(sandbox_identity)
    if scope is None:
        return None
    _thread_key, run_id = scope
    return run_id, canonical_run_skill_view_path(run_id)


def install_run_skill_view_resolver() -> None:
    """Teach DeerFlow's local sandbox provider about run-frozen skill views.

    Idempotent. DeerFlow keeps a neutral hook (``RUN_SKILL_VIEW_RESOLVER``);
    installing here preserves the dependency direction — the runtime never
    imports AgentPlatform, the embedding application injects the behavior.
    """
    from deerflow.sandbox.local import local_sandbox_provider

    if local_sandbox_provider.RUN_SKILL_VIEW_RESOLVER is None:
        local_sandbox_provider.RUN_SKILL_VIEW_RESOLVER = _resolve_run_skill_view
