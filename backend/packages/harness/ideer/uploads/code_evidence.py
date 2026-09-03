"""Thread-private, read-only code evidence package handling.

This module deliberately has no FastAPI dependencies.  ZIP processing is
performed before the package is made visible, and callers receive a manifest
that distinguishes accepted, excluded, and rejected members.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from ideer.config.paths import get_paths
from ideer.runtime.user_context import get_effective_user_id

MAX_COMPRESSED_SIZE = 200 * 1024 * 1024
MAX_EXPANDED_SIZE = 1024 * 1024 * 1024
MAX_MEMBERS = 20_000
MAX_COMPRESSION_RATIO = 200

_EXCLUDED_PARTS = {".git", ".svn", "node_modules", "__pycache__", "build", "dist", "target", ".cache"}
_BINARY_SUFFIXES = {".a", ".so", ".dll", ".dylib", ".o", ".obj", ".exe", ".bin", ".elf"}


class CodeEvidencePackageError(ValueError):
    """Raised when a package cannot be accepted safely."""


@dataclass(frozen=True)
class PackageManifest:
    package_id: str
    original_filename: str
    accepted: tuple[str, ...]
    excluded: tuple[str, ...]
    rejected: tuple[dict[str, str], ...]
    compressed_size: int
    expanded_size: int

    @property
    def source_virtual_path(self) -> str:
        return f"/mnt/user-data/code-evidence/{self.package_id}/source"

    def as_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "original_filename": self.original_filename,
            "accepted": list(self.accepted),
            "excluded": list(self.excluded),
            "rejected": list(self.rejected),
            "compressed_size": self.compressed_size,
            "expanded_size": self.expanded_size,
            "source_virtual_path": self.source_virtual_path,
        }


def package_root(thread_id: str, package_id: str, *, user_id: str | None = None) -> Path:
    """Return a validated package root under the owning Thread."""
    if not package_id or Path(package_id).name != package_id:
        raise ValueError("Invalid package id")
    owner = user_id if user_id is not None else get_effective_user_id()
    return get_paths().thread_dir(thread_id, user_id=owner) / "user-data" / "code-evidence" / package_id


def _member_path(info: zipfile.ZipInfo) -> PurePosixPath:
    raw = info.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or not raw:
        raise CodeEvidencePackageError(f"Unsafe archive path: {info.filename!r}")
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _is_excluded(path: PurePosixPath) -> bool:
    return any(part in _EXCLUDED_PARTS for part in path.parts)


def _preflight(archive: zipfile.ZipFile) -> tuple[list[tuple[zipfile.ZipInfo, PurePosixPath]], list[str], list[dict[str, str]], int]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise CodeEvidencePackageError(f"Archive contains too many members (maximum {MAX_MEMBERS})")
    accepted: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    excluded: list[str] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()
    files: set[str] = set()
    expanded = 0
    for info in infos:
        path = _member_path(info)
        key = path.as_posix().rstrip("/")
        if key in seen:
            raise CodeEvidencePackageError(f"Duplicate archive path: {info.filename!r}")
        seen.add(key)
        if any(parent.as_posix() in files for parent in path.parents) or (not info.is_dir() and any(item.startswith(f"{key}/") for item in files)):
            raise CodeEvidencePackageError(f"Conflicting archive paths: {info.filename!r}")
        if _is_symlink(info):
            raise CodeEvidencePackageError(f"Symbolic links are not allowed: {info.filename!r}")
        if info.file_size < 0 or info.compress_size < 0:
            raise CodeEvidencePackageError(f"Invalid archive member size: {info.filename!r}")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise CodeEvidencePackageError(f"Unsafe compression ratio: {info.filename!r}")
        expanded += info.file_size
        if expanded > MAX_EXPANDED_SIZE:
            raise CodeEvidencePackageError(f"Archive expands beyond {MAX_EXPANDED_SIZE} bytes")
        if info.is_dir() or _is_excluded(path):
            excluded.append(path.as_posix())
        elif path.suffix.lower() in _BINARY_SUFFIXES:
            rejected.append({"path": path.as_posix(), "reason": "Binary target is not accepted"})
        else:
            files.add(key)
            accepted.append((info, path))
    return accepted, excluded, rejected, expanded


def _write_manifest(root: Path, manifest: PackageManifest) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def accept_package(
    source: BinaryIO,
    *,
    thread_id: str,
    original_filename: str,
    max_compressed_size: int = MAX_COMPRESSED_SIZE,
) -> tuple[PackageManifest, Path]:
    """Validate and atomically extract one ZIP package for a Thread."""
    if not original_filename.lower().endswith(".zip"):
        raise CodeEvidencePackageError("Code Evidence Package must be a ZIP archive")
    thread_root = get_paths().thread_dir(thread_id, user_id=get_effective_user_id()) / "user-data" / "code-evidence"
    thread_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".package-", dir=thread_root))
    package_id = uuid.uuid4().hex
    try:
        archive_path = temporary / "package.zip"
        total = 0
        with archive_path.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > max_compressed_size:
                    raise CodeEvidencePackageError(f"Archive exceeds {max_compressed_size} compressed bytes")
                target.write(chunk)
        with zipfile.ZipFile(archive_path) as archive:
            accepted, excluded, rejected, expanded = _preflight(archive)
            source_root = temporary / "source"
            source_root.mkdir()
            extracted = 0
            for info, path in accepted:
                destination = source_root.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source_file, destination.open("wb") as target:
                    while chunk := source_file.read(1024 * 1024):
                        extracted += len(chunk)
                        if extracted > MAX_EXPANDED_SIZE:
                            raise CodeEvidencePackageError(f"Archive expanded beyond {MAX_EXPANDED_SIZE} bytes")
                        target.write(chunk)
            manifest = PackageManifest(package_id, original_filename, tuple(p.as_posix() for _, p in accepted), tuple(excluded), tuple(rejected), total, expanded)
            _write_manifest(temporary, manifest)
        final_root = thread_root / package_id
        os.replace(temporary, final_root)
        return manifest, final_root
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def read_manifest(thread_id: str, package_id: str) -> dict:
    root = package_root(thread_id, package_id)
    try:
        return json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(package_id) from exc


def list_packages(thread_id: str) -> list[dict]:
    root = get_paths().thread_dir(thread_id, user_id=get_effective_user_id()) / "user-data" / "code-evidence"
    if not root.is_dir():
        return []
    result = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            try:
                result.append(read_manifest(thread_id, child.name))
            except FileNotFoundError:
                continue
    return result


def delete_package(thread_id: str, package_id: str) -> None:
    root = package_root(thread_id, package_id)
    if not root.is_dir():
        raise FileNotFoundError(package_id)
    shutil.rmtree(root)
