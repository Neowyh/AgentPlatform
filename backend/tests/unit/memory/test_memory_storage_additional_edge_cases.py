"""Extra coverage tests for storage.py missed lines.

Targets: 92, 100-101, 131-133
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ideer.agents.memory.storage import FileMemoryStorage
from ideer.config.memory_config import MemoryConfig

# --- Line 92: user_id + absolute storage_path ---


def test_get_memory_file_path_user_id_with_absolute_storage_path():
    """Line 92: When user_id is set and config.storage_path is absolute, use it."""
    storage = FileMemoryStorage()
    with patch(
        "ideer.agents.memory.storage.get_memory_config",
        return_value=MemoryConfig(storage_path="/tmp/shared-memory.json"),
    ):
        result = storage._get_memory_file_path(user_id="u1")
    assert result == Path("/tmp/shared-memory.json")


# --- Lines 100-101: legacy path with relative storage_path ---


def test_get_memory_file_path_legacy_with_relative_storage_path():
    """Lines 100-101: Legacy path with relative storage_path resolves against base_dir."""
    storage = FileMemoryStorage()
    mock_paths = MagicMock()
    mock_paths.base_dir = Path("/workspace")

    with (
        patch("ideer.agents.memory.storage.get_memory_config", return_value=MemoryConfig(storage_path=".ideer/memory.json")),
        patch("ideer.agents.memory.storage.get_paths", return_value=mock_paths),
    ):
        result = storage._get_memory_file_path()
    assert result == Path("/workspace/.ideer/memory.json")


def test_get_memory_file_path_legacy_with_absolute_storage_path():
    """Line 100: Legacy path with absolute storage_path uses it as-is."""
    storage = FileMemoryStorage()
    with patch(
        "ideer.agents.memory.storage.get_memory_config",
        return_value=MemoryConfig(storage_path="/opt/memory.json"),
    ):
        result = storage._get_memory_file_path()
    assert result == Path("/opt/memory.json")


# --- Lines 131-133: JSON decode error in _load_memory_from_file ---


def test_load_memory_from_file_returns_empty_on_json_error(tmp_path):
    """Lines 131-133: Returns empty memory on JSON decode error."""
    bad_file = tmp_path / "memory.json"
    bad_file.write_text("not valid json {{{")

    storage = FileMemoryStorage()
    with patch.object(storage, "_get_read_memory_file_path", return_value=bad_file):
        result = storage._load_memory_from_file()
    assert result["version"] == "1.0"
    assert result["facts"] == []


def test_load_memory_from_file_returns_empty_on_os_error(tmp_path):
    """Lines 131-133: Returns empty memory on OSError."""
    storage = FileMemoryStorage()
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.__fspath__ = MagicMock(return_value="/nonexistent/path/memory.json")

    with patch.object(storage, "_get_read_memory_file_path", return_value=mock_path):
        # open() will raise FileNotFoundError
        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = storage._load_memory_from_file()
    assert result["version"] == "1.0"


# --- get_memory_storage error paths ---


def test_get_memory_storage_falls_back_on_invalid_class():
    """get_memory_storage falls back to FileMemoryStorage on import error."""
    import ideer.agents.memory.storage as storage_mod

    old_instance = storage_mod._storage_instance
    storage_mod._storage_instance = None
    try:
        with patch(
            "ideer.agents.memory.storage.get_memory_config",
            return_value=MemoryConfig(storage_class="nonexistent.module.Class"),
        ):
            result = storage_mod.get_memory_storage()
        assert isinstance(result, FileMemoryStorage)
    finally:
        storage_mod._storage_instance = old_instance


def test_get_memory_storage_falls_back_on_non_subclass():
    """get_memory_storage falls back when class is not a MemoryStorage subclass."""
    import ideer.agents.memory.storage as storage_mod

    old_instance = storage_mod._storage_instance
    storage_mod._storage_instance = None
    try:
        with patch(
            "ideer.agents.memory.storage.get_memory_config",
            return_value=MemoryConfig(storage_class="builtins.str"),
        ):
            result = storage_mod.get_memory_storage()
        assert isinstance(result, FileMemoryStorage)
    finally:
        storage_mod._storage_instance = old_instance
