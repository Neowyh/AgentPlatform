"""Tests for ideer.persistence.run.sql — SQLAlchemy-backed RunStore."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# RunRepository static methods
# ---------------------------------------------------------------------------


class TestNormalizeModelName:
    def test_none(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._normalize_model_name(None) is None

    def test_strips_whitespace(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._normalize_model_name("  gpt-4  ") == "gpt-4"

    def test_truncates_long_name(self):
        from ideer.persistence.run.sql import RunRepository

        long = "a" * 200
        result = RunRepository._normalize_model_name(long)
        assert len(result) == 128

    def test_non_string_converted(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._normalize_model_name(123) == "123"

    def test_empty_string(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._normalize_model_name("") == ""


class TestSafeJson:
    def test_none(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._safe_json(None) is None

    def test_primitives(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._safe_json("str") == "str"
        assert RunRepository._safe_json(42) == 42
        assert RunRepository._safe_json(3.14) == 3.14
        assert RunRepository._safe_json(True) is True

    def test_dict_recursive(self):
        from ideer.persistence.run.sql import RunRepository

        data = {"a": 1, "b": {"c": "d"}}
        assert RunRepository._safe_json(data) == {"a": 1, "b": {"c": "d"}}

    def test_list_recursive(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._safe_json([1, [2, 3]]) == [1, [2, 3]]

    def test_tuple(self):
        from ideer.persistence.run.sql import RunRepository

        assert RunRepository._safe_json((1, 2)) == [1, 2]

    def test_pydantic_model_dump(self):
        from ideer.persistence.run.sql import RunRepository

        obj = MagicMock()
        obj.model_dump.return_value = {"key": "value"}
        assert RunRepository._safe_json(obj) == {"key": "value"}

    def test_model_dump_fails_fallback_to_dict(self):
        from ideer.persistence.run.sql import RunRepository

        class HasDict:
            def dict(self):
                return {"fallback": True}

        obj = HasDict()
        assert RunRepository._safe_json(obj) == {"fallback": True}

    def test_both_dumps_fail_fallback_to_str(self):
        from ideer.persistence.run.sql import RunRepository

        obj = object()  # plain object, no model_dump/dict, not JSON serializable
        result = RunRepository._safe_json(obj)
        assert isinstance(result, str)

    def test_json_serializable_object(self):
        from ideer.persistence.run.sql import RunRepository

        # An object that json.dumps can handle but isn't a primitive
        obj = {"key": [1, 2]}
        assert RunRepository._safe_json(obj) == {"key": [1, 2]}


# ---------------------------------------------------------------------------
# RunRepository._row_to_dict
# ---------------------------------------------------------------------------


class TestRowToDict:
    def test_remapping(self):
        from ideer.persistence.run.sql import RunRepository

        now = datetime.now(UTC)
        row = SimpleNamespace()
        row.to_dict = lambda: {
            "run_id": "r1",
            "metadata_json": {"k": "v"},
            "kwargs_json": {"extra": True},
            "created_at": now,
            "updated_at": now,
        }

        result = RunRepository._row_to_dict(row)
        assert result["metadata"] == {"k": "v"}
        assert result["kwargs"] == {"extra": True}
        assert "metadata_json" not in result
        assert "kwargs_json" not in result


# ---------------------------------------------------------------------------
# RunRepository async methods (mocked session factory)
# ---------------------------------------------------------------------------


def _make_repo():
    from ideer.persistence.run.sql import RunRepository

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_sf = MagicMock()
    mock_sf.return_value = mock_session

    repo = RunRepository(mock_sf)
    return repo, mock_session


class TestPut:
    @pytest.mark.asyncio
    async def test_insert_new_row(self):
        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.put("run1", thread_id="t1", model_name="gpt-4")
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_existing_row(self):
        repo, mock_session = _make_repo()
        existing_row = MagicMock()
        mock_session.get = AsyncMock(return_value=existing_row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.put("run1", thread_id="t1", status="running")
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_created_at(self):
        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.put("run1", thread_id="t1", created_at="2024-01-01T00:00:00+00:00")
            mock_session.add.assert_called_once()


class TestGet:
    @pytest.mark.asyncio
    async def test_found(self):
        repo, mock_session = _make_repo()
        now = datetime.now(UTC)
        row = MagicMock()
        row.to_dict.return_value = {
            "run_id": "r1",
            "metadata_json": {},
            "kwargs_json": {},
            "created_at": now,
            "updated_at": now,
            "user_id": "user1",
        }
        row.user_id = "user1"
        mock_session.get = AsyncMock(return_value=row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            result = await repo.get("r1")
            assert result is not None
            assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_not_found(self):
        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            result = await repo.get("r1")
            assert result is None

    @pytest.mark.asyncio
    async def test_user_mismatch_returns_none(self):
        repo, mock_session = _make_repo()
        row = MagicMock()
        row.user_id = "other_user"
        mock_session.get = AsyncMock(return_value=row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            result = await repo.get("r1")
            assert result is None

    @pytest.mark.asyncio
    async def test_no_user_filter(self):
        repo, mock_session = _make_repo()
        now = datetime.now(UTC)
        row = MagicMock()
        row.to_dict.return_value = {
            "run_id": "r1",
            "metadata_json": {},
            "kwargs_json": {},
            "created_at": now,
            "updated_at": now,
            "user_id": "any",
        }
        row.user_id = "any"
        mock_session.get = AsyncMock(return_value=row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value=None):
            result = await repo.get("r1")
            assert result is not None


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status("r1", "running")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_match(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status("r1", "running")
        assert result is False

    @pytest.mark.asyncio
    async def test_with_error(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status("r1", "failed", error="boom")
        assert result is True


class TestUpdateModelName:
    @pytest.mark.asyncio
    async def test_updates(self):
        repo, mock_session = _make_repo()
        mock_session.execute = AsyncMock()

        await repo.update_model_name("r1", "claude-3")
        mock_session.commit.assert_called_once()


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self):
        repo, mock_session = _make_repo()
        row = MagicMock()
        row.user_id = "user1"
        mock_session.get = AsyncMock(return_value=row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.delete("r1")
            mock_session.delete.assert_called_once_with(row)

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        repo, mock_session = _make_repo()
        mock_session.get = AsyncMock(return_value=None)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.delete("r1")
            mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_user_mismatch(self):
        repo, mock_session = _make_repo()
        row = MagicMock()
        row.user_id = "other"
        mock_session.get = AsyncMock(return_value=row)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            await repo.delete("r1")
            mock_session.delete.assert_not_called()


class TestListByThread:
    @pytest.mark.asyncio
    async def test_lists_runs(self):
        repo, mock_session = _make_repo()
        now = datetime.now(UTC)
        row = MagicMock()
        row.to_dict.return_value = {
            "run_id": "r1",
            "metadata_json": {},
            "kwargs_json": {},
            "created_at": now,
            "updated_at": now,
        }
        mock_result = MagicMock()
        mock_result.scalars.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("ideer.persistence.run.sql.resolve_user_id", return_value="user1"):
            result = await repo.list_by_thread("t1")
            assert len(result) == 1


class TestListPending:
    @pytest.mark.asyncio
    async def test_default_before(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_pending()
        assert result == []

    @pytest.mark.asyncio
    async def test_with_datetime_before(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        before = datetime.now(UTC)
        result = await repo.list_pending(before=before)
        assert result == []

    @pytest.mark.asyncio
    async def test_with_string_before(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_pending(before="2024-01-01T00:00:00+00:00")
        assert result == []


class TestListInflight:
    @pytest.mark.asyncio
    async def test_default_before(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_inflight()
        assert result == []

    @pytest.mark.asyncio
    async def test_with_string_before(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_inflight(before="2024-01-01T00:00:00+00:00")
        assert result == []


class TestUpdateRunCompletion:
    @pytest.mark.asyncio
    async def test_success(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_run_completion("r1", status="success", total_tokens=100)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_match(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_run_completion("r1", status="success")
        assert result is False

    @pytest.mark.asyncio
    async def test_with_messages_truncated(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        long_msg = "x" * 3000
        result = await repo.update_run_completion(
            "r1",
            status="success",
            last_ai_message=long_msg,
            first_human_message=long_msg,
        )
        assert result is True


class TestUpdateRunProgress:
    @pytest.mark.asyncio
    async def test_updates(self):
        repo, mock_session = _make_repo()
        mock_session.execute = AsyncMock()

        await repo.update_run_progress("r1", total_tokens=50, llm_call_count=2)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_values_skipped(self):
        repo, mock_session = _make_repo()
        mock_session.execute = AsyncMock()

        await repo.update_run_progress("r1")
        mock_session.commit.assert_called_once()


class TestAggregateTokensByThread:
    @pytest.mark.asyncio
    async def test_empty_result(self):
        repo, mock_session = _make_repo()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.aggregate_tokens_by_thread("t1")
        assert result["total_tokens"] == 0
        assert result["total_runs"] == 0
        assert result["by_model"] == {}

    @pytest.mark.asyncio
    async def test_with_data(self):
        repo, mock_session = _make_repo()

        rows = [
            SimpleNamespace(
                model="gpt-4",
                runs=2,
                total_tokens=200,
                total_input_tokens=100,
                total_output_tokens=100,
                lead_agent=50,
                subagent=30,
                middleware=20,
            ),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.aggregate_tokens_by_thread("t1", include_active=True)
        assert result["total_tokens"] == 200
        assert result["total_runs"] == 2
        assert "gpt-4" in result["by_model"]
