"""Template engine — variable substitution for workflow step parameters.

Supports ``{{inputs.xxx}}`` and ``{{steps.xxx.output}}`` syntax.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"\{\{([^{}]+?)\}\}")

# P2-WF-04: Maximum expression length to prevent CPU pressure from
# arbitrarily long template expressions.
_MAX_EXPR_LENGTH = 1000

# Sentinel distinguishing "path not found" from a legitimate None value.
_MISSING = object()


def render_value(template: str, context: dict[str, Any]) -> Any:
    """Render a template string.

    If the entire string is a single ``{{expr}}``, return the raw value
    (preserving dict/list types).  Otherwise return a string with
    substitutions applied.

    Returns ``None`` for unresolvable full-string templates, or a
    ``{{expr}}`` placeholder for unresolvable partial templates,
    instead of raising KeyError/AttributeError.
    """
    if not isinstance(template, str):
        return template

    # Full-string template → preserve type
    if _PATH_RE.fullmatch(template.strip()):
        expr = template.strip()[2:-2].strip()
        val = _resolve_safe(expr, context)
        return None if val is _MISSING else val

    # Partial template → string substitution
    def _replace(m: re.Match) -> str:
        val = _resolve_safe(m.group(1).strip(), context)
        if val is _MISSING:
            return m.group(0)  # preserve placeholder for unresolvable refs
        return str(val)  # str(None) → "None" for legitimate None values

    return _PATH_RE.sub(_replace, template)


def _render_item(item: Any, context: dict[str, Any]) -> Any:
    """Render a single item in a parameter list, handling nested structures."""
    if isinstance(item, str):
        return render_value(item, context)
    if isinstance(item, dict):
        return render_params(item, context)
    if isinstance(item, list):
        return [_render_item(i, context) for i in item]
    return item


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
            result[k] = [_render_item(i, context) for i in v]
        else:
            result[k] = v
    return result


def _resolve(expr: str, context: dict[str, Any]) -> Any:
    """Evaluate a dot-separated path against the context.

    ``"steps.a.output.field"`` → ``context["steps"]["a"]["output"]["field"]``

    Raises ``KeyError`` or ``AttributeError`` if the path cannot be resolved.
    """
    parts = expr.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"Template expression '{expr}' failed: '{part}' not found in dict")
            current = current[part]
        else:
            # Block access to dunder attributes (e.g. __class__, __globals__) to prevent information leakage
            if part.startswith("__"):
                raise AttributeError(f"Template expression '{expr}' failed: access to private attribute '{part}' is forbidden")
            try:
                current = getattr(current, part)
            except AttributeError:
                raise AttributeError(f"Template expression '{expr}' failed: '{part}' not found on {type(current).__name__}")
    return current


def _resolve_safe(expr: str, context: dict[str, Any]) -> Any:
    """Like ``_resolve`` but returns ``_MISSING`` instead of raising on missing paths.

    Logs a warning when resolution fails so operators can diagnose broken
    template references without crashing the workflow.

    Returns the actual resolved value (including ``None`` if the path exists
    but its value is ``None``), or ``_MISSING`` if the path cannot be resolved.
    """
    # P2-WF-04: Reject excessively long expressions
    if len(expr) > _MAX_EXPR_LENGTH:
        logger.warning("Template expression too long: %d chars (max %d)", len(expr), _MAX_EXPR_LENGTH)
        return _MISSING
    try:
        return _resolve(expr, context)
    except Exception as e:
        logger.warning("Template resolution failed for '{{%s}}': %s", expr, e)
        return _MISSING
