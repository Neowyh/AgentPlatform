"""Canonical Run sandbox identity and exact Skill mount paths."""

from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path

from ideer.config.paths import get_paths, join_host_path

CANONICAL_SKILLS_CONTAINER_PATH = "/mnt/run-skills"
_SCOPE_PREFIX = "canonical_run_"
_RUN_NAMESPACE = uuid.UUID("3ea44ca0-e819-5064-91b7-224484411da3")


def canonical_run_key(run_id: str) -> str:
    try:
        return str(uuid.UUID(run_id))
    except ValueError:
        return str(uuid.uuid5(_RUN_NAMESPACE, run_id))


def canonical_sandbox_scope(thread_id: str, run_id: str) -> str:
    """Return a filesystem-safe sandbox key unique to one frozen Run."""

    canonical_run_id = canonical_run_key(run_id)
    encoded_thread = base64.urlsafe_b64encode(thread_id.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{_SCOPE_PREFIX}{canonical_run_id.replace('-', '')}_{encoded_thread}"


def parse_canonical_sandbox_scope(scope: str | None) -> tuple[str, str] | None:
    if not scope or not scope.startswith(_SCOPE_PREFIX):
        return None
    payload = scope[len(_SCOPE_PREFIX) :]
    run_hex, separator, encoded_thread = payload.partition("_")
    if not separator or not encoded_thread:
        return None
    try:
        run_id = str(uuid.UUID(hex=run_hex))
        padding = "=" * (-len(encoded_thread) % 4)
        thread_id = base64.b64decode(encoded_thread + padding, altchars=b"-_", validate=True).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return None
    if not thread_id:
        return None
    return thread_id, run_id


def canonical_run_skill_view_path(run_id: str) -> Path:
    canonical_run_id = canonical_run_key(run_id)
    return get_paths().base_dir / "resources" / "run-skill-views" / canonical_run_id


def canonical_run_skill_view_host_path(run_id: str) -> str:
    canonical_run_id = canonical_run_key(run_id)
    host_base = os.environ.get("IDEER_HOST_BASE_DIR") or str(get_paths().base_dir)
    return join_host_path(host_base, "resources", "run-skill-views", canonical_run_id)
