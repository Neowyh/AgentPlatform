"""Safe logical-root file operations for the local runtime."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class FileAccessError(Exception):
    """A user-safe file error; physical paths are never included."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code.lower().replace("_", " "))


INVALID_PATH = "INVALID_PATH"
OUTSIDE_ALLOWED_ROOTS = "OUTSIDE_ALLOWED_ROOTS"
NOT_FOUND = "NOT_FOUND"
NOT_A_FILE = "NOT_A_FILE"
NOT_A_DIRECTORY = "NOT_A_DIRECTORY"
PERMISSION_DENIED = "PERMISSION_DENIED"
LOCKED_OR_UNAVAILABLE = "LOCKED_OR_UNAVAILABLE"


@dataclass(frozen=True)
class RootConfig:
    logical_root: str
    physical_root: Path

    def __post_init__(self) -> None:
        logical = "/" + self.logical_root.strip("/")
        if logical == "/" or "\\" in logical or any(part == ".." for part in logical.split("/")):
            raise ValueError("logical root must be named")
        object.__setattr__(self, "logical_root", logical)
        object.__setattr__(self, "physical_root", Path(self.physical_root).resolve(strict=False))


class LocalFileStore:
    def __init__(self, roots: list[RootConfig] | tuple[RootConfig, ...]) -> None:
        self.roots = tuple(roots)

    def _resolve(self, logical_path: str) -> tuple[RootConfig, Path]:
        if not isinstance(logical_path, str) or not logical_path.startswith("/") or "\\" in logical_path:
            raise FileAccessError(INVALID_PATH, "invalid logical path")
        if logical_path.startswith("//"):
            raise FileAccessError(INVALID_PATH, "outside allowed roots")
        if any(part == ".." for part in logical_path.split("/")):
            raise FileAccessError(OUTSIDE_ALLOWED_ROOTS, "outside allowed roots")
        normalized = os.path.normpath(logical_path.replace("\\", "/"))
        normalized_key = os.path.normcase(normalized)
        matches = [
            r
            for r in self.roots
            if normalized_key == os.path.normcase(r.logical_root)
            or normalized_key.startswith(os.path.normcase(r.logical_root + "/"))
        ]
        if not matches:
            raise FileAccessError(OUTSIDE_ALLOWED_ROOTS, "outside allowed roots")
        root = max(matches, key=lambda item: len(item.logical_root))
        suffix = normalized[len(root.logical_root) :].lstrip("/")
        try:
            candidate = (root.physical_root / suffix).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise FileAccessError(LOCKED_OR_UNAVAILABLE, "locked or unavailable") from exc
        try:
            candidate.relative_to(root.physical_root)
        except ValueError as exc:
            raise FileAccessError(OUTSIDE_ALLOWED_ROOTS, "outside allowed roots") from exc
        return root, candidate

    def resolve(self, logical_path: str) -> Path:
        """Resolve a logical path for an internal executor without exposing it."""
        return self._resolve(logical_path)[1]

    def list(self, logical_path: str) -> list[str]:
        root, path = self._resolve(logical_path)
        try:
            if not path.exists():
                raise FileAccessError(NOT_FOUND, "not found")
            if not path.is_dir():
                raise FileAccessError(NOT_A_DIRECTORY, "not a directory")
            entries: list[str] = []
            for item in path.iterdir():
                try:
                    resolved = item.resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise FileAccessError(LOCKED_OR_UNAVAILABLE, "locked or unavailable") from exc
                try:
                    relative = resolved.relative_to(root.physical_root)
                except ValueError as exc:
                    raise FileAccessError(OUTSIDE_ALLOWED_ROOTS, "outside allowed roots") from exc
                entries.append(f"{root.logical_root}/{relative.as_posix()}")
            return sorted(entries)
        except FileAccessError:
            raise
        except PermissionError as exc:
            raise FileAccessError(PERMISSION_DENIED, "permission denied") from exc
        except OSError as exc:
            raise FileAccessError(LOCKED_OR_UNAVAILABLE, "locked or unavailable") from exc

    def read(self, logical_path: str) -> str:
        _, path = self._resolve(logical_path)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, os.O_RDONLY | nofollow)
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                return stream.read()
        except FileNotFoundError as exc:
            raise FileAccessError(NOT_FOUND, "not found") from exc
        except IsADirectoryError as exc:
            raise FileAccessError(NOT_A_FILE, "not a file") from exc
        except PermissionError as exc:
            raise FileAccessError(PERMISSION_DENIED, "permission denied") from exc
        except OSError as exc:
            if nofollow and getattr(exc, "errno", None) in {40, 62}:
                raise FileAccessError(OUTSIDE_ALLOWED_ROOTS, "outside allowed roots") from exc
            raise FileAccessError(LOCKED_OR_UNAVAILABLE, "locked or unavailable") from exc

    def write(self, logical_path: str, content: str) -> None:
        _, path = self._resolve(logical_path)
        if path.exists() and not path.is_file():
            raise FileAccessError(NOT_A_FILE, "not a file")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".local-write-", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        except PermissionError as exc:
            raise FileAccessError(PERMISSION_DENIED, "permission denied") from exc
        except OSError as exc:
            raise FileAccessError(LOCKED_OR_UNAVAILABLE, "locked or unavailable") from exc
