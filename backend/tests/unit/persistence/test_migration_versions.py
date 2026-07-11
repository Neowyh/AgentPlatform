"""Unit coverage for Alembic migration version scripts."""

import importlib


class _BatchOpRecorder:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.altered_columns: list[tuple[str, bool]] = []
        self.added_columns: list[str] = []
        self.dropped_columns: list[str] = []
        self.created_indexes: list[tuple[str, tuple[str, ...], bool]] = []
        self.dropped_indexes: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def alter_column(self, column_name: str, *, nullable: bool):
        self.altered_columns.append((column_name, nullable))

    def add_column(self, column):
        self.added_columns.append(column.name)

    def drop_column(self, column_name: str):
        self.dropped_columns.append(column_name)

    def create_index(self, index_name: str, columns: list[str], *, unique: bool = False):
        self.created_indexes.append((index_name, tuple(columns), unique))

    def drop_index(self, index_name: str):
        self.dropped_indexes.append(index_name)


class _OpRecorder:
    def __init__(self):
        self.executed_sql: list[str] = []
        self.created_tables: list[tuple[str, tuple[object, ...]]] = []
        self.dropped_tables: list[str] = []
        self.added_columns: list[tuple[str, str]] = []
        self.dropped_columns: list[tuple[str, str]] = []
        self.batches: list[_BatchOpRecorder] = []

    def execute(self, sql: str):
        self.executed_sql.append(sql)

    def create_table(self, table_name: str, *columns):
        self.created_tables.append((table_name, columns))

    def drop_table(self, table_name: str):
        self.dropped_tables.append(table_name)

    def add_column(self, table_name: str, column):
        self.added_columns.append((table_name, column.name))

    def drop_column(self, table_name: str, column_name: str):
        self.dropped_columns.append((table_name, column_name))

    def batch_alter_table(self, table_name: str, schema=None):
        batch = _BatchOpRecorder(table_name)
        self.batches.append(batch)
        return batch


def _load(module_name: str):
    return importlib.import_module(f"ideer.persistence.migrations.versions.{module_name}")


def test_not_null_constraints_migration_backfills_and_toggles_nullable(monkeypatch):
    migration = _load("35830514e3ee_add_not_null_constraints")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert len(op.executed_sql) == 22
    assert op.executed_sql[0].startswith("UPDATE feedback SET created_at")
    upgraded = {batch.table_name: batch.altered_columns for batch in op.batches}
    assert upgraded["feedback"] == [("created_at", False)]
    assert ("status", False) in upgraded["runs"]
    assert ("metadata_json", False) in upgraded["threads_meta"]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    downgraded = {batch.table_name: batch.altered_columns for batch in op.batches}
    assert downgraded["feedback"] == [("created_at", True)]
    assert ("status", True) in downgraded["runs"]
    assert ("created_at", True) in downgraded["run_events"]


def test_missing_core_tables_migration_declares_tables_indexes_and_drop_order(monkeypatch):
    migration = _load("c4d5e6f7a8b9_add_missing_core_tables")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == [
        "runs",
        "threads_meta",
        "run_events",
        "feedback",
        "users",
    ]
    indexes = {(batch.table_name, index_name, columns, unique) for batch in op.batches for index_name, columns, unique in batch.created_indexes}
    assert ("runs", "ix_runs_thread_status", ("thread_id", "status"), False) in indexes
    assert ("run_events", "ix_events_run", ("thread_id", "run_id", "seq"), False) in indexes
    assert ("users", "idx_users_oauth_identity", ("oauth_provider", "oauth_id"), True) in indexes

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.dropped_tables == ["users", "feedback", "run_events", "threads_meta", "runs"]


def test_resource_tables_migration_declares_indexes_and_drop_order(monkeypatch):
    migration = _load("xxx_create_resource_tables")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == [
        "resource_metadata",
        "visibility_applications",
    ]
    indexes = {(batch.table_name, index_name, columns, unique) for batch in op.batches for index_name, columns, unique in batch.created_indexes}
    assert ("resource_metadata", "ix_resource_metadata_visibility", ("visibility",), False) in indexes
    assert ("visibility_applications", "ix_visibility_app_resource", ("resource_type", "resource_id"), False) in indexes

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.dropped_tables == ["visibility_applications", "resource_metadata"]


def test_departments_users_ext_migration_declares_tables_and_drop_order(monkeypatch):
    migration = _load("16147afec43b_add_departments_and_users_ext_tables")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == ["departments", "users_ext"]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.dropped_tables == ["users_ext", "departments"]


def test_workflow_runs_migration_declares_table_index_and_drop_order(monkeypatch):
    migration = _load("d7e0060b1ebc_add_workflow_runs_table")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == ["workflow_runs"]
    assert op.batches[0].created_indexes == [("ix_workflow_runs_name", ("workflow_name",), False)]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.batches[0].dropped_indexes == ["ix_workflow_runs_name"]
    assert op.dropped_tables == ["workflow_runs"]


def test_skill_rbac_migration_declares_tables_and_drop_order(monkeypatch):
    migration = _load("e1f2a3b4c5d6_add_skill_rbac_tables")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == [
        "skill_applications",
        "user_skill_preferences",
        "skill_default_configs",
    ]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.dropped_tables == [
        "skill_default_configs",
        "user_skill_preferences",
        "skill_applications",
    ]


def test_audit_logs_migration_declares_indexes_and_drop_order(monkeypatch):
    migration = _load("add_audit_logs_table")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    assert [name for name, _columns in op.created_tables] == ["audit_logs"]
    indexes = {index_name for batch in op.batches for index_name, _columns, _unique in batch.created_indexes}
    assert indexes == {"ix_audit_actor", "ix_audit_action", "ix_audit_resource", "ix_audit_time"}

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    assert op.dropped_tables == ["audit_logs"]


def test_users_ext_disabled_migration_adds_column_indexes_and_reverses(monkeypatch):
    migration = _load("f3a2b1c4d5e6_add_disabled_column_and_indexes")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    batch = op.batches[0]
    assert batch.added_columns == ["disabled"]
    assert batch.created_indexes == [
        ("ix_users_ext_role", ("role",), False),
        ("ix_users_ext_department_id", ("department_id",), False),
    ]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    batch = op.batches[0]
    assert batch.dropped_indexes == ["ix_users_ext_department_id", "ix_users_ext_role"]
    assert batch.dropped_columns == ["disabled"]


def test_resource_metadata_indexes_migration_replaces_indexes(monkeypatch):
    migration = _load("fix_resource_metadata_indexes")
    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.upgrade()

    batch = op.batches[0]
    assert batch.dropped_indexes == ["ix_resource_metadata_visibility", "ix_resource_metadata_type"]
    assert [name for name, _columns, _unique in batch.created_indexes] == [
        "ix_resource_meta_type_visibility",
        "ix_resource_meta_owner_active",
        "ix_resource_meta_dept_active",
    ]

    op = _OpRecorder()
    monkeypatch.setattr(migration, "op", op)

    migration.downgrade()

    batch = op.batches[0]
    assert batch.dropped_indexes == [
        "ix_resource_meta_type_visibility",
        "ix_resource_meta_owner_active",
        "ix_resource_meta_dept_active",
    ]
    assert [name for name, _columns, _unique in batch.created_indexes] == [
        "ix_resource_metadata_visibility",
        "ix_resource_metadata_type",
    ]
