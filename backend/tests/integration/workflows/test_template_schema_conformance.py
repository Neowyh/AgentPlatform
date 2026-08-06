"""Bundled JSON templates and reference outputs must stay in sync with their schemas.

The fault-tree schema splits the ``status`` enum into ``conclusion_status``
(bottom events / root causes) and ``verification_status`` (verification plan
items), but at one point the sample template and the eval-case reference output
were not updated, so any agent following them reproduced the same schema
violation.  These tests guard every ``templates/*.json`` against its sibling
``*.schema.json`` plus the eval-case reference tree, so drift fails the suite
instead of the runtime schema gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = REPO_ROOT / "skills" / "custom" / "fault-zeroing" / "templates"
EVAL_CASE_TREE = REPO_ROOT / "docs" / "zero_agent_eval_cases" / "outputs" / "fault_tree.json"


def _violations(instance: object, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    return [f"{(error.absolute_path and '.'.join(str(p) for p in error.absolute_path)) or '$'}: {error.message}" for error in validator.iter_errors(instance)]


def _template_pairs() -> list[tuple[Path, Path]]:
    return [(path, path.with_suffix(".schema.json")) for path in sorted(TEMPLATES_DIR.glob("*.json")) if path.with_suffix(".schema.json").is_file()]


def test_bundled_json_templates_conform_to_their_schemas() -> None:
    failures: list[str] = []
    for template, schema in _template_pairs():
        errors = _violations(
            json.loads(template.read_text(encoding="utf-8")),
            json.loads(schema.read_text(encoding="utf-8")),
        )
        if errors:
            failures.append(f"{template.relative_to(REPO_ROOT)} violates {schema.relative_to(REPO_ROOT)}:\n" + "\n".join(f"  - {error}" for error in errors))
    assert not failures, "\n".join(failures)


def test_eval_case_reference_tree_conforms_to_fault_tree_schema() -> None:
    schema = TEMPLATES_DIR / "fault_tree.schema.json"
    errors = _violations(
        json.loads(EVAL_CASE_TREE.read_text(encoding="utf-8")),
        json.loads(schema.read_text(encoding="utf-8")),
    )
    assert not errors, f"{EVAL_CASE_TREE.relative_to(REPO_ROOT)} violates {schema.relative_to(REPO_ROOT)}:\n" + "\n".join(f"  - {error}" for error in errors)
