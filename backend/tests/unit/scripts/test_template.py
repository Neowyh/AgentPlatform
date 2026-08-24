"""Tests for the workflow template engine (render_value, render_params, _resolve)."""

from ideer.workflows.template import render_params, render_value

# ── render_value ────────────────────────────────────────────────────


def test_full_template_returns_raw_dict():
    ctx = {"inputs": {"data": {"key": "value"}}}
    result = render_value("{{inputs.data}}", ctx)
    assert result == {"key": "value"}
    assert isinstance(result, dict)


def test_full_template_returns_raw_list():
    ctx = {"inputs": {"items": [1, 2, 3]}}
    result = render_value("{{inputs.items}}", ctx)
    assert result == [1, 2, 3]
    assert isinstance(result, list)


def test_full_template_returns_raw_int():
    ctx = {"inputs": {"count": 42}}
    result = render_value("{{inputs.count}}", ctx)
    assert result == 42
    assert isinstance(result, int)


def test_partial_template_returns_string():
    ctx = {"inputs": {"name": "Alice"}}
    result = render_value("Hello {{inputs.name}}", ctx)
    assert result == "Hello Alice"
    assert isinstance(result, str)


def test_multiple_substitutions():
    ctx = {"inputs": {"a": "foo", "b": "bar"}}
    result = render_value("{{inputs.a}} and {{inputs.b}}", ctx)
    assert result == "foo and bar"


def test_non_string_int_returns_as_is():
    assert render_value(42, {}) == 42


def test_non_string_dict_returns_as_is():
    d = {"key": "val"}
    assert render_value(d, {}) is d


def test_non_string_list_returns_as_is():
    lst = [1, 2]
    assert render_value(lst, {}) is lst


def test_nested_path():
    ctx = {"steps": {"step1": {"output": {"field": "deep_value"}}}}
    result = render_value("{{steps.step1.output.field}}", ctx)
    assert result == "deep_value"


def test_nested_path_partial():
    ctx = {"steps": {"step1": {"output": {"name": "Bob"}}}}
    result = render_value("Result: {{steps.step1.output.name}}", ctx)
    assert result == "Result: Bob"


# ── render_params ───────────────────────────────────────────────────


def test_simple_dict():
    ctx = {"inputs": {"name": "Alice"}}
    params = {"greeting": "Hello {{inputs.name}}"}
    assert render_params(params, ctx) == {"greeting": "Hello Alice"}


def test_nested_dict():
    ctx = {"inputs": {"x": 10}}
    params = {"outer": {"inner": "{{inputs.x}}"}}
    result = render_params(params, ctx)
    assert result == {"outer": {"inner": 10}}


def test_list_of_strings():
    ctx = {"inputs": {"a": "one", "b": "two"}}
    params = {"items": ["{{inputs.a}}", "{{inputs.b}}", "plain"]}
    result = render_params(params, ctx)
    assert result == {"items": ["one", "two", "plain"]}


def test_none_returns_empty_dict():
    assert render_params(None, {"inputs": {}}) == {}


def test_mixed_types():
    ctx = {"inputs": {"name": "Alice", "count": 5}}
    params = {
        "label": "Hello {{inputs.name}}",
        "num": 99,
        "nested": {"val": "{{inputs.count}}"},
        "flag": True,
    }
    result = render_params(params, ctx)
    assert result == {
        "label": "Hello Alice",
        "num": 99,
        "nested": {"val": 5},
        "flag": True,
    }


# ── _resolve (via render_value) ────────────────────────────────────


def test_simple_path():
    ctx = {"inputs": {"name": "Alice"}}
    assert render_value("{{inputs.name}}", ctx) == "Alice"


def test_deep_path():
    ctx = {"steps": {"step1": {"output": {"field": "deep"}}}}
    assert render_value("{{steps.step1.output.field}}", ctx) == "deep"


def test_missing_key_returns_none():
    ctx = {"inputs": {}}
    result = render_value("{{inputs.missing}}", ctx)
    assert result is None
