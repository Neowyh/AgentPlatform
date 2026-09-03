"""Tests for the generic (non-fault-zeroing) agent installer.

Ticket 06: the legacy fault-zeroing install path was removed; the generic
installer keeps serving agents that are not covered by the canonical bundled
resource module.
"""

import ast
import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_agent.py"

SPEC = importlib.util.spec_from_file_location("install_agent_generic", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
install_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_script)


def make_agent_source(source_dir: Path, name: str = "sample-agent") -> None:
    source_dir.mkdir()
    (source_dir / "config.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    (source_dir / "SOUL.md").write_text("# Soul\n", encoding="utf-8")


def test_installer_uses_only_standard_library_imports_for_offline_deploy_hosts() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert "yaml" not in imported_modules
    assert "ideer" not in imported_modules


def test_legacy_fault_zeroing_install_path_is_gone() -> None:
    """The fault-zeroing install shim must not come back (ticket 06)."""

    assert not (REPO_ROOT / "scripts" / "install_fault_zeroing_agent.py").exists()
    source_text = SCRIPT_PATH.read_text(encoding="utf-8")
    # The generic installer must not carry fault-zeroing-specific code.
    assert "merge_fault_zeroing_subagents" not in source_text
    assert "REQUIRED_SUBAGENTS" not in source_text
    assert "AGENT_NAME" not in source_text
    assert "install_fault_zeroing_agent" not in source_text
    # The subagent merge helpers are gone too.
    for helper in (
        "_extract_agent_blocks",
        "_has_subagent",
        "_subagent_description",
        "_find_top_level_block",
    ):
        assert helper not in source_text


def test_install_agent_defaults_to_shared_agent_dir(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    make_agent_source(source_dir)

    target_dir, status = install_script.install_agent(
        agent_name="sample-agent",
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert target_dir == base_dir / "agents" / "sample-agent"
    assert status == "copied"
    assert (target_dir / "config.yaml").read_text(encoding="utf-8") == "name: sample-agent\n"
    assert (target_dir / "SOUL.md").read_text(encoding="utf-8") == "# Soul\n"


def test_install_agent_skips_when_files_match(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "sample-agent"
    make_agent_source(source_dir)
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")
    shutil.copy2(source_dir / "SOUL.md", target_dir / "SOUL.md")

    installed_dir, status = install_script.install_agent(
        agent_name="sample-agent",
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert installed_dir == target_dir
    assert status == "skipped"


def test_install_agent_refuses_to_overwrite_different_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "sample-agent"
    make_agent_source(source_dir, soul="# New Soul\n") if False else make_agent_source(source_dir)
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")
    existing_soul = target_dir / "SOUL.md"
    existing_soul.write_text("# Existing Soul\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="local customizations"):
        install_script.install_agent(
            agent_name="sample-agent",
            source_dir=source_dir,
            base_dir=base_dir,
        )

    assert existing_soul.read_text(encoding="utf-8") == "# Existing Soul\n"


def test_install_agent_refuses_partial_existing_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    target_dir = base_dir / "agents" / "sample-agent"
    make_agent_source(source_dir)
    target_dir.mkdir(parents=True)
    shutil.copy2(source_dir / "config.yaml", target_dir / "config.yaml")

    with pytest.raises(FileExistsError, match="partially installed"):
        install_script.install_agent(
            agent_name="sample-agent",
            source_dir=source_dir,
            base_dir=base_dir,
        )

    assert not (target_dir / "SOUL.md").exists()


def test_install_agent_keeps_user_id_compatibility(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    base_dir = tmp_path / "runtime"
    make_agent_source(source_dir)

    target_dir, status = install_script.install_agent(
        agent_name="sample-agent",
        user_id="user-123",
        source_dir=source_dir,
        base_dir=base_dir,
    )

    assert target_dir == base_dir / "users" / "user-123" / "agents" / "sample-agent"
    assert status == "copied"


def test_default_base_dir_uses_ideer_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime_home = tmp_path / "runtime-home"
    monkeypatch.setenv("IDEER_HOME", str(runtime_home))

    assert install_script.default_base_dir() == runtime_home.resolve()


def test_resolve_config_path_uses_ideer_config_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    assert install_script.resolve_config_path() == config_path.resolve()


def test_main_installs_named_agent_and_upserts_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "source"
    make_agent_source(source_dir, "srs-writing")
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
    monkeypatch.setattr(install_script, "default_source_dir", lambda agent_name: source_dir)
    monkeypatch.setenv("IDEER_HOME", str(runtime_dir))

    exit_code = install_script.main(["--agent", "srs-writing", "--owner", "super-admin"])

    assert exit_code == 0
    target_dir = runtime_dir / "users" / "super-admin-id" / "agents" / "srs-writing"
    assert (target_dir / "config.yaml").is_file()
    with sqlite3.connect(db_path) as connection:
        metadata = connection.execute("SELECT resource_type, resource_id, owner_id, department_id, visibility, version, is_favorited FROM resource_metadata").fetchone()
    assert metadata == ("agent", "srs-writing", "super-admin-id", None, "public", 1, 0)
    assert "Agent directory" in capsys.readouterr().out


def test_main_requires_agent_argument() -> None:
    with pytest.raises(SystemExit):
        install_script.main([])


def test_registry_module_import_does_not_eagerly_import_executor() -> None:
    import os
    import subprocess
    import sys

    code = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path('backend/packages/harness').resolve()))
from ideer.subagents.registry import get_subagent_config
print(callable(get_subagent_config))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "backend" / "packages" / "harness")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
