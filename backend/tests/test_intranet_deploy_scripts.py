"""Regression tests for intranet offline deployment scripts."""

from __future__ import annotations

import os
import stat
import subprocess
import tarfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-intranet.sh"
PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package-intranet-offline.sh"
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_fault_zeroing_agent.py"
COMPOSE_FILE = REPO_ROOT / "docker" / "docker-compose.intranet.yaml"
GUIDE_FILE = REPO_ROOT / "docs" / "deployment" / "禁公网内网离线部署作业指导书.md"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_docker_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    _write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env sh
set -eu
if [ "$1" = "compose" ] && [ "${2:-}" = "version" ]; then
  exit 0
fi
if [ "$1" = "compose" ]; then
  shift
  exit 0
fi
if [ "$1" = "info" ]; then
  exit 0
fi
if [ "$1" = "build" ]; then
  exit 0
fi
if [ "$1" = "pull" ]; then
  exit 0
fi
if [ "$1" = "save" ]; then
  out=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then
      out="$2"
      shift 2
      continue
    fi
    shift
  done
  [ -n "$out" ] || exit 2
  printf 'fake image tar\\n' > "$out"
  exit 0
fi
if [ "$1" = "load" ]; then
  exit 0
fi
echo "unexpected docker invocation: $*" >&2
exit 99
""",
    )
    return bin_dir


def _env_with_fake_docker(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{_fake_docker_bin(tmp_path)}:{env['PATH']}"
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir()
    return env


def _write_source_tree(root: Path, *, include_frontend_env: bool = True) -> None:
    (root / "backend").mkdir(parents=True)
    (root / "frontend").mkdir(parents=True)
    (root / "docker" / "nginx").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "docs" / "fault-zeroing-agent" / "agent").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "README.md").write_text("test\n", encoding="utf-8")
    (root / "Makefile").write_text("help:\n\t@true\n", encoding="utf-8")
    (root / "backend" / "placeholder.txt").write_text("backend\n", encoding="utf-8")
    (root / "frontend" / "placeholder.txt").write_text("frontend\n", encoding="utf-8")
    (root / "docker" / "nginx" / "nginx.conf").write_text("events {}\n", encoding="utf-8")
    (root / "docker" / "docker-compose.intranet.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / "config.example.yaml").write_text(
        """config_version: 10
log_level: info
token_usage:
  enabled: true
models:
sandbox:
  use: deerflow.sandbox.local.local_sandbox_provider:LocalSandboxProvider
""",
        encoding="utf-8",
    )
    (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    if include_frontend_env:
        (root / "frontend" / ".env.example").write_text(
            "# frontend env\n",
            encoding="utf-8",
        )
    (root / "extensions_config.example.json").write_text(
        '{"mcpServers":{},"skills":{}}\n',
        encoding="utf-8",
    )
    (root / "docs" / "fault-zeroing-agent" / "agent" / "config.yaml").write_text(
        "name: fault-zeroing\n",
        encoding="utf-8",
    )
    (root / "docs" / "fault-zeroing-agent" / "agent" / "SOUL.md").write_text(
        "# Fault Zeroing\n",
        encoding="utf-8",
    )
    (root / "docs" / "fault-zeroing-agent" / "subagents.yaml").write_text(
        """subagents:
  custom_agents:
    evidence-reader:
      description: evidence-reader
    fault-tree-builder:
      description: fault-tree-builder
    probability-assessor:
      description: probability-assessor
    root-cause-analyst:
      description: root-cause-analyst
    report-reviewer:
      description: report-reviewer
""",
        encoding="utf-8",
    )
    _write_executable(root / "scripts" / "install_fault_zeroing_agent.py", INSTALL_SCRIPT.read_text(encoding="utf-8"))


def _make_bundle(tmp_path: Path, *, version: str = "test", include_frontend_env: bool = True) -> Path:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir(parents=True)
    source_root = tmp_path / "source-input"
    _write_source_tree(source_root, include_frontend_env=include_frontend_env)
    with tarfile.open(bundle_root / f"deer-flow-source-{version}.tar.gz", "w:gz") as tar:
        for child in source_root.iterdir():
            tar.add(child, arcname=child.name)
    (bundle_root / f"deer-flow-images-{version}.tar").write_text("fake images\n", encoding="utf-8")
    return bundle_root


def _run_deploy(bundle_root: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), "--bundle-root", str(bundle_root), "--version", "test", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_packaged_deploy_script_defaults_to_its_bundle_directory(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    packaged_script = bundle_root / "deploy-intranet.sh"
    packaged_script.write_text(DEPLOY_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    proc = subprocess.run(
        ["bash", "./deploy-intranet.sh", "prepare"],
        cwd=bundle_root,
        env=_env_with_fake_docker(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert (bundle_root / "runtime" / "config.yaml").is_file()
    assert (bundle_root / "env.intranet").is_file()


def test_up_fails_when_frontend_route_is_unhealthy(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)
    bin_dir = Path(env["PATH"].split(":", 1)[0])
    _write_executable(
        bin_dir / "curl",
        """#!/usr/bin/env sh
set -eu
url=""
for arg in "$@"; do
  url="$arg"
done
case "$url" in
  */health|*/api/v1/auth/setup-status)
    exit 0
    ;;
  */)
    exit 22
    ;;
esac
exit 22
""",
    )
    _write_executable(
        bin_dir / "sleep",
        """#!/usr/bin/env sh
exit 0
""",
    )

    proc = _run_deploy(bundle_root, "--no-load", "up", env=env)

    assert proc.returncode != 0
    assert "frontend health check failed" in proc.stderr


def test_prepare_seeds_valid_runtime_config_and_stable_auth_files(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    runtime_dir = bundle_root / "runtime"
    cfg = yaml.safe_load((runtime_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["models"] == []
    assert (runtime_dir / "frontend.env").is_file()
    assert (runtime_dir / "data" / ".better-auth-secret").is_file()
    assert (runtime_dir / "data" / ".internal-auth-token").is_file()

    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert f"DEER_FLOW_FRONTEND_ENV_FILE={runtime_dir}/frontend.env" in env_text
    assert "BETTER_AUTH_SECRET=" in env_text
    assert "DEER_FLOW_INTERNAL_AUTH_TOKEN=" in env_text


def test_prepare_installs_fault_zeroing_agent_to_shared_runtime_dir(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    runtime_dir = bundle_root / "runtime"
    agent_dir = runtime_dir / "data" / "agents" / "fault-zeroing"
    assert (agent_dir / "config.yaml").read_text(encoding="utf-8") == "name: fault-zeroing\n"
    assert (agent_dir / "SOUL.md").read_text(encoding="utf-8") == "# Fault Zeroing\n"
    cfg = yaml.safe_load((runtime_dir / "config.yaml").read_text(encoding="utf-8"))
    assert set(cfg["subagents"]["custom_agents"]) == {
        "evidence-reader",
        "fault-tree-builder",
        "probability-assessor",
        "root-cause-analyst",
        "report-reviewer",
    }
    assert "Agent directory:" in proc.stdout
    assert "Registry check passed:" in proc.stdout


def test_prepare_does_not_install_fault_zeroing_agent_to_user_dirs(tmp_path: Path):
    """Shared-only install: agent should NOT be copied to per-user directories."""
    bundle_root = _make_bundle(tmp_path)
    user_dir = bundle_root / "runtime" / "data" / "users" / "alice"
    user_dir.mkdir(parents=True)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    runtime_dir = bundle_root / "runtime"
    # Shared agent should exist
    assert (runtime_dir / "data" / "agents" / "fault-zeroing" / "config.yaml").is_file()
    # Per-user agent should NOT exist
    assert not (user_dir / "agents" / "fault-zeroing" / "config.yaml").exists()
    assert "installing bundled fault-zeroing agent for existing user" not in proc.stdout


def test_prepare_skips_fault_zeroing_install_when_disabled(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)
    env["DEER_FLOW_INSTALL_FAULT_ZEROING"] = "0"

    proc = _run_deploy(bundle_root, "prepare", env=env)

    assert proc.returncode == 0, proc.stderr
    assert not (bundle_root / "runtime" / "data" / "agents" / "fault-zeroing").exists()
    cfg = yaml.safe_load((bundle_root / "runtime" / "config.yaml").read_text(encoding="utf-8"))
    assert "subagents" not in cfg


def test_status_logs_and_stop_do_not_install_fault_zeroing_agent(tmp_path: Path):
    for command in ("status", "logs", "stop"):
        bundle_root = _make_bundle(tmp_path / command)
        proc = _run_deploy(bundle_root, command, env=_env_with_fake_docker(tmp_path / f"{command}-env"))

        assert proc.returncode == 0, proc.stderr
        assert not (bundle_root / "runtime" / "data" / "agents" / "fault-zeroing").exists()


def test_prepare_reuses_persisted_auth_secrets_when_env_file_is_recreated(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)

    first = _run_deploy(bundle_root, "prepare", env=env)
    assert first.returncode == 0, first.stderr
    runtime_dir = bundle_root / "runtime"
    better_secret = (runtime_dir / "data" / ".better-auth-secret").read_text(encoding="utf-8").strip()
    internal_token = (runtime_dir / "data" / ".internal-auth-token").read_text(encoding="utf-8").strip()
    (bundle_root / "env.intranet").unlink()

    second = _run_deploy(bundle_root, "prepare", env=env)

    assert second.returncode == 0, second.stderr
    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert f"BETTER_AUTH_SECRET={better_secret}" in env_text
    assert f"DEER_FLOW_INTERNAL_AUTH_TOKEN={internal_token}" in env_text


def test_prepare_backfills_auth_secrets_into_existing_env_file(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)
    (bundle_root / "env.intranet").write_text(
        """PORT=3001
DEER_FLOW_GATEWAY_IMAGE=deer-flow-gateway:old
DEER_FLOW_FRONTEND_IMAGE=deer-flow-frontend:old
NGINX_IMAGE=nginx:alpine
""",
        encoding="utf-8",
    )

    first = _run_deploy(bundle_root, "prepare", env=env)
    second = _run_deploy(bundle_root, "prepare", env=env)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    runtime_dir = bundle_root / "runtime"
    better_secret = (runtime_dir / "data" / ".better-auth-secret").read_text(encoding="utf-8").strip()
    internal_token = (runtime_dir / "data" / ".internal-auth-token").read_text(encoding="utf-8").strip()
    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert "PORT=3001" in env_text
    assert "DEER_FLOW_GATEWAY_IMAGE=deer-flow-gateway:old" in env_text
    assert f"BETTER_AUTH_SECRET={better_secret}" in env_text
    assert f"DEER_FLOW_INTERNAL_AUTH_TOKEN={internal_token}" in env_text
    assert env_text.count("BETTER_AUTH_SECRET=") == 1
    assert env_text.count("DEER_FLOW_INTERNAL_AUTH_TOKEN=") == 1


def test_prepare_reports_missing_seed_source_with_actionable_error(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path, include_frontend_env=False)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode != 0
    assert "missing seed source:" in proc.stderr
    assert "frontend/.env.example" in proc.stderr


def test_package_script_documents_runtime_contract_and_excludes_local_artifacts():
    script = PACKAGE_SCRIPT.read_text(encoding="utf-8")

    assert "--exclude='frontend/.env'" in script
    assert "--exclude='frontend/test-results'" in script
    assert "--exclude='frontend/playwright-report'" in script
    assert "--exclude='frontend/tsconfig.tsbuildinfo'" in script
    assert "--exclude='backend/.ruff_cache'" in script
    assert "Use ./deploy-intranet.sh" in script
    assert "generates env.intranet plus runtime/* files during prepare" in script


def test_package_source_archive_includes_runtime_seed_templates(tmp_path: Path):
    output_dir = tmp_path / "bundle"
    env = _env_with_fake_docker(tmp_path)

    proc = subprocess.run(
        [
            "bash",
            str(PACKAGE_SCRIPT),
            "--version",
            "test",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    with tarfile.open(output_dir / "deer-flow-source-test.tar.gz", "r:gz") as tar:
        names = set(tar.getnames())

    assert ".env.example" in names
    assert "config.example.yaml" in names
    assert "extensions_config.example.json" in names
    assert "frontend/.env.example" in names
    assert "frontend/.env" not in names
    assert not (output_dir / "docker-compose.intranet.yaml").exists()
    assert not (output_dir / "env.intranet.example").exists()

    manifest = (output_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    sha256sums = (output_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "- docker-compose.intranet.yaml" not in manifest
    assert "env.intranet.example" not in manifest
    assert "docker-compose.intranet.yaml" not in sha256sums
    assert "env.intranet.example" not in sha256sums


def test_intranet_compose_uses_runtime_env_contract_and_internal_token():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "${DEER_FLOW_FRONTEND_ENV_FILE:?DEER_FLOW_FRONTEND_ENV_FILE must be set}" in compose
    assert "${DEER_FLOW_ENV_FILE:?DEER_FLOW_ENV_FILE must be set}" in compose
    assert "DEER_FLOW_INTERNAL_AUTH_TOKEN=${DEER_FLOW_INTERNAL_AUTH_TOKEN}" in compose


def test_intranet_gateway_startup_does_not_sync_dependencies():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "uv run --no-sync uvicorn app.gateway.app:app" in compose


def test_intranet_runbook_points_frontend_env_to_runtime_file():
    guide = GUIDE_FILE.read_text(encoding="utf-8")

    assert "runtime/frontend.env" in guide
    assert "脚本所在目录" in guide
    assert "find runtime -maxdepth 4 -type f | sort" in guide
    assert "ls runtime/data" not in guide
    assert "source/docker/docker-compose.intranet.yaml" in guide
    assert "docker-compose.intranet.yaml\n" not in guide
    assert "env.intranet.example" not in guide
    assert "frontend` 启动失败：确认 `frontend/.env` 存在" not in guide
    assert "登录后无法进入主页" in guide
    assert "frontend is healthy: http://127.0.0.1:2026/" in guide
    assert "curl -fsS http://127.0.0.1:2026/" in guide
