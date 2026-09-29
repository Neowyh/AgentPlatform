import ast
import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "install_srs_writing_agent.py"
SPEC = importlib.util.spec_from_file_location("install_srs_writing_agent", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
install_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_script)

SAMPLE_CONFIG = """config_version: 10
tool_groups:
- name: web
- name: bash
tools:
- name: read_file
  group: file:read
  use: deerflow.sandbox.tools:read_file_tool
- name: bash
  group: bash
  use: deerflow.sandbox.tools:bash_tool
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
"""


def write_sample_config(path: Path) -> Path:
    path.write_text(SAMPLE_CONFIG, encoding="utf-8")
    return path


def test_help_and_docstring_position_installer_as_legacy_local_tool(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Docs must mark this installer as legacy local-dev; distribution is seeded."""
    docstring = install_script.__doc__ or ""
    assert "legacy" in docstring.lower()
    assert "Bundled resource seed" in docstring
    assert "allow_host_bash" in docstring

    with pytest.raises(SystemExit):
        install_script.parse_args(["--help"])
    help_text = capsys.readouterr().out
    assert "legacy" in help_text.lower()
    assert "Bundled resource seed" in help_text
    assert "arbitrary commands" in help_text


def test_installer_uses_only_standard_library_imports_for_offline_deploy_hosts() -> None:
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported_modules = {alias.name.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_modules.update(node.module.split(".", 1)[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)

    assert "yaml" not in imported_modules
    assert "ideer" not in imported_modules


def test_wire_srs_config_adds_and_is_idempotent(tmp_path: Path) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")

    first = install_script.wire_srs_config(config_path, enable_host_bash=True)
    assert first["changed"] is True
    assert first["actions"]["document_tool_group"] == "added"
    assert first["actions"]["read_document_tool"] == "added"
    assert first["actions"]["allow_host_bash"] == "changed"
    assert first["backup_path"] is not None
    assert Path(first["backup_path"]).is_file()

    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert {"name": "document"} in parsed["tool_groups"]
    assert {
        "name": "read_document",
        "group": "document",
        "use": "app.agentplatform.community.doc_reader.tools:read_document_tool",
    } in parsed["tools"]
    assert parsed["sandbox"]["allow_host_bash"] is True

    text = config_path.read_text(encoding="utf-8")
    assert text.count("- name: document") == 1
    assert text.count("- name: read_document") == 1
    assert text.count("allow_host_bash: true") == 1

    second = install_script.wire_srs_config(config_path, enable_host_bash=True)
    assert second["changed"] is False
    assert set(second["actions"].values()) == {"present"}
    assert config_path.read_text(encoding="utf-8") == text


def test_wire_srs_config_default_leaves_allow_host_bash_untouched(tmp_path: Path) -> None:
    """Default install must not widen permissions: host bash stays as-is."""
    config_path = write_sample_config(tmp_path / "config.yaml")

    result = install_script.wire_srs_config(config_path)

    assert "allow_host_bash" not in result["actions"]
    assert "allow_host_bash: false" in config_path.read_text(encoding="utf-8")


def test_wire_srs_config_default_does_not_create_allow_host_bash(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("config_version: 10\ntool_groups:\n- name: web\n", encoding="utf-8")

    install_script.wire_srs_config(config_path)

    assert "allow_host_bash" not in config_path.read_text(encoding="utf-8")


def test_wire_srs_config_dry_run_writes_nothing(tmp_path: Path) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    before = config_path.read_text(encoding="utf-8")

    result = install_script.wire_srs_config(config_path, dry_run=True)

    assert result["changed"] is True
    assert result["backup_path"] is None
    assert config_path.read_text(encoding="utf-8") == before


def test_wire_srs_config_single_backup_across_runs(tmp_path: Path) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    install_script.wire_srs_config(config_path)
    backup = config_path.with_name("config.yaml.bak-before-srs-agent")
    assert backup.is_file()
    first_inode = backup.stat().st_ino

    install_script.wire_srs_config(config_path)
    assert backup.stat().st_ino == first_inode


def test_provision_officecli_lifecycle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "vendor" / "officecli" / "officecli"
    source.parent.mkdir(parents=True)
    source.write_text("binary", encoding="utf-8")
    bin_path = tmp_path / "bin" / "officecli"

    assert install_script.provision_officecli(repo, bin_path=bin_path, dry_run=True)["status"] == "will_create"
    assert not bin_path.exists()

    assert install_script.provision_officecli(repo, bin_path=bin_path)["status"] == "created"
    assert install_script.provision_officecli(repo, bin_path=bin_path)["status"] == "linked"
    assert install_script.officecli_available(bin_path, bundled=source) is True


def test_provision_officecli_conflict_requires_force(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "vendor" / "officecli" / "officecli"
    source.parent.mkdir(parents=True)
    source.write_text("binary", encoding="utf-8")
    bin_path = tmp_path / "bin" / "officecli"
    bin_path.parent.mkdir(parents=True)
    bin_path.write_text("something else", encoding="utf-8")

    assert install_script.provision_officecli(repo, bin_path=bin_path)["status"] == "conflict"
    assert bin_path.read_text(encoding="utf-8") == "something else"

    assert install_script.provision_officecli(repo, bin_path=bin_path, force=True)["status"] == "replaced"
    assert install_script.officecli_available(bin_path, bundled=source) is True


def test_provision_officecli_replaces_dangling_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "vendor" / "officecli" / "officecli"
    source.parent.mkdir(parents=True)
    source.write_text("binary", encoding="utf-8")
    bin_path = tmp_path / "bin" / "officecli"
    bin_path.parent.mkdir(parents=True)
    bin_path.symlink_to(tmp_path / "gone" / "officecli")

    result = install_script.provision_officecli(repo, bin_path=bin_path)

    assert result["status"] == "replaced"
    assert install_script.officecli_available(bin_path, bundled=source) is True
    assert bin_path.resolve() == source.resolve()


def test_provision_officecli_reuses_content_equivalent_existing_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source = repo / "vendor" / "officecli" / "officecli"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"bundled binary")
    bin_path = tmp_path / "bin" / "officecli"
    bin_path.parent.mkdir(parents=True)
    bin_path.write_bytes(source.read_bytes())

    result = install_script.provision_officecli(repo, bin_path=bin_path)

    assert result["status"] == "equivalent"
    assert bin_path.read_bytes() == source.read_bytes()
    assert install_script.officecli_available(bin_path, bundled=source) is True


def test_provision_officecli_missing_source(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    result = install_script.provision_officecli(repo, bin_path=tmp_path / "bin" / "officecli")
    assert result["status"] == "missing_source"


def test_bundled_agent_and_officecli_present_in_repo() -> None:
    repo_root = install_script.repo_root()
    for path in (
        repo_root / "resources" / "agents" / "srs-writing" / "config.yaml",
        repo_root / "resources" / "agents" / "srs-writing" / "SOUL.md",
        repo_root / "vendor" / "officecli" / "officecli",
    ):
        assert path.is_file(), f"Bundled path missing: {path}"


@pytest.mark.parametrize(
    ("config_text", "host_bash_expected", "expected_ok"),
    [
        ("sandbox:\n  allow_host_bash: false\n", False, True),
        ("config_version: 1\n", False, True),
        ("sandbox:\n  allow_host_bash: true\n", False, False),
        ("sandbox:\n  allow_host_bash: true\n", True, True),
        ("sandbox:\n  allow_host_bash: false\n", True, False),
    ],
)
def test_verify_install_allow_host_bash_semantics(
    tmp_path: Path,
    config_text: str,
    host_bash_expected: bool,
    expected_ok: bool,
) -> None:
    """The host-bash check mirrors the install mode: expected off by default."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_text, encoding="utf-8")

    report = install_script.verify_install(
        config_path,
        owner_id=None,
        require_officecli=False,
        host_bash_expected=host_bash_expected,
    )

    assert report["checks"]["allow_host_bash"] is expected_ok


def test_verify_install_reports_state(tmp_path: Path) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    install_script.wire_srs_config(config_path)
    report = install_script.verify_install(config_path, owner_id=None)

    assert report["checks"]["config_yaml"] is True
    assert report["checks"]["document_group"] is True
    assert report["checks"]["read_document_tool"] is True
    # Default mode expects host bash off; the sample config keeps it false.
    assert report["checks"]["allow_host_bash"] is True
    assert report["checks"]["agent_files"] is False


def test_main_installs_agent_and_wires_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    source = tmp_path / "agent-src"
    source.mkdir(parents=True)
    (source / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    config_path = write_sample_config(tmp_path / "config.yaml")

    import install_agent

    monkeypatch.setattr(install_agent, "default_source_dir", lambda agent_name: source)
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(runtime))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    exit_code = install_script.main(["--agent", "srs-writing", "--user-id", "user-1", "--no-officecli"])

    assert exit_code == 0
    agent_dir = runtime / "users" / "user-1" / "agents" / "srs-writing"
    assert (agent_dir / "config.yaml").is_file()
    assert (agent_dir / "SOUL.md").is_file()
    assert install_script._has_document_tool_group(config_path.read_text(encoding="utf-8").splitlines(keepends=True))

    # Running again is a no-op for the agent plus config, and stays green.
    assert install_script.main(["--agent", "srs-writing", "--user-id", "user-1", "--no-officecli"]) == 0
    assert config_path.read_text(encoding="utf-8").count("- name: document") == 1

    # Default install (no --host-bash) verifies green without allow_host_bash.
    assert install_script.main(["--agent", "srs-writing", "--user-id", "user-1", "--no-officecli", "--verify-only"]) == 0


def test_main_host_bash_flag_enables_and_warns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--host-bash is the explicit opt-in and must print the risk warning."""
    runtime = tmp_path / "runtime"
    source = tmp_path / "agent-src"
    source.mkdir(parents=True)
    (source / "config.yaml").write_text("name: srs-writing\n", encoding="utf-8")
    (source / "SOUL.md").write_text("# Soul\n", encoding="utf-8")
    config_path = write_sample_config(tmp_path / "config.yaml")

    import install_agent

    monkeypatch.setattr(install_agent, "default_source_dir", lambda agent_name: source)
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(runtime))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    exit_code = install_script.main(["--host-bash", "--user-id", "user-1", "--no-officecli"])

    assert exit_code == 0
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert parsed["sandbox"]["allow_host_bash"] is True
    output = capsys.readouterr().out
    assert "arbitrary commands on the host" in output
    assert "授权智能体在宿主机执行任意命令" in output


def test_main_dry_run_host_bash_flag_shows_plan_and_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    before = config_path.read_text(encoding="utf-8")
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(tmp_path / "runtime"))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    exit_code = install_script.main(["--dry-run", "--host-bash", "--skip-agent", "--no-officecli", "--user-id", "user-1"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "set sandbox.allow_host_bash = true" in output
    assert "arbitrary commands on the host" in output
    assert config_path.read_text(encoding="utf-8") == before


def test_main_no_host_bash_flag_is_deprecated_noop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--no-host-bash stays accepted for old automation but is a no-op."""
    config_path = write_sample_config(tmp_path / "config.yaml")
    before = config_path.read_text(encoding="utf-8")
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(tmp_path / "runtime"))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    exit_code = install_script.main(["--no-host-bash", "--dry-run", "--skip-agent", "--no-officecli", "--user-id", "user-1"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "deprecated" in output.lower()
    assert "sandbox.allow_host_bash" not in output
    assert config_path.read_text(encoding="utf-8") == before


def test_host_bash_flags_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        install_script.parse_args(["--host-bash", "--no-host-bash"])


def test_main_verify_only_reports_current_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(tmp_path / "runtime"))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    # Nothing installed yet: verify-only reports the gaps without side effects.
    exit_code = install_script.main(["--verify-only", "--user-id", "user-1"])

    assert exit_code == 1
    assert not (tmp_path / "runtime").exists()


def test_main_dry_run_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = write_sample_config(tmp_path / "config.yaml")
    before = config_path.read_text(encoding="utf-8")
    monkeypatch.delenv("DEER_FLOW_HOME", raising=False)
    monkeypatch.setenv("IDEER_HOME", str(tmp_path / "runtime"))
    monkeypatch.setenv("IDEER_CONFIG_PATH", str(config_path))

    exit_code = install_script.main(["--dry-run", "--user-id", "user-1"])

    assert exit_code == 0
    assert "allow_host_bash" not in capsys.readouterr().out
    assert config_path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "runtime").exists()
