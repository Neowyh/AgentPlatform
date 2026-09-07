"""Network mode detection for iDeer.

Detects whether the system is running in online (internet accessible) or
offline (intranet only) mode. This affects which tools and skills are loaded.
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum

logger = logging.getLogger(__name__)


class NetworkMode(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


def get_network_mode() -> NetworkMode:
    """Get the current network mode from environment.

    Priority:
    1. IDEER_NETWORK_MODE env var (explicit override)
    2. Default to 'online'

    Note: Auto-detection of network mode is not implemented.
    In intranet environments, set IDEER_NETWORK_MODE=offline explicitly.
    """
    env_mode = os.environ.get("IDEER_NETWORK_MODE", "").lower()
    if env_mode == "offline":
        logger.info("Network mode set to OFFLINE via IDEER_NETWORK_MODE env var")
        return NetworkMode.OFFLINE
    elif env_mode == "online":
        return NetworkMode.ONLINE
    elif env_mode:
        # Unrecognized value - warn and default to online
        logger.warning(
            "Unrecognized IDEER_NETWORK_MODE value %r, defaulting to ONLINE. Valid values: 'online', 'offline'",
            env_mode,
        )

    # Default to online — explicit offline via env var or config
    return NetworkMode.ONLINE


def is_offline() -> bool:
    """Convenience check for offline mode."""
    return get_network_mode() == NetworkMode.OFFLINE
