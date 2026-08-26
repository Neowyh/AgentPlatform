"""Schema-gate fixtures for the fault-zeroing intermediate tree schema.

The workflow ``schemas`` gate (compiler ``_check_write_schemas``) validates
agent-written files with ``Draft202012Validator``. These tests pin the
contract of ``fault_tree_structure.schema.json``: structural fields are
mandatory, assessment fields stay nullable because they are only filled by
``evidence_assessment``.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO_ROOT / "resources" / "skills" / "fault-zeroing" / "templates" / "fault_tree_structure.schema.json"


@pytest.fixture()
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _tree(**overrides):
    tree = {
        "top_event": "设备无法启动",
        "intermediate_events": [
            {
                "id": "IE-001",
                "name": "供电失效",
                "description": "主供电通路失效",
                "parent_ids": ["TOP"],
                "logic": "OR",
            }
        ],
        "bottom_events": [
            {
                "id": "BE-001",
                "name": "保险丝熔断",
                "description": "主回路保险丝熔断",
                "parent_ids": ["IE-001"],
                # Assessment fields left null by deductive_tree.
                "evidence_ids": None,
                "probability": None,
                "probability_basis": None,
                "confidence": None,
                "status": None,
                "verification_suggestion": None,
            }
        ],
        "logic": [{"type": "OR", "parent": "IE-001", "children": ["BE-001"]}],
    }
    tree.update(overrides)
    return tree


def test_deductive_tree_output_with_null_assessment_fields_passes(validator):
    errors = list(validator.iter_errors(_tree()))
    assert errors == []


def test_missing_top_level_key_fails(validator):
    tree = _tree()
    del tree["logic"]
    assert any("logic" in error.message for error in validator.iter_errors(tree))


def test_empty_top_event_fails(validator):
    assert list(validator.iter_errors(_tree(top_event=""))) != []


def test_bottom_event_without_parent_ids_fails(validator):
    tree = _tree()
    del tree["bottom_events"][0]["parent_ids"]
    assert list(validator.iter_errors(tree)) != []


def test_assessment_fields_are_optional(validator):
    tree = _tree()
    for key in ("evidence_ids", "probability", "probability_basis", "confidence", "status", "verification_suggestion"):
        del tree["bottom_events"][0][key]
    assert list(validator.iter_errors(tree)) == []


def test_schema_is_looser_than_final_fault_tree_schema():
    """The intermediate schema must accept status=None, unlike the final one."""
    final_schema = json.loads((SCHEMA_PATH.parent / "fault_tree.schema.json").read_text(encoding="utf-8"))
    assert "null" not in str(final_schema["$defs"]["conclusion_status"]["enum"])
    structure_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert structure_schema["$defs"]["bottom_event_structure"]["properties"]["status"]["type"] == ["string", "null"]
