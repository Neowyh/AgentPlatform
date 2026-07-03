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
from ideer.persistence.models.resource_metadata import ResourceMetadata
from ideer.persistence.models.run_event import RunEventRow
from ideer.persistence.models.skill_application import SkillApplication, SkillApplicationStatus
from ideer.persistence.models.skill_default_config import SkillDefaultConfig
from ideer.persistence.models.user import DepartmentModel, ResourceVisibility, UserModel, UserRole
from ideer.persistence.models.user_skill_preference import UserSkillPreference
from ideer.persistence.models.visibility_application import VisibilityApplication, VisibilityApplicationStatus
from ideer.persistence.models.workflow import WorkflowRunRow
from ideer.persistence.run.model import RunRow
from ideer.persistence.thread_meta.model import ThreadMetaRow
from ideer.persistence.user.model import UserRow

__all__ = [
    "DepartmentModel",
    "FeedbackRow",
    "ResourceMetadata",
    "ResourceVisibility",
    "RunEventRow",
    "RunRow",
    "SkillApplication",
    "SkillApplicationStatus",
    "SkillDefaultConfig",
    "ThreadMetaRow",
    "UserModel",
    "UserSkillPreference",
    "UserRole",
    "UserRow",
    "VisibilityApplication",
    "VisibilityApplicationStatus",
    "WorkflowRunRow",
]
