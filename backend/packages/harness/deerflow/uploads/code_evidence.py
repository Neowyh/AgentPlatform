"""Runtime-neutral Code Evidence path projection.

Package acceptance and manifest governance belong to AgentPlatform.  Runtime
tools only need this validated path projection to read an already-frozen
package during a Run.
"""

from __future__ import annotations

from pathlib import Path

from deerflow.config.paths import get_paths
from deerflow.runtime.user_context import get_effective_user_id


def package_root(thread_id: str, package_id: str, *, user_id: str | None = None) -> Path:
    """Return the caller-scoped root of a validated Code Evidence package."""
    if not package_id or Path(package_id).name != package_id:
        raise ValueError("Invalid package id")
    owner = user_id if user_id is not None else get_effective_user_id()
    return get_paths().thread_dir(thread_id, user_id=owner) / "user-data" / "code-evidence" / package_id
