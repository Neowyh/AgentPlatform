import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.acceptance.run_gate8_acceptance import capture_gate8

from tests.gate8_acceptance import _REQUIRED_SCENARIOS, _SCENARIO_OBSERVATIONS


def _write_manifest(path: Path, command: list[str]) -> None:
    path.write_text(
        json.dumps({"scenarios": {name: {"command": command} for name in _REQUIRED_SCENARIOS}}),
        encoding="utf-8",
    )


def _write_gate7(path: Path, candidate: str) -> None:
    path.write_text(
        json.dumps({"candidate_commit": candidate, "status": "passed"}),
        encoding="utf-8",
    )


def test_gate8_capture_runs_each_scenario_and_strictly_validates_the_artifact(
    tmp_path: Path,
) -> None:
    candidate = "candidate-sha"
    emitter = tmp_path / "emit_evidence.py"
    emitter.write_text(
        "import json, os\n"
        "observations = json.loads(os.environ['GATE8_REQUIRED_OBSERVATIONS'])\n"
        "evidence = {\n"
        "  'candidate_commit': os.environ['GATE8_CANDIDATE_COMMIT'],\n"
        "  'scenario': os.environ['GATE8_SCENARIO'],\n"
        "  'real_execution': True,\n"
        "  'observed_steps': ['scenario command ran'],\n"
        "  'assertions': ['scenario assertion passed'],\n"
        "  'observations': {key: 'observed' for key in observations},\n"
        "}\n"
        "if os.environ['GATE8_SCENARIO'] == 'run_snapshot_freeze':\n"
        "  evidence['observations'].update(old_run_snapshot={'run_status': 'success'}, new_run_snapshot={'run_status': 'success'})\n"
        "with open(os.environ['GATE8_EVIDENCE_PATH'], 'w') as output:\n"
        "  json.dump(evidence, output)\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    gate7 = tmp_path / "gate7.json"
    output = tmp_path / "gate8.json"
    _write_manifest(manifest, [sys.executable, str(emitter)])
    _write_gate7(gate7, candidate)

    artifact = capture_gate8(
        manifest_path=manifest,
        gate7_artifact=gate7,
        output_path=output,
        candidate=candidate,
        branch="test",
    )

    assert artifact["verdict"] == "passed"
    assert set(artifact["scenarios"]) == set(_REQUIRED_SCENARIOS)
    assert all(
        artifact["scenarios"][name]["status"] == "executed" and artifact["scenarios"][name]["exit_status"] == 0 and set(artifact["scenarios"][name]["observations"]) == set(_SCENARIO_OBSERVATIONS[name]) for name in _REQUIRED_SCENARIOS
    )


def test_gate8_capture_keeps_nonzero_scenarios_incomplete(tmp_path: Path) -> None:
    candidate = "candidate-sha"
    manifest = tmp_path / "manifest.json"
    gate7 = tmp_path / "gate7.json"
    output = tmp_path / "gate8.json"
    _write_manifest(manifest, [sys.executable, "-c", "raise SystemExit(7)"])
    _write_gate7(gate7, candidate)

    artifact = capture_gate8(
        manifest_path=manifest,
        gate7_artifact=gate7,
        output_path=output,
        candidate=candidate,
        branch="test",
    )

    assert artifact["verdict"] == "incomplete"
    assert all(artifact["scenarios"][name]["result"] == "incomplete" and artifact["scenarios"][name]["exit_status"] == 7 for name in _REQUIRED_SCENARIOS)
