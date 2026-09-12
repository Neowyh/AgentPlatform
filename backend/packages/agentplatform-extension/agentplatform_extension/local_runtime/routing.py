"""Run-scoped device routing; raw device identity never reaches tool payloads."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .authorization import LocalAuthorization


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
    def __init__(self, route: DeviceRoute | None = None, authorization: LocalAuthorization | None = None) -> None:
        self._route = route
        self._authorization = authorization

    @classmethod
    def select(
        cls,
        candidates: list[Mapping[str, Any]],
        capability: str,
        *,
        requested_device_id: str | None = None,
    ) -> RunDeviceRouter:
        """Select exactly one eligible online device and freeze that route."""
        eligible = [
            item for item in candidates if bool(item.get("online", item.get("device_online", False))) and capability in set(item.get("capabilities", ())) and (requested_device_id is None or item.get("device_id") == requested_device_id)
        ]
        if len(eligible) != 1:
            raise ValueError("local device selection is ambiguous or unavailable")
        return cls(DeviceRoute(str(eligible[0]["device_id"])))

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

    def revalidate(self, authorization: LocalAuthorization) -> None:
        """Apply a server/local policy refresh without changing the frozen route."""
        self._authorization = authorization

    def ensure_allowed(self, capability: str) -> None:
        if self._authorization is not None and not self._authorization.allows(capability):
            raise PermissionError(f"local capability is no longer authorized: {capability}")

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
        self.ensure_allowed(capability)
        return await sender(self.route.device_id, capability, dict(payload))
