"""Run-scoped device routing; raw device identity never reaches tool payloads."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeviceRoute:
    device_id: str
    logical_target: str = "local"

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must be non-empty")
        if self.logical_target != "local":
            raise ValueError("local runtime routes must use the local logical target")


class RunDeviceRouter:
    def __init__(self, route: DeviceRoute | None = None) -> None:
        self._route = route

    def freeze(self, route: DeviceRoute) -> None:
        if self._route is not None and self._route != route:
            raise RuntimeError("device route is frozen for this run")
        self._route = route

    @property
    def route(self) -> DeviceRoute:
        if self._route is None:
            raise RuntimeError("no device route is available")
        return self._route

    def target(self) -> str:
        return self.route.logical_target

    async def dispatch(
        self,
        capability: str,
        payload: Mapping[str, Any],
        sender: Callable[[str, str, Mapping[str, Any]], Awaitable[Any]],
    ) -> Any:
        """Send a logical local task through the frozen route.

        ``device_id`` is supplied only to the trusted server-side sender. It
        is never added to the model-visible payload.
        """
        return await sender(self.route.device_id, capability, dict(payload))
