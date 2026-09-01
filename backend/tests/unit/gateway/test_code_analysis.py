import subprocess
from pathlib import Path

from ideer.uploads.code_analysis import confidence_for_finding, fixed_scanner_commands, inventory_package, normalize_scanner_output, run_fixed_scanner


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
    monkeypatch.setattr("ideer.uploads.code_analysis.shutil.which", lambda name: "/usr/bin/" + name)
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

    monkeypatch.setattr("ideer.uploads.code_analysis.subprocess.run", timeout)
    output = tmp_path / "scanner.txt"

    returncode, raw = run_fixed_scanner(["cppcheck", "source"], cwd=tmp_path, output_file=output)

    assert returncode == 124
    assert "timed out" in raw
    assert output.read_text() == raw
