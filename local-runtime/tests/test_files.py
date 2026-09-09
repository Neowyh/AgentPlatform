import ctypes
import os
from pathlib import Path

import pytest
from core.files import FileAccessError, LocalFileStore, RootConfig


def test_list_and_read_expose_only_logical_paths(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    (root / "hello.txt").write_text("hello", encoding="utf-8")
    store = LocalFileStore([RootConfig("/projects", root)])

    assert store.list("/projects") == ["/projects/hello.txt"]
    assert store.read("/projects/hello.txt") == "hello"


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("/projects/../secret.txt", "outside allowed roots"),
        ("/projects/hello.txt/../../secret", "outside allowed roots"),
        ("/PROJECTS-OTHER/secret.txt", "outside allowed roots"),
        ("//server/share/secret.txt", "outside allowed roots"),
        ("\\\\server\\share\\secret.txt", "invalid logical path"),
    ],
)
def test_unsafe_paths_are_rejected(tmp_path: Path, path: str, error: str) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    store = LocalFileStore([RootConfig("/projects", root)])

    with pytest.raises(FileAccessError, match=error):
        store.read(path)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows path semantics")
def test_case_variant_inside_root_is_canonicalized(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    (root / "ReadMe.txt").write_text("safe", encoding="utf-8")
    store = LocalFileStore([RootConfig("/projects", root)])

    assert store.read("/PROJECTS/README.TXT") == "safe"


@pytest.mark.skipif(os.name != "nt", reason="requires Windows junctions")
def test_junction_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    outside = tmp_path / "Outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    junction = root / "linked"
    result = os.system(f'cmd /c mklink /J "{junction}" "{outside}" >NUL')
    if result != 0:
        pytest.skip("junction creation is unavailable")
    store = LocalFileStore([RootConfig("/projects", root)])

    with pytest.raises(FileAccessError, match="outside allowed roots"):
        store.read("/projects/linked/secret.txt")


@pytest.mark.skipif(os.name != "nt", reason="requires Windows exclusive file handles")
def test_locked_file_has_safe_error_without_drive_path(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    locked = root / "locked.txt"
    locked.write_text("secret", encoding="utf-8")
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(str(locked), 0x80000000, 0, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        pytest.skip("exclusive handle could not be created")
    try:
        store = LocalFileStore([RootConfig("/projects", root)])
        with pytest.raises(FileAccessError) as error:
            store.read("/projects/locked.txt")
        assert str(tmp_path).lower() not in str(error.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")
    store = LocalFileStore([RootConfig("/projects", root)])

    with pytest.raises(FileAccessError, match="outside allowed roots"):
        store.read("/projects/link.txt")


def test_errors_do_not_reveal_physical_paths(tmp_path: Path) -> None:
    store = LocalFileStore([RootConfig("/projects", tmp_path / "missing")])

    with pytest.raises(FileAccessError) as error:
        store.read("/projects/nope.txt")
    assert str(tmp_path) not in str(error.value)
