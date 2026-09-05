"""ORM model registration entry point.

Importing this module ensures all ORM models are registered with
``Base.metadata`` so Alembic autogenerate detects every table.

The actual ORM classes have moved to entity-specific subpackages:
- ``ideer.persistence.thread_meta``
- ``ideer.persistence.run``
- ``ideer.persistence.feedback``
- ``ideer.persistence.user``

``RunEventRow`` remains in ``ideer.persistence.models.run_event`` because
its storage implementation lives in ``ideer.runtime.events.store.db`` and
there is no matching entity directory.
"""

from app.agentplatform.audit_model import AuditLog
from app.agentplatform.visibility_models import VisibilityApplication, VisibilityApplicationStatus
from ideer.persistence.feedback.model import FeedbackRow
from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceDraft,
    ResourceFavorite,
    ResourceLifecycleStatus,
    ResourceNotification,
    ResourceProvenance,
    ResourceStorageKind,
    ResourceType,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.run_event import RunEventRow
from ideer.persistence.models.user import DepartmentModel, ResourceVisibility, UserModel, UserRole
from ideer.persistence.models.workflow_legacy import LegacyWorkflowRunRow
from ideer.persistence.run.model import RunRow
from ideer.persistence.thread_meta.model import ThreadMetaRow
from ideer.persistence.user.model import UserRow

__all__ = [
    "AuditLog",
    "DepartmentModel",
    "FeedbackRow",
    "LegacyWorkflowRunRow",
    "Resource",
    "ResourceDependency",
    "ResourceDraft",
    "ResourceFavorite",
    "ResourceLifecycleStatus",
    "ResourceNotification",
    "ResourceMetadata",
    "ResourceProvenance",
    "ResourceStorageKind",
    "ResourceType",
    "ResourceVersion",
    "ResourceVisibility",
    "RunEventRow",
    "RunRow",
    "RunResourceSnapshot",
    "ThreadMetaRow",
    "UserModel",
    "UserRole",
    "UserRow",
    "VisibilityApplication",
    "VisibilityApplicationStatus",
]
