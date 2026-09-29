import ast
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "resources" / "skills" / "srs-writing" / "scripts" / "validate_srs_outputs.py"
SPEC = importlib.util.spec_from_file_location("validate_srs_outputs", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
# The skill source directory is packaged verbatim into bundled seeds, so
# loading the validator from it must not drop .pyc files there.
_dont_write_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    SPEC.loader.exec_module(validator)
finally:
    sys.dont_write_bytecode = _dont_write_bytecode


@pytest.fixture(autouse=True)
def _reset_failures() -> None:
    validator.CHECK_FAILURES.clear()
    validator.WARNINGS.clear()
    yield
    validator.CHECK_FAILURES.clear()
    validator.WARNINGS.clear()


def make_docx(path: Path, texts: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in texts)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


def make_docx_with_empty_document_xml(path: Path) -> None:
    """Valid zip container whose word/document.xml entry holds zero bytes of body text."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", "")


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


def make_outputs_dir(
    tmp_path: Path,
    data: dict,
    *,
    dir_name: str = "outputs",
    rejected_in_docx: list[str] | None = None,
    srs_texts: list[str] | None = None,
    matrix_texts: list[str] | None = None,
) -> Path:
    outputs = tmp_path / dir_name
    outputs.mkdir()
    (outputs / "progress.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    present_ids = [r["id"] for r in data["requirements"] if r["status"] != "rejected"]
    srs_final = srs_texts if srs_texts is not None else present_ids + [rid for rid in (rejected_in_docx or [])]
    matrix_final = matrix_texts if matrix_texts is not None else present_ids
    make_docx(outputs / "srs_document.docx", srs_final)
    make_docx(outputs / "traceability-matrix.docx", matrix_final)
    (outputs / "requirement-catalog.md").write_text("\n".join(r["id"] for r in data["requirements"]) + "\n", encoding="utf-8")
    return outputs


def test_validator_uses_only_standard_library_imports() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert "yaml" not in imported_modules
    assert "ideer" not in imported_modules
    assert imported_modules <= {"__future__", "argparse", "json", "re", "sys", "zipfile", "pathlib"}


def test_loading_validator_does_not_write_pycache_into_skill_source_dir() -> None:
    assert not (SCRIPT_PATH.parent / "__pycache__").exists()


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


# --- check_vague_words ------------------------------------------------------


def test_check_vague_words_warns_for_accepted_and_modified_only() -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1", "description": "软件应及时响应操作"},
            {"id": "F-5.2-1", "status": "modified", "source_function": "F-5.2", "source_chapter": "5.2", "description": "界面应尽量简洁且高效"},
            {"id": "F-5.2-2", "status": "rejected", "source_function": "F-5.2", "source_chapter": "5.2", "description": "适当的时候应自动锁屏"},
        ],
    )

    validator.check_vague_words(data)

    assert validator.CHECK_FAILURES == []
    assert validator.WARNINGS == [
        "requirement F-5.1-1 description contains vague wording: 及时",
        "requirement F-5.2-1 description contains vague wording: 高效, 尽量",
    ]


def test_check_vague_words_clean_descriptions_produce_no_warning() -> None:
    validator.check_vague_words(make_data())

    assert validator.CHECK_FAILURES == []
    assert validator.WARNINGS == []


def test_main_outputs_dir_with_only_vague_word_warning_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = make_data(
        functions=[{"id": "F-5.1", "name": "登录与权限管理"}],
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1", "description": "软件应及时响应操作"}],
    )
    outputs = make_outputs_dir(tmp_path, data)
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 0

    captured = capsys.readouterr().out
    assert "vague wording: 及时" in captured
    assert "ALL CHECKS PASSED" in captured


# --- check_id_presence ------------------------------------------------------


def test_check_id_presence_missing_from_srs_reports(tmp_path: Path) -> None:
    data = make_data(
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1", "description": "软件启动后应显示登录界面"}],
    )
    outputs = make_outputs_dir(tmp_path, data, srs_texts=["unrelated body text"])

    validator.check_id_presence(outputs, data)

    assert validator.CHECK_FAILURES == ["accepted requirement F-5.1-1 does not appear in srs_document.docx"]


def test_check_id_presence_missing_from_matrix_reports(tmp_path: Path) -> None:
    data = make_data(
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1", "description": "软件启动后应显示登录界面"}],
    )
    outputs = make_outputs_dir(tmp_path, data, matrix_texts=["matrix only"])

    validator.check_id_presence(outputs, data)

    assert validator.CHECK_FAILURES == ["accepted requirement F-5.1-1 does not appear in traceability-matrix.docx"]


def test_check_id_presence_all_accepted_ids_present_passes(tmp_path: Path) -> None:
    data = make_data()
    outputs = make_outputs_dir(tmp_path, data)

    validator.check_id_presence(outputs, data)

    assert validator.CHECK_FAILURES == []


def test_check_id_presence_rejected_id_not_required_in_docs(tmp_path: Path) -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1", "description": "软件启动后应显示登录界面"},
            {"id": "F-5.1-2", "status": "rejected", "source_function": "F-5.1", "source_chapter": "5.1", "description": "记住登录密码功能"},
        ],
    )
    outputs = make_outputs_dir(tmp_path, data)

    validator.check_id_presence(outputs, data)

    assert validator.CHECK_FAILURES == []


def test_check_id_presence_missing_docx_reports_no_duplicate(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    validator.check_id_presence(outputs, make_data())

    assert validator.CHECK_FAILURES == []


def test_main_docx_with_empty_document_xml_reports_error_and_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    outputs = make_outputs_dir(tmp_path, make_data())
    make_docx_with_empty_document_xml(outputs / "srs_document.docx")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "FAILED with the following issues" in captured
    assert "no readable text in srs_document.docx" in captured


# --- check_requirement_catalog ----------------------------------------------


def test_check_requirement_catalog_missing_reports(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    validator.check_requirement_catalog(outputs, make_data())

    assert validator.CHECK_FAILURES == ["missing requirement-catalog.md"]


def test_check_requirement_catalog_missing_progress_ids_reports(tmp_path: Path) -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.1-2", "status": "rejected", "source_function": "F-5.1", "source_chapter": "5.1"},
        ],
    )
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "requirement-catalog.md").write_text("目录\n\nF-5.1-1 已采纳\n", encoding="utf-8")

    validator.check_requirement_catalog(outputs, data)

    assert validator.CHECK_FAILURES == ["requirement-catalog.md is missing requirement IDs: ['F-5.1-2']"]


def test_check_requirement_catalog_unknown_ids_reports(tmp_path: Path) -> None:
    data = make_data(
        requirements=[{"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"}],
    )
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "requirement-catalog.md").write_text("F-5.1-1\nF-9.9-1\n", encoding="utf-8")

    validator.check_requirement_catalog(outputs, data)

    assert validator.CHECK_FAILURES == ["requirement-catalog.md contains IDs not in progress.json: ['F-9.9-1']"]


def test_check_requirement_catalog_consistent_passes(tmp_path: Path) -> None:
    data = make_data()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    ids = "\n".join(r["id"] for r in data["requirements"])
    (outputs / "requirement-catalog.md").write_text(f"需求目录\n{ids}\n", encoding="utf-8")

    validator.check_requirement_catalog(outputs, data)

    assert validator.CHECK_FAILURES == []


def test_main_outputs_dir_without_catalog_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = make_data()
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "progress.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    make_docx(outputs / "srs_document.docx", ["F-5.1-1", "F-5.2-1"])
    make_docx(outputs / "traceability-matrix.docx", ["F-5.1-1", "F-5.2-1"])
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    assert "missing requirement-catalog.md" in capsys.readouterr().out


def test_main_non_utf8_catalog_reports_failure_instead_of_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = make_data()
    outputs = make_outputs_dir(tmp_path, data)
    (outputs / "requirement-catalog.md").write_text("\n".join(r["id"] for r in data["requirements"]) + "\n", encoding="utf-16")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "FAILED with the following issues" in captured
    assert "cannot read requirement-catalog.md" in captured


# --- check_pending_requirements ---------------------------------------------


def test_check_pending_requirements_complete_stage_with_pending_reports() -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.1-2", "status": "pending", "source_function": "F-5.1", "source_chapter": "5.1"},
        ],
    )

    validator.check_pending_requirements(data)

    assert validator.CHECK_FAILURES == ["stage 'complete' still has pending requirements (not accepted/modified/rejected): ['F-5.1-2']"]


def test_check_pending_requirements_missing_status_counts_as_pending() -> None:
    data = make_data(
        requirements=[{"id": "F-5.1-1", "source_function": "F-5.1", "source_chapter": "5.1"}],
    )

    validator.check_pending_requirements(data)

    assert len(validator.CHECK_FAILURES) == 1
    assert "F-5.1-1" in validator.CHECK_FAILURES[0]


def test_check_pending_requirements_review_stage_is_also_final() -> None:
    data = make_data(
        stage="review",
        requirements=[{"id": "F-5.1-1", "status": "proposed", "source_function": "F-5.1", "source_chapter": "5.1"}],
    )

    validator.check_pending_requirements(data)

    assert len(validator.CHECK_FAILURES) == 1
    assert "stage 'review'" in validator.CHECK_FAILURES[0]


def test_check_pending_requirements_early_stage_with_pending_passes() -> None:
    data = make_data(
        stage="document_generation",
        requirements=[{"id": "F-5.1-1", "status": "pending", "source_function": "F-5.1", "source_chapter": "5.1"}],
    )

    validator.check_pending_requirements(data)

    assert validator.CHECK_FAILURES == []


def test_check_pending_requirements_all_terminal_passes() -> None:
    validator.check_pending_requirements(make_data())

    assert validator.CHECK_FAILURES == []


def test_main_complete_stage_with_pending_requirement_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    data = make_data(
        requirements=[
            {"id": "F-5.1-1", "status": "accepted", "source_function": "F-5.1", "source_chapter": "5.1"},
            {"id": "F-5.2-1", "status": "modified", "source_function": "F-5.2", "source_chapter": "5.2"},
            {"id": "F-5.2-2", "status": "pending", "source_function": "F-5.2", "source_chapter": "5.2"},
        ],
    )
    outputs = make_outputs_dir(tmp_path, data)
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    assert "still has pending requirements" in capsys.readouterr().out


# --- discover_run_dirs -------------------------------------------------------


def test_discover_run_dirs_flat_layout_returns_outputs_dir_itself(tmp_path: Path) -> None:
    outputs = make_outputs_dir(tmp_path, make_data())

    assert validator.discover_run_dirs(outputs) == [outputs]


def test_discover_run_dirs_returns_single_taskbook_subdir(tmp_path: Path) -> None:
    run_dir = make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-alpha")

    assert validator.discover_run_dirs(tmp_path) == [run_dir]


def test_discover_run_dirs_returns_all_taskbook_subdirs_sorted(tmp_path: Path) -> None:
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-beta")
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-alpha")

    assert validator.discover_run_dirs(tmp_path) == [tmp_path / "srs-taskbook-alpha", tmp_path / "srs-taskbook-beta"]


def test_discover_run_dirs_entries_without_progress_json_are_ignored(tmp_path: Path) -> None:
    parent = tmp_path / "outputs"
    parent.mkdir()
    (parent / "srs-empty").mkdir()
    (parent / "notes.txt").write_text("not a run", encoding="utf-8")

    assert validator.discover_run_dirs(parent) == []


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


def test_main_single_taskbook_subdir_is_validated_and_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-alpha")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(tmp_path)])

    assert validator.main() == 0

    assert "ALL CHECKS PASSED" in capsys.readouterr().out


def test_main_without_progress_json_anywhere_keeps_missing_progress_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    parent = tmp_path / "outputs"
    parent.mkdir()
    (parent / "srs-taskbook-alpha").mkdir()
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(parent)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "could not load progress.json" in captured
    assert "ALL CHECKS PASSED" not in captured


def test_main_multiple_taskbook_subdirs_all_pass_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-beta")
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-alpha")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(tmp_path)])

    assert validator.main() == 0

    captured = capsys.readouterr().out
    assert "srs-taskbook-alpha" in captured
    assert "srs-taskbook-beta" in captured
    assert captured.count("ALL CHECKS PASSED") == 2


def test_main_multiple_taskbook_subdirs_any_failure_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-alpha")
    broken = make_outputs_dir(tmp_path, make_data(), dir_name="srs-taskbook-beta")
    (broken / "requirement-catalog.md").unlink()
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(tmp_path)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "missing requirement-catalog.md" in captured
    assert "srs-taskbook-alpha" in captured
    assert "srs-taskbook-beta" in captured


# --- severity grading -------------------------------------------------------


def test_main_warn_does_not_affect_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    outputs = make_outputs_dir(tmp_path, make_data())
    validator.warn("requirement F-5.1-1 description contains vague wording: 及时")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 0

    captured = capsys.readouterr().out
    assert "[warn] requirement F-5.1-1 description contains vague wording: 及时" in captured
    assert "ALL CHECKS PASSED" in captured


def test_main_error_still_nonzero_when_warnings_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    outputs = make_outputs_dir(tmp_path, make_data())
    validator.warn("requirement F-5.1-1 description contains vague wording: 及时")
    validator.fail("some blocking error")
    monkeypatch.setattr(sys, "argv", ["validate_srs_outputs.py", "--outputs-dir", str(outputs)])

    assert validator.main() == 1

    captured = capsys.readouterr().out
    assert "[warn] requirement F-5.1-1 description contains vague wording: 及时" in captured
    assert "FAILED with the following issues" in captured
    assert "some blocking error" in captured
