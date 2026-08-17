"""Tests covering missing error paths in ideer.agents.memory.storage.

Targets:
- Lines 49, 54, 59: abstract method ``pass`` bodies (via concrete subclass calling super)
- Lines 149-150, 161-162: OSError from stat() in load()
- Lines 177-178: OSError from stat() in reload()
- Lines 204-205: OSError from stat() in save()
- Line 228: second check in get_memory_storage double-checked locking
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ideer.agents.memory.storage import (
    FileMemoryStorage,
    MemoryStorage,
    create_empty_memory,
    get_memory_storage,
)
from ideer.config.memory_config import MemoryConfig

# ---------------------------------------------------------------------------
# Lines 49, 54, 59 -- abstract method ``pass`` bodies
# ---------------------------------------------------------------------------


class _DelegatingStorage(MemoryStorage):
    """Concrete subclass that calls super() to exercise the abstract ``pass`` bodies."""

    def __init__(self):
        self._data = create_empty_memory()

    def load(self, agent_name=None, *, user_id=None):
        # Call the abstract base to exercise line 49
        super().load(agent_name, user_id=user_id)
        return self._data

    def reload(self, agent_name=None, *, user_id=None):
        # Call the abstract base to exercise line 54
        super().reload(agent_name, user_id=user_id)
        return self._data

    def save(self, memory_data, agent_name=None, *, user_id=None):
        # Call the abstract base to exercise line 59
        super().save(memory_data, agent_name, user_id=user_id)
        self._data = memory_data
        return True


class TestAbstractMethodBodies:
    """Cover the ``pass`` statements in the abstract base class methods."""

    def test_abstract_load_body(self):
        """Calling super().load() should exercise the abstract pass (line 49)."""
        storage = _DelegatingStorage()
        result = storage.load()
        assert isinstance(result, dict)
        assert result["version"] == "1.0"

    def test_abstract_reload_body(self):
        """Calling super().reload() should exercise the abstract pass (line 54)."""
        storage = _DelegatingStorage()
        result = storage.reload()
        assert isinstance(result, dict)

    def test_abstract_save_body(self):
        """Calling super().save() should exercise the abstract pass (line 59)."""
        storage = _DelegatingStorage()
        data = create_empty_memory()
        result = storage.save(data)
        assert result is True


def _make_mock_path(exists: bool = True, stat_raises: bool = False):
    """Create a MagicMock that behaves like a Path for exists() and stat()."""
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = exists
    if stat_raises:
        mock_path.stat.side_effect = OSError("stat failed")
    else:
        mock_stat_result = MagicMock()
        mock_stat_result.st_mtime = 12345.0
        mock_path.stat.return_value = mock_stat_result
    return mock_path


class TestLoadOSErrorPaths:
    """Cover OSError handling when stat() fails inside load()."""

    def test_load_oserror_on_initial_stat(self, tmp_path):
        """Lines 149-150: OSError from stat() on initial mtime read should set mtime=None."""
        storage = FileMemoryStorage()

        # File "exists" but stat() raises -> triggers lines 149-150
        file_path = _make_mock_path(exists=True, stat_raises=True)

        with patch.object(storage, "_get_memory_file_path", return_value=file_path):
            with patch.object(storage, "_load_memory_from_file", return_value=create_empty_memory()):
                result = storage.load()

        assert result["version"] == "1.0"
        assert "facts" in result

    def test_load_oserror_on_final_stat(self, tmp_path):
        """Lines 161-162: OSError from stat() on final mtime read should set mtime=None."""
        storage = FileMemoryStorage()

        # Track stat calls: first succeeds (line 148), second raises (line 160)
        stat_call_count = 0

        def stat_side_effect():
            nonlocal stat_call_count
            stat_call_count += 1
            if stat_call_count == 2:
                raise OSError("stat failed on final read")
            result = MagicMock()
            result.st_mtime = 12345.0
            return result

        file_path = _make_mock_path(exists=True)
        file_path.stat.side_effect = stat_side_effect

        with patch.object(storage, "_get_memory_file_path", return_value=file_path):
            with patch.object(storage, "_load_memory_from_file", return_value=create_empty_memory()):
                result = storage.load()

        assert result["version"] == "1.0"
        assert stat_call_count == 2


# ---------------------------------------------------------------------------
# Lines 177-178 -- OSError from stat() in reload()
# ---------------------------------------------------------------------------


class TestReloadOSErrorPath:
    """Cover OSError handling when stat() fails inside reload()."""

    def test_reload_oserror_on_stat(self, tmp_path):
        """Lines 177-178: OSError from stat() during reload should set mtime=None."""
        storage = FileMemoryStorage()

        # File exists but stat() raises -> triggers lines 177-178
        file_path = _make_mock_path(exists=True, stat_raises=True)

        with patch.object(storage, "_get_memory_file_path", return_value=file_path):
            with patch.object(storage, "_load_memory_from_file", return_value=create_empty_memory()):
                result = storage.reload()

        assert result["version"] == "1.0"


# ---------------------------------------------------------------------------
# Lines 204-205 -- OSError from stat() in save()
# ---------------------------------------------------------------------------


class TestSaveOSErrorPath:
    """Cover OSError handling when stat() fails inside save() after file write."""

    def test_save_oserror_on_post_write_stat(self, tmp_path):
        """Lines 204-205: OSError from stat() after the file has been written.

        The inner try/except on lines 202-205 should catch the OSError from
        stat() and set mtime=None, while save() still returns True.
        """
        memory_file = tmp_path / "memory.json"

        mock_paths = MagicMock()
        mock_paths.memory_file = memory_file

        with patch("ideer.agents.memory.storage.get_paths", return_value=mock_paths):
            with patch(
                "ideer.agents.memory.storage.get_memory_config",
                return_value=MemoryConfig(storage_path=""),
            ):
                storage = FileMemoryStorage()

                # Patch _get_memory_file_path to return a path whose
                # stat() raises, but whose parent/mkdir/replace still work
                # by using the real path under the hood.
                real_path = memory_file

                class _HybridPath(type(memory_file)):
                    """Delegates I/O to real_path but raises on stat()."""

                    def stat(self, *, follow_symlinks=True):
                        raise OSError("stat failed after write")

                    @property
                    def parent(self):
                        return real_path.parent

                    def with_suffix(self, suffix):
                        return real_path.with_suffix(suffix)

                    def __fspath__(self):
                        return str(real_path)

                hybrid = _HybridPath(str(real_path))
                with patch.object(storage, "_get_memory_file_path", return_value=hybrid):
                    result = storage.save(create_empty_memory())

                # The inner except (lines 204-205) catches the OSError;
                # save() should still return True.
                assert result is True


# ---------------------------------------------------------------------------
# Line 228 -- second check in get_memory_storage double-checked locking
# ---------------------------------------------------------------------------


class TestGetMemoryStorageDoubleCheckedLocking:
    """Cover line 228: the second ``_storage_instance is not None`` check inside the lock."""

    def test_second_check_returns_instance_set_by_another_thread(self):
        """Line 228: if another thread sets _storage_instance between the outer
        check and acquiring the lock, the second check should return it."""
        import ideer.agents.memory.storage as storage_mod

        storage_mod._storage_instance = None

        sentinel = FileMemoryStorage.__new__(FileMemoryStorage)

        # We will set _storage_instance right when the lock is acquired.
        real_lock = storage_mod._storage_lock

        acquire_count = 0

        class _InterceptingLock:
            """A lock wrapper that sets _storage_instance on the first acquire."""

            def __enter__(self):
                nonlocal acquire_count
                acquire_count += 1
                if acquire_count == 1:
                    # Simulate another thread winning the race
                    storage_mod._storage_instance = sentinel
                real_lock.__enter__()
                return self

            def __exit__(self, *args):
                real_lock.__exit__(*args)

        try:
            with patch.object(storage_mod, "_storage_lock", _InterceptingLock()):
                with patch(
                    "ideer.agents.memory.storage.get_memory_config",
                    return_value=MemoryConfig(storage_class="ideer.agents.memory.storage.FileMemoryStorage"),
                ):
                    result = get_memory_storage()

            # Should return the sentinel (set by "another thread"), not a new instance
            assert result is sentinel
        finally:
            storage_mod._storage_instance = None
