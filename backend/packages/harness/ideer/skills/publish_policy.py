"""Publication policy for catalog-managed skills."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ideer.resources.service import ResourceConflict


class SkillPublishDenied(ResourceConflict):
    """Raised when a security scan explicitly rejects a skill publication."""


class SkillPublishPolicy:
    """Apply the stable publication decision contract to a scan result.

    Older callers may provide operational ``status`` values instead of a
    moderation ``decision``. Those values remain compatible; an explicit
    block/reject is the only result that can publish a skill unsuccessfully.
    """

    _DENIED_VALUES = frozenset({"block", "blocked", "reject", "rejected", "deny", "denied"})

    def assert_publishable(self, scan_result: Mapping[str, Any] | None) -> None:
        result = scan_result or {}
        decision = str(result.get("decision") or result.get("status") or "").strip().lower()
        if decision in self._DENIED_VALUES:
            reason = str(result.get("reason") or result.get("message") or "security policy denied publication")
            raise SkillPublishDenied(f"Skill publication denied: {reason}")


__all__ = ["SkillPublishDenied", "SkillPublishPolicy"]
