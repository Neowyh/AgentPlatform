from pathlib import Path

from select_test_lanes import classify_changes
from test_preflight import LANES


def test_documentation_only_change_selects_governance_checks() -> None:
    plan = classify_changes(["docs/testing/README.md", "AGENTS.md"])

    assert plan["channels"] == ["governance"]
    assert plan["docs_only"] is True
    assert any("documentation-only" in reason for reason in plan["reasons"]["governance"])


def test_backend_and_frontend_changes_select_each_channel_once() -> None:
    plan = classify_changes(["backend/app/gateway/auth.py", "frontend/src/app/page.tsx"])

    assert plan["channels"] == [
        "governance",
        "backend-standard",
        "frontend-standard",
        "frontend-smoke",
        "static-checks",
        "real-e2e",
    ]
    assert any("authentication" in reason for reason in plan["reasons"]["real-e2e"])


def test_runtime_and_configuration_changes_expand_validation() -> None:
    plan = classify_changes(["config.yaml", "local-runtime/src/runtime.py"])

    assert plan["channels"] == [
        "governance",
        "backend-standard",
        "frontend-standard",
        "local-runtime",
        "frontend-smoke",
        "static-checks",
    ]
    assert any("configuration" in reason for reason in plan["reasons"]["backend-standard"])


def test_workflow_and_unknown_paths_expand_instead_of_being_treated_as_docs() -> None:
    workflow = classify_changes([".github/workflows/backend-unit-tests.yml"])
    unknown = classify_changes(["vendor/new-format/generated.dat"])

    assert "backend-standard" in workflow["channels"]
    assert "frontend-smoke" in workflow["channels"]
    assert "static-checks" in workflow["channels"]
    assert unknown["channels"] == workflow["channels"]
    assert any("unclassified path" in reason for reason in unknown["reasons"]["backend-standard"])


def test_empty_change_set_runs_governance_and_records_reason() -> None:
    plan = classify_changes([])

    assert plan["channels"] == ["governance"]
    assert any("no changed files" in reason for reason in plan["reasons"]["governance"])


def test_backend_live_is_a_distinct_manual_lane() -> None:
    runner = (Path(__file__).resolve().parents[4] / "scripts/run-test-lane.sh").read_text(encoding="utf-8")

    assert "backend-live" in LANES
    assert "backend-live)" in runner
    assert "TEST_LANE_STATUS lane=backend-live status=unexecuted" in runner


def test_non_documentation_files_under_docs_expand_validation() -> None:
    for path in ("docs/config.yaml", "docs/scripts/check.py"):
        plan = classify_changes([path])
        assert plan["docs_only"] is False
        assert "backend-standard" in plan["channels"]
        assert "frontend-standard" in plan["channels"]


def test_known_documentation_screenshots_remain_governance_only() -> None:
    plan = classify_changes(["docs/manual/screenshots/01-login-page.png"])

    assert plan["channels"] == ["governance"]
    assert plan["docs_only"] is True


def test_deleted_code_is_included_in_git_selection(tmp_path, monkeypatch):
    import subprocess

    from select_test_lanes import _changed_paths

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/code.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("rm", "backend/code.py")
    git("commit", "-m", "delete")
    monkeypatch.chdir(tmp_path)
    plan = classify_changes(_changed_paths(base, "HEAD"))
    assert "backend-standard" in plan["channels"]


def test_runtime_skill_instructions_are_not_documentation_only():
    plan = classify_changes(["resources/skills/example/SKILL.md"])
    assert not plan["docs_only"]
    assert "backend-standard" in plan["channels"]
    assert "frontend-smoke" in plan["channels"]
    assert "real-e2e" in plan["channels"]
