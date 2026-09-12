"""Server-side effective local capability authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LocalAuthorization:
    agent_capabilities: frozenset[str] = frozenset()
    caller_capabilities: frozenset[str] = frozenset()
    device_capabilities: frozenset[str] = frozenset()
    local_policy_capabilities: frozenset[str] = frozenset()
    workflow_capabilities: frozenset[str] = frozenset()
    platform_capabilities: frozenset[str] = frozenset()
    device_online: bool = False

    @classmethod
    def from_capabilities(
        cls,
        capabilities: set[str] | frozenset[str],
        *,
        device_online: bool,
    ) -> LocalAuthorization:
        """Build a caller-scoped authorization projection from one capability set.

        This is useful at the host boundary where the six policy sources have
        already been evaluated.  Keeping the projection explicit still lets
        tests and callers represent a veto from any individual source.
        """
        values = frozenset(capabilities)
        return cls(
            agent_capabilities=values,
            caller_capabilities=values,
            device_capabilities=values,
            local_policy_capabilities=values,
            workflow_capabilities=values,
            platform_capabilities=values,
            device_online=device_online,
        )

    @property
    def effective(self) -> frozenset[str]:
        if not self.device_online:
            return frozenset()
        return frozenset(self.agent_capabilities & self.caller_capabilities & self.device_capabilities & self.local_policy_capabilities & self.workflow_capabilities & self.platform_capabilities)

    def allows(self, capability: str) -> bool:
        return capability in self.effective


def child_authorization(parent: LocalAuthorization, declared: set[str]) -> LocalAuthorization:
    """Delegate only a subset of the parent's already effective capabilities."""
    allowed = parent.effective & declared
    return LocalAuthorization(
        agent_capabilities=frozenset(allowed),
        caller_capabilities=frozenset(allowed),
        device_capabilities=frozenset(allowed),
        local_policy_capabilities=frozenset(allowed),
        workflow_capabilities=frozenset(allowed),
        platform_capabilities=frozenset(allowed),
        device_online=parent.device_online,
    )


@dataclass(frozen=True)
class RunAuthorizationSnapshot:
    """Immutable six-factor authorization and device route captured at Run creation."""

    run_id: str
    thread_id: str
    device_id: str
    policy_version: str
    authorization: LocalAuthorization

    def __post_init__(self) -> None:
        if not self.run_id or not self.thread_id or not self.device_id or not self.policy_version:
            raise ValueError("run authorization snapshot identity is required")

    @property
    def effective(self) -> frozenset[str]:
        return self.authorization.effective

    def validate(self, current: LocalAuthorization, *, device_id: str) -> None:
        """Fail closed when device, policy, or any authorization factor changed."""
        if device_id != self.device_id or not current.device_online:
            raise PermissionError("run device is unavailable")
        if not self.effective.issuperset(current.effective):
            # A refresh may only narrow permissions; this check catches an
            # unexpected replacement that would broaden the frozen snapshot.
            raise PermissionError("run authorization changed")

    def child(self, declared: set[str]) -> RunAuthorizationSnapshot:
        return RunAuthorizationSnapshot(
            run_id=self.run_id,
            thread_id=self.thread_id,
            device_id=self.device_id,
            policy_version=self.policy_version,
            authorization=child_authorization(self.authorization, declared),
        )

    def as_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "device_id": self.device_id,
            "policy_version": self.policy_version,
            "effective_capabilities": sorted(self.effective),
        }
