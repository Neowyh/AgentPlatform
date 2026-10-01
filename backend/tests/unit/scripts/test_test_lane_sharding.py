import json
import os
import subprocess
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[4] / "scripts/run-test-lane.sh"


@pytest.mark.parametrize("lane,parallel", [("backend-serial", False), ("backend-standard", True)])
def test_shards_keep_serial_execution_sequential(tmp_path, lane, parallel):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    python_stub = binaries / "python-stub"
    python_stub.write_text("#!/usr/bin/env bash\nexit 0\n")
    python_stub.chmod(0o755)
    capture = tmp_path / "arguments.json"
    uv_stub = binaries / "uv"
    uv_stub.write_text("#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\nPath(os.environ['ARGUMENT_CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n")
    uv_stub.chmod(0o755)
    result = subprocess.run(
        ["bash", str(RUNNER), lane],
        env={
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "PYTHON": str(python_stub),
            "ARGUMENT_CAPTURE": str(capture),
            "TEST_LANE_SKIP_PREFLIGHT": "1",
            "TEST_LANE_ARTIFACT_DIR": str(tmp_path / "logs"),
            "TEST_LANE_SHARDS": "4",
            "TEST_LANE_SHARD_INDEX": "2",
            "TEST_LANE_COVERAGE": "0",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    arguments = json.loads(capture.read_text())
    assert arguments[arguments.index("--splits") + 1] == "4"
    assert arguments[arguments.index("--group") + 1] == "2"
    assert ("-n" in arguments) is parallel
    assert ("--dist" in arguments) is parallel


def test_full_validation_has_one_serial_owner():
    import yaml

    definition = yaml.load((RUNNER.parent.parent / ".github/workflows/backend-unit-tests.yml").read_text(), Loader=yaml.BaseLoader)
    serial = definition["jobs"]["backend-serial"]
    assert "strategy" not in serial
    assert serial["needs"] == "backend-full"
    serial_steps = [step for step in serial["steps"] if "run" in step]
    serial_runs = [step for step in serial_steps if "run-test-lane.sh backend-serial" in step["run"]]
    assert len(serial_runs) == 1
    assert serial_runs[0]["env"]["TEST_LANE_SHARDS"] == "0"
    shard_runs = [step["run"] for step in definition["jobs"]["backend-full"]["steps"] if "run" in step]
    assert any("run-test-lane.sh backend-standard" in command for command in shard_runs)
    assert not any("run-test-lane.sh backend-full" in command or "run-test-lane.sh backend-serial" in command for command in shard_runs)
