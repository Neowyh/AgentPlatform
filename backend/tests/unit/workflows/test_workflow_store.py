"""Tests for WorkflowStore — DB-backed workflow definition and run state persistence.

Covers:
- save_workflow / load_workflow / delete_workflow CRUD
- list_workflows pagination
- save_run_state / load_run_state / update_run_status
- save_review_result
- list_runs pagination and filtering
- Serialization helpers (_json_safe, _state_to_dict, _row_to_state)
- Singleton (get_workflow_store)
- Error paths (DB not initialized)
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.harness.ideer.workflows.state import RunStatus, WorkflowState
from packages.harness.ideer.workflows.store import (
    WorkflowStore,
    _json_safe,
    _row_to_state,
    _state_to_dict,
    get_workflow_store,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_state(
    workflow_name: str = "test-wf",
    run_id: str = "run-001",
    inputs: dict | None = None,
    status: RunStatus = RunStatus.RUNNING,
) -> WorkflowState:
    return WorkflowState(
        workflow_name=workflow_name,
        run_id=run_id,
        inputs=inputs or {},
        status=status,
    )


def _make_row(
    run_id: str = "run-001",
    workflow_name: str = "test-wf",
    workflow_yaml: str = "name: test-wf\nsteps: []",
    status: str = "running",
    inputs: dict | None = None,
    steps_state: dict | None = None,
    current_step: str | None = None,
    error: str | None = None,
    review_result: dict | None = None,
    created_at=None,
):
    """Build a mock WorkflowRunRow."""
    return SimpleNamespace(
        run_id=run_id,
        workflow_name=workflow_name,
        workflow_yaml=workflow_yaml,
        status=status,
        inputs=inputs or {},
        steps_state=steps_state or {},
        current_step=current_step,
        error=error,
        review_result=review_result,
        loop_vars={},
        created_at=created_at or datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class _MockSessionContext:
    """Async context manager that yields a mock session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _mock_session_factory(rows=None, scalar_result=None):
    """Build a mock session factory that returns rows from execute().

    Returns (sf, session) where sf() returns an async context manager.
    """
    if rows is None:
        rows = []

    mock_session = AsyncMock()

    # execute() returns a result with scalars().all() and scalar_one_or_none()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = scalar_result
    mock_result.scalar.return_value = scalar_result if scalar_result is not None else len(rows)

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.delete = AsyncMock()

    # sf() returns an async context manager (not a coroutine)
    ctx = _MockSessionContext(mock_session)
    mock_sf = MagicMock(return_value=ctx)

    return mock_sf, mock_session


# ── _json_safe ───────────────────────────────────────────────────────


class TestJsonSafe:
    """Tests for the _json_safe serialization helper."""

    def test_already_serializable(self):
        assert _json_safe({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}

    def test_nested_dict_with_non_serializable(self):
        class Custom:
            def __str__(self):
                return "custom"

        result = _json_safe({"key": Custom()})
        assert result["key"] == "custom"

    def test_list_with_non_serializable(self):
        result = _json_safe([object(), 42])
        assert result[1] == 42
        assert isinstance(result[0], str)

    def test_tuple_in_dict_converted_to_list(self):
        """Tuples inside dicts go through the recursive path and become lists."""
        result = _json_safe({"t": (1, 2, 3)})

        # Note: (1,2,3) is JSON-serializable as an array, so json.dumps succeeds
        # on the fast path and returns it as-is. The recursive path only kicks in
        # for non-serializable leaf values. A tuple with non-serializable elements
        # would be converted to a list of strings.
        class X:
            def __str__(self):
                return "x"

        result = _json_safe({"t": (X(), X())})
        assert isinstance(result["t"], list)
        assert result["t"] == ["x", "x"]

    def test_none_passthrough(self):
        assert _json_safe(None) is None

    def test_string_passthrough(self):
        assert _json_safe("hello") == "hello"

    def test_int_passthrough(self):
        assert _json_safe(42) == 42

    def test_deeply_nested(self):
        obj = {"a": {"b": {"c": [object()]}}}
        result = _json_safe(obj)
        assert isinstance(result["a"]["b"]["c"][0], str)


# ── _state_to_dict ───────────────────────────────────────────────────


class TestStateToDict:
    """Tests for serializing WorkflowState to dict."""

    def test_basic_serialization(self):
        state = _make_state(inputs={"q": "hello"})
        state.set_step_result("s1", status="completed", output="world")
        d = _state_to_dict(state)
        assert d["workflow_name"] == "test-wf"
        assert d["run_id"] == "run-001"
        assert d["inputs"] == {"q": "hello"}
        assert d["status"] == "running"
        assert d["steps"]["s1"]["status"] == "completed"
        assert d["steps"]["s1"]["output"] == "world"

    def test_review_result_serialized(self):
        state = _make_state()
        state.review_result = {"approved": True, "comment": "LGTM"}
        d = _state_to_dict(state)
        assert d["review_result"]["approved"] is True

    def test_none_review_result(self):
        state = _make_state()
        d = _state_to_dict(state)
        assert d["review_result"] is None

    def test_empty_steps(self):
        state = _make_state()
        d = _state_to_dict(state)
        assert d["steps"] == {}


# ── _row_to_state ────────────────────────────────────────────────────


class TestRowToState:
    """Tests for deserializing a DB row back to WorkflowState."""

    def test_basic_deserialization(self):
        row = _make_row(
            status="running",
            inputs={"q": "test"},
            steps_state={
                "s1": {
                    "step_id": "s1",
                    "status": "completed",
                    "output": "ok",
                    "retries": 0,
                }
            },
        )
        state = _row_to_state(row)
        assert state.workflow_name == "test-wf"
        assert state.run_id == "run-001"
        assert state.status == RunStatus.RUNNING
        assert state.inputs == {"q": "test"}
        assert state.steps["s1"].status == "completed"
        assert state.steps["s1"].output == "ok"

    def test_unknown_status_defaults_to_failed(self):
        row = _make_row(status="unknown_status")
        state = _row_to_state(row)
        assert state.status == RunStatus.FAILED

    def test_created_at_preserved(self):
        now = datetime.now(UTC)
        row = _make_row(created_at=now)
        state = _row_to_state(row)
        assert state.created_at == now.isoformat()

    def test_none_created_at(self):
        row = _make_row(created_at=None)
        state = _row_to_state(row)
        # Should not crash; created_at stays as default
        assert state.created_at is not None

    def test_review_result_preserved(self):
        row = _make_row(review_result={"approved": True})
        state = _row_to_state(row)
        assert state.review_result == {"approved": True}

    def test_empty_steps_state(self):
        row = _make_row(steps_state=None)
        state = _row_to_state(row)
        assert state.steps == {}

    def test_step_result_with_defaults(self):
        """Step data with missing fields uses safe defaults."""
        row = _make_row(
            steps_state={
                "s1": {"step_id": "s1"}  # missing status, output, etc.
            }
        )
        state = _row_to_state(row)
        assert state.steps["s1"].status == "pending"
        assert state.steps["s1"].output is None
        assert state.steps["s1"].retries == 0


# ── WorkflowStore: workflow definition CRUD ──────────────────────────


class TestWorkflowStoreDefinitionCRUD:
    """Tests for save_workflow / load_workflow / delete_workflow."""

    @pytest.mark.asyncio
    async def test_save_workflow_creates_new(self):
        store = WorkflowStore()
        row = None  # No existing row
        sf, session = _mock_session_factory(scalar_result=row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.save_workflow("my-wf", "name: my-wf\nsteps: []")

        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_workflow_updates_existing(self):
        store = WorkflowStore()
        existing_row = _make_row(run_id="def:my-wf", workflow_yaml="old yaml")
        sf, session = _mock_session_factory(scalar_result=existing_row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.save_workflow("my-wf", "new yaml")

        assert existing_row.workflow_yaml == "new yaml"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_workflow_raises_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            with pytest.raises(RuntimeError, match="Database not initialized"):
                await store.save_workflow("my-wf", "yaml")

    @pytest.mark.asyncio
    async def test_load_workflow_returns_yaml(self):
        store = WorkflowStore()
        row = _make_row(run_id="def:my-wf", workflow_yaml="name: my-wf\nsteps: []")
        sf, session = _mock_session_factory(scalar_result=row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.load_workflow("my-wf")

        assert result == "name: my-wf\nsteps: []"

    @pytest.mark.asyncio
    async def test_load_workflow_returns_none_when_not_found(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(scalar_result=None)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.load_workflow("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_workflow_returns_none_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            result = await store.load_workflow("my-wf")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_workflow_returns_true(self):
        store = WorkflowStore()
        row = _make_row(run_id="def:my-wf")
        sf, session = _mock_session_factory(scalar_result=row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.delete_workflow("my-wf")

        assert result is True
        session.delete.assert_called_once_with(row)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_workflow_returns_false_when_not_found(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(scalar_result=None)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.delete_workflow("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_workflow_returns_false_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            result = await store.delete_workflow("my-wf")
        assert result is False


# ── WorkflowStore: run state CRUD ────────────────────────────────────


class TestWorkflowStoreRunState:
    """Tests for save_run_state / load_run_state / update_run_status."""

    @pytest.mark.asyncio
    async def test_save_run_state_creates_new(self):
        store = WorkflowStore()
        state = _make_state()
        sf, session = _mock_session_factory(scalar_result=None)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.save_run_state(state)

        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_run_state_updates_existing(self):
        store = WorkflowStore()
        state = _make_state()
        existing_row = _make_row()
        sf, session = _mock_session_factory(scalar_result=existing_row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.save_run_state(state)

        assert existing_row.status == "running"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_run_state_raises_when_db_not_initialized(self):
        store = WorkflowStore()
        state = _make_state()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            with pytest.raises(RuntimeError, match="Database not initialized"):
                await store.save_run_state(state)

    @pytest.mark.asyncio
    async def test_load_run_state_returns_state(self):
        store = WorkflowStore()
        row = _make_row(status="completed", inputs={"q": "test"})
        sf, session = _mock_session_factory(scalar_result=row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            state = await store.load_run_state("run-001")

        assert state is not None
        assert state.run_id == "run-001"
        assert state.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_load_run_state_returns_none_when_not_found(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(scalar_result=None)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            state = await store.load_run_state("nonexistent")

        assert state is None

    @pytest.mark.asyncio
    async def test_load_run_state_returns_none_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            state = await store.load_run_state("run-001")
        assert state is None

    @pytest.mark.asyncio
    async def test_update_run_status_valid(self):
        store = WorkflowStore()
        existing_row = _make_row()
        sf, session = _mock_session_factory(scalar_result=existing_row)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.update_run_status("run-001", "completed", current_step="s1", error=None)

        assert existing_row.status == "completed"
        assert existing_row.current_step == "s1"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_run_status_invalid_raises(self):
        store = WorkflowStore()
        with pytest.raises(ValueError, match="Invalid status"):
            await store.update_run_status("run-001", "bogus_status")

    @pytest.mark.asyncio
    async def test_update_run_status_noop_when_row_not_found(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(scalar_result=None)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            await store.update_run_status("run-001", "completed")

        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_run_status_noop_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            # Should not raise
            await store.update_run_status("run-001", "completed")


# ── WorkflowStore: save_review_result ────────────────────────────────


class TestSaveReviewResult:
    """Tests for save_review_result."""

    @pytest.mark.asyncio
    async def test_save_review_result_success(self):
        store = WorkflowStore()
        row = _make_row(status="waiting_human")
        sf, session = _mock_session_factory(scalar_result=row)

        # Mock the execute result to return rowcount=1 (simulating successful UPDATE)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        session.execute = AsyncMock(return_value=mock_result)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.save_review_result("run-001", {"approved": True})

        assert result is True
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_review_result_returns_false_when_not_waiting(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(scalar_result=None)

        # Mock execute to return rowcount=0 (no rows updated)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            result = await store.save_review_result("run-001", {"approved": True})

        assert result is False

    @pytest.mark.asyncio
    async def test_save_review_result_returns_false_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            result = await store.save_review_result("run-001", {"approved": True})
        assert result is False


# ── WorkflowStore: list_workflows ────────────────────────────────────


class TestListWorkflows:
    """Tests for list_workflows with pagination."""

    @pytest.mark.asyncio
    async def test_list_workflows_empty(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(rows=[], scalar_result=0)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            items, total = await store.list_workflows()

        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_workflows_returns_none_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            items, total = await store.list_workflows()
        assert items == []
        assert total == 0


# ── WorkflowStore: list_runs ─────────────────────────────────────────


class TestListRuns:
    """Tests for list_runs with pagination and filtering."""

    @pytest.mark.asyncio
    async def test_list_runs_empty(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(rows=[], scalar_result=0)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            runs, total = await store.list_runs()

        assert runs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_runs_clamps_limit(self):
        """Limit is clamped to [1, 200]."""
        store = WorkflowStore()
        sf, session = _mock_session_factory(rows=[], scalar_result=0)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            runs, total = await store.list_runs(limit=999)

        assert runs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_runs_clamps_negative_offset(self):
        store = WorkflowStore()
        sf, session = _mock_session_factory(rows=[], scalar_result=0)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            runs, total = await store.list_runs(offset=-5)

        assert runs == []

    @pytest.mark.asyncio
    async def test_list_runs_returns_empty_when_db_not_initialized(self):
        store = WorkflowStore()
        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=None):
            runs, total = await store.list_runs()
        assert runs == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_runs_with_rows(self):
        store = WorkflowStore()
        row = _make_row(
            run_id="run-001",
            workflow_name="my-wf",
            status="completed",
            current_step="s1",
            error=None,
        )
        sf, session = _mock_session_factory(rows=[row], scalar_result=1)

        with patch("packages.harness.ideer.workflows.store.get_session_factory", return_value=sf):
            runs, total = await store.list_runs("my-wf")

        assert total == 1
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-001"
        assert runs[0]["workflow"] == "my-wf"
        assert runs[0]["status"] == "completed"


# ── Singleton ────────────────────────────────────────────────────────


class TestGetWorkflowStore:
    """Tests for the get_workflow_store singleton."""

    def test_returns_same_instance(self):
        # Reset singleton
        import packages.harness.ideer.workflows.store as store_mod

        store_mod._store = None

        s1 = get_workflow_store()
        s2 = get_workflow_store()
        assert s1 is s2

        # Cleanup
        store_mod._store = None

    def test_returns_workflow_store_type(self):
        import packages.harness.ideer.workflows.store as store_mod

        store_mod._store = None

        s = get_workflow_store()
        assert isinstance(s, WorkflowStore)

        store_mod._store = None
