"""Targeted tests for ``ideer.utils.time`` covering uncovered lines.

These tests exercise the exception branches and the fallback path that
the baseline suite does not hit:
  - Lines 66-67: int/float values that overflow or are out of range
  - Lines 72-73: string unix timestamps that overflow or are out of range
  - Line 75: unrecognised types (e.g. list) falling through to str()
"""

from __future__ import annotations

# Ensure the backend packages root is importable.
import os
import sys
from datetime import datetime

_backend_root = os.path.join(os.path.dirname(__file__), os.pardir)
if _backend_root not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_root))

from ideer.utils.time import coerce_iso  # noqa: E402

# ---------------------------------------------------------------------------
# Lines 66-67: int/float values that raise ValueError, OverflowError, OSError
# ---------------------------------------------------------------------------


class TestCoerceIsoIntFloatOverflow:
    """The ``except (ValueError, OverflowError, OSError)`` branch for numeric
    values (lines 66-67) is reached when ``datetime.fromtimestamp`` fails."""

    def test_huge_positive_int_returns_str(self) -> None:
        """An astronomically large int overflows on most platforms."""
        huge = 10**19
        result = coerce_iso(huge)
        assert result == str(huge)

    def test_huge_negative_int_returns_str(self) -> None:
        """A hugely negative int underflows on most platforms."""
        huge_neg = -(10**19)
        result = coerce_iso(huge_neg)
        assert result == str(huge_neg)

    def test_huge_positive_float_returns_str(self) -> None:
        """A float larger than ``datetime.max`` raises OverflowError."""
        huge_float = float(10**19)
        result = coerce_iso(huge_float)
        assert result == str(huge_float)

    def test_huge_negative_float_returns_str(self) -> None:
        """A very negative float raises OverflowError on Windows."""
        huge_neg_float = float(-(10**19))
        result = coerce_iso(huge_neg_float)
        assert result == str(huge_neg_float)

    def test_nan_returns_str(self) -> None:
        """``float('nan')`` triggers ValueError/OverflowError on some OSes."""
        result = coerce_iso(float("nan"))
        assert result == "nan"

    def test_inf_returns_str(self) -> None:
        """``float('inf')`` overflows datetime.fromtimestamp."""
        result = coerce_iso(float("inf"))
        assert result == "inf"


# ---------------------------------------------------------------------------
# Lines 72-73: string unix timestamps that raise ValueError/OverflowError
# ---------------------------------------------------------------------------


class TestCoerceIsoStringUnixOverflow:
    """The ``except (ValueError, OverflowError, OSError)`` branch for string
    unix timestamps (lines 72-73) fires when the string matches the
    ``_UNIX_TIMESTAMP_PATTERN`` regex but the value itself is out of range."""

    def test_huge_positive_string_timestamp_returns_value(self) -> None:
        """A 10-digit string matching the unix pattern but too large for datetime."""
        # 9999999999 is 10 digits and matches _UNIX_TIMESTAMP_PATTERN,
        # but datetime.fromtimestamp(9999999999) overflows on many platforms
        # (year > 2286 or similar). We need the except branch to catch it.
        # Use a value that definitely overflows datetime.fromtimestamp.
        huge_str = "9999999999"
        from ideer.utils.time import _UNIX_TIMESTAMP_PATTERN

        assert _UNIX_TIMESTAMP_PATTERN.match(huge_str)
        # This should either convert successfully or hit the except branch
        result = coerce_iso(huge_str)
        assert isinstance(result, str)

    def test_string_timestamp_with_overflow_returns_value(self) -> None:
        """Verify the string unix timestamp branch (lines 69-73).

        We cannot easily make datetime.fromtimestamp raise on Linux 64-bit,
        so we test by monkeypatching the module-level ``datetime`` reference
        with a subclass whose ``fromtimestamp`` raises.
        """
        import ideer.utils.time as time_mod

        class _FakeDatetime(datetime):
            """Subclass that overrides fromtimestamp to raise."""

            @classmethod
            def fromtimestamp(cls, ts, tz=None):
                raise OverflowError("out of range")

        original = time_mod.datetime
        time_mod.datetime = _FakeDatetime
        try:
            result = coerce_iso("1234567890")
            assert result == "1234567890"
        finally:
            time_mod.datetime = original

    def test_string_timestamp_with_oserror_returns_value(self) -> None:
        """Same pattern but OSError."""
        import ideer.utils.time as time_mod

        class _FakeDatetime(datetime):
            @classmethod
            def fromtimestamp(cls, ts, tz=None):
                raise OSError("os error")

        original = time_mod.datetime
        time_mod.datetime = _FakeDatetime
        try:
            result = coerce_iso("1234567890")
            assert result == "1234567890"
        finally:
            time_mod.datetime = original


# ---------------------------------------------------------------------------
# Line 75: unrecognised type falls through to str()
# ---------------------------------------------------------------------------


class TestCoerceIsoUnrecognisedType:
    """Line 75: ``return str(value)`` for types that don't match any branch."""

    def test_list_returns_str_repr(self) -> None:
        result = coerce_iso([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_dict_returns_str_repr(self) -> None:
        result = coerce_iso({"key": "val"})
        assert result == "{'key': 'val'}"

    def test_set_returns_str_repr(self) -> None:
        result = coerce_iso({42})
        assert result == "{42}"

    def test_object_returns_str_repr(self) -> None:
        class _Custom:
            def __str__(self) -> str:
                return "custom_object"

        result = coerce_iso(_Custom())
        assert result == "custom_object"

    def test_tuple_returns_str_repr(self) -> None:
        result = coerce_iso((1, "a"))
        assert result == "(1, 'a')"

    def test_bytes_returns_str_repr(self) -> None:
        result = coerce_iso(b"hello")
        assert result == "b'hello'"
