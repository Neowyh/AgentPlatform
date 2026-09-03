"""Regression tests for intranet offline deployment scripts."""

from __future__ import annotations

import ast
import os
import stat
import subprocess
import tarfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-intranet.sh"
PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package-intranet-offline.sh"
MANIFEST_SCRIPT = REPO_ROOT / "scripts" / "intranet_bundle_manifest.py"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check-intranet.sh"
INSTALL_AGENT_SCRIPT = REPO_ROOT / "scripts" / "install_agent.py"
INSTALL_SRS_SCRIPT = REPO_ROOT / "scripts" / "install_srs_writing_agent.py"
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
if [ "$1" = "--version" ] || [ "$1" = "-v" ]; then
  echo "Docker version 24.0.0, build fake"
  exit 0
fi
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
if [ "$1" = "image" ]; then
  shift
  case "$1" in
    inspect)
      shift
      img=""
      while [ "$#" -gt 0 ]; do
        case "$1" in
          --format) shift 2 ;;
          -*) shift ;;
          *) img="$1"; shift ;;
        esac
      done
      if [ -z "${FAKE_DOCKER_INSPECTABLE:-}" ]; then
        exit 0
      fi
      printf '%s\n' "$FAKE_DOCKER_INSPECTABLE" | grep -qxF "$img"
      exit $?
      ;;
    rm)
      shift
      echo "rm $*" >> "${FAKE_DOCKER_LOG:-/dev/null}"
      exit 0
      ;;
    *) echo "unexpected docker image: $*" >&2; exit 99 ;;
  esac
fi
if [ "$1" = "images" ]; then
  printf '%s\n' ${FAKE_DOCKER_IMAGES:-"ideer-gateway:test ideer-frontend:test nginx:alpine ideer-sandbox:test"}
  exit 0
fi
if [ "$1" = "build" ]; then
  exit 0
fi
if [ "$1" = "pull" ]; then
  exit 0
fi
if [ "$1" = "tag" ]; then
  exit 0
fi
if [ "$1" = "save" ]; then
  out=""
  images=""
  while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then
      out="$2"
      shift 2
      continue
    fi
    images="$images $1"
    shift
  done
  [ -n "$out" ] || exit 2
  echo "FAKE-SAVE:${images}"
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
  use: ideer.sandbox.local.local_sandbox_provider:LocalSandboxProvider
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
    (root / "docs" / "srs-writing-agent" / "agent").mkdir(parents=True)
    (root / "docs" / "srs-writing-agent" / "agent" / "config.yaml").write_text(
        "name: srs-writing\n",
        encoding="utf-8",
    )
    (root / "docs" / "srs-writing-agent" / "agent" / "SOUL.md").write_text(
        "# SRS Writing\n",
        encoding="utf-8",
    )
    (root / "workflows").mkdir()
    (root / "workflows" / "fault-zeroing.yaml").write_text(
        "name: fault-zeroing\nversion: 1\n",
        encoding="utf-8",
    )
    (root / "skills" / "custom" / "fault-zeroing" / "templates").mkdir(parents=True)
    (root / "skills" / "custom" / "fault-zeroing" / "templates" / "corrective_actions.schema.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    _write_executable(
        root / "scripts" / "install_agent.py",
        (REPO_ROOT / "scripts" / "install_agent.py").read_text(encoding="utf-8"),
    )
    _write_executable(
        root / "scripts" / "install_srs_writing_agent.py",
        (REPO_ROOT / "scripts" / "install_srs_writing_agent.py").read_text(encoding="utf-8"),
    )
    (root / "vendor" / "officecli").mkdir(parents=True)
    (root / "vendor" / "officecli" / "officecli").write_text("fake binary\n", encoding="utf-8")


def _make_bundle(tmp_path: Path, *, version: str = "test", include_frontend_env: bool = True) -> Path:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir(parents=True)
    source_root = tmp_path / "source-input"
    _write_source_tree(source_root, include_frontend_env=include_frontend_env)
    with tarfile.open(bundle_root / f"ideer-source-{version}.tar.gz", "w:gz") as tar:
        for child in source_root.iterdir():
            tar.add(child, arcname=child.name)
    (bundle_root / f"ideer-images-{version}.tar").write_text("fake images\n", encoding="utf-8")
    return bundle_root


def _run_deploy(bundle_root: Path, *args: str, env: dict[str, str], version: str = "test") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DEPLOY_SCRIPT), "--bundle-root", str(bundle_root), "--version", version, "--skip-check", *args],
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


def test_bundled_resource_seed_runs_inside_gateway_container(tmp_path: Path):
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "seed_custom_skill_owners.py" not in script
    assert "--skills-dir" not in script
    assert 'docker compose -p ideer -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T gateway' in script
    assert '--db "$runtime_home/data/ideer.db"' not in script
    assert 'docker cp "$SOURCE_DIR/scripts/seed_bundled_resources.py" ideer-gateway:/tmp/seed_bundled_resources.py' in script
    assert 'docker cp "$SOURCE_DIR/bundled-resources.json" ideer-gateway:/tmp/bundled-resources.json' in script
    assert "--manifest /tmp/bundled-resources.json --source-root /app --owner" in script
    assert '--conflict-policy \'"$BUNDLED_CONFLICT"' in script


def test_bundled_conflict_option_is_validated_and_parsed(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)

    proc = _run_deploy(bundle_root, "--bundled-conflict", "force", "prepare", env=env)
    assert proc.returncode != 0
    assert "must be keep or override" in proc.stderr

    proc = _run_deploy(bundle_root, "--bundled-conflict", "override", "prepare", env=env)
    assert proc.returncode == 0, proc.stderr

    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    assert 'BUNDLED_CONFLICT="${IDEER_BUNDLED_CONFLICT:-keep}"' in script


def test_deploy_fails_closed_when_any_bundled_resource_seed_fails() -> None:
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert 'die "public resource initialization failed"' in script
    assert "if ! seed_bundled_workflows; then" in script
    assert 'die "bundled workflow initialization failed"' in script
    assert "Idempotent; failures are warnings, not fatal." not in script


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
    assert f"IDEER_FRONTEND_ENV_FILE={runtime_dir}/frontend.env" in env_text
    assert "BETTER_AUTH_SECRET=" in env_text
    assert "IDEER_INTERNAL_AUTH_TOKEN=" in env_text


def test_prepare_no_longer_installs_bundled_agents(tmp_path: Path):
    """prepare only seeds runtime config; bundled agents are installed post-up as
    the super admin's public resources (they need the runtime DB)."""
    bundle_root = _make_bundle(tmp_path)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    runtime_dir = bundle_root / "runtime"
    assert not (runtime_dir / "data" / "agents").exists()


def test_prepare_never_installs_agents_into_per_user_directories(tmp_path: Path):
    """prepare never touches per-user agent directories."""
    bundle_root = _make_bundle(tmp_path)
    user_dir = bundle_root / "runtime" / "data" / "users" / "alice"
    user_dir.mkdir(parents=True)

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    runtime_dir = bundle_root / "runtime"
    assert not (runtime_dir / "data" / "agents").exists()
    assert not (user_dir / "agents" / "fault-zeroing").exists()


def test_status_logs_and_stop_do_not_install_agents(tmp_path: Path):
    for command in ("status", "logs", "stop"):
        bundle_root = _make_bundle(tmp_path / command)
        proc = _run_deploy(bundle_root, command, env=_env_with_fake_docker(tmp_path / f"{command}-env"))

        assert proc.returncode == 0, proc.stderr
        assert not (bundle_root / "runtime" / "data" / "agents" / "fault-zeroing").exists()


def test_deploy_script_wires_admin_bootstrap_and_bundled_resource_steps():
    """The up/restart flow seeds the complete manifest after admin bootstrap."""
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "initialize_super_admin" in script
    assert "/api/v1/auth/initialize" in script
    assert "IDEER_ADMIN_EMAIL:-super_admin@test.com" in script
    assert "IDEER_ADMIN_PASSWORD:-super_admin@test.com" in script
    assert "install_admin_bundled_resources" in script
    assert "seed_bundled_resources.py" in script
    assert "bundled-resources.json" in script
    assert "--conflict-policy" in script
    assert "seed_custom_skill_owners.py" not in script
    assert "install_agent.py" not in script
    assert "install_srs_writing_agent.py" not in script
    assert "cleanup_legacy_shared_agent" not in script
    assert "find_super_admin_id" in script
    assert "install_bundled_agents" not in script
    assert "prepare_bundle 0" not in script


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
    assert f"IDEER_INTERNAL_AUTH_TOKEN={internal_token}" in env_text


def test_prepare_backfills_auth_secrets_into_existing_env_file(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)
    (bundle_root / "env.intranet").write_text(
        """PORT=3001
IDEER_GATEWAY_IMAGE=ideer-gateway:old
IDEER_FRONTEND_IMAGE=ideer-frontend:old
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
    assert "IDEER_GATEWAY_IMAGE=ideer-gateway:test" in env_text
    assert "IDEER_FRONTEND_IMAGE=ideer-frontend:test" in env_text
    assert f"BETTER_AUTH_SECRET={better_secret}" in env_text
    assert f"IDEER_INTERNAL_AUTH_TOKEN={internal_token}" in env_text
    assert env_text.count("BETTER_AUTH_SECRET=") == 1
    assert env_text.count("IDEER_INTERNAL_AUTH_TOKEN=") == 1


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
    assert "deploy-intranet.sh" in script
    assert ".env.intranet" in script


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
    with tarfile.open(output_dir / "ideer-source-test.tar.gz", "r:gz") as tar:
        names = set(tar.getnames())

    assert ".env.example" in names
    assert "config.example.yaml" in names
    assert "extensions_config.example.json" in names
    assert "frontend/.env.example" in names
    assert "frontend/.env" not in names
    assert "resources/workflows/fault-zeroing.yaml" in names
    assert "bundled-resources.json" in names
    assert "scripts/seed_bundled_resources.py" in names
    assert "resources/skills/fault-zeroing/templates/corrective_actions.schema.json" in names
    assert not (output_dir / "docker-compose.intranet.yaml").exists()
    assert not (output_dir / "env.intranet.example").exists()

    manifest = (output_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    sha256sums = (output_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "- docker-compose.intranet.yaml" not in manifest
    assert "env.intranet.example" not in manifest
    assert "docker-compose.intranet.yaml" not in sha256sums
    assert "env.intranet.example" not in sha256sums


def test_package_script_fails_when_skills_manifest_skill_missing(tmp_path: Path):
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
            "--skills-manifest",
            "fault-zeroing,definitely-missing-skill",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "skills-manifest lists missing custom skill" in proc.stderr
    assert "definitely-missing-skill" in proc.stderr


def test_package_manifest_records_custom_skills_and_exclusion(tmp_path: Path):
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
            "--skills-manifest",
            "fault-zeroing",
            "--exclude-skills",
            "fault-zeroing",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "both in --skills-manifest and --exclude-skills" in proc.stdout

    manifest = (output_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    assert "Custom Skills (resources/skills bundled in the source archive):" in manifest
    assert "Excluded: fault-zeroing" in manifest
    assert "  - fault-zeroing" not in manifest

    with tarfile.open(output_dir / "ideer-source-test.tar.gz", "r:gz") as tar:
        names = set(tar.getnames())
    assert "resources/skills/fault-zeroing/SKILL.md" not in names


def test_intranet_compose_uses_runtime_env_contract_and_internal_token():
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "${IDEER_FRONTEND_ENV_FILE:?IDEER_FRONTEND_ENV_FILE must be set}" in compose
    assert "${IDEER_ENV_FILE:?IDEER_ENV_FILE must be set}" in compose
    assert "IDEER_INTERNAL_AUTH_TOKEN=${IDEER_INTERNAL_AUTH_TOKEN}" in compose


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


def test_check_script_uses_bundle_version_images_and_runtime_env_contract(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    (bundle_root / "config.intranet.yaml").write_text(
        "models: []\n",
        encoding="utf-8",
    )
    (bundle_root / "env.intranet").write_text(
        "PORT=2026\nIDEER_GATEWAY_IMAGE=ideer-gateway:test\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["bash", str(CHECK_SCRIPT)],
        cwd=bundle_root,
        env=_env_with_fake_docker(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "ideer-gateway:test" in out
    assert "ideer-frontend:test" in out
    assert "nginx:alpine" in out
    assert "ideer-gateway:latest" not in out
    assert "env.intranet" in out
    assert "docker/.env.intranet" not in out
    assert "Port 2026" in out
    assert "PASSED" in out


def test_check_script_warns_when_env_file_is_missing(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    (bundle_root / "config.intranet.yaml").write_text(
        "models: []\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["bash", str(CHECK_SCRIPT)],
        cwd=bundle_root,
        env=_env_with_fake_docker(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "env.intranet" in proc.stdout
    assert "prepare" in proc.stdout


def test_guide_documents_bundled_agent_and_workflow_hooks():
    guide = GUIDE_FILE.read_text(encoding="utf-8")

    assert "installing bundled fault-zeroing agent for super admin (public)..." in guide
    assert "installing bundled srs-writing agent for super admin (public)..." in guide
    assert "agents_api" in guide
    assert "officecli" in guide
    assert "bundled-resources.json" in guide
    assert "seed" in guide
    assert "super_admin@test.com" in guide
    assert "公开" in guide
    assert "users/<" in guide or "users/" in guide


def _signature_annotations(tree: ast.AST):
    for node in tree.body:
        # Module-level variable annotations are evaluated at import time;
        # function-local ones are not (PEP 526).
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.annotation
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                if arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns


def test_installer_scripts_remain_python36_parseable() -> None:
    """Bundled-agent installers run with the HOST python3, which on older
    intranet servers (e.g. CentOS 7) is 3.6. They must not use 3.7+ syntax:
    walrus, the future-annotations import, PEP 604 unions, or builtin generic
    annotations, nor the 3.7+ subprocess.run(capture_output=) parameter."""
    for script in (INSTALL_AGENT_SCRIPT, INSTALL_SRS_SCRIPT):
        source = script.read_text(encoding="utf-8")
        ast.parse(source, filename=str(script), feature_version=(3, 6))
        assert "from __future__ import annotations" not in source
        assert ":=" not in source
        tree = ast.parse(source, filename=str(script))
        for annotation in _signature_annotations(tree):
            assert not isinstance(annotation, ast.BinOp), f"{script}: PEP 604 union in annotation"
            if isinstance(annotation, ast.Subscript):
                assert not isinstance(annotation.value, ast.Name) or annotation.value.id not in (
                    "list",
                    "dict",
                    "tuple",
                    "set",
                ), f"{script}: builtin generic annotation"

    srs_source = INSTALL_SRS_SCRIPT.read_text(encoding="utf-8")
    assert "capture_output" not in srs_source
    assert "stdout=subprocess.PIPE" in srs_source


def test_upgrade_refreshes_env_image_tags_and_reextracts_source(tmp_path: Path):
    """Re-running prepare with a new bundle version must switch env.intranet to
    the new image tags and replace the extracted source tree (C0)."""
    bundle_root = _make_bundle(tmp_path, version="v1")
    env = _env_with_fake_docker(tmp_path)

    first = _run_deploy(bundle_root, "prepare", env=env, version="v1")
    assert first.returncode == 0, first.stderr
    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert "IDEER_GATEWAY_IMAGE=ideer-gateway:v1" in env_text
    assert "IDEER_FRONTEND_IMAGE=ideer-frontend:v1" in env_text
    assert (bundle_root / "source" / ".bundle-version").read_text(encoding="utf-8").strip() == "v1"

    source_input = tmp_path / "source-input"
    (source_input / "frontend" / "version-marker.txt").write_text("v2\n", encoding="utf-8")
    with tarfile.open(bundle_root / "ideer-source-v2.tar.gz", "w:gz") as tar:
        for child in source_input.iterdir():
            tar.add(child, arcname=child.name)
    (bundle_root / "ideer-images-v2.tar").write_text("fake images v2\n", encoding="utf-8")

    second = _run_deploy(bundle_root, "prepare", env=env, version="v2")
    assert second.returncode == 0, second.stderr
    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert "IDEER_GATEWAY_IMAGE=ideer-gateway:v2" in env_text
    assert "IDEER_FRONTEND_IMAGE=ideer-frontend:v2" in env_text
    assert (bundle_root / "source" / ".bundle-version").read_text(encoding="utf-8").strip() == "v2"
    assert (bundle_root / "source" / "frontend" / "version-marker.txt").read_text(encoding="utf-8").strip() == "v2"


def test_upgrade_preserves_custom_image_values(tmp_path: Path):
    """Image tags that do not look like a bundle image (custom registry) must
    survive prepare untouched."""
    bundle_root = _make_bundle(tmp_path)
    (bundle_root / "env.intranet").write_text(
        "IDEER_GATEWAY_IMAGE=harbor.internal.com/ideer/gateway:custom\n",
        encoding="utf-8",
    )

    proc = _run_deploy(bundle_root, "prepare", env=_env_with_fake_docker(tmp_path))

    assert proc.returncode == 0, proc.stderr
    env_text = (bundle_root / "env.intranet").read_text(encoding="utf-8")
    assert "IDEER_GATEWAY_IMAGE=harbor.internal.com/ideer/gateway:custom" in env_text
    assert "ideer-gateway:test" not in env_text


def _prune_env(tmp_path: Path, env: dict[str, str], versions: list[str]) -> dict[str, str]:
    images = []
    for v in versions:
        images += [f"ideer-gateway:{v}", f"ideer-frontend:{v}"]
    images += ["nginx:alpine", "ideer-sandbox:v1", "ideer-sandbox:v2"]
    env["FAKE_DOCKER_IMAGES"] = "\n".join(images)
    env["FAKE_DOCKER_LOG"] = str(tmp_path / "docker-calls.log")
    (tmp_path / "docker-calls.log").write_text("", encoding="utf-8")
    return env


def test_prune_old_removes_only_stale_gateway_and_frontend_tags(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path, version="v4")
    env = _prune_env(tmp_path, _env_with_fake_docker(tmp_path), ["v1", "v2", "v3", "v4"])

    proc = _run_deploy(bundle_root, "prune-old", env=env, version="v4")

    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "removing old image: ideer-gateway:v1" in out
    assert "removing old image: ideer-frontend:v1" in out
    assert "removing old image: ideer-gateway:v2" not in out
    assert "removing old image: ideer-frontend:v2" not in out
    assert "removing old image: ideer-sandbox" not in out
    assert "removing old image: nginx" not in out
    assert "image pruning complete" in out

    calls = (tmp_path / "docker-calls.log").read_text(encoding="utf-8")
    assert "rm ideer-gateway:v1" in calls
    assert "rm ideer-frontend:v1" in calls
    assert "ideer-gateway:v2" not in calls
    assert "ideer-sandbox" not in calls
    assert "nginx" not in calls


def test_prune_old_dry_run_previews_without_removing(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path, version="v4")
    env = _prune_env(tmp_path, _env_with_fake_docker(tmp_path), ["v1", "v2", "v3", "v4"])

    prepared = _run_deploy(bundle_root, "prepare", env=env, version="v4")
    assert prepared.returncode == 0, prepared.stderr
    log = (tmp_path / "docker-calls.log").read_text(encoding="utf-8")

    dry = _run_deploy(bundle_root, "--dry-run", "prune-old", env=env, version="v4")

    assert dry.returncode == 0, dry.stderr
    assert "[dry-run] docker image rm ideer-gateway:v1" in dry.stdout
    assert (tmp_path / "docker-calls.log").read_text(encoding="utf-8") == log


def test_prune_old_rejects_invalid_keep_versions(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path)
    env = _env_with_fake_docker(tmp_path)

    proc = _run_deploy(bundle_root, "--keep-versions", "abc", "prune-old", env=env)

    assert proc.returncode != 0
    assert "--keep-versions must be a non-negative integer" in proc.stderr


def test_prune_old_keep_zero_removes_all_but_current(tmp_path: Path):
    bundle_root = _make_bundle(tmp_path, version="v4")
    env = _prune_env(tmp_path, _env_with_fake_docker(tmp_path), ["v1", "v2", "v3", "v4"])

    proc = _run_deploy(bundle_root, "--keep-versions", "0", "prune-old", env=env, version="v4")

    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "removing old image: ideer-gateway:v1" in out
    assert "removing old image: ideer-gateway:v3" in out
    assert "removing old image: ideer-gateway:v4" not in out


def test_load_reuses_local_sandbox_tag_for_incremental_bundle(tmp_path: Path):
    """When the versioned sandbox tag is absent (incremental bundle), deploy
    must retag a locally present ideer-sandbox:* and warn."""
    bundle_root = _make_bundle(tmp_path, version="v2")
    env = _env_with_fake_docker(tmp_path)
    env["FAKE_DOCKER_IMAGES"] = "\n".join(["ideer-gateway:v2", "ideer-frontend:v2", "nginx:alpine", "ideer-sandbox:v1"])
    env["FAKE_DOCKER_INSPECTABLE"] = "ideer-gateway:v2\nideer-frontend:v2\nnginx:alpine\nideer-sandbox:v1"

    proc = _run_deploy(bundle_root, "load", env=env, version="v2")

    assert proc.returncode == 0, proc.stderr
    assert "retagging local ideer-sandbox:v1" in proc.stdout
    assert "reusing local ideer-sandbox:v1" in proc.stderr


def test_package_incremental_bundle_saves_only_gateway_and_frontend(tmp_path: Path):
    output_dir = tmp_path / "bundle"
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    (base_dir / "wheels").mkdir()
    (base_dir / "bundle-manifest.json").write_text(
        '{"version":"v1","components":{"gateway":"old","frontend":"old"},"source_files":{},"source_roots":[]}',
        encoding="utf-8",
    )
    env = _env_with_fake_docker(tmp_path)

    proc = subprocess.run(
        [
            "bash",
            str(PACKAGE_SCRIPT),
            "--version",
            "v2",
            "--output-dir",
            str(output_dir),
            "--incremental",
            "--incremental-from",
            str(base_dir),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    save_line = [line for line in proc.stdout.splitlines() if line.startswith("FAKE-SAVE:")]
    assert save_line, proc.stdout
    saved = save_line[0]
    assert "ideer-gateway:v2" in saved
    assert "ideer-frontend:v2" in saved
    assert "nginx:alpine" not in saved
    assert "ideer-sandbox" not in saved

    manifest = (output_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    assert "Bundle type: incremental" in manifest
    assert "Incremental from: v1" in manifest
    assert "not included" in manifest
    assert "Incremental bundles are for upgrading an existing deployment only" in manifest


def test_package_full_bundle_manifest_marks_bundle_type_full(tmp_path: Path):
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
    manifest = (output_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    assert "Bundle type: full" in manifest
    assert "Bundle type: incremental" not in manifest
    assert "Incremental bundles are for upgrading an existing deployment only" not in manifest


def test_manifest_helper_builds_source_delta_and_deletion_list(tmp_path: Path):
    base = tmp_path / "base"
    current = tmp_path / "current"
    base.mkdir()
    current.mkdir()
    (base / "keep.txt").write_text("same\n", encoding="utf-8")
    (base / "change.txt").write_text("old\n", encoding="utf-8")
    (base / "delete.txt").write_text("gone\n", encoding="utf-8")
    (current / "keep.txt").write_text("same\n", encoding="utf-8")
    (current / "change.txt").write_text("new\n", encoding="utf-8")
    (current / "add.txt").write_text("new file\n", encoding="utf-8")

    base_manifest = tmp_path / "base.json"
    current_manifest = tmp_path / "current.json"
    delta = tmp_path / "delta.tar.gz"
    deleted = tmp_path / "deleted.txt"
    for root, output in ((base, base_manifest), (current, current_manifest)):
        proc = subprocess.run(
            ["python3", str(MANIFEST_SCRIPT), "snapshot", "--root", str(root), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
    proc = subprocess.run(
        [
            "python3",
            str(MANIFEST_SCRIPT),
            "delta",
            "--root",
            str(current),
            "--base",
            str(base_manifest),
            "--manifest",
            str(current_manifest),
            "--archive",
            str(delta),
            "--deleted",
            str(deleted),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert deleted.read_text(encoding="utf-8").splitlines() == ["delete.txt"]
    with tarfile.open(delta, "r:gz") as tar:
        assert set(tar.getnames()) == {"add.txt", "change.txt"}


def test_manifest_helper_applies_delta_and_verifies_result(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "old.txt").write_text("old\n", encoding="utf-8")
    base_manifest = tmp_path / "base.json"
    current_manifest = tmp_path / "current.json"
    delta = tmp_path / "delta.tar.gz"
    deleted = tmp_path / "deleted.txt"
    subprocess.run(["python3", str(MANIFEST_SCRIPT), "snapshot", "--root", str(root), "--output", str(base_manifest)], check=True)
    (root / "new.txt").write_text("new\n", encoding="utf-8")
    (root / "old.txt").unlink()
    subprocess.run(
        ["python3", str(MANIFEST_SCRIPT), "delta", "--root", str(root), "--base", str(base_manifest), "--manifest", str(current_manifest), "--archive", str(delta), "--deleted", str(deleted)],
        check=True,
    )
    (root / "old.txt").write_text("old\n", encoding="utf-8")
    (root / "new.txt").unlink()
    proc = subprocess.run(["python3", str(MANIFEST_SCRIPT), "apply", "--root", str(root), "--archive", str(delta), "--deleted", str(deleted), "--manifest", str(current_manifest)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert not (root / "old.txt").exists()
    assert (root / "new.txt").read_text(encoding="utf-8") == "new\n"


def test_manifest_helper_keeps_root_unchanged_when_verification_fails(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "old.txt").write_text("old\n", encoding="utf-8")
    archive = tmp_path / "delta.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        changed = tmp_path / "changed.txt"
        changed.write_text("changed\n", encoding="utf-8")
        tar.add(changed, arcname="old.txt")
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("", encoding="utf-8")
    manifest = tmp_path / "bad.json"
    manifest.write_text('{"source_files":{"old.txt":"sha256:invalid"}}\n', encoding="utf-8")
    proc = subprocess.run(["python3", str(MANIFEST_SCRIPT), "apply", "--root", str(root), "--archive", str(archive), "--deleted", str(deleted), "--manifest", str(manifest)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert (root / "old.txt").read_text(encoding="utf-8") == "old\n"
