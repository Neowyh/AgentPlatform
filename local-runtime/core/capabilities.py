"""Device capability announcements and the six-factor effective set."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityAnnouncement:
    device_id: str
    capabilities: frozenset[str]
    online: bool = True
    policy_compatible: frozenset[str] = frozenset()


class CapabilityRegistry:
    def __init__(self) -> None:
        self._devices: dict[str, CapabilityAnnouncement] = {}

    def update(self, announcement: CapabilityAnnouncement) -> None:
        self._devices[announcement.device_id] = announcement

    def get(self, device_id: str) -> CapabilityAnnouncement | None:
        return self._devices.get(device_id)

    def effective(
        self,
        *,
        device_id: str,
        agent: set[str],
        caller: set[str],
        workflow: set[str],
        platform: set[str],
    ) -> frozenset[str]:
        device = self._devices.get(device_id)
        if device is None or not device.online:
            return frozenset()
        return frozenset(
            agent
            & caller
            & set(device.capabilities)
            & set(device.policy_compatible)
            & workflow
            & platform
        )
