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


@pytest.mark.parametrize("path", ["/projects/../secret.txt", "/projects/hello.txt/../../secret"])
def test_traversal_is_rejected(tmp_path: Path, path: str) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    store = LocalFileStore([RootConfig("/projects", root)])

    with pytest.raises(FileAccessError, match="outside allowed roots"):
        store.read(path)


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
