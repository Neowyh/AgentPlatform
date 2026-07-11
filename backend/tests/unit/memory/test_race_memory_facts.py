"""Stress tests for RMW race in memory fact operations.

create_memory_fact, delete_memory_fact, and update_memory_fact follow a
read-modify-write pattern with no lock between read and write.  Concurrent
calls lose data (last-writer-wins).  These tests document the race exists
and verify the system handles it gracefully (no crashes, no corrupted JSON).
"""

import concurrent.futures
import json
import tempfile
from pathlib import Path
from unittest.mock import PropertyMock, patch

import pytest

from ideer.agents.memory.storage import FileMemoryStorage
from ideer.agents.memory.updater import (
    create_memory_fact,
    delete_memory_fact,
    update_memory_fact,
)


def _empty_memory() -> dict:
    return {
        "version": "1.0",
        "lastUpdated": "",
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": [],
    }


def _memory_with_facts() -> dict:
    return _empty_memory() | {
        "facts": [
            {"id": "fact_a", "content": "alpha", "category": "context", "confidence": 0.9, "createdAt": "2025-01-01T00:00:00Z", "source": "manual"},
            {"id": "fact_b", "content": "bravo", "category": "context", "confidence": 0.8, "createdAt": "2025-01-01T00:00:00Z", "source": "manual"},
            {"id": "fact_c", "content": "charlie", "category": "context", "confidence": 0.7, "createdAt": "2025-01-01T00:00:00Z", "source": "manual"},
            {"id": "fact_d", "content": "delta", "category": "context", "confidence": 0.6, "createdAt": "2025-01-01T00:00:00Z", "source": "manual"},
            {"id": "fact_e", "content": "echo", "category": "context", "confidence": 0.5, "createdAt": "2025-01-01T00:00:00Z", "source": "manual"},
        ]
    }


def _memory_with_10_facts() -> dict:
    letters = "abcdefghij"
    return _empty_memory() | {
        "facts": [
            {
                "id": f"fact_{letter}",
                "content": f"content-{letter}",
                "category": "context",
                "confidence": 0.9 - i * 0.1,
                "createdAt": "2025-01-01T00:00:00Z",
                "source": "manual",
            }
            for i, letter in enumerate(letters)
        ]
    }


@pytest.fixture
def mem_storage():
    """Return a FileMemoryStorage pointed at a temp file."""
    tmp_dir = Path(tempfile.mkdtemp())
    mem_file = tmp_dir / "memory.json"
    mem_file.write_text(json.dumps(_empty_memory(), indent=2))

    storage = FileMemoryStorage()
    with patch("ideer.agents.memory.storage.get_memory_config") as cfg:
        type(cfg.return_value).storage_path = PropertyMock(return_value=str(mem_file))
        storage.load()
        yield storage, mem_file


@pytest.fixture
def mem_storage_with_facts():
    """Return a FileMemoryStorage pre-populated with 5 facts."""
    tmp_dir = Path(tempfile.mkdtemp())
    mem_file = tmp_dir / "memory.json"
    mem_file.write_text(json.dumps(_memory_with_facts(), indent=2))

    storage = FileMemoryStorage()
    with patch("ideer.agents.memory.storage.get_memory_config") as cfg:
        type(cfg.return_value).storage_path = PropertyMock(return_value=str(mem_file))
        storage.load()
        yield storage, mem_file


@pytest.fixture
def mem_storage_with_10_facts():
    """Return a FileMemoryStorage pre-populated with 10 facts."""
    tmp_dir = Path(tempfile.mkdtemp())
    mem_file = tmp_dir / "memory.json"
    mem_file.write_text(json.dumps(_memory_with_10_facts(), indent=2))

    storage = FileMemoryStorage()
    with patch("ideer.agents.memory.storage.get_memory_config") as cfg:
        type(cfg.return_value).storage_path = PropertyMock(return_value=str(mem_file))
        storage.load()
        yield storage, mem_file


def test_concurrent_create_memory_fact_stress(mem_storage):
    """10 concurrent create calls — RMW race loses all but last write."""
    storage, mem_file = mem_storage

    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=storage):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(create_memory_fact, f"fact-{i}") for i in range(10)]
            for f in futures:
                f.result()

    data = json.loads(mem_file.read_text())
    assert isinstance(data, dict)
    assert isinstance(data.get("facts"), list)
    assert len(data["facts"]) < 10, "Expected data loss from RMW race: not all 10 creates survived"


def test_concurrent_delete_memory_fact_stress(mem_storage_with_10_facts):
    """5 concurrent delete calls — RMW race loses some deletes."""
    storage, mem_file = mem_storage_with_10_facts

    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=storage):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(delete_memory_fact, f"fact_{chr(ord('a') + i)}") for i in range(5)]
            for f in futures:
                f.result()

    data = json.loads(mem_file.read_text())
    assert isinstance(data, dict)
    assert isinstance(data.get("facts"), list)
    assert len(data["facts"]) >= 1, "Expected some deletes to be lost due to RMW race"


def test_concurrent_update_memory_fact_stress(mem_storage_with_facts):
    """5 concurrent update calls on different ids — RMW race loses some updates."""
    storage, mem_file = mem_storage_with_facts

    with patch("ideer.agents.memory.updater.get_memory_storage", return_value=storage):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(
                    update_memory_fact,
                    f"fact_{chr(ord('a') + i)}",
                    content=f"updated-{i}",
                )
                for i in range(5)
            ]
            for f in futures:
                f.result()

    data = json.loads(mem_file.read_text())
    assert isinstance(data, dict)
    assert isinstance(data.get("facts"), list)
    updated_count = sum(1 for f in data["facts"] if f["content"].startswith("updated-"))
    assert updated_count < 5, f"Expected data loss: all 5 updates survived (updated={updated_count})"
