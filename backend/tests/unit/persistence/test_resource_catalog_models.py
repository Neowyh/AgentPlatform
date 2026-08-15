"""Contracts for the canonical Skill, Agent, and Workflow resource catalog."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from ideer.persistence.models.resource_catalog import (
    Resource,
    ResourceDependency,
    ResourceDraft,
    ResourceFavorite,
    ResourceLifecycleStatus,
    ResourceStorageKind,
    ResourceType,
    ResourceVersion,
    RunResourceSnapshot,
)
from ideer.persistence.models.visibility_application import VisibilityApplication
from ideer.persistence.models.workflow_v2 import WorkflowV2RunRow


def _unique_column_sets(model: type) -> set[tuple[str, ...]]:
    return {tuple(column.name for column in constraint.columns) for constraint in model.__table__.constraints if isinstance(constraint, UniqueConstraint)}


def _check_sql(model: type) -> set[str]:
    return {str(constraint.sqltext) for constraint in model.__table__.constraints if isinstance(constraint, CheckConstraint)}


def test_catalog_enums_are_closed_to_the_accepted_contract() -> None:
    assert {item.value for item in ResourceType} == {"skill", "agent", "workflow"}
    assert {item.value for item in ResourceLifecycleStatus} == {"active", "archived", "suspended"}
    assert {item.value for item in ResourceStorageKind} == {"filesystem", "database", "bundled"}


def test_resource_identity_and_revision_columns_match_the_contract() -> None:
    columns = Resource.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "type",
        "slug",
        "display_name",
        "owner_id",
        "visibility",
        "scope_department_id",
        "lifecycle_status",
        "latest_version",
        "draft_revision",
        "storage_kind",
        "storage_key",
        "system_owned",
        "authz_revision",
        "created_at",
        "updated_at",
    }
    assert ("type", "owner_id", "slug") in _unique_column_sets(Resource)
    assert {"latest_version >= 0", "draft_revision >= 0", "authz_revision >= 1"} <= _check_sql(Resource)


def test_published_versions_are_immutable_resource_scoped_records() -> None:
    columns = ResourceVersion.__table__.columns

    assert set(columns.keys()) == {
        "id",
        "resource_id",
        "version",
        "content_hash",
        "storage_key",
        "scan_result",
        "content",
        "created_by",
        "published_at",
        "source_resource_id",
        "source_version",
    }
    assert ("resource_id", "version") in _unique_column_sets(ResourceVersion)
    assert "version >= 1" in _check_sql(ResourceVersion)


def test_dependency_and_snapshot_rows_use_resource_ids_and_actual_versions() -> None:
    assert set(ResourceDependency.__table__.columns.keys()) == {
        "id",
        "source_resource_id",
        "target_resource_id",
        "created_at",
    }
    assert ("source_resource_id", "target_resource_id") in _unique_column_sets(ResourceDependency)
    assert "source_resource_id <> target_resource_id" in _check_sql(ResourceDependency)

    snapshot_columns = RunResourceSnapshot.__table__.columns
    assert set(snapshot_columns.keys()) == {
        "id",
        "run_id",
        "root_resource_id",
        "resource_id",
        "version",
        "content_hash",
        "authz_revision",
        "resolved_at",
    }
    assert ("run_id", "resource_id") in _unique_column_sets(RunResourceSnapshot)
    assert {"version >= 1", "authz_revision >= 1"} <= _check_sql(RunResourceSnapshot)


def test_favorites_and_drafts_are_user_and_resource_scoped() -> None:
    assert set(ResourceFavorite.__table__.columns.keys()) == {"user_id", "resource_id", "created_at"}
    assert {column.name for column in ResourceFavorite.__table__.primary_key.columns} == {"user_id", "resource_id"}

    assert set(ResourceDraft.__table__.columns.keys()) == {
        "resource_id",
        "revision",
        "content_hash",
        "storage_key",
        "content",
        "modified_by",
        "updated_at",
    }
    assert {column.name for column in ResourceDraft.__table__.primary_key.columns} == {"resource_id"}
    assert "revision >= 1" in _check_sql(ResourceDraft)


def test_visibility_applications_can_pin_a_canonical_resource_version() -> None:
    columns = VisibilityApplication.__table__.columns

    assert {"canonical_resource_id", "requested_version", "requested_hash"} <= set(columns.keys())
    assert columns["canonical_resource_id"].nullable is True
    assert columns["requested_version"].nullable is True
    assert columns["requested_hash"].nullable is True


def test_workflow_runs_can_reference_a_canonical_resource_without_breaking_legacy_names() -> None:
    columns = WorkflowV2RunRow.__table__.columns

    assert "workflow_name" in columns
    assert columns["workflow_resource_id"].nullable is True
    assert columns["runner_tool_groups"].nullable is True
