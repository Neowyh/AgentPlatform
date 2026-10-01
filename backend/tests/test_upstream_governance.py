"""Registration gates read candidate evidence and fail closed."""

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("upstream_gate", ROOT / "scripts/check_upstream_patches.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def run(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def make_repo(tmp_path):
    run(tmp_path, "init")
    run(tmp_path, "config", "user.email", "test@example.com")
    run(tmp_path, "config", "user.name", "Test")
    path = tmp_path / "backend/packages/harness/deerflow/runtime.py"
    path.parent.mkdir(parents=True)
    path.write_text("original\n")
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "baseline")
    return path, run(tmp_path, "rev-parse", "HEAD")


def ledger(root, entries, budget=44):
    code_budget = min(budget, 43)
    document_budget = budget - code_budget
    registry = {
        "schema_version": 1,
        "upstream_baseline": run(root, "rev-parse", "HEAD"),
        "file_budget": budget,
        "budget_basis": {"code_files": code_budget, "document_files": document_budget, "previous_code_files": code_budget, "previous_document_files": document_budget, "amendment": "Test fixture budget allocation."},
        "patches": entries,
    }
    sources = []
    for item in entries:
        sources.append(
            f"### {item['id']}: test source\n\n"
            f"- **原因**: {item['reason']}\n"
            f"- **上游替代方案**: {item['alternative']}\n"
            f"- **修改**: {item['impact']}\n"
            f"- **Owner**: {item['owner']}\n"
            f"- **移除条件**: {item['removal']}\n"
            f"- **测试**: {', '.join(item['verification'])}\n"
        )
    (root / "UPSTREAM_PATCH_LEDGER.md").write_text("\n".join(sources) + "<!-- upstream-registry:start -->\n```json\n" + json.dumps(registry) + "\n```\n<!-- upstream-registry:end -->\n")


def entry(status="current"):
    return {
        "id": "PATCH-001",
        "paths": ["backend/packages/harness/deerflow/runtime.py"],
        "reason": "contract",
        "alternative": "no extension hook",
        "impact": "runtime",
        "owner": "runtime team",
        "removal": "upstream hook",
        "verification": ["tests/test_runtime_contract.py::test_contract"],
        "verification_status": status,
        "lifecycle_status": "open",
        "current_verification": {"command": "pytest tests/test_runtime_contract.py -q", "result": "1 passed"},
    }


def test_unregistered_and_missing_current_evidence_are_blocked(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    ledger(tmp_path, [])
    assert any("unregistered" in e for e in gate.check(tmp_path, baseline, None, baseline)["errors"])
    ledger(tmp_path, [entry("historical")])
    assert any("current verification" in e for e in gate.check(tmp_path, baseline, None, baseline)["errors"])
    ledger(tmp_path, [entry()])
    assert gate.check(tmp_path, baseline, None, baseline)["status"] == "pass"


def test_revision_check_uses_candidate_ledger_and_total_budget(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    ledger(tmp_path, [entry()], budget=0)
    run(tmp_path, "add", ".")
    run(tmp_path, "commit", "-m", "candidate")
    head = run(tmp_path, "rev-parse", "HEAD")
    ledger(tmp_path, [], budget=44)
    report = gate.check(tmp_path, baseline, head, baseline)
    assert report["total_files"] == 1
    assert any("budget exceeded" in e for e in report["errors"])
    assert not any("unregistered" in e for e in report["errors"])


def test_non_fast_forward_mirror_is_blocked(tmp_path):
    _, baseline = make_repo(tmp_path)
    run(tmp_path, "branch", "-M", "main")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(tmp_path), str(origin)], check=True, capture_output=True)
    upstream = tmp_path / "upstream.git"
    subprocess.run(["git", "clone", "--bare", str(tmp_path), str(upstream)], check=True, capture_output=True)
    run(tmp_path, "remote", "add", "origin", str(origin))
    (tmp_path / "local.txt").write_text("local fork")
    run(tmp_path, "add", "local.txt")
    run(tmp_path, "commit", "-m", "fork")
    run(tmp_path, "push", "origin", "main")
    import os

    result = subprocess.run(["bash", str(ROOT / "scripts/sync_upstream_mirror.sh")], cwd=tmp_path, env={**os.environ, "UPSTREAM_MIRROR_URL": str(upstream), "UPSTREAM_MIRROR_APPLY": "1"}, capture_output=True, text=True)
    assert result.returncode != 0
    assert "cannot fast-forward" in result.stderr
    assert run(origin, "rev-parse", "main") == run(tmp_path, "rev-parse", "HEAD")
    assert run(upstream, "rev-parse", "main") == baseline


def test_upstream_baseline_must_match_the_ledger_pin(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    ledger(tmp_path, [entry()])
    run(tmp_path, "commit", "--allow-empty", "-m", "other pin")
    other = run(tmp_path, "rev-parse", "HEAD")

    report = gate.check(tmp_path, baseline, None, other)

    assert any("baseline pin mismatch" in error for error in report["errors"])


def test_deleted_harness_path_remains_registered_and_requires_candidate_evidence(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.unlink()
    ledger(tmp_path, [entry()])

    report = gate.check(tmp_path, baseline, None, baseline)

    assert report["total_files"] == 1
    assert report["deleted_files"] == 1
    assert report["status"] == "pass"


def test_revision_deleted_harness_path_is_counted_and_registered(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.unlink()
    ledger(tmp_path, [entry()])
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-m", "delete patched file")
    head = run(tmp_path, "rev-parse", "HEAD")

    report = gate.check(tmp_path, baseline, head, baseline)

    assert report["total_files"] == 1
    assert report["deleted_files"] == 1
    assert report["status"] == "pass"


def test_new_entry_needs_current_command_and_result(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    changed = entry("historical")
    changed["current_verification"] = {"command": "", "result": ""}
    ledger(tmp_path, [changed])

    errors = gate.check(tmp_path, baseline, None, baseline)["errors"]

    assert any("current verification command" in error for error in errors)
    assert any("current verification result" in error for error in errors)


def test_failed_current_verification_result_blocks_candidate(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    changed = entry()
    changed["current_verification"]["result"] = "1 failed"
    ledger(tmp_path, [changed])

    errors = gate.check(tmp_path, baseline, None, baseline)["errors"]

    assert any("current verification result must report success" in error for error in errors)


def test_placeholder_metadata_and_invalid_paths_are_rejected(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    broken = entry()
    broken["reason"] = "See PATCH-001 rationale in this ledger"
    broken["paths"] = ["backend/packages/harness/deerflow/../outside.py"]
    ledger(tmp_path, [broken])

    errors = gate.check(tmp_path, baseline, None, baseline)["errors"]

    assert any("placeholder" in error for error in errors)
    assert any("invalid harness path" in error for error in errors)


def test_document_budget_amendment_cannot_raise_code_file_budget(tmp_path):
    path, baseline = make_repo(tmp_path)
    path.write_text("changed\n")
    registry_entry = entry()
    registry_entry["paths"] = [str(path.relative_to(tmp_path)), str(path.relative_to(tmp_path)).replace("runtime.py", "runtime.md")]
    path.rename(path.with_suffix(".md"))
    ledger(tmp_path, [registry_entry], budget=2)
    content = (tmp_path / "UPSTREAM_PATCH_LEDGER.md").read_text()
    content = content.replace('"code_files": 2, "document_files": 0, "previous_code_files": 2, "previous_document_files": 0', '"code_files": 0, "document_files": 2, "previous_code_files": 0, "previous_document_files": 2')
    (tmp_path / "UPSTREAM_PATCH_LEDGER.md").write_text(content)

    report = gate.check(tmp_path, baseline, None, baseline)

    assert any("code patch budget exceeded" in error for error in report["errors"])


def test_readability_patch_references_retained_root_test_file():
    ledger_text = (ROOT / "UPSTREAM_PATCH_LEDGER.md").read_text()

    assert "backend/tests/test_readability.py::test_extract_article_falls_back_when_readability_js_fails" in ledger_text
    assert "backend/tests/unit/tools/test_readability.py" not in ledger_text
