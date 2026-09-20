"""Device-local runtime settings: identity, roots, MCP config, and policy grading.

This is the object the Tray edits and the runtime reads. It is deliberately a
plain data model with a JSON file behind it — no UI, no server round trip — so
the whole control surface is testable headless. Consent must be completable on
the machine itself (baseline §24), and so must the configuration it depends on.

The file stores logical roots, the server address, and per-capability policy
rules. It never stores secret values: credentials live in the OS secure store
and appear here only as ``local:<name>`` references.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .files import RootConfig
from .policy import LocalPolicy, RiskLevel

#: The Broker boundary a device connects to (``app/gateway/routers/devices.py``).
DEVICE_WS_PATH = "/api/devices/ws"


class CapabilityRule(StrEnum):
    """The §9 Level 1 choice offered to the user for one capability."""

    ALWAYS_ALLOW = "always_allow"
    ASK_FIRST = "ask_first"
    DENY = "deny"


@dataclass
class RuntimeSettings:
    server_url: str = ""
    device_name: str = ""
    user_name: str = ""
    device_id: str = ""
    runtime_version: str = "0.1.0"
    #: Bearer credential for this device's Broker session, issued at pairing by
    #: ``POST /api/devices/register/complete``. It is what lets the device prove
    #: it is the paired device on reconnect; treat it like a password.
    session_token: str = ""
    roots: list[dict[str, str]] = field(default_factory=list)
    rules: dict[str, str] = field(default_factory=dict)
    #: Per-capability risk-tier overrides: ``{"local.python": "level_2"}``.
    risk_levels: dict[str, str] = field(default_factory=dict)
    mcp_config_path: str = ""
    secret_backend: str = "auto"
    audit_db_path: str = ""
    #: Where these settings were loaded from; set by ``load_controller``.
    config_path: str = ""

    # --- server address --------------------------------------------------

    def websocket_url(self) -> str:
        """The device-facing WebSocket for the configured server address.

        Pairing stores what the user typed. A bare host, or one with a trailing
        slash, gets the Broker's ``/api/devices/ws`` boundary appended; a URL
        that already names a path is taken as given, because that path is the
        operator's choice.
        """
        url = self.server_url.strip()
        for http, ws in (("http://", "ws://"), ("https://", "wss://")):
            if url.startswith(http):
                url = ws + url[len(http) :]
        scheme, _, rest = url.partition("://")
        if scheme not in {"ws", "wss"} or not rest:
            raise ValueError(
                f"server_url {self.server_url!r} is not an http(s) or ws(s) address"
            )
        host = rest.partition("/")[0]
        path = rest[len(host) :].partition("?")[0].rstrip("/")
        if not path:
            path = DEVICE_WS_PATH
        return f"{scheme}://{host}{path}"

    # --- capability policy ---------------------------------------------

    def policy(self) -> LocalPolicy:
        """Project the stored rules onto the policy the runtime enforces."""
        denied: set[str] = set()
        always: set[str] = set()
        consent: set[str] = set()
        for capability, rule in self.rules.items():
            if rule == CapabilityRule.DENY.value:
                denied.add(capability)
            elif rule == CapabilityRule.ALWAYS_ALLOW.value:
                always.add(capability)
            elif rule == CapabilityRule.ASK_FIRST.value:
                consent.add(capability)
        level_one: set[str] = set()
        level_two: set[str] = set()
        for capability, level in self.risk_levels.items():
            if level == RiskLevel.LEVEL_1.value:
                level_one.add(capability)
            elif level == RiskLevel.LEVEL_2.value:
                level_two.add(capability)
        return LocalPolicy(
            denied_capabilities=frozenset(denied),
            consent_required_capabilities=frozenset(consent),
            always_allow_capabilities=frozenset(always),
            level_one_capabilities=frozenset(level_one),
            level_two_capabilities=frozenset(level_two),
        )

    def set_rule(self, capability: str, rule: CapabilityRule) -> None:
        self.rules[capability] = rule.value

    def set_risk_level(self, capability: str, level: RiskLevel) -> None:
        """Move a capability to another tier.

        Level 2 here means the capability is denied outright by the local
        policy (an unconfirmed tier is Level 2 by default), so grading work
        down to Level 2 is how a user switches it off without deleting the
        servers or roots it belongs to.
        """
        self.risk_levels[capability] = level.value

    def risk_level_for(self, capability: str) -> RiskLevel | None:
        stored = self.risk_levels.get(capability)
        return RiskLevel(stored) if stored else None

    def rule_for(self, capability: str) -> CapabilityRule:
        """The effective rule; ungraded capabilities ask first."""
        stored = self.rules.get(capability)
        if stored in {member.value for member in CapabilityRule}:
            return CapabilityRule(stored)
        return CapabilityRule.ASK_FIRST

    def policy_hash(self) -> str:
        """Hash published in HELLO so the server can tell a stale policy."""
        canonical = json.dumps(
            {"rules": self.rules, "roots": self.roots},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # --- allowed roots ---------------------------------------------------

    def file_roots(self) -> list[RootConfig]:
        return [
            RootConfig(
                logical_root=str(entry.get("logical_root", "")),
                physical_root=Path(str(entry.get("physical_root", ""))),
            )
            for entry in self.roots
        ]

    def add_root(self, logical_root: str, physical_root: str | Path) -> None:
        self.roots = [
            entry for entry in self.roots if entry.get("logical_root") != logical_root
        ]
        self.roots.append(
            {
                "logical_root": logical_root,
                "physical_root": str(Path(physical_root).resolve(strict=False)),
            }
        )

    def remove_root(self, logical_root: str) -> None:
        self.roots = [entry for entry in self.roots if entry.get("logical_root") != logical_root]

    # --- persistence -----------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return target

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeSettings:
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


def load_settings(path: str | Path) -> RuntimeSettings:
    """Read settings; a missing file is a fresh runtime, not an error."""
    source = Path(path)
    if not source.exists():
        return RuntimeSettings()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("runtime settings must be a JSON object")
    return RuntimeSettings.from_dict(data)
