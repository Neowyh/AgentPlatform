"""Fail-loud repository-root resolution shared by the detectors.

Depth-indexed resolution (`Path(__file__).resolve().parents[N]`) fails
silently when a detector file moves to a different directory depth: scan
roots resolve under the wrong directory, nothing is scanned, and the
detector reports zero findings with no error. Walking upward to a
repository marker turns that into an immediate error instead.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT_MARKER = ".git"


def _is_git_repository_marker(path: Path) -> bool:
    """Reject placeholder mount points that merely happen to contain `.git`."""
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").startswith("gitdir:")
        except OSError:
            return False
    return path.is_dir() and (path / "HEAD").is_file() and (path / "config").is_file()


def resolve_repo_root(start: Path) -> Path:
    """Return the repository root above `start` (the directory containing `.git`).

    `.git` is checked with `exists()` rather than `is_dir()` so git worktrees
    (where `.git` is a file) resolve correctly.

    Raises:
        RuntimeError: when no marker is found above `start`, so a relocated
            detector fails loudly instead of silently scanning an empty tree.
    """
    resolved = start.resolve()
    for candidate in (resolved, *resolved.parents):
        if _is_git_repository_marker(candidate / REPO_ROOT_MARKER):
            return candidate
    raise RuntimeError(f"could not resolve the repository root: no '{REPO_ROOT_MARKER}' marker found above {resolved}; refusing to guess scan paths")
