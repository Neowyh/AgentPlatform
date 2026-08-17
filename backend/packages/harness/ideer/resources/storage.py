"""Safe filesystem storage for immutable Skill and Agent resource versions."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ideer.persistence.models.resource_catalog import ResourceType


class StorageError(RuntimeError):
    pass


class StorageValidationError(StorageError):
    pass


class StorageConflict(StorageError):
    pass


@dataclass(frozen=True)
class StorageLimits:
    max_files: int = 1_000
    max_total_bytes: int = 100 * 1024 * 1024
    max_file_bytes: int = 20 * 1024 * 1024
    max_archive_bytes: int = 100 * 1024 * 1024


@dataclass(frozen=True)
class StagedResource:
    resource_type: ResourceType
    resource_id: str
    path: Path
    content_hash: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class InspectedResource:
    resource_type: ResourceType
    content_hash: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class PublishedResource:
    resource_type: ResourceType
    resource_id: str
    version: int
    path: Path
    storage_key: str
    content_hash: str


@dataclass(frozen=True)
class DraftResource:
    resource_type: ResourceType
    resource_id: str
    revision: int
    path: Path
    storage_key: str
    content_hash: str


@dataclass(frozen=True)
class ReconciliationReport:
    missing_versions: list[str]
    hash_mismatches: list[str]
    unreferenced_versions: list[str]
    orphan_staging: list[str]
    missing_drafts: list[str]
    draft_hash_mismatches: list[str]
    orphan_drafts: list[str]


class ResourceStorage:
    _TYPE_DIRECTORIES = {
        ResourceType.SKILL: "skills",
        ResourceType.AGENT: "agents",
    }
    _EXECUTABLE_SUFFIXES = {".bat", ".cmd", ".com", ".dll", ".exe", ".msi", ".ps1", ".sh", ".so"}
    _AGENT_RUNTIME_ENTRIES = {"agent-memory", "memory.json", "outputs", "threads", "uploads", "user-data"}

    def __init__(
        self,
        base_dir: str | Path,
        *,
        limits: StorageLimits | None = None,
        allow_scanned_executables: bool = False,
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.resources_root = self.base_dir / "resources"
        self.limits = limits or StorageLimits()
        self.allow_scanned_executables = allow_scanned_executables

    @staticmethod
    def _resource_type(value: ResourceType | str) -> ResourceType:
        try:
            resource_type = ResourceType(value)
        except ValueError as exc:
            raise StorageValidationError(f"Unsupported filesystem resource type: {value}") from exc
        if resource_type == ResourceType.WORKFLOW:
            raise StorageValidationError("Workflow content is stored in the database")
        return resource_type

    @staticmethod
    def _resource_id(value: str) -> str:
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise StorageValidationError("resource_id must be a UUID") from exc
        return str(parsed)

    def _resource_root(self, resource_type: ResourceType, resource_id: str) -> Path:
        return self.resources_root / self._TYPE_DIRECTORIES[resource_type] / resource_id

    @staticmethod
    def _relative_files(source: Path) -> list[tuple[Path, Path]]:
        files: list[tuple[Path, Path]] = []
        for entry in source.rglob("*"):
            relative = entry.relative_to(source)
            if entry.is_symlink():
                raise StorageValidationError(f"Resource contains symlink: {relative.as_posix()}")
            if entry.is_dir():
                continue
            if not entry.is_file():
                raise StorageValidationError(f"Resource contains non-regular file: {relative.as_posix()}")
            files.append((relative, entry))
        return sorted(files, key=lambda item: item[0].as_posix())

    def _validate_files(self, resource_type: ResourceType, files: list[tuple[Path, Path]]) -> tuple[int, int]:
        if len(files) > self.limits.max_files:
            raise StorageValidationError(f"Resource file count exceeds limit {self.limits.max_files}")
        names = {relative.as_posix() for relative, _ in files}
        required = "SKILL.md" if resource_type == ResourceType.SKILL else "config.yaml"
        if required not in names:
            raise StorageValidationError(f"Resource is missing required file {required}")

        total_bytes = 0
        for relative, source in files:
            if resource_type == ResourceType.AGENT and relative.parts[0] in self._AGENT_RUNTIME_ENTRIES:
                raise StorageValidationError(f"Agent definition contains runtime state: {relative.as_posix()}")
            metadata = source.lstat()
            if not self.allow_scanned_executables and (metadata.st_mode & 0o111 or source.suffix.lower() in self._EXECUTABLE_SUFFIXES):
                raise StorageValidationError(f"Resource contains unscanned executable content: {relative.as_posix()}")
            if metadata.st_size > self.limits.max_file_bytes:
                raise StorageValidationError(f"Resource file exceeds size limit: {relative.as_posix()}")
            total_bytes += metadata.st_size
            if total_bytes > self.limits.max_total_bytes:
                raise StorageValidationError(f"Resource total size exceeds limit {self.limits.max_total_bytes}")
        return len(files), total_bytes

    def inspect_directory(self, resource_type: ResourceType | str, source_dir: str | Path) -> InspectedResource:
        canonical_type = self._resource_type(resource_type)
        source = Path(source_dir)
        if source.is_symlink() or not source.is_dir():
            raise StorageValidationError("Resource source must be a non-symlink directory")
        files = self._relative_files(source)
        file_count, total_bytes = self._validate_files(canonical_type, files)
        return InspectedResource(
            resource_type=canonical_type,
            content_hash=self._hash_directory(source),
            file_count=file_count,
            total_bytes=total_bytes,
        )

    @staticmethod
    def _copy_regular_file(source: Path, destination: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise StorageValidationError(f"Resource contains non-regular file: {source.name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with os.fdopen(descriptor, "rb", closefd=False) as source_file, destination.open("xb") as destination_file:
                shutil.copyfileobj(source_file, destination_file)
            destination.chmod(0o644)
        finally:
            os.close(descriptor)

    @staticmethod
    def _hash_directory(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted((value for value in root.rglob("*") if value.is_file()), key=lambda value: value.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix().encode()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            with path.open("rb") as value:
                while chunk := value.read(1024 * 1024):
                    digest.update(chunk)
        return digest.hexdigest()

    def stage_directory(self, resource_type: ResourceType | str, resource_id: str, source_dir: str | Path) -> StagedResource:
        canonical_type = self._resource_type(resource_type)
        canonical_id = self._resource_id(resource_id)
        source = Path(source_dir)
        inspected = self.inspect_directory(canonical_type, source)
        files = self._relative_files(source)
        file_count, total_bytes = inspected.file_count, inspected.total_bytes

        staging_root = self._resource_root(canonical_type, canonical_id) / "staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staged_path = staging_root / str(uuid.uuid4())
        staged_path.mkdir()
        try:
            for relative, source_file in files:
                self._copy_regular_file(source_file, staged_path / relative)
            content_hash = self._hash_directory(staged_path)
        except BaseException:
            shutil.rmtree(staged_path, ignore_errors=True)
            raise
        return StagedResource(
            resource_type=canonical_type,
            resource_id=canonical_id,
            path=staged_path,
            content_hash=content_hash,
            file_count=file_count,
            total_bytes=total_bytes,
        )

    @staticmethod
    def _make_read_only(root: Path) -> None:
        for path in sorted(root.rglob("*"), key=lambda value: len(value.parts), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        root.chmod(0o555)

    def publish_staged(self, staged: StagedResource, *, version: int) -> PublishedResource:
        if version < 1:
            raise ValueError("version must be positive")
        expected_staging_root = self._resource_root(staged.resource_type, staged.resource_id) / "staging"
        if staged.path.parent != expected_staging_root or not staged.path.is_dir():
            raise StorageValidationError("Staged resource is outside its canonical staging directory")
        destination = self._resource_root(staged.resource_type, staged.resource_id) / "versions" / str(version)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise StorageConflict(f"Resource version {version} already exists")
        os.replace(staged.path, destination)
        self._make_read_only(destination)
        return PublishedResource(
            resource_type=staged.resource_type,
            resource_id=staged.resource_id,
            version=version,
            path=destination,
            storage_key=destination.relative_to(self.resources_root).as_posix(),
            content_hash=staged.content_hash,
        )

    def store_draft(self, staged: StagedResource, *, revision: int) -> DraftResource:
        if revision < 1:
            raise ValueError("revision must be positive")
        expected_staging_root = self._resource_root(staged.resource_type, staged.resource_id) / "staging"
        if staged.path.parent != expected_staging_root or not staged.path.is_dir():
            raise StorageValidationError("Staged resource is outside its canonical staging directory")
        destination = self._resource_root(staged.resource_type, staged.resource_id) / "draft" / str(revision)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise StorageConflict(f"Resource draft revision {revision} already exists")
        os.replace(staged.path, destination)
        self._make_read_only(destination)
        return DraftResource(
            resource_type=staged.resource_type,
            resource_id=staged.resource_id,
            revision=revision,
            path=destination,
            storage_key=destination.relative_to(self.resources_root).as_posix(),
            content_hash=staged.content_hash,
        )

    def stage_draft(
        self,
        resource_type: ResourceType | str,
        resource_id: str,
        *,
        revision: int,
    ) -> StagedResource:
        canonical_type = self._resource_type(resource_type)
        canonical_id = self._resource_id(resource_id)
        source = self._resource_root(canonical_type, canonical_id) / "draft" / str(revision)
        if not source.is_dir() or source.is_symlink():
            raise StorageValidationError(f"Resource draft revision {revision} does not exist")
        return self.stage_directory(canonical_type, canonical_id, source)

    def copy_published_version(
        self,
        resource_type: ResourceType | str,
        source_resource_id: str,
        source_version: int,
        target_resource_id: str,
        target_version: int,
    ) -> PublishedResource:
        canonical_type = self._resource_type(resource_type)
        source_id = self._resource_id(source_resource_id)
        source = self._resource_root(canonical_type, source_id) / "versions" / str(source_version)
        if not source.is_dir():
            raise StorageValidationError(f"Published source version {source_version} does not exist")
        staged = self.stage_directory(canonical_type, target_resource_id, source)
        return self.publish_staged(staged, version=target_version)

    def create_run_skill_view(
        self,
        run_id: str,
        versions: list[tuple[str, int, str]],
    ) -> Path:
        """Atomically build a read-only view containing only frozen Skill versions."""

        from ideer.resources.canonical_sandbox import canonical_run_key

        canonical_run_id = canonical_run_key(run_id)
        view_root = self.resources_root / "run-skill-views"
        destination = view_root / canonical_run_id
        if destination.exists():
            expected_ids = {self._resource_id(resource_id) for resource_id, _version, _hash in versions}
            actual_ids = {path.name for path in (destination / "custom").iterdir()} if (destination / "custom").is_dir() else set()
            if actual_ids != expected_ids:
                raise StorageConflict(f"Run Skill view {canonical_run_id} already exists with different resources")
            for resource_id, version, content_hash in versions:
                inspected = self.inspect_directory("skill", destination / "custom" / self._resource_id(resource_id))
                if inspected.content_hash != content_hash:
                    raise StorageConflict(f"Run Skill view {canonical_run_id} has a hash mismatch")
            return destination

        view_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{canonical_run_id}-", dir=view_root))
        try:
            custom_root = staging / "custom"
            custom_root.mkdir()
            seen: set[str] = set()
            for resource_id, version, content_hash in versions:
                canonical_id = self._resource_id(resource_id)
                if canonical_id in seen:
                    raise StorageValidationError(f"Duplicate Skill resource in Run view: {canonical_id}")
                if version < 1:
                    raise StorageValidationError("Skill version must be positive")
                source = self._resource_root(ResourceType.SKILL, canonical_id) / "versions" / str(version)
                inspected = self.inspect_directory("skill", source)
                if inspected.content_hash != content_hash:
                    raise StorageValidationError(f"Frozen Skill hash mismatch for {canonical_id}@{version}")
                target = custom_root / canonical_id
                target.mkdir()
                for relative, source_file in self._relative_files(source):
                    self._copy_regular_file(source_file, target / relative)
                seen.add(canonical_id)
            self._make_read_only(staging)
            os.replace(staging, destination)
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise
        return destination

    @staticmethod
    def _validate_archive_member(info: zipfile.ZipInfo) -> PurePosixPath:
        if "\\" in info.filename:
            raise StorageValidationError("Archive member contains path traversal separator")
        relative = PurePosixPath(info.filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise StorageValidationError("Archive member contains path traversal")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise StorageValidationError("Archive contains symlink")
        return relative

    def stage_archive(self, resource_type: ResourceType | str, resource_id: str, archive_path: str | Path) -> StagedResource:
        archive = Path(archive_path)
        if archive.stat().st_size > self.limits.max_archive_bytes:
            raise StorageValidationError("Archive exceeds compressed size limit")
        self.resources_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as value, tempfile.TemporaryDirectory(prefix="resource-archive-", dir=self.resources_root) as temp_dir:
            members = [info for info in value.infolist() if not info.is_dir()]
            if len(members) > self.limits.max_files:
                raise StorageValidationError(f"Archive file count exceeds limit {self.limits.max_files}")
            total_size = 0
            extracted_root = Path(temp_dir)
            for info in members:
                relative = self._validate_archive_member(info)
                if info.file_size > self.limits.max_file_bytes:
                    raise StorageValidationError(f"Archive member exceeds size limit: {relative.as_posix()}")
                total_size += info.file_size
                if total_size > self.limits.max_total_bytes:
                    raise StorageValidationError("Archive expanded size exceeds limit")
                destination = extracted_root.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with value.open(info) as source_file, destination.open("xb") as destination_file:
                    shutil.copyfileobj(source_file, destination_file)
                destination.chmod(0o644)
            return self.stage_directory(resource_type, resource_id, extracted_root)

    def discard_staged(self, staged: StagedResource) -> bool:
        expected_staging_root = self._resource_root(staged.resource_type, staged.resource_id) / "staging"
        if staged.path.parent != expected_staging_root:
            raise StorageValidationError("Staged resource is outside its canonical staging directory")
        if not staged.path.exists():
            return False
        if staged.path.is_symlink() or not staged.path.is_dir():
            raise StorageValidationError("Staged resource is not a regular directory")
        shutil.rmtree(staged.path)
        return True

    def discard_draft(
        self,
        resource_type: ResourceType | str,
        resource_id: str,
        *,
        revision: int,
    ) -> bool:
        canonical_type = self._resource_type(resource_type)
        canonical_id = self._resource_id(resource_id)
        path = self._resource_root(canonical_type, canonical_id) / "draft" / str(revision)
        if not path.exists():
            return False
        if path.is_symlink() or not path.is_dir() or self._contains_symlink(path):
            raise StorageValidationError("Resource draft is not a regular directory")
        for child in path.rglob("*"):
            child.chmod(0o755 if child.is_dir() else 0o644)
        path.chmod(0o755)
        shutil.rmtree(path)
        return True

    @staticmethod
    def _safe_storage_key(storage_key: str) -> PurePosixPath:
        value = PurePosixPath(storage_key)
        if value.is_absolute() or ".." in value.parts or "\\" in storage_key:
            raise StorageValidationError(f"Invalid storage key: {storage_key}")
        return value

    @staticmethod
    def _contains_symlink(root: Path) -> bool:
        return root.is_symlink() or any(path.is_symlink() for path in root.rglob("*"))

    def reconcile(
        self,
        expected_versions: dict[str, str],
        *,
        expected_drafts: dict[str, str] | None = None,
    ) -> ReconciliationReport:
        expected: dict[str, str] = {}
        for storage_key, content_hash in expected_versions.items():
            expected[self._safe_storage_key(storage_key).as_posix()] = content_hash

        expected_draft_map: dict[str, str] = {}
        for storage_key, content_hash in (expected_drafts or {}).items():
            expected_draft_map[self._safe_storage_key(storage_key).as_posix()] = content_hash

        disk_versions: set[str] = set()
        disk_drafts: set[str] = set()
        orphan_staging: list[str] = []
        for type_directory in self._TYPE_DIRECTORIES.values():
            type_root = self.resources_root / type_directory
            if not type_root.is_dir():
                continue
            for resource_root in type_root.iterdir():
                if resource_root.is_symlink() or not resource_root.is_dir():
                    continue
                versions_root = resource_root / "versions"
                if versions_root.is_dir():
                    for version_root in versions_root.iterdir():
                        if version_root.is_dir() and not version_root.is_symlink():
                            disk_versions.add(version_root.relative_to(self.resources_root).as_posix())
                staging_root = resource_root / "staging"
                if staging_root.is_dir():
                    orphan_staging.extend(path.relative_to(self.resources_root).as_posix() for path in staging_root.iterdir() if path.is_dir() and not path.is_symlink())
                drafts_root = resource_root / "draft"
                if drafts_root.is_dir():
                    for draft_root in drafts_root.iterdir():
                        if draft_root.is_dir() and not draft_root.is_symlink():
                            disk_drafts.add(draft_root.relative_to(self.resources_root).as_posix())

        missing_versions: list[str] = []
        hash_mismatches: list[str] = []
        for storage_key, content_hash in expected.items():
            version_root = self.resources_root.joinpath(*PurePosixPath(storage_key).parts)
            if storage_key not in disk_versions or not version_root.is_dir():
                missing_versions.append(storage_key)
            elif self._contains_symlink(version_root) or self._hash_directory(version_root) != content_hash:
                hash_mismatches.append(storage_key)

        missing_drafts: list[str] = []
        draft_hash_mismatches: list[str] = []
        for storage_key, content_hash in expected_draft_map.items():
            draft_root = self.resources_root.joinpath(*PurePosixPath(storage_key).parts)
            if storage_key not in disk_drafts or not draft_root.is_dir():
                missing_drafts.append(storage_key)
            elif self._contains_symlink(draft_root) or self._hash_directory(draft_root) != content_hash:
                draft_hash_mismatches.append(storage_key)

        return ReconciliationReport(
            missing_versions=sorted(missing_versions),
            hash_mismatches=sorted(hash_mismatches),
            unreferenced_versions=sorted(disk_versions - set(expected)),
            orphan_staging=sorted(orphan_staging),
            missing_drafts=sorted(missing_drafts),
            draft_hash_mismatches=sorted(draft_hash_mismatches),
            orphan_drafts=sorted(disk_drafts - set(expected_draft_map)),
        )
