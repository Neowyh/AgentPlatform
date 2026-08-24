"""Guard against reintroducing the dual module identity ``packages.harness.*``.

The canonical import path is the installed top-level package ``ideer.*``
(hatchling wheel: ``packages = ["ideer"]``). ``backend/tests/conftest.py``
puts ``backend/`` on ``sys.path``, which makes ``packages.harness.ideer.*``
importable as a *second, independent* module identity via implicit namespace
packages. Patching one identity does not affect the other, which caused
silent test failures (see dev-log findings 2026-08-24). All test code was
migrated to ``ideer.*``; this test keeps it that way.
"""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
GUARD_MARKER = "packages.harness"


def test_no_source_file_references_packages_harness_namespace() -> None:
    offenders: list[str] = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if path == Path(__file__):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - non-source files
            continue
        if GUARD_MARKER in text:
            offenders.append(str(path.relative_to(BACKEND_ROOT)))

    assert offenders == [], (
        "Found references to the 'packages.harness' namespace. "
        "Import and patch targets must use the canonical top-level package "
        "'ideer.*' instead; 'packages.harness.ideer.*' resolves to an "
        f"independent second module instance. Offenders: {offenders}"
    )
