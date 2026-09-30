import errno
import json
import os
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from deerflow.uploads.code_analysis import (
    ScannerStatus,
    confidence_for_finding,
    detect_language,
    detect_scanner,
    fixed_scanner_commands,
    inventory_package,
    normalize_scanner_output,
    overall_scanner_status,
    run_fixed_scanner,
    run_static_analysis,
    write_analysis_summary,
)


def _write_fake_binary(bin_dir: Path, name: str, script: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / name
    binary.write_text(textwrap.dedent(script).lstrip(), encoding="utf-8")
    binary.chmod(0o755)


def test_inventory_finds_cross_file_sources_and_build_metadata(tmp_path: Path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "include").mkdir()
    (source / "src/main.c").write_text("int main(void) { return 0; }")
    (source / "include/main.h").write_text("#pragma once")
    (source / "compile_commands.json").write_text("[]")

    result = inventory_package(tmp_path)

    assert result["source_files"] == ["include/main.h", "src/main.c"]
    assert result["headers"] == ["include/main.h"]
    assert result["build_metadata"] == ["compile_commands.json"]
    assert result["compilation_configuration_verified"] is True


def test_static_alert_alone_is_never_confirmed():
    assert confidence_for_finding(has_correlated_context=False) == "high_risk_candidate"
    assert confidence_for_finding(has_correlated_context=True) == "high_risk_candidate"
    assert confidence_for_finding(has_correlated_context=True, is_static_alert=False) == "confirmed"


def test_scanner_commands_are_fixed_and_shell_free(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("deerflow.uploads.code_analysis.shutil.which", lambda name: "/usr/bin/" + name)
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "main.c").write_text("int main(void) { return 0; }")
    commands = fixed_scanner_commands(tmp_path, tmp_path / "output")
    assert {name for name, _ in commands} == {"clang-tidy", "cppcheck"}
    assert all("--shell" not in args for _, args in commands)
    clang_args = dict(commands)["clang-tidy"]
    assert "--" in clang_args
    assert any(arg.endswith("/source/main.c") for arg in clang_args[: clang_args.index("--")])


def test_cppcheck_output_is_normalized_to_package_relative_evidence(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    file_path = source / "main.c"
    file_path.write_text("int main(void) {}")
    raw = '<results><errors><error id="nullPointer" msg="possible null dereference"><location file="main.c" line="7" /></error></errors></results>'

    findings = normalize_scanner_output("cppcheck", "2.0", raw, source_root=source)

    assert [finding.as_dict() for finding in findings] == [
        {
            "scanner": "cppcheck",
            "version": "2.0",
            "rule_id": "nullPointer",
            "path": "main.c",
            "line": 7,
            "message": "possible null dereference",
            "confidence": "high_risk_candidate",
        }
    ]


def test_scanner_timeout_is_recorded_and_bounded(tmp_path: Path, monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] > 0
        raise subprocess.TimeoutExpired(kwargs.get("args", args[0]), kwargs["timeout"])

    monkeypatch.setattr("deerflow.uploads.code_analysis.subprocess.run", timeout)
    output_dir = tmp_path / "analysis"

    outcome = run_fixed_scanner(["cppcheck", "source"], cwd=tmp_path, output_dir=output_dir, timeout=120)

    assert outcome.exit_code == 124
    assert outcome.timed_out is True
    assert "timed out" in (output_dir / "cppcheck.stderr.txt").read_text()


def test_cppcheck_results_xml_on_stdout_and_progress_on_stderr_parse_separately(tmp_path: Path, monkeypatch):
    """Defect 1 regression: cppcheck writes its results XML to stdout and its
    progress lines to stderr; concatenating the two streams breaks the XML
    parse and silently drops every finding."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.c").write_text("int main(void) { int* p = 0; return *p; }")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<results version="2">\n'
        '    <cppcheck version="2.10"/>\n'
        "    <errors>\n"
        '        <error id="nullPointer" severity="error" msg="Null pointer dereference: p">'
        f'<location file="{source / "main.c"}" line="1" info="..."/></error>\n'
        "    </errors>\n"
        "</results>\n"
    )
    _write_fake_binary(
        tmp_path / "bin",
        "cppcheck",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Cppcheck 2.10")
        else:
            sys.stdout.write({xml!r})
            sys.stderr.write("Checking main.c...\\n1/1 files checked 100% done\\n")
        """,
    )
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")

    outcome = run_fixed_scanner(["cppcheck", "--xml", str(source)], cwd=tmp_path, output_dir=tmp_path / "analysis", timeout=120)

    assert outcome.exit_code == 0
    assert "1/1 files checked" in outcome.stderr
    findings = normalize_scanner_output("cppcheck", "2.10", outcome.stdout, source_root=source)

    assert [finding.rule_id for finding in findings] == ["nullPointer"]
    assert findings[0].path == "main.c"
    assert findings[0].line == 1


def _make_package(tmp_path: Path, *, with_compile_db: bool = True) -> Path:
    package_root = tmp_path / "pkg-1"
    source = package_root / "source"
    source.mkdir(parents=True)
    (source / "main.c").write_text("int main(void) { return 0; }")
    if with_compile_db:
        (source / "compile_commands.json").write_text("[]")
    return package_root


def test_scanner_status_contract_fields():
    status = ScannerStatus("cppcheck", available=True, version="2.10", exit_code=1, timed_out=False, skipped_reason=None)
    assert status.as_dict() == {
        "name": "cppcheck",
        "available": True,
        "version": "2.10",
        "exit_code": 1,
        "timed_out": False,
        "skipped_reason": None,
    }


def test_detect_scanner_reports_availability_and_version(tmp_path: Path, monkeypatch):
    base_path = os.environ["PATH"]
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert detect_scanner("cppcheck") == (False, None)

    _write_fake_binary(tmp_path / "bin", "cppcheck", '#!/usr/bin/env python3\nprint("Cppcheck 2.10")\n')
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{base_path}")
    assert detect_scanner("cppcheck") == (True, "2.10")


def test_overall_rollup_discloses_unavailable_partial_and_completed():
    unavailable = [ScannerStatus("clang-tidy", available=False, skipped_reason="not found"), ScannerStatus("cppcheck", available=False, skipped_reason="not found")]
    assert overall_scanner_status(unavailable) == "scanners_unavailable"

    policy_skip_and_ran = [ScannerStatus("clang-tidy", available=True, skipped_reason="missing compile_commands.json"), ScannerStatus("cppcheck", available=True, exit_code=0)]
    assert overall_scanner_status(policy_skip_and_ran) == "completed"

    partial = [ScannerStatus("clang-tidy", available=True, exit_code=0), ScannerStatus("cppcheck", available=False, skipped_reason="not found")]
    assert overall_scanner_status(partial) == "partial"

    timed_out = [ScannerStatus("cppcheck", available=True, exit_code=124, timed_out=True)]
    assert overall_scanner_status(timed_out) == "partial"

    assert overall_scanner_status([]) == "completed"


def test_missing_scanner_binaries_are_disclosed_not_dropped(tmp_path: Path, monkeypatch):
    """Defect 2 regression: every scanner gets a status record; a missing
    binary can no longer silently vanish from the analysis."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    package_root = _make_package(tmp_path)

    result = run_static_analysis(package_root)

    assert result.package_id == "pkg-1"
    assert [(s.name, s.available, s.skipped_reason is not None) for s in result.statuses] == [
        ("clang-tidy", False, True),
        ("cppcheck", False, True),
    ]
    assert result.findings == []
    assert result.overall == "scanners_unavailable"
    assert detect_language(result.inventory) == "c_cpp"


def test_scanner_timeout_tiers_by_source_file_count():
    """Defect 3 regression: the timeout budget scales with package size
    (<=200 source files 120s, otherwise 600s) instead of a fixed 120s."""
    from deerflow.uploads.code_analysis import (
        LARGE_PACKAGE_SCANNER_TIMEOUT_SECONDS,
        SMALL_PACKAGE_SCANNER_TIMEOUT_SECONDS,
        scanner_timeout_seconds,
    )

    assert scanner_timeout_seconds(1) == SMALL_PACKAGE_SCANNER_TIMEOUT_SECONDS == 120
    assert scanner_timeout_seconds(200) == 120
    assert scanner_timeout_seconds(201) == 600
    assert scanner_timeout_seconds(10_000) == LARGE_PACKAGE_SCANNER_TIMEOUT_SECONDS == 600


@pytest.mark.parametrize("source_count,expected_timeout", [(3, 120), (201, 600)])
def test_run_static_analysis_applies_tiered_timeout(tmp_path, monkeypatch, source_count, expected_timeout):
    seen_timeouts: list[int] = []

    def record_run(command, **kwargs):
        if "--version" in command:
            return SimpleNamespace(returncode=0, stdout="1.0", stderr="")
        seen_timeouts.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("deerflow.uploads.code_analysis.subprocess.run", record_run)
    monkeypatch.setattr("deerflow.uploads.code_analysis.detect_scanner", lambda name: (True, "1.0"))
    package_root = tmp_path / "pkg-tier"
    source = package_root / "source"
    source.mkdir(parents=True)
    (source / "compile_commands.json").write_text("[]")
    for index in range(source_count):
        (source / f"m{index}.c").write_text("int x;\n")

    run_static_analysis(package_root)

    assert seen_timeouts == [expected_timeout, expected_timeout]


def test_run_fixed_scanner_captures_e2big_instead_of_crashing(tmp_path, monkeypatch):
    """Defect 4 regression: handing clang-tidy a huge argv can raise E2BIG at
    exec time; the scanner run must capture the failure, never propagate it."""

    def e2big(*args, **kwargs):
        raise OSError(errno.E2BIG, "Argument list too long")

    monkeypatch.setattr("deerflow.uploads.code_analysis.subprocess.run", e2big)
    output_dir = tmp_path / "analysis"

    outcome = run_fixed_scanner(["clang-tidy", "--quiet"], cwd=tmp_path, output_dir=output_dir, timeout=120)

    assert outcome.exit_code is None
    assert outcome.start_error is not None and "Argument list too long" in outcome.start_error
    assert "Argument list too long" in (output_dir / "clang-tidy.stderr.txt").read_text()


def test_start_failure_is_disclosed_as_partial_scan(tmp_path, monkeypatch):
    seen: dict = {}

    def record_run(command, **kwargs):
        if "--version" in command:
            return SimpleNamespace(returncode=0, stdout="14.0.6", stderr="")
        seen["argv_len"] = len(command)
        raise OSError(errno.E2BIG, "Argument list too long")

    monkeypatch.setattr("deerflow.uploads.code_analysis.subprocess.run", record_run)
    monkeypatch.setattr("deerflow.uploads.code_analysis.detect_scanner", lambda name: (True, "14.0.6"))
    package_root = _make_package(tmp_path)

    result = run_static_analysis(package_root)

    clang = next(s for s in result.statuses if s.name == "clang-tidy")
    assert clang.available is True
    assert clang.exit_code is None
    assert clang.skipped_reason is not None and "failed to start" in clang.skipped_reason
    assert clang.as_dict()["skipped_reason"] is not None
    assert result.overall == "partial"
    assert seen["argv_len"] > 0


def test_no_compilation_database_skips_clang_tidy_but_runs_cppcheck(tmp_path, monkeypatch):
    """clang-tidy needs a compilation database; without one it is skipped with
    a recorded reason while cppcheck still runs, and the rollup stays
    completed (a documented policy skip is not degradation)."""
    base_path = os.environ["PATH"]
    source = tmp_path / "pkg-2" / "source"
    source.mkdir(parents=True)
    (source / "main.c").write_text("int main(void) { return 0; }")
    clang_line = f"{source / 'main.c'}:1:1: warning: unused variable 'x' [unused-variable]"
    _write_fake_binary(
        tmp_path / "bin",
        "clang-tidy",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Debian clang-tidy version 14.0.6")
            sys.exit(0)
        print({clang_line!r})
        """,
    )
    _write_fake_binary(
        tmp_path / "bin",
        "cppcheck",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Cppcheck 2.10")
            sys.exit(0)
        sys.stdout.write('<results version="2"><errors><error id="arrayIndexOutOfBounds" msg="out of bounds"><location file="{source / "main.c"}" line="1"/></error></errors></results>')
        sys.stderr.write("Checking main.c...\\n")
        """,
    )
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{base_path}")

    result = run_static_analysis(tmp_path / "pkg-2")

    clang = next(s for s in result.statuses if s.name == "clang-tidy")
    cpp = next(s for s in result.statuses if s.name == "cppcheck")
    assert clang.available is True
    assert clang.skipped_reason is not None and "compile_commands.json" in clang.skipped_reason
    assert clang.exit_code is None
    assert cpp.available is True and cpp.exit_code == 0 and cpp.version == "2.10"
    assert result.overall == "completed"

    rule_ids = sorted(f.rule_id for f in result.findings)
    assert rule_ids == ["arrayIndexOutOfBounds"]
    assert result.findings[0].scanner == "cppcheck"
    assert result.findings[0].confidence == "high_risk_candidate"


def test_with_compilation_database_both_c_cpp_scanners_run(tmp_path, monkeypatch):
    base_path = os.environ["PATH"]
    source = tmp_path / "pkg-3" / "source"
    source.mkdir(parents=True)
    (source / "main.c").write_text("int main(void) { return 0; }")
    (source / "compile_commands.json").write_text("[]")
    clang_line = f"{source / 'main.c'}:1:1: warning: variable length array [clang-analyzer-core.UndefinedBinaryOperatorResult]"
    _write_fake_binary(
        tmp_path / "bin",
        "clang-tidy",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Debian clang-tidy version 14.0.6")
            sys.exit(0)
        print({clang_line!r})
        """,
    )
    _write_fake_binary(
        tmp_path / "bin",
        "cppcheck",
        """
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Cppcheck 2.10")
            sys.exit(0)
        sys.stdout.write('<results version="2"><errors></errors></results>')
        """,
    )
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{base_path}")

    result = run_static_analysis(tmp_path / "pkg-3")

    assert all(s.skipped_reason is None for s in result.statuses)
    assert result.overall == "completed"
    clang_findings = [f for f in result.findings if f.scanner == "clang-tidy"]
    assert len(clang_findings) == 1
    assert clang_findings[0].path == "main.c"
    assert clang_findings[0].line == 1
    assert clang_findings[0].rule_id == "clang-analyzer-core.UndefinedBinaryOperatorResult"
    assert clang_findings[0].version == "14.0.6"


def test_python_package_dispatches_to_ruff_and_bandit_readonly(tmp_path, monkeypatch):
    """Python-only packages run ruff and bandit; both strictly read-only."""
    base_path = os.environ["PATH"]
    source = tmp_path / "pkg-py" / "source"
    (source / "pkgmod").mkdir(parents=True)
    (source / "pkgmod" / "app.py").write_text("import os\n")
    ruff_json = f'[{{"code": "F401", "message": "`os` imported but unused", "filename": "{source / "pkgmod" / "app.py"}", "location": {{"row": 1, "column": 8}}, "end_location": {{"row": 1, "column": 11}}, "fix": null}}]'
    bandit_json = f'{{"errors": [], "results": [{{"test_id": "B404", "issue_text": "Consider possible security implications associated with the subprocess module.", "filename": "{source / "pkgmod" / "app.py"}", "line_number": 3}}]}}'
    _write_fake_binary(
        tmp_path / "bin",
        "ruff",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("ruff 0.15.12")
            sys.exit(0)
        sys.stdout.write({ruff_json!r})
        sys.exit(1)
        """,
    )
    _write_fake_binary(
        tmp_path / "bin",
        "bandit",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("bandit 1.7.10")
            sys.exit(0)
        sys.stdout.write({bandit_json!r})
        sys.exit(1)
        """,
    )
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{base_path}")

    result = run_static_analysis(tmp_path / "pkg-py")

    assert detect_language(result.inventory) == "python"
    assert [(s.name, s.exit_code) for s in result.statuses] == [("ruff", 1), ("bandit", 1)]
    assert result.overall == "completed"

    by_scanner = {f.scanner: f for f in result.findings}
    assert by_scanner["ruff"].rule_id == "F401"
    assert by_scanner["ruff"].path == "pkgmod/app.py"
    assert by_scanner["ruff"].line == 1
    assert by_scanner["bandit"].rule_id == "B404"
    assert by_scanner["bandit"].path == "pkgmod/app.py"
    assert by_scanner["bandit"].line == 3
    # Finding Confidence contract: a static alert alone is never confirmed.
    assert all(f.confidence == "high_risk_candidate" for f in result.findings)
    assert all(f.confidence != "confirmed" for f in result.findings)


def test_normalize_ruff_and_bandit_json_shapes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n")
    absolute = str(source / "a.py")

    ruff_findings = normalize_scanner_output(
        "ruff",
        "0.15.12",
        f'[{{"code": "E501", "message": "line too long", "filename": "{absolute}", "location": {{"row": 2, "column": 80}}}}]',
        source_root=source,
    )
    assert (ruff_findings[0].scanner, ruff_findings[0].rule_id, ruff_findings[0].path, ruff_findings[0].line) == ("ruff", "E501", "a.py", 2)

    bandit_findings = normalize_scanner_output(
        "bandit",
        "1.7.10",
        f'{{"results": [{{"test_id": "B101", "issue_text": "Use of assert detected.", "filename": "{absolute}", "line_number": 1}}]}}',
        source_root=source,
    )
    assert (bandit_findings[0].scanner, bandit_findings[0].rule_id, bandit_findings[0].path, bandit_findings[0].line) == ("bandit", "B101", "a.py", 1)


def test_mixed_package_prefers_c_cpp_dispatch(tmp_path):
    source = tmp_path / "pkg-mixed" / "source"
    source.mkdir(parents=True)
    (source / "main.c").write_text("int main(void) { return 0; }")
    (source / "tool.py").write_text("print(1)\n")

    assert detect_language(inventory_package(tmp_path / "pkg-mixed")) == "c_cpp"


def test_package_without_supported_sources_skips_scanners(tmp_path, monkeypatch):
    source = tmp_path / "pkg-docs" / "source"
    source.mkdir(parents=True)
    (source / "readme.md").write_text("only docs\n")

    result = run_static_analysis(tmp_path / "pkg-docs")

    assert result.statuses == []
    assert result.findings == []
    assert result.overall == "completed"


def test_analysis_artifacts_land_in_package_analysis_dir(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    package_root = _make_package(tmp_path)
    result = run_static_analysis(package_root)

    write_analysis_summary(package_root / "analysis", result)

    inventory = json.loads((package_root / "analysis" / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["compilation_configuration_verified"] is True
    assert json.loads((package_root / "analysis" / "findings.json").read_text(encoding="utf-8")) == []

    scanner_status = json.loads((package_root / "analysis" / "scanner_status.json").read_text(encoding="utf-8"))
    assert scanner_status["package_id"] == "pkg-1"
    assert [s["name"] for s in scanner_status["scanners"]] == ["clang-tidy", "cppcheck"]
    assert all(s["available"] is False and s["skipped_reason"] for s in scanner_status["scanners"])
    assert scanner_status["overall"] == "scanners_unavailable"
