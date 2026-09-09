"""Safe logical-root file operations for the local runtime."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class FileAccessError(Exception):
    """A user-safe file error; physical paths are never included."""


@dataclass(frozen=True)
class RootConfig:
    logical_root: str
    physical_root: Path

    def __post_init__(self) -> None:
        logical = "/" + self.logical_root.strip("/")
        if logical == "/":
            raise ValueError("logical root must be named")
        object.__setattr__(self, "logical_root", logical)
        object.__setattr__(self, "physical_root", Path(self.physical_root).resolve(strict=False))


class LocalFileStore:
    def __init__(self, roots: list[RootConfig] | tuple[RootConfig, ...]) -> None:
        self.roots = tuple(roots)

    def _resolve(self, logical_path: str) -> tuple[RootConfig, Path]:
        if not logical_path.startswith("/") or "\\" in logical_path:
            raise FileAccessError("invalid logical path")
        normalized = os.path.normpath(logical_path.replace("\\", "/"))
        matches = [r for r in self.roots if normalized == r.logical_root or normalized.startswith(r.logical_root + "/")]
        if not matches:
            raise FileAccessError("outside allowed roots")
        root = max(matches, key=lambda item: len(item.logical_root))
        suffix = normalized[len(root.logical_root) :].lstrip("/")
        candidate = (root.physical_root / suffix).resolve(strict=False)
        try:
            candidate.relative_to(root.physical_root)
        except ValueError as exc:
            raise FileAccessError("outside allowed roots") from exc
        return root, candidate

    def resolve(self, logical_path: str) -> Path:
        """Resolve a logical path for an internal executor without exposing it."""
        return self._resolve(logical_path)[1]

    def list(self, logical_path: str) -> list[str]:
        root, path = self._resolve(logical_path)
        if not path.exists():
            raise FileAccessError("not found")
        if not path.is_dir():
            raise FileAccessError("not a directory")
        return sorted(f"{root.logical_root}/{item.relative_to(root.physical_root).as_posix()}" for item in path.iterdir() if item.resolve(strict=False).is_relative_to(root.physical_root))

    def read(self, logical_path: str) -> str:
        _, path = self._resolve(logical_path)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, os.O_RDONLY | nofollow)
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                return stream.read()
        except FileNotFoundError as exc:
            raise FileAccessError("not found") from exc
        except IsADirectoryError as exc:
            raise FileAccessError("not a file") from exc
        except PermissionError as exc:
            raise FileAccessError("permission denied") from exc
        except OSError as exc:
            if nofollow and getattr(exc, "errno", None) in {40, 62}:
                raise FileAccessError("outside allowed roots") from exc
            raise FileAccessError("locked or unavailable") from exc

    def write(self, logical_path: str, content: str) -> None:
        _, path = self._resolve(logical_path)
        if path.exists() and not path.is_file():
            raise FileAccessError("not a file")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, temporary = tempfile.mkstemp(prefix=".local-write-", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except PermissionError as exc:
            raise FileAccessError("permission denied") from exc
