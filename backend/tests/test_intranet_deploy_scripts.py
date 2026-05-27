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
COMPOSE_FILE = REPO_ROOT / "docker" / "docker-compose.intranet.yaml"
GUIDE_FILE = REPO_ROOT / "docs" / "deployment" / "禁公网内网离线部署作业指导书.md"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_docker_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
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


def _make_bundle(tmp_path: Path, *, version: str = "test", include_frontend_env: bool = True) -> Path:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
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

    assert "/home/deploy/deer-flow is only an example bundle root" in script
    assert "DEER_FLOW_BUNDLE_ROOT" in script
    assert "DEER_FLOW_INTERNAL_AUTH_TOKEN=replace-with-a-fixed-internal-token" in script
    assert "--exclude='frontend/.env'" in script
    assert "--exclude='frontend/test-results'" in script
    assert "--exclude='frontend/playwright-report'" in script
    assert "--exclude='frontend/tsconfig.tsbuildinfo'" in script
    assert "--exclude='backend/.ruff_cache'" in script
    assert "Use ./deploy-intranet.sh instead of running docker compose directly" in script


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


def test_intranet_compose_uses_runtime_env_contract_and_internal_token():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "${DEER_FLOW_FRONTEND_ENV_FILE:?DEER_FLOW_FRONTEND_ENV_FILE must be set}" in compose
    assert "${DEER_FLOW_ENV_FILE:?DEER_FLOW_ENV_FILE must be set}" in compose
    assert "DEER_FLOW_INTERNAL_AUTH_TOKEN=${DEER_FLOW_INTERNAL_AUTH_TOKEN}" in compose


def test_intranet_runbook_points_frontend_env_to_runtime_file():
    guide = GUIDE_FILE.read_text(encoding="utf-8")

    assert "runtime/frontend.env" in guide
    assert "frontend` 启动失败：确认 `frontend/.env` 存在" not in guide
    assert "登录后无法进入主页" in guide
    assert "frontend is healthy: http://127.0.0.1:2026/" in guide
    assert "curl -fsS http://127.0.0.1:2026/" in guide
