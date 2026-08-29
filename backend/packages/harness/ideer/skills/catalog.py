"""Single seam for discovering the Skills available to an Agent runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ideer.skills.types import Skill

_CATALOGS: dict[int, tuple[object, SkillCatalog]] = {}


class _SkillSource(Protocol):
    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]: ...

    def get_skills_root_path(self) -> Path: ...


class SkillCatalog:
    """Cache-aware facade over SkillStorage's discovery protocol.

    Storage remains responsible for parsing and policy details.  Callers use
    this facade so discovery, cache invalidation, and future availability
    policy changes have one public seam.
    """

    def __init__(self, source: _SkillSource) -> None:
        self._source = source
        self._cache: dict[tuple[bool, int], list[Skill]] = {}

    def list_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        """Return the current sorted Skill list without exposing storage."""
        signature = self._root_signature()
        key = (enabled_only, signature)
        if key not in self._cache:
            self._cache[key] = list(self._source.load_skills(enabled_only=enabled_only))
        return list(self._cache[key])

    def invalidate(self) -> None:
        """Discard cached discovery results after a Resource or config write."""
        self._cache.clear()

    def _root_signature(self) -> int:
        get_root = getattr(self._source, "get_skills_root_path", None)
        if get_root is None:
            # Lightweight compatibility doubles and remote sources may not
            # expose filesystem metadata; their owner can call invalidate().
            return -1
        root = get_root()
        if not root.exists():
            return 0
        return sum(stat.st_mtime_ns ^ stat.st_size for path in root.rglob("SKILL.md") if (stat := path.stat()))


def get_skill_catalog(source: _SkillSource | None = None) -> SkillCatalog:
    """Build a catalog for the supplied storage or the configured storage."""
    if source is None:
        from ideer.skills.storage import get_or_new_skill_storage

        source = get_or_new_skill_storage()
    source_key = id(source)
    cached = _CATALOGS.get(source_key)
    if cached is None or cached[0] is not source:
        catalog = SkillCatalog(source)
        _CATALOGS[source_key] = (source, catalog)
        return catalog
    return cached[1]


__all__ = ["SkillCatalog", "get_skill_catalog"]
