"""S1 seam: the ``analyze_code_evidence`` tool over the fixed scan library.

Ticket 01: the tool is the model's only entry to static analysis for Code
Evidence Packages. It accepts nothing but this thread's package root under
``/mnt/user-data/code-evidence/``, dispatches scanners by language, writes
inventory/findings/scanner_status into ``<package>/analysis/`` and discloses
scanner unavailability honestly.

Everything here drives the tool coroutine directly (the builtin-tool test
convention) against the real scan library; only the filesystem home and the
scanner binaries on PATH are test doubles.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agentplatform.tools import analyze_code_evidence_tool as tool_module
from deerflow.config.paths import Paths


def _runtime(thread_id: str = "thread-1", user_id: str = "owner-1") -> SimpleNamespace:
    context: dict = {"thread_id": thread_id, "user_id": user_id, "user_role": "user"}
    return SimpleNamespace(state=None, context=context, config={"configurable": {"thread_id": thread_id}})


def _package_root(env, thread_id: str = "thread-1", package_id: str = "pkg-1") -> Path:
    return env.paths.thread_dir(thread_id, user_id="owner-1") / "user-data" / "code-evidence" / package_id


def _seed_c_cpp_package(env, *, with_compile_db: bool = True, package_id: str = "pkg-1") -> Path:
    root = _package_root(env, package_id=package_id)
    source = root / "source"
    source.mkdir(parents=True)
    (source / "main.c").write_text("int main(void) { return *p; }")
    if with_compile_db:
        (source / "compile_commands.json").write_text("[]")
    return root


def _seed_python_package(env, *, package_id: str = "pkg-1") -> Path:
    root = _package_root(env, package_id=package_id)
    (root / "source" / "pkgmod").mkdir(parents=True)
    (root / "source" / "pkgmod" / "app.py").write_text("import os\n")
    return root


def _write_fake_binary(env, name: str, script: str) -> None:
    bin_dir = env.tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / name
    binary.write_text(textwrap.dedent(script).lstrip(), encoding="utf-8")
    binary.chmod(0o755)


def _install_fake_c_cpp_scanners(env, *, source: Path) -> None:
    base_path = os.environ["PATH"]
    clang_line = f"{source / 'main.c'}:1:1: warning: variable length array [clang-analyzer-core]"
    _write_fake_binary(
        env,
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
        env,
        "cppcheck",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("Cppcheck 2.10")
            sys.exit(0)
        sys.stdout.write('<results version="2"><errors><error id="nullPointer" msg="Null pointer dereference: p"><location file="{source / "main.c"}" line="1"/></error></errors></results>')
        sys.stderr.write("Checking main.c...\\n")
        """,
    )
    env.monkeypatch.setenv("PATH", f"{env.tmp_path / 'bin'}:{base_path}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    monkeypatch.setattr("app.agentplatform.code_evidence.get_paths", lambda: paths)
    return SimpleNamespace(paths=paths, tmp_path=tmp_path, monkeypatch=monkeypatch)


async def _call(runtime, package_root: str) -> dict:
    raw = await tool_module.analyze_code_evidence_tool.coroutine(runtime=runtime, package_root=package_root)
    return json.loads(raw)


@pytest.mark.asyncio
async def test_paths_outside_the_package_root_are_structurally_rejected(env) -> None:
    _seed_c_cpp_package(env)

    for declared in [
        "/mnt/user-data/uploads/evidence.zip",
        "/mnt/user-data",
        "/etc/passwd",
        "/mnt/user-data/code-evidence/../../etc",
        "",
    ]:
        payload = await _call(_runtime(), declared)
        assert payload["reason_code"] == "package_path_rejected", declared
        assert payload["allowed_pattern"] == "/mnt/user-data/code-evidence/<package_id>"
        assert "error" in payload


@pytest.mark.asyncio
async def test_unknown_package_id_is_reported_not_raised(env) -> None:
    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/missing-pkg")

    assert payload["reason_code"] == "package_not_found"
    assert "missing-pkg" in payload["error"]


@pytest.mark.asyncio
async def test_thread_context_is_required(env) -> None:
    runtime = _runtime()
    runtime.context = {}
    runtime.config = {"configurable": {}}

    payload = await _call(runtime, "/mnt/user-data/code-evidence/pkg-1")

    assert payload["reason_code"] == "thread_context_missing"


@pytest.mark.asyncio
async def test_c_cpp_package_runs_fixed_scanners_and_writes_artifacts(env) -> None:
    package_dir = _seed_c_cpp_package(env)
    _install_fake_c_cpp_scanners(env, source=package_dir / "source")

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1")

    assert payload["package_id"] == "pkg-1"
    assert payload["language"] == "c_cpp"
    assert payload["overall"] == "completed"
    assert payload["findings_count"] >= 1
    assert payload["inventory_summary"]["compilation_configuration_verified"] is True

    analysis = package_dir / "analysis"
    assert (analysis / "inventory.json").is_file()
    assert (analysis / "findings.json").is_file()
    scanner_status = json.loads((analysis / "scanner_status.json").read_text(encoding="utf-8"))
    assert scanner_status["package_id"] == "pkg-1"
    assert [s["name"] for s in scanner_status["scanners"]] == ["clang-tidy", "cppcheck"]
    assert scanner_status["overall"] == "completed"


@pytest.mark.asyncio
async def test_no_compilation_database_skips_clang_tidy_with_recorded_reason(env) -> None:
    package_dir = _seed_c_cpp_package(env, with_compile_db=False)
    _install_fake_c_cpp_scanners(env, source=package_dir / "source")

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1")

    clang = next(s for s in payload["scanner_status"] if s["name"] == "clang-tidy")
    cpp = next(s for s in payload["scanner_status"] if s["name"] == "cppcheck")
    assert clang["available"] is True
    assert clang["skipped_reason"] is not None and "compile_commands.json" in clang["skipped_reason"]
    assert clang["exit_code"] is None
    assert cpp["exit_code"] == 0
    assert payload["overall"] == "completed"
    on_disk = json.loads((package_dir / "analysis" / "scanner_status.json").read_text(encoding="utf-8"))
    assert next(s for s in on_disk["scanners"] if s["name"] == "clang-tidy")["skipped_reason"]


@pytest.mark.asyncio
async def test_python_package_gets_ruff_and_bandit_and_alerts_never_confirmed(env) -> None:
    package_dir = _seed_python_package(env)
    base_path = os.environ["PATH"]
    app_py = package_dir / "source" / "pkgmod" / "app.py"
    _write_fake_binary(
        env,
        "ruff",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("ruff 0.15.12")
            sys.exit(0)
        sys.stdout.write('[{{"code": "F401", "message": "`os` imported but unused", "filename": "{app_py}", "location": {{"row": 1, "column": 8}}}}]')
        sys.exit(1)
        """,
    )
    _write_fake_binary(
        env,
        "bandit",
        f"""
        #!/usr/bin/env python3
        import sys
        if "--version" in sys.argv:
            print("bandit 1.7.10")
            sys.exit(0)
        sys.stdout.write('[{{"results": [{{"test_id": "B404", "issue_text": "subprocess import", "filename": "{app_py}", "line_number": 3}}]}}]')
        sys.exit(1)
        """,
    )
    env.monkeypatch.setenv("PATH", f"{env.tmp_path / 'bin'}:{base_path}")

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1/source")

    assert payload["language"] == "python"
    assert [s["name"] for s in payload["scanner_status"]] == ["ruff", "bandit"]
    assert payload["findings_count"] == 2
    assert all(finding["confidence"] == "high_risk_candidate" for finding in payload["findings_preview"])
    assert all(finding["confidence"] != "confirmed" for finding in payload["findings_preview"])


@pytest.mark.asyncio
async def test_missing_scanner_binaries_are_disclosed_as_unavailable(env) -> None:
    package_dir = _seed_c_cpp_package(env)
    empty = env.tmp_path / "empty-bin"
    empty.mkdir()
    env.monkeypatch.setenv("PATH", str(empty))

    payload = await _call(_runtime(), "/mnt/user-data/code-evidence/pkg-1")

    assert payload["overall"] == "scanners_unavailable"
    assert payload["findings_count"] == 0
    assert all(s["available"] is False and s["skipped_reason"] for s in payload["scanner_status"])
    on_disk = json.loads((package_dir / "analysis" / "scanner_status.json").read_text(encoding="utf-8"))
    assert on_disk["overall"] == "scanners_unavailable"
