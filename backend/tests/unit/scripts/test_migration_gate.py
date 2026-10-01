import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/migration-tests.yml"


def workflow():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def test_migration_required_check_exists_for_unrelated_prs():
    definition = workflow()
    assert "paths" not in definition["on"]["pull_request"]
    assert "paths" in definition["on"]["push"]
    assert definition["jobs"]["migration-gate"]["name"] == "Migration Gate"


@pytest.mark.parametrize(
    "selected,result,selection_result,expected",
    [
        ("false", "skipped", "success", 0),
        ("true", "success", "success", 0),
        ("true", "failure", "success", 1),
        ("true", "cancelled", "success", 1),
        ("true", "skipped", "success", 1),
        ("true", "", "success", 1),
        ("false", "skipped", "failure", 1),
        ("", "skipped", "success", 1),
    ],
)
def test_migration_gate_requires_selected_success(selected, result, selection_result, expected):
    script = workflow()["jobs"]["migration-gate"]["steps"][0]["run"]
    output = subprocess.run(
        ["bash", "-e", "-c", script],
        env={
            **os.environ,
            "RUN_MIGRATION": selected,
            "MIGRATION_RESULT": result,
            "SELECT_RESULT": selection_result,
        },
        capture_output=True,
        text=True,
    )
    assert (output.returncode == 0) == (expected == 0), output.stderr


def test_migration_selector_detects_deletion_and_rejects_invalid_refs(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    migration = tmp_path / "backend/packages/harness/deerflow/persistence/example.py"
    migration.parent.mkdir(parents=True)
    migration.write_text("example = 1\n")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("rm", str(migration.relative_to(tmp_path)))
    git("commit", "-m", "delete migration input")
    head = git("rev-parse", "HEAD")
    selector = workflow()["jobs"]["select-migration"]["steps"][1]["run"]
    output_file = tmp_path / "github-output"

    def select(base_sha, head_sha, draft="false"):
        output_file.write_text("")
        result = subprocess.run(
            ["bash", "-e", "-c", selector],
            cwd=tmp_path,
            env={
                **os.environ,
                "EVENT_NAME": "pull_request",
                "IS_DRAFT": draft,
                "BASE_SHA": base_sha,
                "HEAD_SHA": head_sha,
                "GITHUB_OUTPUT": str(output_file),
            },
            capture_output=True,
            text=True,
        )
        return result.returncode, output_file.read_text()

    assert select(base, head) == (0, "required=true\n")
    (tmp_path / "README.md").write_text("Documentation\n")
    git("add", ".")
    git("commit", "-m", "unrelated documentation")
    assert select(head, "HEAD") == (0, "required=false\n")
    assert select("invalid-ref", "HEAD")[0] != 0
    assert select(base, "HEAD", draft="true") == (0, "required=false\n")
