"""Run-scoped device routing; raw device identity never reaches tool payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceRoute:
    device_id: str
    logical_target: str = "local"


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
