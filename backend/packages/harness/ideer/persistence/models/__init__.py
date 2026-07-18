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

from ideer.persistence.feedback.model import FeedbackRow
from ideer.persistence.models.audit_log import AuditLog
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.run_event import RunEventRow
from ideer.persistence.models.user import DepartmentModel, ResourceVisibility, UserModel, UserRole
from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus
from ideer.persistence.models.workflow_legacy import LegacyWorkflowRunRow
from ideer.persistence.models.workflow_v2 import (
    WorkflowCommandRow,
    WorkflowDefinitionVersionRow,
    WorkflowTaskRow,
    WorkflowV2EventRow,
    WorkflowV2RunRow,
)
from ideer.persistence.run.model import RunRow
from ideer.persistence.thread_meta.model import ThreadMetaRow
from ideer.persistence.user.model import UserRow

__all__ = [
    "AuditLog",
    "DepartmentModel",
    "FeedbackRow",
    "LegacyWorkflowRunRow",
    "ResourceMetadata",
    "ResourceVisibility",
    "RunEventRow",
    "RunRow",
    "ThreadMetaRow",
    "UserModel",
    "UserRole",
    "UserRow",
    "VisibilityApplication",
    "VisibilityApplicationStatus",
    "WorkflowCommandRow",
    "WorkflowDefinitionVersionRow",
    "WorkflowTaskRow",
    "WorkflowV2EventRow",
    "WorkflowV2RunRow",
]
