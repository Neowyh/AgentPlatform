"""Property-based tests using Hypothesis.

Validates invariants and properties that should hold for all valid inputs.
"""

from hypothesis import given, settings
from hypothesis import strategies as st


class TestStringProperties:
    """String processing property tests."""

    @given(st.text(min_size=0, max_size=10000))
    @settings(max_examples=50)
    def test_string_length_invariant(self, text):
        """string length should always be non-negative."""
        assert len(text) >= 0

    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=30)
    def test_string_strip_idempotent(self, text):
        """stripping a string twice should give the same result."""
        assert text.strip().strip() == text.strip()

    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=30)
    def test_string_encode_decode_roundtrip(self, text):
        """encoding then decoding UTF-8 should return the original string."""
        assert text.encode("utf-8").decode("utf-8") == text


class TestDictProperties:
    """Dictionary processing property tests."""

    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(st.integers(), st.text(), st.booleans()),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_dict_merge_preserves_keys(self, d):
        """merging dict with empty dict should preserve all keys."""
        merged = {**{}, **d}
        assert set(merged.keys()) == set(d.keys())

    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(st.integers(), st.text()),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=30)
    def test_dict_update_preserves_values(self, d):
        """updating dict with itself should preserve all values."""
        original = dict(d)
        d.update(original)
        for key in original:
            assert d[key] == original[key]


class TestListProperties:
    """List processing property tests."""

    @given(st.lists(st.integers(), min_size=0, max_size=100))
    @settings(max_examples=30)
    def test_list_sort_idempotent(self, lst):
        """sorting a list twice should give the same result."""
        assert sorted(sorted(lst)) == sorted(lst)

    @given(st.lists(st.integers(), min_size=0, max_size=100))
    @settings(max_examples=30)
    def test_list_reverse_twice_identity(self, lst):
        """reversing a list twice should give the original list."""
        assert list(reversed(list(reversed(lst)))) == lst

    @given(st.lists(st.integers(), min_size=0, max_size=50))
    @settings(max_examples=30)
    def test_list_dedup_subset(self, lst):
        """deduplicated list should be a subset of original."""
        deduped = list(dict.fromkeys(lst))
        assert len(deduped) <= len(lst)
        for item in deduped:
            assert item in lst


class TestNumericProperties:
    """Numeric processing property tests."""

    @given(st.integers(min_value=-1000000, max_value=1000000))
    @settings(max_examples=50)
    def test_absolute_value_non_negative(self, n):
        """absolute value should always be non-negative."""
        assert abs(n) >= 0

    @given(st.integers(min_value=0, max_value=1000000))
    @settings(max_examples=50)
    def test_square_root_squared_close(self, n):
        """sqrt(n) ** 2 should be close to n."""
        import math

        result = math.isqrt(n) ** 2
        assert result <= n
        assert n - result <= 2 * math.isqrt(n) + 1


class TestPathProperties:
    """Path processing property tests."""

    @given(st.text(min_size=1, max_size=100).filter(lambda t: "/" not in t and ".." not in t))
    @settings(max_examples=30)
    def test_path_join_no_traversal(self, component):
        """joining path components should not create traversal."""
        import os

        base = "/tmp/test"
        result = os.path.join(base, component)
        assert result.startswith(base)

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=30)
    def test_path_normcase_idempotent(self, path):
        """normalizing path case twice should give the same result."""
        import os

        assert os.path.normcase(os.path.normcase(path)) == os.path.normcase(path)
