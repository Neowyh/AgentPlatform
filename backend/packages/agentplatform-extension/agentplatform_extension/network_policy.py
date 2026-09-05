"""Default-deny network policy for enterprise runs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class NetworkPolicy:
    """Allow only explicitly listed internal hosts unless opted in."""

    allowed_hosts: tuple[str, ...] = ()
    allow_public: bool = False

    def allows(self, target: str) -> bool:
        parsed = urlparse(target if "://" in target else f"https://{target}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if not host:
            return False
        if host in {item.lower().rstrip(".") for item in self.allowed_hosts}:
            return True
        if self.allow_public and not self._is_private_or_local(host):
            return True
        return False

    @staticmethod
    def _is_private_or_local(host: str) -> bool:
        return host == "localhost" or host.endswith(".local") or host.startswith(("10.", "192.168.", "127."))
