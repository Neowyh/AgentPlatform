"""Supplementary tests for the workflow template engine.

Covers edge cases not in test_template.py:
- Unresolvable references return placeholder (partial) or None (full)
- Dunder attribute blocking in _resolve
- List of dicts in render_params
- Non-string, non-dict, non-list values in render_params
- Whitespace in template expressions
"""

from __future__ import annotations

from packages.harness.ideer.workflows.template import render_params, render_value

# ── Unresolvable references ─────────────────────────────────────────


class TestUnresolvableReferences:
    """Tests for graceful handling of missing template variables."""

    def test_full_template_missing_key_returns_none(self):
        """Full-string template with missing key returns None."""
        result = render_value("{{inputs.missing}}", {"inputs": {}})
        assert result is None

    def test_partial_template_missing_key_preserves_placeholder(self):
        """Partial template with missing key keeps the placeholder string."""
        result = render_value("Hello {{inputs.missing}}", {"inputs": {}})
        assert result == "Hello {{inputs.missing}}"

    def test_full_template_deep_missing_returns_none(self):
        result = render_value("{{steps.s1.output.field}}", {"steps": {}})
        assert result is None

    def test_partial_template_deep_missing_preserves_placeholder(self):
        result = render_value("Result: {{steps.s1.output.field}}", {"steps": {}})
        assert result == "Result: {{steps.s1.output.field}}"

    def test_multiple_unresolvable_partial(self):
        """Multiple missing keys in partial template all preserved."""
        result = render_value("{{a.x}} and {{b.y}}", {})
        assert result == "{{a.x}} and {{b.y}}"

    def test_mix_resolved_and_unresolved(self):
        ctx = {"inputs": {"name": "Alice"}}
        result = render_value("{{inputs.name}} {{inputs.missing}}", ctx)
        assert result == "Alice {{inputs.missing}}"


# ── Dunder attribute blocking ────────────────────────────────────────


class TestDunderBlocking:
    """Tests that dunder attributes are blocked in template expressions."""

    def test_dunder_class_blocked(self):
        """Accessing __class__ should return placeholder (not leak type info)."""
        result = render_value("{{inputs.__class__}}", {"inputs": {}})
        # _resolve_safe catches AttributeError, returns _MISSING → None for full template
        assert result is None

    def test_dunder_globals_blocked(self):
        result = render_value("{{inputs.__globals__}}", {"inputs": {}})
        assert result is None

    def test_dunder_in_partial_preserves_placeholder(self):
        result = render_value("{{inputs.__class__}}", {"inputs": {}})
        assert result is None  # full-string template returns None


# ── render_params edge cases ─────────────────────────────────────────


class TestRenderParamsEdgeCases:
    """Additional render_params scenarios."""

    def test_list_of_dicts(self):
        """List containing dicts should have their params rendered."""
        ctx = {"inputs": {"url": "https://example.com"}}
        params = {
            "items": [
                {"link": "{{inputs.url}}"},
                {"link": "{{inputs.url}}"},
            ]
        }
        result = render_params(params, ctx)
        assert result["items"][0]["link"] == "https://example.com"
        assert result["items"][1]["link"] == "https://example.com"

    def test_list_with_mixed_types(self):
        """List with strings, dicts, ints, and bools."""
        ctx = {"inputs": {"name": "test"}}
        params = {
            "data": [
                "{{inputs.name}}",
                {"key": "{{inputs.name}}"},
                42,
                True,
                None,
            ]
        }
        result = render_params(params, ctx)
        assert result["data"][0] == "test"
        assert result["data"][1] == {"key": "test"}
        assert result["data"][2] == 42
        assert result["data"][3] is True
        assert result["data"][4] is None

    def test_none_values_preserved(self):
        """None values in params dict are preserved as-is."""
        result = render_params({"key": None}, {})
        assert result["key"] is None

    def test_boolean_values_preserved(self):
        result = render_params({"flag": True, "other": False}, {})
        assert result["flag"] is True
        assert result["other"] is False

    def test_integer_values_preserved(self):
        result = render_params({"count": 0, "size": 100}, {})
        assert result["count"] == 0
        assert result["size"] == 100

    def test_empty_dict(self):
        assert render_params({}, {"inputs": {}}) == {}

    def test_deeply_nested_dict(self):
        ctx = {"inputs": {"val": "deep"}}
        params = {"a": {"b": {"c": {"d": "{{inputs.val}}"}}}}
        result = render_params(params, ctx)
        assert result["a"]["b"]["c"]["d"] == "deep"


# ── render_value with whitespace ─────────────────────────────────────


class TestWhitespaceInExpressions:
    """Tests for whitespace handling in template expressions."""

    def test_spaces_around_expression(self):
        ctx = {"inputs": {"x": 42}}
        result = render_value("{{ inputs.x }}", ctx)
        assert result == 42

    def test_extra_whitespace_in_path(self):
        ctx = {"inputs": {"x": "ok"}}
        result = render_value("{{  inputs.x  }}", ctx)
        assert result == "ok"

    def test_tabs_in_expression(self):
        ctx = {"inputs": {"x": "tab"}}
        result = render_value("{{\tinputs.x\t}}", ctx)
        assert result == "tab"


# ── render_value with None context values ────────────────────────────


class TestNoneContextValues:
    """Tests when context values are legitimately None."""

    def test_full_template_returns_none_value(self):
        """When the resolved value IS None (key exists, value is None)."""
        ctx = {"inputs": {"x": None}}
        result = render_value("{{inputs.x}}", ctx)
        assert result is None

    def test_partial_template_none_value_becomes_string(self):
        """str(None) = 'None' in partial template."""
        ctx = {"inputs": {"x": None}}
        result = render_value("Value: {{inputs.x}}", ctx)
        assert result == "Value: None"
