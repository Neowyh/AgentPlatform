"""Small Local Runtime client surface for allowed-root file access."""

from .capabilities import CapabilityAnnouncement, CapabilityRegistry
from .consent import ConsentExchange, ConsentRequest, ConsentStore, request_hash
from .file_service import FileTaskResult, LocalFileService
from .files import FileAccessError, LocalFileStore, RootConfig
from .policy import LocalPolicy, PolicyDecision
from .transport import LocalRuntimeClient

__all__ = [
    "CapabilityAnnouncement",
    "CapabilityRegistry",
    "ConsentExchange",
    "ConsentRequest",
    "ConsentStore",
    "FileAccessError",
    "FileTaskResult",
    "LocalFileService",
    "LocalFileStore",
    "LocalPolicy",
    "PolicyDecision",
    "RootConfig",
    "request_hash",
    "LocalRuntimeClient",
]
