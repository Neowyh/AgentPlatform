"""Server-side effective local capability authorization."""

from __future__ import annotations

from dataclasses import dataclass


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
