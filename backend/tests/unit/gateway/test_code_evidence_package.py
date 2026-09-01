import io
import stat
import zipfile

import pytest

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
