"""Unit tests for scripts/start-local.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "start-local.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc_env = os.environ.copy()
    proc_env.pop("REQUIRED_ENV_VARS", None)
    proc_env.pop("CONFIG_FILE", None)
    proc_env.pop("START_TARGET", None)
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["sh", str(SCRIPT), *args],
        env=proc_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_start_script_exists_and_is_posix_sh():
    assert SCRIPT.is_file()
    proc = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def test_print_command_works_with_required_env_and_config(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("config_version: 5\nmodels: []\n", encoding="utf-8")
    proc = _run(
        "--print-command",
        env={
            "CONFIG_FILE": str(config_file),
            "REQUIRED_ENV_VARS": "DEEPSEEK_API_KEY",
            "DEEPSEEK_API_KEY": "test-key",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("make start")


def test_missing_required_env_fails(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("config_version: 5\nmodels: []\n", encoding="utf-8")
    proc = _run(
        "--print-command",
        env={
            "CONFIG_FILE": str(config_file),
            "REQUIRED_ENV_VARS": "DEEPSEEK_API_KEY",
        },
    )
    assert proc.returncode != 0
    assert "missing required environment variable: DEEPSEEK_API_KEY" in proc.stderr


def test_invalid_required_env_name_fails(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("config_version: 5\nmodels: []\n", encoding="utf-8")
    proc = _run(
        "--print-command",
        env={
            "CONFIG_FILE": str(config_file),
            "REQUIRED_ENV_VARS": "DEEPSEEK_API_KEY;bad",
            "DEEPSEEK_API_KEY": "test-key",
        },
    )
    assert proc.returncode != 0
    assert "invalid environment variable name: DEEPSEEK_API_KEY;bad" in proc.stderr


def test_missing_config_file_fails(tmp_path: Path):
    proc = _run(
        "--print-command",
        env={
            "CONFIG_FILE": str(tmp_path / "missing-config.yaml"),
            "REQUIRED_ENV_VARS": "",
            "DEEPSEEK_API_KEY": "test-key",
        },
    )
    assert proc.returncode != 0
    assert "missing config file" in proc.stderr


def test_invalid_start_target_fails(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("config_version: 5\nmodels: []\n", encoding="utf-8")
    proc = _run(
        "--print-command",
        env={
            "CONFIG_FILE": str(config_file),
            "REQUIRED_ENV_VARS": "",
            "START_TARGET": "start;bad",
        },
    )
    assert proc.returncode != 0
    assert "invalid make target: start;bad" in proc.stderr


@pytest.mark.parametrize("bad_arg", ["--unknown", "extra"])
def test_unexpected_argument_fails(tmp_path: Path, bad_arg: str):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("config_version: 5\nmodels: []\n", encoding="utf-8")
    proc = _run(
        bad_arg,
        env={
            "CONFIG_FILE": str(config_file),
            "REQUIRED_ENV_VARS": "",
            "DEEPSEEK_API_KEY": "test-key",
        },
    )
    assert proc.returncode != 0
    assert "unexpected argument" in proc.stderr
