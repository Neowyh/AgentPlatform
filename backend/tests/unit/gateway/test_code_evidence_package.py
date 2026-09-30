import io
import stat
import zipfile
from pathlib import PurePosixPath

import pytest

from app.agentplatform import code_evidence
from app.agentplatform.code_evidence import CodeEvidencePackageError, _preflight
from deerflow.uploads.code_evidence import package_root as runtime_package_root


def make_zip(entries: list[tuple[str, bytes, int | None]]):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.external_attr = mode << 16
            archive.writestr(info, data)
    stream.seek(0)
    return zipfile.ZipFile(stream)


def test_preflight_preserves_cross_file_sources_and_excludes_build_outputs():
    archive = make_zip(
        [
            ("src/main.c", b"int main(void) { return 0; }", None),
            ("include/main.h", b"#pragma once", None),
            ("build/app.o", b"binary", None),
        ]
    )

    accepted, excluded, rejected, expanded = _preflight(archive)

    assert [path.as_posix() for _, path in accepted] == ["src/main.c", "include/main.h"]
    assert excluded == ["build/app.o"]
    assert rejected == []
    assert expanded == 46


@pytest.mark.parametrize("name", ["../escape.c", "/absolute.c", "src/../../escape.c"])
def test_preflight_rejects_unsafe_paths(name):
    archive = make_zip([(name, b"x", None)])
    with pytest.raises(CodeEvidencePackageError, match="Unsafe archive path"):
        _preflight(archive)


def test_preflight_rejects_symbolic_links():
    archive = make_zip([("src/link.c", b"target", stat.S_IFLNK | 0o777)])
    with pytest.raises(CodeEvidencePackageError, match="Symbolic links"):
        _preflight(archive)


def test_preflight_rejects_duplicate_paths():
    archive = make_zip([("src/main.c", b"one", None), ("src/main.c", b"two", None)])
    with pytest.raises(CodeEvidencePackageError, match="Duplicate"):
        _preflight(archive)


def test_preflight_rejects_file_directory_conflict_in_either_order():
    for entries in [
        [("src", b"file", None), ("src/main.c", b"child", None)],
        [("src/main.c", b"child", None), ("src", b"file", None)],
    ]:
        archive = make_zip(entries)
        with pytest.raises(CodeEvidencePackageError, match="Conflicting"):
            _preflight(archive)


def test_preflight_accepts_whitelisted_binary_suffixes():
    archive = make_zip(
        [
            ("build/app.o", b"binary", None),
            ("src/app.o", b"\x7fELF", None),
            ("firmware.bin", b"\x00\x01", None),
            ("listing.hex", b":10000000", None),
            ("symbols.map", b"Archive member included", None),
            ("libfoo.a", b"!<arch>", None),
            ("app.exe", b"MZ", None),
        ]
    )

    accepted, excluded, rejected, _ = _preflight(archive)

    assert excluded == ["build/app.o"]
    assert rejected == []
    assert [path.as_posix() for _, path in accepted] == [
        "src/app.o",
        "firmware.bin",
        "listing.hex",
        "symbols.map",
        "libfoo.a",
        "app.exe",
    ]


def test_preflight_rejects_oversized_binary_with_size_limit_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(code_evidence, "BINARY_EVIDENCE_MAX_BYTES", 4)
    archive = make_zip([("src/app.o", b"0123456789", None)])

    _, _, rejected, _ = _preflight(archive)

    assert rejected == [{"path": "src/app.o", "reason": "Binary evidence exceeds the 4 bytes per-file limit"}]


def test_preflight_still_accepts_unknown_suffixes_as_text():
    archive = make_zip([("notes.dat", b"plain text", None)])

    accepted, excluded, rejected, _ = _preflight(archive)

    assert [path.as_posix() for _, path in accepted] == ["notes.dat"]
    assert excluded == []
    assert rejected == []


def test_accept_package_records_binary_flags_and_bytes_in_manifest():
    payload = b"\x7fELF-firmware"
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("src/main.c", b"int main(void) { return 0; }")
        archive.writestr("firmware.bin", payload)
    source.seek(0)

    manifest, root = code_evidence.accept_package(source, thread_id="thread-1", original_filename="evidence.zip")

    by_path = {entry["path"]: entry for entry in manifest.accepted}
    assert by_path["src/main.c"] == {"path": "src/main.c", "binary": False, "bytes": 28}
    assert by_path["firmware.bin"] == {"path": "firmware.bin", "binary": True, "bytes": len(payload)}
    assert manifest.as_dict()["accepted"] == list(manifest.accepted)
    assert (root / "source" / "firmware.bin").read_bytes() == payload


def test_accept_package_bounds_actual_extracted_bytes(tmp_path, monkeypatch):
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("src/main.c", b"0123456789")
    source.seek(0)
    monkeypatch.setattr(code_evidence, "MAX_EXPANDED_SIZE", 5)
    monkeypatch.setattr(
        code_evidence,
        "_preflight",
        lambda archive: ([(archive.infolist()[0], PurePosixPath("src/main.c"))], [], [], 0),
    )

    with pytest.raises(CodeEvidencePackageError, match="expanded"):
        code_evidence.accept_package(source, thread_id="thread-1", original_filename="evidence.zip")


def test_accept_package_applies_caller_compressed_size_limit():
    source = io.BytesIO()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("src/main.c", b"source")
    source.seek(0)

    with pytest.raises(CodeEvidencePackageError, match="compressed bytes"):
        code_evidence.accept_package(
            source,
            thread_id="thread-1",
            original_filename="evidence.zip",
            max_compressed_size=1,
        )


@pytest.mark.parametrize("package_id", ["../escape", "/absolute", ""])
def test_runtime_package_root_rejects_unvalidated_package_id(package_id):
    with pytest.raises(ValueError, match="Invalid package id"):
        runtime_package_root("thread-1", package_id)
