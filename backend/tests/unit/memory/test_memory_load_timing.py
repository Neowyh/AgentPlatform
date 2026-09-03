"""First-token timing logs (T1): memory-load stage emits one timing record."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from ideer.agents.memory.storage import FileMemoryStorage
from ideer.config.memory_config import MemoryConfig


def test_memory_load_stage_emits_timing(caplog, tmp_path):
    """FileMemoryStorage.load logs stage=memory_load timing."""

    def mock_get_paths():
        mock_paths = MagicMock()
        mock_paths.memory_file = tmp_path / "memory.json"
        return mock_paths

    with patch("ideer.agents.memory.storage.get_paths", side_effect=mock_get_paths):
        with patch(
            "ideer.agents.memory.storage.get_memory_config",
            return_value=MemoryConfig(storage_path=""),
        ):
            storage = FileMemoryStorage()
            with caplog.at_level(logging.INFO, logger="ideer.agents.memory.storage"):
                storage.load(None)

    assert any("first_token_timing" in message and "stage=memory_load" in message for message in caplog.messages)
