"""Unit tests for json_compat: JSON dialect-aware value matching for SQLAlchemy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, create_mock_engine, select

from ideer.persistence.json_compat import (
    _INT64_MAX,
    _INT64_MIN,
    _PG,
    _SQLITE,
    ALLOWED_FILTER_VALUE_TYPES,
    JsonMatch,
    _build_clause,
    _compile_default,
    _compile_pg,
    _compile_sqlite,
    _type_check,
    json_match,
    validate_metadata_filter_key,
    validate_metadata_filter_value,
)

# ── validate_metadata_filter_key ────────────────────────────────────────────


class TestValidateMetadataFilterKey:
    def test_valid_keys(self):
        assert validate_metadata_filter_key("hello") is True
        assert validate_metadata_filter_key("a1b2") is True
        assert validate_metadata_filter_key("with-dash") is True
        assert validate_metadata_filter_key("with_underscore") is True
        assert validate_metadata_filter_key("A1Z9") is True
        assert validate_metadata_filter_key("x") is True

    def test_empty_string_rejected(self):
        assert validate_metadata_filter_key("") is False

    def test_none_rejected(self):
        assert validate_metadata_filter_key(None) is False

    def test_integer_rejected(self):
        assert validate_metadata_filter_key(123) is False

    def test_special_characters_rejected(self):
        assert validate_metadata_filter_key("hello world") is False
        assert validate_metadata_filter_key("key.subkey") is False
        assert validate_metadata_filter_key("key/value") is False
        assert validate_metadata_filter_key("key=value") is False
        assert validate_metadata_filter_key("key?key") is False
        assert validate_metadata_filter_key("key'or1") is False
        assert validate_metadata_filter_key('key"val') is False
        assert validate_metadata_filter_key("key;DROP") is False
        assert validate_metadata_filter_key("$key") is False
        assert validate_metadata_filter_key("key@val") is False

    def test_unicode_rejected(self):
        assert validate_metadata_filter_key("key_中文") is False
        assert validate_metadata_filter_key("café") is False


# ── validate_metadata_filter_value ──────────────────────────────────────────


class TestValidateMetadataFilterValue:
    def test_none_allowed(self):
        assert validate_metadata_filter_value(None) is True

    def test_bool_allowed(self):
        assert validate_metadata_filter_value(True) is True
        assert validate_metadata_filter_value(False) is True

    def test_int_within_int64_allowed(self):
        assert validate_metadata_filter_value(0) is True
        assert validate_metadata_filter_value(42) is True
        assert validate_metadata_filter_value(-1) is True
        assert validate_metadata_filter_value(_INT64_MIN) is True
        assert validate_metadata_filter_value(_INT64_MAX) is True

    def test_int_outside_int64_rejected(self):
        assert validate_metadata_filter_value(_INT64_MIN - 1) is False
        assert validate_metadata_filter_value(_INT64_MAX + 1) is False
        assert validate_metadata_filter_value(2**100) is False
        assert validate_metadata_filter_value(-(2**100)) is False

    def test_float_allowed(self):
        assert validate_metadata_filter_value(1.5) is True
        assert validate_metadata_filter_value(-0.001) is True
        assert validate_metadata_filter_value(float("inf")) is True
        assert validate_metadata_filter_value(float("nan")) is True

    def test_str_allowed(self):
        assert validate_metadata_filter_value("hello") is True
        assert validate_metadata_filter_value("") is True

    def test_list_rejected(self):
        assert validate_metadata_filter_value([1, 2]) is False

    def test_dict_rejected(self):
        assert validate_metadata_filter_value({"a": 1}) is False

    def test_bytes_rejected(self):
        assert validate_metadata_filter_value(b"hello") is False

    def test_tuple_rejected(self):
        assert validate_metadata_filter_value((1, 2)) is False

    def test_set_rejected(self):
        assert validate_metadata_filter_value({1, 2}) is False

    def test_object_rejected(self):
        assert validate_metadata_filter_value(object()) is False

    def test_allowed_types_tuple_matches(self):
        assert ALLOWED_FILTER_VALUE_TYPES == (type(None), bool, int, float, str)

    def test_bool_not_treated_as_int_for_range_check(self):
        """bool is a subclass of int in Python, but should not trigger int64 range check."""
        assert validate_metadata_filter_value(True) is True
        assert validate_metadata_filter_value(False) is True


# ── JsonMatch construction ──────────────────────────────────────────────────


class TestJsonMatchConstruction:
    def _make_column(self):
        metadata = MetaData()
        t = Table("items", metadata, Column("id", Integer), Column("data", String))
        return t.c.data

    def test_basic_construction(self):
        col = self._make_column()
        m = JsonMatch(col, "name", "Alice")
        assert m.key == "name"
        assert m.value == "Alice"
        assert m.column is col

    def test_invalid_key_raises_value_error(self):
        col = self._make_column()
        with pytest.raises(ValueError, match="must match"):
            JsonMatch(col, "invalid key!", "val")

    def test_invalid_value_type_raises_type_error(self):
        col = self._make_column()
        with pytest.raises(TypeError, match="must be None, bool, int, float, or str"):
            JsonMatch(col, "key", [1, 2])

    def test_int_out_of_range_raises_type_error(self):
        col = self._make_column()
        with pytest.raises(TypeError, match="out of signed 64-bit range"):
            JsonMatch(col, "key", _INT64_MAX + 1)

    def test_none_value_accepted(self):
        col = self._make_column()
        m = JsonMatch(col, "key", None)
        assert m.value is None

    def test_bool_value_accepted(self):
        col = self._make_column()
        m = JsonMatch(col, "key", True)
        assert m.value is True

    def test_float_value_accepted(self):
        col = self._make_column()
        m = JsonMatch(col, "key", 3.14)
        assert m.value == 3.14

    def test_inherit_cache_true(self):
        assert JsonMatch.inherit_cache is True

    def test_type_is_boolean(self):
        from sqlalchemy.types import Boolean

        assert isinstance(JsonMatch.type, Boolean)

    def test_is_implicitly_boolean(self):
        assert JsonMatch._is_implicitly_boolean is True

    def test_string_value_accepted(self):
        col = self._make_column()
        m = JsonMatch(col, "key", "hello")
        assert m.value == "hello"

    def test_int_value_accepted(self):
        col = self._make_column()
        m = JsonMatch(col, "key", 42)
        assert m.value == 42

    def test_traverse_internals_defined(self):
        names = [name for name, _ in JsonMatch._traverse_internals]
        assert "column" in names
        assert "key" in names
        assert "value" in names


# ── json_match convenience function ─────────────────────────────────────────


class TestJsonMatchFunction:
    def test_returns_json_match(self):
        metadata = MetaData()
        t = Table("items", metadata, Column("data", String))
        result = json_match(t.c.data, "key", "val")
        assert isinstance(result, JsonMatch)
        assert result.key == "key"
        assert result.value == "val"


# ── _Dialect dataclass ─────────────────────────────────────────────────────


class TestDialectDataclass:
    def test_sqlite_dialect_fields(self):
        assert _SQLITE.null_type == "null"
        assert _SQLITE.num_types == ("integer", "real")
        assert _SQLITE.num_cast == "REAL"
        assert _SQLITE.int_types == ("integer",)
        assert _SQLITE.int_cast == "INTEGER"
        assert _SQLITE.int_guard is None
        assert _SQLITE.string_type == "text"
        assert _SQLITE.bool_type is None

    def test_pg_dialect_fields(self):
        assert _PG.null_type == "null"
        assert _PG.num_types == ("number",)
        assert _PG.num_cast == "DOUBLE PRECISION"
        assert _PG.int_types == ("number",)
        assert _PG.int_cast == "BIGINT"
        assert _PG.int_guard is not None
        assert _PG.string_type == "string"
        assert _PG.bool_type == "boolean"

    def test_dialect_is_frozen(self):
        assert _SQLITE.__dataclass_params__.frozen is True
        assert _PG.__dataclass_params__.frozen is True


# ── _type_check helper ─────────────────────────────────────────────────────


class TestTypeCheck:
    def test_single_type(self):
        result = _type_check("typeof", ("text",))
        assert result == "typeof = 'text'"

    def test_multiple_types(self):
        result = _type_check("typeof", ("integer", "real"))
        assert result == "typeof IN ('integer', 'real')"

    def test_three_types(self):
        result = _type_check("x", ("a", "b", "c"))
        assert result == "x IN ('a', 'b', 'c')"


# ── _build_clause for different value types ────────────────────────────────


class TestBuildClause:
    def _make_compiler(self, dialect_name="sqlite"):
        engine = create_mock_engine(f"{dialect_name}://", executor=lambda *a, **kw: None)
        stmt = select(1)
        return engine.dialect.statement_compiler(engine.dialect, stmt)

    def test_none_value_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", None, _SQLITE)
        assert clause == "typeof = 'null'"

    def test_none_value_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", None, _PG)
        assert clause == "typeof = 'null'"

    def test_bool_true_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", True, _SQLITE)
        assert clause == "typeof = 'true'"

    def test_bool_false_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", False, _SQLITE)
        assert clause == "typeof = 'false'"

    def test_bool_true_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", True, _PG)
        assert "typeof = 'boolean'" in clause
        assert "extract = 'true'" in clause

    def test_bool_false_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", False, _PG)
        assert "typeof = 'boolean'" in clause
        assert "extract = 'false'" in clause

    def test_int_value_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", 42, _SQLITE)
        assert "integer" in clause
        assert "CAST(extract AS INTEGER)" in clause

    def test_int_value_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", 42, _PG)
        assert "CASE WHEN" in clause
        assert "BIGINT" in clause

    def test_float_value_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", 3.14, _SQLITE)
        assert "REAL" in clause

    def test_float_value_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", 3.14, _PG)
        assert "DOUBLE PRECISION" in clause

    def test_string_value_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "hello", _SQLITE)
        assert "text" in clause

    def test_string_value_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "hello", _PG)
        assert "string" in clause

    def test_zero_int(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", 0, _SQLITE)
        assert "integer" in clause
        assert "?" in clause

    def test_negative_int(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", -5, _SQLITE)
        assert "integer" in clause
        assert "?" in clause

    def test_empty_string_value_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "", _SQLITE)
        assert "text" in clause

    def test_empty_string_value_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "", _PG)
        assert "string" in clause

    def test_float_inf_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", float("inf"), _SQLITE)
        assert "REAL" in clause

    def test_float_nan_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", float("nan"), _SQLITE)
        assert "REAL" in clause

    def test_float_neg_zero_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", -0.0, _SQLITE)
        assert "REAL" in clause

    def test_int64_boundary_values_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause_min = _build_clause(compiler, "typeof", "extract", _INT64_MIN, _SQLITE)
        assert "integer" in clause_min
        clause_max = _build_clause(compiler, "typeof", "extract", _INT64_MAX, _SQLITE)
        assert "integer" in clause_max

    def test_int64_boundary_values_pg(self):
        compiler = self._make_compiler("sqlite")
        clause_min = _build_clause(compiler, "typeof", "extract", _INT64_MIN, _PG)
        assert "CASE WHEN" in clause_min
        clause_max = _build_clause(compiler, "typeof", "extract", _INT64_MAX, _PG)
        assert "CASE WHEN" in clause_max

    def test_bool_true_clause_structure_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", True, _PG)
        assert "(" in clause
        assert ")" in clause
        assert "AND" in clause

    def test_bool_false_clause_structure_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", False, _PG)
        assert "(" in clause
        assert ")" in clause
        assert "AND" in clause

    def test_string_clause_full_structure_sqlite(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "hello", _SQLITE)
        assert "typeof = 'text'" in clause
        assert "?" in clause

    def test_string_clause_full_structure_pg(self):
        compiler = self._make_compiler("sqlite")
        clause = _build_clause(compiler, "typeof", "extract", "hello", _PG)
        assert "typeof = 'string'" in clause
        assert "?" in clause


# ── SQL compilation via real engine ─────────────────────────────────────────


class TestSqliteCompilation:
    @pytest.fixture()
    def engine_and_table(self):
        engine = create_engine("sqlite://")
        metadata = MetaData()
        t = Table(
            "test_items",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("metadata", String),
        )
        metadata.create_all(engine)
        return engine, t

    def test_select_with_json_match_compiles(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "name", "Alice")
        stmt = select(t.c.id).where(m)
        compiled = stmt.compile(dialect=engine.dialect)
        sql = str(compiled)
        assert "json_type" in sql
        assert "json_extract" in sql
        assert '"name"' in sql

    def test_select_with_none_value(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "key", None)
        stmt = select(t.c.id).where(m)
        sql = str(stmt.compile(dialect=engine.dialect))
        assert "'null'" in sql

    def test_select_with_bool_value(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "active", True)
        stmt = select(t.c.id).where(m)
        sql = str(stmt.compile(dialect=engine.dialect))
        assert "'true'" in sql

    def test_select_with_int_value(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "count", 42)
        stmt = select(t.c.id).where(m)
        sql = str(stmt.compile(dialect=engine.dialect))
        assert "INTEGER" in sql

    def test_select_with_float_value(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "score", 9.5)
        stmt = select(t.c.id).where(m)
        sql = str(stmt.compile(dialect=engine.dialect))
        assert "REAL" in sql

    def test_select_with_string_value(self, engine_and_table):
        engine, t = engine_and_table
        m = json_match(t.c.metadata, "name", "hello")
        stmt = select(t.c.id).where(m)
        sql = str(stmt.compile(dialect=engine.dialect))
        assert "text" in sql

    def test_insert_and_query_roundtrip(self, engine_and_table):
        engine, t = engine_and_table
        import json

        with engine.begin() as conn:
            conn.execute(t.insert().values(id=1, metadata=json.dumps({"name": "Alice", "age": 30})))
            conn.execute(t.insert().values(id=2, metadata=json.dumps({"name": "Bob", "age": 25})))

        m = json_match(t.c.metadata, "name", "Alice")
        stmt = select(t.c.id).where(m)
        with engine.connect() as conn:
            result = conn.execute(stmt).fetchall()
        assert len(result) == 1
        assert result[0][0] == 1

    def test_insert_none_metadata_query_null(self, engine_and_table):
        engine, t = engine_and_table
        import json

        with engine.begin() as conn:
            conn.execute(t.insert().values(id=1, metadata=json.dumps({"key": None})))
            conn.execute(t.insert().values(id=2, metadata=json.dumps({"key": "value"})))

        m = json_match(t.c.metadata, "key", None)
        stmt = select(t.c.id).where(m)
        with engine.connect() as conn:
            result = conn.execute(stmt).fetchall()
        assert len(result) == 1
        assert result[0][0] == 1

    def test_insert_bool_metadata_query(self, engine_and_table):
        engine, t = engine_and_table
        import json

        with engine.begin() as conn:
            conn.execute(t.insert().values(id=1, metadata=json.dumps({"active": True})))
            conn.execute(t.insert().values(id=2, metadata=json.dumps({"active": False})))

        m = json_match(t.c.metadata, "active", True)
        stmt = select(t.c.id).where(m)
        with engine.connect() as conn:
            result = conn.execute(stmt).fetchall()
        assert len(result) == 1
        assert result[0][0] == 1


# ── _compile_default raises for unsupported dialect ─────────────────────────


class TestCompileDefault:
    def test_unsupported_dialect_raises(self):
        col = MagicMock()
        col.key = "data"
        compiler = MagicMock()
        compiler.dialect.name = "mysql"
        compiler.process.return_value = '"data"'
        m = JsonMatch(col, "key", "val")
        with pytest.raises(NotImplementedError, match="supports only sqlite and postgresql"):
            _compile_default(m, compiler)

    def test_unsupported_dialect_error_includes_dialect_name(self):
        col = MagicMock()
        col.key = "data"
        compiler = MagicMock()
        compiler.dialect.name = "oracle"
        compiler.process.return_value = '"data"'
        m = JsonMatch(col, "key", "val")
        with pytest.raises(NotImplementedError, match="oracle"):
            _compile_default(m, compiler)


# ── _compile_sqlite / _compile_pg key validation defense ─────────────────────


class TestCompileKeyValidation:
    def _make_compiler(self, dialect_name="sqlite"):
        engine = create_mock_engine(f"{dialect_name}://", executor=lambda *a, **kw: None)
        stmt = select(1)
        return engine.dialect.statement_compiler(engine.dialect, stmt)

    def _make_element(self, key, value="val"):
        col = MagicMock()
        col.key = "data"
        return JsonMatch(col, key, value)

    def _make_bypassed_element(self, key, value="val"):
        """Create a JsonMatch bypassing __init__ to test compiler-level key defense."""
        col = MagicMock()
        col.key = "data"
        obj = object.__new__(JsonMatch)
        obj.column = col
        obj.key = key
        obj.value = value
        return obj

    def test_compile_sqlite_invalid_key_raises(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_bypassed_element("invalid key!")
        with pytest.raises(ValueError, match="Key escaped validation"):
            _compile_sqlite(element, compiler)

    def test_compile_pg_invalid_key_raises(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_bypassed_element("invalid key!")
        with pytest.raises(ValueError, match="Key escaped validation"):
            _compile_pg(element, compiler)

    def test_compile_sqlite_valid_key_produces_json_type(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("name")
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "json_extract" in result
        assert '"name"' in result

    def test_compile_pg_valid_key_produces_json_typeof(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("name")
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "->>" in result
        assert "'name'" in result

    def test_compile_sqlite_none_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("key", None)
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "'null'" in result

    def test_compile_pg_none_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("key", None)
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "'null'" in result

    def test_compile_sqlite_bool_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("active", True)
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "'true'" in result

    def test_compile_pg_bool_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("active", True)
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "boolean" in result

    def test_compile_sqlite_int_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("count", 42)
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "INTEGER" in result

    def test_compile_pg_int_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("count", 42)
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "CASE WHEN" in result
        assert "BIGINT" in result

    def test_compile_sqlite_float_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("score", 3.14)
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "REAL" in result

    def test_compile_pg_float_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("score", 3.14)
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "DOUBLE PRECISION" in result

    def test_compile_sqlite_string_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("name", "hello")
        result = _compile_sqlite(element, compiler)
        assert "json_type" in result
        assert "text" in result

    def test_compile_pg_string_value(self):
        compiler = self._make_compiler("sqlite")
        element = self._make_element("name", "hello")
        result = _compile_pg(element, compiler)
        assert "json_typeof" in result
        assert "string" in result
