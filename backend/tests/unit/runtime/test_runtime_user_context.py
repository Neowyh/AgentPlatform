from pathlib import Path


def test_pytest_process_uses_temporary_ideer_home(monkeypatch, tmp_path):
    """The upstream home mechanism is the DEER_FLOW_HOME env var (the old
    IDEER_HOME pytest contract is gone): setting it must steer Paths away
    from the repo-local production home."""
    import os

    test_home = tmp_path / "deer-flow-pytest-abc123"
    monkeypatch.setenv("DEER_FLOW_HOME", str(test_home))

    from deerflow.config.paths import Paths

    resolved = Paths().base_dir.resolve()
    production_home = (Path(__file__).resolve().parents[2] / ".deer-flow").resolve()

    assert resolved == test_home.resolve()
    assert resolved != production_home
    assert "deer-flow-pytest-" in resolved.name
    assert "DEER_FLOW_HOME" in os.environ
