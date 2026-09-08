"""The final runtime gate rejects a reintroduced legacy runtime import."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("source", "expected_status"),
    [("from deerflow.config import get_app_config\n", 0), ("from ideer.config import get_app_config\n", 1)],
)
def test_runtime_boundary_requires_zero_legacy_imports(tmp_path: Path, source: str, expected_status: int) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    gate = scripts / "check-runtime-boundary.sh"
    shutil.copyfile(Path(__file__).resolve().parents[4] / "scripts" / gate.name, gate)
    app = tmp_path / "backend" / "app"
    app.mkdir(parents=True)
    (app / "entry.py").write_text(source, encoding="utf-8")
    env = dict(os.environ)
    env.pop("RUNTIME_BOUNDARY_MAX_IMPORT_FILES", None)

    result = subprocess.run(["bash", str(gate)], capture_output=True, text=True, env=env, check=False)

    assert result.returncode == expected_status, result.stdout + result.stderr
