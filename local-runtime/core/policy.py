"""Local execution policy; this layer can veto every server decision."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONSENT_REQUIRED = "consent_required"


@dataclass(frozen=True)
class LocalPolicy:
    denied_capabilities: frozenset[str] = field(default_factory=frozenset)
    consent_required_capabilities: frozenset[str] = field(default_factory=frozenset)
    always_allow_capabilities: frozenset[str] = field(default_factory=frozenset)
    dangerous_capabilities: frozenset[str] = field(default_factory=frozenset)

    def authorize(
        self, capability: str, payload: dict[str, Any], *, consent: bool = False
    ) -> PolicyDecision:
        del payload  # The policy seam receives the exact payload for future rules.
        if capability in self.denied_capabilities:
            return PolicyDecision.DENY
        if capability in self.dangerous_capabilities:
            return PolicyDecision.DENY
        if capability in self.always_allow_capabilities:
            return PolicyDecision.ALLOW
        level_one = capability in {"local.files.write", "local.python"}
        if level_one and not consent:
            return PolicyDecision.CONSENT_REQUIRED
        return PolicyDecision.ALLOW
