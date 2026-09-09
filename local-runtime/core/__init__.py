"""Small Local Runtime client surface for allowed-root file access."""

from .capabilities import CapabilityAnnouncement, CapabilityRegistry
from .file_service import FileTaskResult, LocalFileService
from .files import FileAccessError, LocalFileStore, RootConfig
from .policy import LocalPolicy, PolicyDecision
from .transport import LocalRuntimeClient

__all__ = [
    "CapabilityAnnouncement",
    "CapabilityRegistry",
    "FileAccessError",
    "FileTaskResult",
    "LocalFileService",
    "LocalFileStore",
    "LocalPolicy",
    "PolicyDecision",
    "RootConfig",
    "LocalRuntimeClient",
]
