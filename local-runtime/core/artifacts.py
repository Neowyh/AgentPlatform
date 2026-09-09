"""Explicit, bounded artifact upload handles."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class ArtifactUploader(Protocol):
    def upload(self, name: str, content: bytes) -> str: ...


class MemoryArtifactUploader:
    def __init__(self) -> None:
        self.items: dict[str, bytes] = {}

    def upload(self, name: str, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        handle = f"local://{digest}/{Path(name).name}"
        self.items[handle] = content
        return handle
