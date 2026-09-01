import io
import stat
import zipfile
from pathlib import PurePosixPath

import pytest

from ideer.uploads import code_evidence
from ideer.uploads.code_evidence import CodeEvidencePackageError, _preflight


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


def test_preflight_reports_binary_targets_as_rejected():
    archive = make_zip([("build/app.o", b"binary", None), ("src/app.o", b"binary", None)])

    _, excluded, rejected, _ = _preflight(archive)

    assert excluded == ["build/app.o"]
    assert rejected == [{"path": "src/app.o", "reason": "Binary target is not accepted"}]


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
