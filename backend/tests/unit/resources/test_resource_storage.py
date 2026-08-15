"""Filesystem safety and publication contracts for canonical resources."""

from __future__ import annotations

import os
import stat
import uuid
import zipfile
from pathlib import Path

import pytest

from ideer.persistence.models.resource_catalog import ResourceType
from ideer.resources.storage import ResourceStorage, StorageLimits, StorageValidationError


def _uuid() -> str:
    return str(uuid.uuid4())


def _skill_source(root: Path, text: str = "# Example\n") -> Path:
    source = root / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(text)
    support = source / "references"
    support.mkdir()
    (support / "guide.md").write_text("guide\n")
    return source


def test_stage_and_publish_use_uuid_layout_hash_and_read_only_versions(tmp_path: Path) -> None:
    resource_id = _uuid()
    storage = ResourceStorage(tmp_path)
    source = _skill_source(tmp_path)

    staged = storage.stage_directory(ResourceType.SKILL, resource_id, source)
    published = storage.publish_staged(staged, version=1)

    assert staged.content_hash == published.content_hash
    assert published.path == tmp_path / "resources" / "skills" / resource_id / "versions" / "1"
    assert (published.path / "SKILL.md").read_text() == "# Example\n"
    assert stat.S_IMODE(published.path.stat().st_mode) == 0o555
    assert stat.S_IMODE((published.path / "SKILL.md").stat().st_mode) == 0o444
    assert not staged.path.exists()


def test_same_content_has_stable_hash_and_fork_is_an_independent_copy(tmp_path: Path) -> None:
    source_id = _uuid()
    target_id = _uuid()
    storage = ResourceStorage(tmp_path)
    source = _skill_source(tmp_path)
    published = storage.publish_staged(storage.stage_directory("skill", source_id, source), version=1)

    forked = storage.copy_published_version("skill", source_id, 1, target_id, 1)

    assert forked.content_hash == published.content_hash
    assert forked.path != published.path
    assert os.stat(forked.path / "SKILL.md").st_ino != os.stat(published.path / "SKILL.md").st_ino


@pytest.mark.parametrize("unsafe_kind", ["symlink", "executable"])
def test_stage_rejects_links_and_unscanned_executable_content(tmp_path: Path, unsafe_kind: str) -> None:
    source = _skill_source(tmp_path)
    if unsafe_kind == "symlink":
        (source / "linked.md").symlink_to(source / "SKILL.md")
    else:
        script = source / "run.sh"
        script.write_text("#!/bin/sh\nexit 0\n")
        script.chmod(0o755)

    with pytest.raises(StorageValidationError, match="symlink|executable"):
        ResourceStorage(tmp_path).stage_directory("skill", _uuid(), source)


def test_stage_enforces_file_count_and_total_size_limits(tmp_path: Path) -> None:
    source = _skill_source(tmp_path)
    (source / "extra.md").write_text("extra")
    storage = ResourceStorage(tmp_path, limits=StorageLimits(max_files=2, max_total_bytes=1024, max_file_bytes=1024))

    with pytest.raises(StorageValidationError, match="file count"):
        storage.stage_directory("skill", _uuid(), source)


def test_archive_rejects_path_traversal_before_extraction(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as value:
        value.writestr("SKILL.md", "# Safe looking")
        value.writestr("../escape.txt", "escape")

    storage = ResourceStorage(tmp_path)
    with pytest.raises(StorageValidationError, match="path traversal"):
        storage.stage_archive("skill", _uuid(), archive)

    assert not (tmp_path / "escape.txt").exists()


def test_reconcile_reports_missing_mismatched_unreferenced_and_staging_orphans(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    referenced_id = _uuid()
    unreferenced_id = _uuid()
    staged_id = _uuid()
    missing_id = _uuid()
    source = _skill_source(tmp_path)
    referenced = storage.publish_staged(storage.stage_directory("skill", referenced_id, source), version=1)
    unreferenced = storage.publish_staged(storage.stage_directory("skill", unreferenced_id, source), version=1)
    staged = storage.stage_directory("skill", staged_id, source)

    referenced.path.chmod(0o755)
    (referenced.path / "SKILL.md").chmod(0o644)
    (referenced.path / "SKILL.md").write_text("tampered\n")
    report = storage.reconcile(
        {
            referenced.storage_key: referenced.content_hash,
            f"skills/{missing_id}/versions/1": "m" * 64,
        }
    )

    assert report.missing_versions == [f"skills/{missing_id}/versions/1"]
    assert report.hash_mismatches == [referenced.storage_key]
    assert report.unreferenced_versions == [unreferenced.storage_key]
    assert report.orphan_staging == [staged.path.relative_to(storage.resources_root).as_posix()]


def test_discard_staged_is_idempotent(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    staged = storage.stage_directory("skill", _uuid(), _skill_source(tmp_path))

    assert storage.discard_staged(staged) is True
    assert storage.discard_staged(staged) is False


def test_draft_is_canonical_and_publication_stages_an_independent_copy(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    resource_id = _uuid()
    staged = storage.stage_directory("skill", resource_id, _skill_source(tmp_path))

    draft = storage.store_draft(staged, revision=1)
    publication_staging = storage.stage_draft("skill", resource_id, revision=1)

    assert draft.storage_key == f"skills/{resource_id}/draft/1"
    assert draft.content_hash == staged.content_hash
    assert publication_staging.content_hash == draft.content_hash
    assert publication_staging.path != draft.path
    assert draft.path.is_dir()


def test_reconcile_reports_draft_consistency_without_deleting_any_content(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    resource_id = _uuid()
    orphan_id = _uuid()
    source = _skill_source(tmp_path)
    draft = storage.store_draft(storage.stage_directory("skill", resource_id, source), revision=1)
    orphan = storage.store_draft(storage.stage_directory("skill", orphan_id, source), revision=1)

    draft.path.chmod(0o755)
    (draft.path / "SKILL.md").chmod(0o644)
    (draft.path / "SKILL.md").write_text("changed")
    report = storage.reconcile({}, expected_drafts={draft.storage_key: draft.content_hash})

    assert report.draft_hash_mismatches == [draft.storage_key]
    assert report.orphan_drafts == [orphan.storage_key]
    assert draft.path.exists()
    assert orphan.path.exists()


def test_inspection_is_read_only_and_agent_runtime_state_is_rejected(tmp_path: Path) -> None:
    storage = ResourceStorage(tmp_path)
    source = tmp_path / "agent-source"
    source.mkdir()
    (source / "config.yaml").write_text("name: example\n")

    inspected = storage.inspect_directory("agent", source)

    assert len(inspected.content_hash) == 64
    assert not storage.resources_root.exists()
    (source / "memory.json").write_text("{}")
    with pytest.raises(StorageValidationError, match="runtime state"):
        storage.inspect_directory("agent", source)
