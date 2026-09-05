from __future__ import annotations


def test_audit_log_has_one_agentplatform_owned_mapper() -> None:
    from app.agentplatform.audit_model import AuditLog
    from ideer.persistence.models import AuditLog as RegistryAuditLog
    from ideer.persistence.models.audit_log import AuditLog as LegacyAuditLog

    assert RegistryAuditLog is AuditLog
    assert LegacyAuditLog is AuditLog
    assert list(AuditLog.metadata.tables).count("audit_logs") == 1


def test_visibility_application_has_one_agentplatform_owned_mapper() -> None:
    from app.agentplatform.visibility_models import VisibilityApplication
    from ideer.persistence.models import VisibilityApplication as RegistryModel
    from ideer.persistence.models.visibility_application import VisibilityApplication as LegacyModel

    assert RegistryModel is VisibilityApplication
    assert LegacyModel is VisibilityApplication
    assert list(VisibilityApplication.metadata.tables).count("visibility_applications") == 1


def test_resource_runtime_seam_preserves_implementation_identity() -> None:
    from app.agentplatform.resource_runtime import ResourceStorage
    from app.agentplatform.resources.storage import ResourceStorage as StorageImpl

    assert ResourceStorage is StorageImpl


def test_workflow_runtime_seam_preserves_store_identity() -> None:
    from app.agentplatform.workflow_runtime import WorkflowV2Store
    from app.agentplatform.workflows.v2.store import WorkflowV2Store as StoreImpl

    assert WorkflowV2Store is StoreImpl
