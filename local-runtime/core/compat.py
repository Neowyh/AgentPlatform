"""Small standard-library compatibility shims for the Windows 7 runtime."""

from datetime import timezone
from enum import Enum

try:
    from datetime import UTC as UTC
except ImportError:  # pragma: no cover - Python 3.10 and older
    UTC = timezone.utc

try:
    from enum import StrEnum as StrEnum
except ImportError:  # pragma: no cover - exercised on Python 3.10 and older

    class StrEnum(str, Enum):
        """Backport of :class:`enum.StrEnum` used by Python 3.8/3.9."""

        def __str__(self) -> str:
            return self.value
