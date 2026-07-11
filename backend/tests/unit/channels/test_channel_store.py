"""Comprehensive tests for ChannelStore — JSON-file-backed IM thread mapping store.

Tests cover:
- __init__ (with explicit path, with default path)
- _load (existing file, missing file, corrupt JSON, OSError)
- _save (normal write, error cleanup)
- _key (with/without topic_id)
- get_thread_id (found, not found, with topic_id)
- set_thread_id (create new, update existing, with topic_id, with user_id)
- remove (specific topic, all topics for chat, no match)
- list_entries (all, filtered by channel, with topic_id entries)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.channels.store import ChannelStore

# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestChannelStoreInit:
    def test_init_with_explicit_path(self, tmp_path):
        """Store initializes with a given file path."""
        store_path = tmp_path / "test_store.json"
        store = ChannelStore(path=store_path)
        assert store._path == store_path
        assert store._data == {}

    def test_init_creates_parent_directory(self, tmp_path):
        """Parent directories are created if they don't exist."""
        store_path = tmp_path / "deep" / "nested" / "store.json"
        store = ChannelStore(path=store_path)
        assert store._path.parent.exists()
        assert store._data == {}

    def test_init_loads_existing_data(self, tmp_path):
        """Existing store file is loaded on init."""
        store_path = tmp_path / "store.json"
        data = {"slack:C123": {"thread_id": "t1", "user_id": "u1", "created_at": 100.0, "updated_at": 200.0}}
        store_path.write_text(json.dumps(data), encoding="utf-8")

        store = ChannelStore(path=store_path)
        assert store._data == data

    def test_init_with_default_path(self):
        """When path=None, uses get_paths() to determine default location."""
        mock_paths = MagicMock()
        mock_paths.base_dir = "/tmp/ideer-test"

        with patch("ideer.config.paths.get_paths", return_value=mock_paths):
            store = ChannelStore(path=None)

        assert "channels" in str(store._path)
        assert "store.json" in str(store._path)


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------


class TestChannelStoreLoad:
    def test_load_missing_file_returns_empty(self, tmp_path):
        """Missing file returns empty dict."""
        store = ChannelStore(path=tmp_path / "nonexistent.json")
        assert store._data == {}

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        """Corrupt JSON file returns empty dict with warning."""
        store_path = tmp_path / "corrupt.json"
        store_path.write_text("not valid json {{{", encoding="utf-8")

        store = ChannelStore(path=store_path)
        assert store._data == {}

    def test_load_os_error_returns_empty(self, tmp_path):
        """OSError during read returns empty dict."""
        store_path = tmp_path / "unreadable.json"
        store_path.write_text("{}", encoding="utf-8")

        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            store = ChannelStore(path=store_path)

        assert store._data == {}


# ---------------------------------------------------------------------------
# _save
# ---------------------------------------------------------------------------


class TestChannelStoreSave:
    def test_save_writes_data_atomically(self, tmp_path):
        """_save writes data via temp file and rename."""
        store_path = tmp_path / "store.json"
        store = ChannelStore(path=store_path)

        store._data = {"key": {"thread_id": "t1"}}
        store._save()

        assert store_path.exists()
        loaded = json.loads(store_path.read_text(encoding="utf-8"))
        assert loaded == {"key": {"thread_id": "t1"}}

    def test_save_cleans_up_temp_file_on_error(self, tmp_path):
        """Temp file is cleaned up if write fails."""
        store_path = tmp_path / "store.json"
        store = ChannelStore(path=store_path)
        store._data = {"key": {"thread_id": "t1"}}

        with patch("json.dump", side_effect=RuntimeError("write failed")):
            with pytest.raises(RuntimeError, match="write failed"):
                store._save()

        # No temp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


# ---------------------------------------------------------------------------
# _key
# ---------------------------------------------------------------------------


class TestChannelStoreKey:
    def test_key_without_topic(self):
        key = ChannelStore._key("slack", "C123")
        assert key == "slack:C123"

    def test_key_with_topic(self):
        key = ChannelStore._key("slack", "C123", "topic-456")
        assert key == "slack:C123:topic-456"

    def test_key_with_none_topic(self):
        key = ChannelStore._key("slack", "C123", None)
        assert key == "slack:C123"

    def test_key_with_empty_topic(self):
        """Empty string topic_id is falsy, treated as no topic."""
        key = ChannelStore._key("slack", "C123", "")
        assert key == "slack:C123"


# ---------------------------------------------------------------------------
# get_thread_id
# ---------------------------------------------------------------------------


class TestGetThreadId:
    def test_returns_thread_id_when_found(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {"slack:C123": {"thread_id": "t-abc", "user_id": "u1", "created_at": 0, "updated_at": 0}}

        assert store.get_thread_id("slack", "C123") == "t-abc"

    def test_returns_none_when_not_found(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        assert store.get_thread_id("slack", "C123") is None

    def test_returns_thread_id_with_topic(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {"slack:C123:t1": {"thread_id": "t-topic", "user_id": "u1", "created_at": 0, "updated_at": 0}}

        assert store.get_thread_id("slack", "C123", "t1") == "t-topic"

    def test_returns_none_for_wrong_topic(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {"slack:C123:t1": {"thread_id": "t-topic", "user_id": "u1", "created_at": 0, "updated_at": 0}}

        assert store.get_thread_id("slack", "C123", "t2") is None


# ---------------------------------------------------------------------------
# set_thread_id
# ---------------------------------------------------------------------------


class TestSetThreadId:
    def test_creates_new_entry(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        with patch("app.channels.store.time.time", return_value=1000.0):
            store.set_thread_id("slack", "C123", "thread-1", user_id="user-1")

        entry = store._data["slack:C123"]
        assert entry["thread_id"] == "thread-1"
        assert entry["user_id"] == "user-1"
        assert entry["created_at"] == 1000.0
        assert entry["updated_at"] == 1000.0

    def test_updates_existing_entry_preserves_created_at(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {
                "thread_id": "old-thread",
                "user_id": "u1",
                "created_at": 500.0,
                "updated_at": 600.0,
            }
        }

        with patch("app.channels.store.time.time", return_value=1000.0):
            store.set_thread_id("slack", "C123", "new-thread")

        entry = store._data["slack:C123"]
        assert entry["thread_id"] == "new-thread"
        assert entry["created_at"] == 500.0  # preserved
        assert entry["updated_at"] == 1000.0  # updated

    def test_with_topic_id(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        store.set_thread_id("slack", "C123", "thread-t", topic_id="topic-1")

        assert "slack:C123:topic-1" in store._data
        assert store._data["slack:C123:topic-1"]["thread_id"] == "thread-t"

    def test_saves_to_disk(self, tmp_path):
        store_path = tmp_path / "store.json"
        store = ChannelStore(path=store_path)

        store.set_thread_id("slack", "C123", "thread-1")

        loaded = json.loads(store_path.read_text(encoding="utf-8"))
        assert "slack:C123" in loaded
        assert loaded["slack:C123"]["thread_id"] == "thread-1"

    def test_default_user_id_is_empty(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        store.set_thread_id("slack", "C123", "thread-1")

        assert store._data["slack:C123"]["user_id"] == ""


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_specific_topic(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123:t1": {"thread_id": "t1"},
            "slack:C123:t2": {"thread_id": "t2"},
        }

        result = store.remove("slack", "C123", topic_id="t1")

        assert result is True
        assert "slack:C123:t1" not in store._data
        assert "slack:C123:t2" in store._data

    def test_remove_specific_topic_not_found(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        result = store.remove("slack", "C123", topic_id="nonexistent")

        assert result is False

    def test_remove_all_topics_for_chat(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "base"},
            "slack:C123:t1": {"thread_id": "t1"},
            "slack:C123:t2": {"thread_id": "t2"},
            "slack:C456": {"thread_id": "other"},
        }

        result = store.remove("slack", "C123")

        assert result is True
        assert "slack:C123" not in store._data
        assert "slack:C123:t1" not in store._data
        assert "slack:C123:t2" not in store._data
        assert "slack:C456" in store._data  # Different chat untouched

    def test_remove_no_match_returns_false(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        result = store.remove("slack", "nonexistent")

        assert result is False

    def test_remove_saves_to_disk(self, tmp_path):
        store_path = tmp_path / "store.json"
        store = ChannelStore(path=store_path)
        store._data = {"slack:C123": {"thread_id": "t1"}}
        store._save()

        store.remove("slack", "C123")

        loaded = json.loads(store_path.read_text(encoding="utf-8"))
        assert "slack:C123" not in loaded

    def test_remove_prefix_does_not_match_similar_keys(self, tmp_path):
        """Ensure prefix matching is exact (C123 should not match C1234)."""
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "t1"},
            "slack:C1234": {"thread_id": "t2"},
        }

        store.remove("slack", "C123")

        assert "slack:C1234" in store._data


# ---------------------------------------------------------------------------
# list_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    def test_list_all_entries(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "t1", "user_id": "u1", "created_at": 0, "updated_at": 0},
            "feishu:C456": {"thread_id": "t2", "user_id": "u2", "created_at": 0, "updated_at": 0},
        }

        results = store.list_entries()

        assert len(results) == 2
        channels = {r["channel_name"] for r in results}
        assert channels == {"slack", "feishu"}

    def test_list_filtered_by_channel(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "t1", "user_id": "u1", "created_at": 0, "updated_at": 0},
            "feishu:C456": {"thread_id": "t2", "user_id": "u2", "created_at": 0, "updated_at": 0},
        }

        results = store.list_entries(channel_name="slack")

        assert len(results) == 1
        assert results[0]["channel_name"] == "slack"
        assert results[0]["chat_id"] == "C123"

    def test_list_with_topic_id(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123:t1": {"thread_id": "t-topic", "user_id": "u1", "created_at": 0, "updated_at": 0},
        }

        results = store.list_entries()

        assert len(results) == 1
        assert results[0]["topic_id"] == "t1"
        assert results[0]["channel_name"] == "slack"
        assert results[0]["chat_id"] == "C123"

    def test_list_without_topic_id(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "t1", "user_id": "u1", "created_at": 0, "updated_at": 0},
        }

        results = store.list_entries()

        assert len(results) == 1
        assert "topic_id" not in results[0]

    def test_list_empty_store(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")

        results = store.list_entries()
        assert results == []

    def test_list_no_match_on_channel_filter(self, tmp_path):
        store = ChannelStore(path=tmp_path / "store.json")
        store._data = {
            "slack:C123": {"thread_id": "t1", "user_id": "u1", "created_at": 0, "updated_at": 0},
        }

        results = store.list_entries(channel_name="discord")
        assert results == []


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_set_thread_id(self, tmp_path):
        """Multiple threads calling set_thread_id should not corrupt data."""
        store = ChannelStore(path=tmp_path / "store.json")
        errors = []

        def worker(channel_id, thread_id):
            try:
                for i in range(10):
                    store.set_thread_id("slack", f"C{channel_id}", f"thread-{thread_id}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i, i)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store._data) == 5  # 5 different chat IDs

    def test_concurrent_remove(self, tmp_path):
        """Multiple threads calling remove should not corrupt data."""
        store = ChannelStore(path=tmp_path / "store.json")
        for i in range(10):
            store._data[f"slack:C{i}"] = {"thread_id": f"t{i}"}
        store._save()

        errors = []

        def worker(chat_id):
            try:
                store.remove("slack", f"C{chat_id}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(store._data) == 0
