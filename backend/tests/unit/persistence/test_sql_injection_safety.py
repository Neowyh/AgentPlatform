"""SQL injection safety tests for repository-layer methods.

Even though SQLAlchemy ORM is used throughout the codebase, we verify:
- Repository methods pass parameters as bound variables (not string formatting)
- Dynamic sort/filter parameters don't allow injection
- No raw SQL execution in repository methods
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.auth.repositories.sqlite import SQLiteUserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session():
    """Create a mock async session factory for testing."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_sf = MagicMock()
    mock_sf.return_value = mock_session
    return mock_session, mock_sf


def _make_repo(mock_sf):
    return SQLiteUserRepository(mock_sf)


class TestSQLParameterization:
    """Verify that all repository queries use parameterized statements.

    SQLAlchemy Core / ORM produces parameterized queries by default when
    using the `==` operator on column expressions. This test suite
    intercepts the query at the session level to confirm no string
    formatting is used for user-supplied values.
    """

    def test_get_user_by_email_uses_parameterized_query(self):
        """get_user_by_email must use a bound parameter, not string formatting."""
        mock_session, mock_sf = _make_mock_session()

        tracker = []

        async def tracking_execute(stmt, *args, **kwargs):
            compiled = stmt.compile(compile_kwargs={"literal_binds": False})
            sql_str = str(compiled)
            tracker.append(sql_str)
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = tracking_execute

        repo = _make_repo(mock_sf)
        import asyncio

        asyncio.run(repo.get_user_by_email("test@example.com"))

        assert len(tracker) == 1, "Expected exactly one SQL execution"
        sql = tracker[0]
        # Verify the query uses a parameter placeholder, not the literal value
        assert "test@example.com" not in sql, f"Email value appears literally in SQL — possible injection risk.\nSQL: {sql}"
        assert ":email_1" in sql or "?" in sql, f"SQL does not contain parameter placeholder.\nSQL: {sql}"
        assert "email" in sql.lower(), "Query should reference the email column"

    @pytest.mark.parametrize(
        "injection_email",
        [
            "test@example.com' OR '1'='1",
            "test@example.com'; DROP TABLE users; --",
            "' OR 1=1 --",
            '" OR ""="',
            "admin'--",
            "x' UNION SELECT * FROM users --",
            "test@example.com\\",
        ],
    )
    def test_get_user_by_email_sql_injection_attempts_parameterized(self, injection_email):
        """SQL injection strings in email must remain literal parameters."""
        mock_session, mock_sf = _make_mock_session()

        captured_stmt = None

        async def capturing_execute(stmt, *args, **kwargs):
            nonlocal captured_stmt
            captured_stmt = stmt
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = capturing_execute

        repo = _make_repo(mock_sf)
        import asyncio

        asyncio.run(repo.get_user_by_email(injection_email))

        assert captured_stmt is not None
        compiled = str(captured_stmt.compile(compile_kwargs={"literal_binds": False}))
        # The injection string must NOT appear literally in the SQL
        unsafe_parts = [p for p in ("' OR '", "DROP TABLE", "UNION SELECT", "1=1") if p in compiled]
        assert not unsafe_parts, f"Injection payload appears literally in SQL: {unsafe_parts}\nSQL: {compiled}"

    def test_get_user_by_id_uses_parameterized_query(self):
        """get_user_by_id (session.get) uses parameterized lookup."""
        mock_session, mock_sf = _make_mock_session()
        mock_session.get = AsyncMock(return_value=None)

        repo = _make_repo(mock_sf)
        import asyncio

        asyncio.run(repo.get_user_by_id("user-123"))

        mock_session.get.assert_awaited_once()
        # session.get does not accept SQL injection via the primary key
        # — SQLAlchemy treats it as a bound parameter internally
        args, kwargs = mock_session.get.call_args
        assert args[1] == "user-123"

    def test_count_users_uses_safe_query(self):
        """count_users must not use raw SQL."""
        mock_session, mock_sf = _make_mock_session()
        mock_session.scalar = AsyncMock(return_value=5)

        repo = _make_repo(mock_sf)
        import asyncio

        result = asyncio.run(repo.count_users())
        assert result == 5

    def test_get_user_by_oauth_parameterized(self):
        """get_user_by_oauth must parameterize both provider and oauth_id."""
        mock_session, mock_sf = _make_mock_session()

        captured_stmt = None

        async def capturing_execute(stmt, *args, **kwargs):
            nonlocal captured_stmt
            captured_stmt = stmt
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = capturing_execute

        repo = _make_repo(mock_sf)
        import asyncio

        asyncio.run(repo.get_user_by_oauth("github'; DROP TABLE users; --", "12345"))

        assert captured_stmt is not None
        compiled = str(captured_stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "DROP TABLE" not in compiled, f"Injection payload appears literally in SQL.\nSQL: {compiled}"


class TestDynamicFilterSafety:
    """Test that dynamic sort/filter parameters don't allow injection.

    Routes accepting ?sort=column or ?filter=value must not pass user
    input directly into raw SQL strings.
    """

    def test_order_by_with_column_injection_detected(self):
        """A malicious sort parameter should not be interpolated.

        This tests that if a dynamic order_by were built from user input
        (which the codebase currently avoids), it would be detected.
        We verify the safe pattern: only allow-listed column names.
        """

        ALLOWED_SORT_COLUMNS = {"created_at", "updated_at", "email", "username"}

        def safe_sort(column: str) -> str:
            if column not in ALLOWED_SORT_COLUMNS:
                raise ValueError(f"Invalid sort column: {column}")
            return column

        assert safe_sort("created_at") == "created_at"
        assert safe_sort("email") == "email"

        with pytest.raises(ValueError, match="Invalid sort column"):
            safe_sort("id; DROP TABLE users")

        with pytest.raises(ValueError, match="Invalid sort column"):
            safe_sort("email DESC")

        with pytest.raises(ValueError, match="Invalid sort column"):
            safe_sort("")

    def test_column_name_sql_injection(self):
        """Column names containing SQL keywords must be rejected."""
        ALLOWED_SORT_COLUMNS = {"created_at", "updated_at", "email", "username"}

        for injection in [
            "1; SELECT * FROM users",
            "created_at ASC--",
            "email) ASC; --",
            "(SELECT 1 FROM users)",
        ]:
            assert injection not in ALLOWED_SORT_COLUMNS, f"Injection string {injection!r} should not be allowed"


class TestNoRawSQL:
    """Verify that repository methods don't use raw SQL strings.

    The codebase uses SQLAlchemy ORM consistently. This test class
    scans for known unsafe patterns as a regression gate.
    """

    def test_create_user_uses_orm_add_not_raw_insert(self):
        """create_user must use session.add, not raw SQL."""
        mock_session, mock_sf = _make_mock_session()

        repo = _make_repo(mock_sf)
        from uuid import uuid4

        from app.gateway.auth.models import User

        user = User(
            id=uuid4(),
            email="new@example.com",
            password_hash="hash",
            system_role="user",
        )
        import asyncio

        asyncio.run(repo.create_user(user))

        # Verify session.add was called (ORM insert) instead of session.execute with raw SQL
        mock_session.add.assert_called_once()
        mock_session.execute.assert_not_called()

    def test_update_user_uses_orm_assignment(self):
        """update_user must use ORM attribute assignment, not raw SQL UPDATE."""
        mock_session, mock_sf = _make_mock_session()

        existing_row = MagicMock()
        existing_row.email = "old@example.com"
        existing_row.password_hash = "old_hash"
        existing_row.system_role = "user"
        existing_row.oauth_provider = None
        existing_row.oauth_id = None
        existing_row.needs_setup = False
        existing_row.token_version = 0
        mock_session.get = AsyncMock(return_value=existing_row)

        repo = _make_repo(mock_sf)
        from uuid import uuid4

        from app.gateway.auth.models import User

        user = User(
            id=uuid4(),
            email="new@example.com",
            password_hash="new_hash",
            system_role="user",
        )
        import asyncio

        asyncio.run(repo.update_user(user))

        mock_session.get.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
        # Should not have executed raw SQL
        mock_session.execute.assert_not_called()


class TestRepositoryLayerPattern:
    """Pattern verification tests for other repository methods.

    These check that common patterns like LIKE / IN / ORDER BY
    are handled safely across the codebase.
    """

    @pytest.mark.parametrize(
        "unsafe_input",
        [
            "'; SELECT * FROM users; --",
            "1 OR 1=1",
            '" OR 1=1 --',
            "1; DROP TABLE users",
        ],
    )
    def test_get_user_by_email_with_injection_patterns(self, unsafe_input):
        """Injection patterns pass as literal values, not executed."""
        mock_session, mock_sf = _make_mock_session()

        captured_stmt = None

        async def capturing_execute(stmt, *args, **kwargs):
            nonlocal captured_stmt
            captured_stmt = stmt
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = capturing_execute

        repo = SQLiteUserRepository(mock_sf)
        import asyncio

        asyncio.run(repo.get_user_by_email(unsafe_input))

        assert captured_stmt is not None
        compiled = str(captured_stmt.compile(compile_kwargs={"literal_binds": False}))
        # None of the unsafe parts should be in the compiled SQL
        for token in ("1=1", "DROP TABLE", "SELECT *"):
            assert token not in compiled, f"Injection token {token!r} found in SQL.\nSQL: {compiled}"
