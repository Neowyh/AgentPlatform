"""Template engine — variable substitution for workflow step parameters.

Supports ``{{inputs.xxx}}`` and ``{{steps.xxx.output}}`` syntax.
"""

from __future__ import annotations

import re
from typing import Any

_PATH_RE = re.compile(r"\{\{([^{}]+?)\}\}")


def render_value(template: str, context: dict[str, Any]) -> Any:
    """Render a template string.

    If the entire string is a single ``{{expr}}``, return the raw value
    (preserving dict/list types).  Otherwise return a string with
    substitutions applied.
    """
    if not isinstance(template, str):
        return template

    # Full-string template → preserve type
    if _PATH_RE.fullmatch(template.strip()):
        expr = template.strip()[2:-2].strip()
        return _resolve(expr, context)

    # Partial template → string substitution
    def _replace(m: re.Match) -> str:
        val = _resolve(m.group(1).strip(), context)
        return str(val)

    return _PATH_RE.sub(_replace, template)


def render_params(params: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """Recursively render all template strings in a parameter dict."""
    if params is None:
        return {}
    result: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str):
            result[k] = render_value(v, context)
        elif isinstance(v, dict):
            result[k] = render_params(v, context)
        elif isinstance(v, list):
            result[k] = [render_value(i, context) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result


def _resolve(expr: str, context: dict[str, Any]) -> Any:
    """Evaluate a dot-separated path against the context.

    ``"steps.a.output.field"`` → ``context["steps"]["a"]["output"]["field"]``
    """
    parts = expr.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict):
            current = current[part]
        else:
            current = getattr(current, part)
    return current
