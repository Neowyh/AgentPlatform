"""Unit tests for gateway/audit.py — record_audit function."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: build a mock session factory / session
# ---------------------------------------------------------------------------


def _make_mock_session_factory(session_cls=None):
    """Return (mock_factory, mock_session) where mock_factory() returns a mock_session via __aenter__."""
    mock_session = MagicMock() if session_cls is None else session_cls()
    mock_session.commit = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_factory, mock_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordAuditSuccess:
    """正常记录审计日志：所有参数齐全，session commit 成功。"""

    @pytest.mark.asyncio
    async def test_all_params(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(
                actor_id="u1",
                action="delete",
                resource_type="skill",
                resource_id="s1",
                detail={"old": "a", "new": "b"},
                ip_address="127.0.0.1",
            )

        session.add.assert_called_once()
        session.commit.assert_awaited_once()
        entry = session.add.call_args[0][0]
        assert entry.actor_id == "u1"
        assert entry.action == "delete"
        assert entry.resource_type == "skill"
        assert entry.resource_id == "s1"
        assert json.loads(entry.detail) == {"old": "a", "new": "b"}
        assert entry.ip_address == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_minimal_params(self):
        """只传必填参数 actor_id 和 action，其余均为 None。"""
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(actor_id="u2", action="create")

        entry = session.add.call_args[0][0]
        assert entry.actor_id == "u2"
        assert entry.action == "create"
        assert entry.resource_type is None
        assert entry.resource_id is None
        assert entry.detail is None
        assert entry.ip_address is None


class TestRecordAuditSessionFactoryNone:
    """session_factory 返回 None 时应直接 return，不报错。"""

    @pytest.mark.asyncio
    async def test_factory_none_no_error(self):
        from app.gateway.audit import record_audit

        with patch("app.gateway.audit.get_session_factory", return_value=None):
            # Should return silently — no exception, no DB call
            await record_audit(actor_id="u1", action="delete")


class TestRecordAuditDbError:
    """数据库操作异常时应捕获并记录日志，不应抛出。"""

    @pytest.mark.asyncio
    async def test_commit_failure_swallows_exception(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()
        session.commit.side_effect = RuntimeError("db down")

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            with patch("app.gateway.audit.logger") as mock_logger:
                await record_audit(actor_id="u1", action="delete")

        mock_logger.exception.assert_called_once_with("Failed to record audit log")

    @pytest.mark.asyncio
    async def test_add_failure_swallows_exception(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()
        session.add.side_effect = RuntimeError("model error")

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            with patch("app.gateway.audit.logger") as mock_logger:
                await record_audit(actor_id="u1", action="create")

        mock_logger.exception.assert_called_once_with("Failed to record audit log")


class TestRecordAuditDetailSerialization:
    """detail 参数的 JSON 序列化行为。"""

    @pytest.mark.asyncio
    async def test_detail_none_stores_none(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(actor_id="u1", action="update", detail=None)

        entry = session.add.call_args[0][0]
        assert entry.detail is None

    @pytest.mark.asyncio
    async def test_chinese_characters_preserved(self):
        """ensure_ascii=False 应保留中文字符，不转为 \\uXXXX。"""
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(
                actor_id="u1",
                action="update",
                detail={"reason": "权限变更"},
            )

        entry = session.add.call_args[0][0]
        assert "权限变更" in entry.detail
        assert "\\u" not in entry.detail

    @pytest.mark.asyncio
    async def test_nested_detail(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(
                actor_id="u1",
                action="update",
                detail={"a": [1, 2], "b": {"c": True}},
            )

        entry = session.add.call_args[0][0]
        assert json.loads(entry.detail) == {"a": [1, 2], "b": {"c": True}}


class TestRecordAuditEntryAttributes:
    """验证写入的 AuditLog 对象属性。"""

    @pytest.mark.asyncio
    async def test_id_is_hex_string(self):
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(actor_id="u1", action="create")

        entry = session.add.call_args[0][0]
        assert isinstance(entry.id, str)
        assert len(entry.id) == 32
        assert int(entry.id, 16), f"ID '{entry.id}' is not valid hex"

    @pytest.mark.asyncio
    async def test_ids_unique_per_call(self):
        """多次调用应生成不同的 UUID。"""
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(actor_id="u1", action="create")
            first_id = session.add.call_args[0][0].id

            await record_audit(actor_id="u1", action="create")
            second_id = session.add.call_args[0][0].id

        assert first_id != second_id

    @pytest.mark.asyncio
    async def test_add_called_before_commit(self):
        """session.add 应在 session.commit 之前被调用。"""
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()
        call_order = []
        session.add.side_effect = lambda *a, **kw: call_order.append("add")

        original_side_effect = session.commit.side_effect

        async def track_commit(*a, **kw):
            call_order.append("commit")
            if original_side_effect is not None:
                return await original_side_effect(*a, **kw)

        session.commit.side_effect = track_commit

        with patch("app.gateway.audit.get_session_factory", return_value=factory):
            await record_audit(actor_id="u1", action="delete")

        assert call_order == ["add", "commit"]

    @pytest.mark.asyncio
    async def test_session_factory_called(self):
        """get_session_factory 应被实际调用。"""
        from app.gateway.audit import record_audit

        factory, session = _make_mock_session_factory()

        with patch("app.gateway.audit.get_session_factory", return_value=factory) as mock_sf:
            await record_audit(actor_id="u1", action="create")

        mock_sf.assert_called_once()
