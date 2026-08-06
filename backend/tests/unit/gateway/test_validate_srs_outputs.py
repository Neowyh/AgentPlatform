import ast
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "validate_srs_outputs.py"
SPEC = importlib.util.spec_from_file_location("validate_srs_outputs", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


@pytest.fixture(autouse=True)
def _reset_failures() -> None:
    validator.CHECK_FAILURES.clear()
    yield
    validator.CHECK_FAILURES.clear()


def make_docx(path: Path, texts: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in texts)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


def make_data(**overrides) -> dict:
    data = {
        "stage": "complete",
        "functions": [
            {"id": "F-5.1", "name": "登录与权限管理"},
            {"id": "F-5.2", "name": "检测项目管理"},
        ],
        "requirements": [
            {
                "id": "F-5.1-1",
                "status": "accepted",
                "source_function": "F-5.1",
                "source_chapter": "5.1",
                "description": "软件启动后应显示登录界面",
            },
            {
                "id": "F-5.2-1",
                "status": "modified",
                "source_function": "F-5.2",
                "source_chapter": "5.2",
                "description": "软件应支持检测项目的创建",
            },
        ],
        "gaps": [],
        "declared_gaps": [],
    }
    data.update(overrides)
    return data


def make_outputs_dir(tmp_path: Path, data: dict, *, rejected_in_docx: list[str] | None = None) -> Path:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "progress.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    srs_texts = [f"{r['id']} {r.get('description', '')}" for r in data["requirements"] if r["status"] != "rejected"]
    srs_texts += [rid for rid in (rejected_in_docx or [])]
    make_docx(outputs / "srs_document.docx", srs_texts)
    make_docx(outputs / "traceability-matrix.docx", ["matrix"])
    return outputs


def test_validator_uses_only_standard_library_imports() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert "yaml" not in imported_modules
    assert "ideer" not in imported_modules
    assert imported_modules <= {"__future__", "argparse", "json", "re", "sys", "zipfile", "pathlib"}


# --- load_progress ---------------------------------------------------------


def test_load_progress_missing_file_reports_failure(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    data = validator.load_progress(outputs)

    assert data == {}
    assert validator.CHECK_FAILURES == [f"missing progress.json under {outputs}"]


def test_load_progress_invalid_json_reports_failure(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "progress.json").write_text("{not json", encoding="utf-8")

    data = validator.load_progress(outputs)

    assert data == {}
    assert validator.CHECK_FAILURES and "not valid JSON" in validator.CHECK_FAILURES[0]


def test_load_progress_non_object_reports_failure(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "progress.json").write_text("[1, 2]", encoding="utf-8")

    data = validator.load_progress(outputs)

    assert data == {}
    assert validator.CHECK_FAILURES == ["progress.json top-level must be an object"]


# --- check_id_uniqueness ---------------------------------------------------


def test_check_id_uniqueness_accepts_valid_ids() -> None:
    requirements = [
        {"id": "F-5.1-1"},
        {"id": "F-5.2-1"},
        {"id": "F-6-1"},
    ]

    validator.check_id_uniqueness(requirements)

    assert validator.CHECK_FAILURES == []


def test_check_id_uniqueness_reports_duplicates() -> None:
    requirements = [{"id": "F-5.1-1"}, {"id": "F-5.1-1"}]

    validator.check_id_uniqueness(requirements)

    assert validator.CHECK_FAILURES == ["duplicate requirement IDs: ['F-5.1-1']"]


def test_check_id_uniqueness_reports_bad_format_and_missing_id() -> None:
    requirements = [{"id": "5.1-1"}, {"id": "F-5.1"}, {}]

    validator.check_id_uniqueness(requirements)

    assert len(validator.CHECK_FAILURES) == 3
    assert any("does not match F-<chapter>-<seq> format" in msg for msg in validator.CHECK_FAILURES)
    assert any("missing its ID" in msg for msg in validator.CHECK_FAILURES)


# --- check_traceability ----------------------------------------------------


def test_check_traceability_full_coverage_passes() -> None:
    validator.check_traceability(make_data())

    assert validator.CHECK_FAILURES == []


def test_check_traceability_accepts_uppercase_id_key() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}],
        requirements=[{"ID": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"}],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == []


def test_check_traceability_missing_source_reports_forward_break() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}],
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": None, "source_chapter": "5.1"}],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == [
        "accepted requirement F-5.1-1 has no source function item (forward trace broken)",
        "function items with no accepted requirement (undeclared gaps): ['F-5.1']",
    ]


def test_check_traceability_missing_chapter_reports_reverse_break() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}],
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": None}],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == ["accepted requirement F-5.1-1 has no task-book chapter source (reverse trace broken)"]


def test_check_traceability_unknown_function_reports() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}],
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-9.9", "source_chapter": "5.1"}],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == [
        "accepted requirement F-5.1-1 references unknown function item 'F-9.9'",
        "function items with no accepted requirement (undeclared gaps): ['F-5.1']",
    ]


def test_check_traceability_undeclared_gap_reports() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}, {"id": "F-5.2", "name": "检测项目管理"}, {"id": "F-6.1", "name": "交付文档"}],
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.2-1", "status": "accepted", "source_function": "F-5.2", "source_chapter": "5.2"},
        ],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == ["function items with no accepted requirement (undeclared gaps): ['F-6.1']"]


def test_check_traceability_declared_gap_is_exempt() -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}, {"id": "F-6.1", "name": "交付文档"}],
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"}],
        gaps=[{"function_id": "F-6.1", "reason": "交付物不构成运行需求"}],
        declared_gaps=["F-6.1"],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == []


def test_check_traceability_rejected_requirement_not_required_for_coverage() -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.2-1", "status": "rejected", "source_function": "F-5.2", "source_chapter": "5.2"},
        ],
    )

    validator.check_traceability(data)

    assert validator.CHECK_FAILURES == ["function items with no accepted requirement (undeclared gaps): ['F-5.2']"]


# --- check_artifacts -------------------------------------------------------


def test_check_artifacts_missing_docx_reports(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    make_docx(outputs / "srs_document.docx", ["ok"])
    data = make_data()

    validator.check_artifacts(outputs, data)

    assert validator.CHECK_FAILURES == ["missing traceability-matrix.docx"]


def test_check_artifacts_empty_docx_reports(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "srs_document.docx").write_bytes(b"")
    (outputs / "traceability-matrix.docx").write_bytes(b"")
    data = make_data()

    validator.check_artifacts(outputs, data)

    assert validator.CHECK_FAILURES == ["srs_document.docx is empty", "traceability-matrix.docx is empty"]


def test_check_artifacts_rejected_id_leak_reports(tmp_path: Path) -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.1-2", "status": "rejected", "source_function": "F-5.1", "source_chapter": "5.1"},
        ],
    )
    outputs = make_outputs_dir(tmp_path, data, rejected_in_docx=["F-5.1-2"])

    validator.check_artifacts(outputs, data)

    assert validator.CHECK_FAILURES == ["rejected requirement IDs appear in srs_document.docx: ['F-5.1-2']"]


def test_check_artifacts_rejected_id_absent_passes(tmp_path: Path) -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.1-2", "status": "rejected", "source_function": "F-5.1", "source_chapter": "5.1"},
        ],
    )
    outputs = make_outputs_dir(tmp_path, data)

    validator.check_artifacts(outputs, data)

    assert validator.CHECK_FAILURES == []


# --- main ------------------------------------------------------------------


def test_main_all_checks_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    outputs = make_outputs_dir(tmp_path, make_data())
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 0

    assert "ALL CHECKS PASSED" in capsys.readouterr().out


def test_main_failure_returns_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = make_data(requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"}])
    outputs = make_outputs_dir(tmp_path, data)
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "FAILED with the following issues" in captured
    assert "F-5.2" in captured


def test_main_outputs_dir_missing_returns_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(missing)])

    assert validator.main() == 1

    assert "outputs directory not found" in capsys.readouterr().out
