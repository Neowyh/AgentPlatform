import ast
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "install_fault_zeroing_agent.py"
SPEC = importlib.util.spec_from_file_location("install_fault_zeroing_agent", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
install_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_script)
install_fault_zeroing_agent = install_script.install_fault_zeroing_agent
BUNDLED_WORKFLOW_FILES = install_script.BUNDLED_WORKFLOW_FILES


def make_agent_source(source_dir: Path, *, soul: str = "# Soul\n") -> None:
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text("name: fault-zeroing\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text(soul, encoding="utf-8")


def test_installer_uses_only_standard_library_imports_for_offline_deploy_hosts() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert "yaml" not in imported_modules
    assert "ideer" not in imported_modules


def test_install_fault_zeroing_agent_defaults_to_shared_agent_dir(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    make_agent_source(source_dir)

    target_dir, status = install_fault_zeroing_agent(
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert target_dir == base_dir / "agents" / "fault-zeroing"
    assert status == "copied"
    assert (target_dir / "config.yaml").read_text(encoding="utf-8") == "name: fault-zeroing\n"
    assert (target_dir / "SOUL.md").read_text(encoding="utf-8") == "# Soul\n"


def test_install_fault_zeroing_agent_skips_when_files_match(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "fault-zeroing"
    make_agent_source(source_dir)
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")
    shutil.copy2(source_dir / "SOUL.md", target_dir / "SOUL.md")

    installed_dir, status = install_fault_zeroing_agent(
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert installed_dir == target_dir
    assert status == "skipped"


def test_install_fault_zeroing_agent_refuses_to_overwrite_different_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "fault-zeroing"
    make_agent_source(source_dir, soul="# New Soul\n")
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")
    existing_soul = target_dir / "SOUL.md"
    existing_soul.write_text("# Existing Soul\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="local customizations"):
        install_fault_zeroing_agent(
            source_dir=source_dir,
            base_dir=base_dir,
        )

    assert existing_soul.read_text(encoding="utf-8") == "# Existing Soul\n"


def test_install_fault_zeroing_agent_refuses_partial_existing_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "fault-zeroing"
    make_agent_source(source_dir)
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")

    with pytest.raises(FileExistsError, match="partially installed"):
        install_fault_zeroing_agent(
            source_dir=source_dir,
            base_dir=base_dir,
        )

    assert not (target_dir / "SOUL.md").exists()


def test_install_fault_zeroing_agent_keeps_user_id_compatibility(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    make_agent_source(source_dir)

    target_dir, status = install_fault_zeroing_agent(
        user_id="user-123",
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert target_dir == base_dir / "users" / "user-123" / "agents" / "fault-zeroing"
    assert status == "copied"


def test_default_base_dir_uses_deer_flow_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("IDEER_HOME", str(runtime_home))

    assert install_script.default_base_dir() == runtime_home.resolve()


def test_resolve_config_path_uses_deer_flow_config_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    assert install_script.resolve_config_path() == config_path.resolve()


def test_bundled_workflow_files_present_in_repo() -> None:
    missing = [name for name in BUNDLED_WORKFLOW_FILES if not (install_script.repo_root() / name).is_file()]
    assert missing == [], f"Bundled workflow files missing from repo: {missing}"


def test_bundled_workflow_file_check_reports_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing bundled workflow file"):
        install_script._validate_bundled_workflow_files(tmp_path)


def test_bundled_workflow_file_check_accepts_present_files(tmp_path: Path) -> None:
    for name in BUNDLED_WORKFLOW_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test\n", encoding="utf-8")

    install_script._validate_bundled_workflow_files(tmp_path)


def test_install_agent_installs_srs_writing_to_shared_dir(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text("# Soul\n", encoding="utf-8")

    target_dir, status = install_script.install_agent(
        agent_name="srs-writing",
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert target_dir == base_dir / "agents" / "srs-writing"
    assert status == "copied"
    assert (target_dir / "config.yaml").read_text(encoding="utf-8") == "name: srs-writing\n"
    assert (target_dir / "SOUL.md").read_text(encoding="utf-8") == "# Soul\n"


def test_main_skips_subagent_merge_when_subagents_file_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    monkeypatch.setattr(install_script, "default_source_dir", lambda agent_name="fault-zeroing": source_dir)
    monkeypatch.setattr(install_script, "default_subagents_file", lambda agent_name="fault-zeroing": tmp_path / "subagents.yaml")
    monkeypatch.setenv("IDEER_HOME", str(tmp_path / "runtime"))

    exit_code = install_script.main(["--agent", "srs-writing"])

    assert exit_code == 0
    assert (tmp_path / "runtime" / "agents" / "srs-writing" / "config.yaml").is_file()
    assert "none - no bundled subagents.yaml" in capsys.readouterr().out


def test_install_agent_owner_super_admin_installs_to_per_user_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    runtime_dir = tmp_path / "runtime"
    db_path = runtime_dir / "data" / "ideer.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users_ext (id TEXT PRIMARY KEY, role TEXT NOT NULL, disabled INTEGER NOT NULL);
            INSERT INTO users_ext VALUES ('super-admin-id', 'super_admin', 0);
            CREATE TABLE resource_metadata (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                department_id TEXT,
                visibility TEXT NOT NULL,
                version INTEGER NOT NULL,
                is_favorited INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(resource_type, resource_id, owner_id)
            );
            """
        )

    monkeypatch.setattr(install_script, "default_source_dir", lambda agent_name="fault-zeroing": source_dir)
    monkeypatch.setattr(
        install_script,
        "default_subagents_file",
        lambda agent_name="fault-zeroing": tmp_path / "subagents.yaml",
    )
    monkeypatch.setenv("IDEER_HOME", str(runtime_dir))

    exit_code = install_script.main(["--agent", "srs-writing", "--owner", "super-admin"])

    assert exit_code == 0
    target_dir = runtime_dir / "users" / "super-admin-id" / "agents" / "srs-writing"
    assert (target_dir / "config.yaml").is_file()
    with sqlite3.connect(db_path) as connection:
        metadata = connection.execute("SELECT resource_type, resource_id, owner_id, department_id, visibility, version, is_favorited FROM resource_metadata").fetchone()
    assert metadata == ("agent", "srs-writing", "super-admin-id", None, "public", 1, 0)


def test_install_agent_owner_missing_super_admin_reports_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    runtime_dir = tmp_path / "runtime"
    db_path = runtime_dir / "data" / "ideer.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE users_ext (id TEXT PRIMARY KEY, role TEXT NOT NULL, disabled INTEGER NOT NULL)")

    monkeypatch.setattr(install_script, "default_source_dir", lambda agent_name="fault-zeroing": source_dir)
    monkeypatch.setenv("IDEER_HOME", str(runtime_dir))

    exit_code = install_script.main(["--agent", "srs-writing", "--owner", "super-admin"])

    assert exit_code == 1
    assert "super_admin not found in" in capsys.readouterr().err
    assert not (runtime_dir / "users").exists()


def test_registry_module_import_does_not_eagerly_import_executor() -> None:
    code = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path('backend/packages/harness').resolve()))
from ideer.subagents.registry import get_subagent_config
print(callable(get_subagent_config))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPT_PATH.parents[1] / "backend" / "packages" / "harness")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SCRIPT_PATH.parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
