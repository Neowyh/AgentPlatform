"""Tests for ideer.reflection.resolvers covering uncovered lines."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ideer.reflection.resolvers import (
    _build_missing_dependency_hint,
    resolve_class,
    resolve_variable,
)

# ---------------------------------------------------------------------------
# _build_missing_dependency_hint — line 20
# ---------------------------------------------------------------------------


class TestBuildMissingDependencyHint:
    """Cover _build_missing_dependency_hint branches."""

    def test_line_20_missing_module_from_err_name_not_in_hints(self):
        """Line 20: module_root is NOT in MODULE_TO_PACKAGE_HINTS, missing_module
        comes from err.name and is also NOT in MODULE_TO_PACKAGE_HINTS, so the
        default ``replace('_', '-')`` path is taken."""
        module_path = "some_unknown_pkg.submodule"
        err = ImportError("No module named 'google.auth'")
        err.name = "google.auth"

        hint = _build_missing_dependency_hint(module_path, err)

        # module_root = "some_unknown_pkg" — not in MODULE_TO_PACKAGE_HINTS
        # missing_module = "google.auth" (from err.name) — not in MODULE_TO_PACKAGE_HINTS
        # Falls through to: "google.auth".replace("_", "-") == "google.auth"
        assert "google.auth" in hint
        assert "uv add google.auth" in hint

    def test_line_20_missing_module_from_err_name_in_hints(self):
        """Line 20: module_root is NOT in hints, but missing_module (from
        err.name) IS in MODULE_TO_PACKAGE_HINTS, so the hint uses the known
        package name."""
        module_path = "transitive_pkg.submodule"
        err = ImportError("cannot import name 'xyz'")
        err.name = "langchain_anthropic"  # this IS in MODULE_TO_PACKAGE_HINTS

        hint = _build_missing_dependency_hint(module_path, err)

        # module_root = "transitive_pkg" — not in hints
        # missing_module = "langchain_anthropic" — IS in hints
        assert "langchain-anthropic" in hint
        assert "uv add langchain-anthropic" in hint

    def test_line_18_root_in_hints_skips_line_20(self):
        """When module_root IS in MODULE_TO_PACKAGE_HINTS, line 18 sets the
        package_name and the ``if`` block (line 19-20) is NOT entered."""
        module_path = "langchain_openai.submodule"
        err = ImportError("No module named 'openai'")
        err.name = "openai"

        hint = _build_missing_dependency_hint(module_path, err)

        # module_root = "langchain_openai" — in hints → package_name set on line 18
        assert "langchain-openai" in hint

    def test_fallback_to_module_root_when_err_has_no_name(self):
        """When err.name is None, missing_module falls back to module_root."""
        module_path = "my_custom_lib.submodule"
        err = ImportError("something broke")
        # No .name attribute → getattr returns None → missing_module = module_root

        hint = _build_missing_dependency_hint(module_path, err)

        assert "my-custom-lib" in hint


# ---------------------------------------------------------------------------
# resolve_variable — line 57 (non-ModuleNotFoundError ImportError)
# ---------------------------------------------------------------------------


class TestResolveVariableLine57:
    """Cover the non-ModuleNotFoundError ImportError branch."""

    @patch("ideer.reflection.resolvers.import_module")
    def test_plain_importerror_preserved(self, mock_import):
        """Line 57: When import_module raises a plain ImportError (not
        ModuleNotFoundError) and err.name != module_root, the original error
        message is preserved."""
        err = ImportError("cannot import name 'Bar' from 'foo.baz'")
        err.name = "foo.baz"
        mock_import.side_effect = err

        with pytest.raises(ImportError, match="Error importing module foo.baz"):
            resolve_variable("foo.baz:Bar")

    @patch("ideer.reflection.resolvers.import_module")
    def test_importerror_without_name_attr(self, mock_import):
        """Line 57: ImportError without a .name attribute, where the error is
        not a ModuleNotFoundError."""
        # Create an ImportError subclass that is NOT ModuleNotFoundError
        err = ImportError("some syntax-related import failure")
        # Ensure it's not a ModuleNotFoundError
        assert not isinstance(err, ModuleNotFoundError)
        # err.name defaults to None via getattr, and None != module_root
        mock_import.side_effect = err

        with pytest.raises(ImportError, match="Error importing module some_pkg.mod"):
            resolve_variable("some_pkg.mod:Thing")

    @patch("ideer.reflection.resolvers.import_module")
    def test_module_not_found_error_reaches_hint(self, mock_import):
        """ModuleNotFoundError should go through the hint path (line 53-55),
        NOT line 57."""
        mock_import.side_effect = ModuleNotFoundError("No module named 'missing'")

        with pytest.raises(ImportError, match="Missing dependency"):
            resolve_variable("missing:Thing")


# ---------------------------------------------------------------------------
# resolve_variable — lines 61-62 (AttributeError)
# ---------------------------------------------------------------------------


class TestResolveVariableAttributeError:
    """Cover the AttributeError branch when the attribute doesn't exist."""

    def test_attribute_not_found(self):
        """Lines 61-62: getattr raises AttributeError when the module doesn't
        define the requested attribute."""
        # 'os' is a guaranteed importable module; 'nonexistent_thing_xyz' won't exist
        with pytest.raises(ImportError, match="does not define a nonexistent_thing_xyz"):
            resolve_variable("os:nonexistent_thing_xyz")


# ---------------------------------------------------------------------------
# resolve_variable — lines 67-68 (tuple expected_type)
# ---------------------------------------------------------------------------


class TestResolveVariableTupleType:
    """Cover the tuple-type validation branch."""

    def test_tuple_type_mismatch(self):
        """Lines 67-68: expected_type is a tuple of types and the variable
        doesn't match any of them."""
        with pytest.raises(ValueError, match="is not an instance of"):
            resolve_variable(
                "builtins:int",
                expected_type=(str, float),
            )

    def test_tuple_type_match(self):
        """When expected_type is a tuple and the variable matches one, it
        succeeds (not an error path, but confirms the happy path)."""
        # resolve_variable("builtins:max") returns the max function (builtin_function_or_method)
        # which is an instance of (int, str) won't work. Use a value that is an instance.
        # Use builtins:True which is an instance of int (bool is subclass of int).
        result = resolve_variable("builtins:True", expected_type=(int, str))
        assert result is True

    def test_tuple_type_error_message_lists_all_names(self):
        """Lines 67-68: The error message should join type names with ' or '."""
        with pytest.raises(ValueError, match="str or float"):
            resolve_variable(
                "builtins:int",
                expected_type=(str, float),
            )

    def test_single_type_mismatch_uses_name(self):
        """When expected_type is a single type (not a tuple), __name__ is used."""
        with pytest.raises(ValueError, match="is not an instance of str"):
            resolve_variable("builtins:int", expected_type=str)


# ---------------------------------------------------------------------------
# resolve_class — line 90 (model_class is not a type)
# ---------------------------------------------------------------------------


class TestResolveClassNotAType:
    """Cover the 'not a type' branch in resolve_class."""

    @patch("ideer.reflection.resolvers.resolve_variable")
    def test_line_90_resolved_value_is_not_type(self, mock_resolve):
        """Line 90: When resolve_variable returns a non-type value despite
        expected_type=type, resolve_class raises ValueError."""
        # Bypass resolve_variable's internal type check by mocking it directly
        mock_resolve.return_value = "not a type"

        with pytest.raises(ValueError, match="is not a valid class"):
            resolve_class("some.module:SomeThing")


# ---------------------------------------------------------------------------
# resolve_class — line 93 (not subclass of base_class)
# ---------------------------------------------------------------------------


class TestResolveClassNotSubclass:
    """Cover the 'not a subclass' branch in resolve_class."""

    @patch("ideer.reflection.resolvers.resolve_variable")
    def test_line_93_not_subclass_of_base(self, mock_resolve):
        """Line 93: When the resolved class is a type but not a subclass of
        base_class, resolve_class raises ValueError."""
        # int IS a type, but it's NOT a subclass of list
        mock_resolve.return_value = int

        with pytest.raises(ValueError, match="is not a subclass of list"):
            resolve_class("builtins:int", base_class=list)

    @patch("ideer.reflection.resolvers.resolve_variable")
    def test_subclass_check_passes(self, mock_resolve):
        """Happy path: the resolved class IS a subclass of base_class."""
        mock_resolve.return_value = bool  # bool is a subclass of int

        result = resolve_class("builtins:bool", base_class=int)
        assert result is bool

    @patch("ideer.reflection.resolvers.resolve_variable")
    def test_no_base_class_check(self, mock_resolve):
        """When base_class is None, the subclass check is skipped."""
        mock_resolve.return_value = int

        result = resolve_class("builtins:int", base_class=None)
        assert result is int
