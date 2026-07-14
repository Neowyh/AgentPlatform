from pathlib import Path


def test_pytest_process_uses_temporary_ideer_home():
    import os

    test_home = Path(os.environ["IDEER_HOME"]).resolve()
    production_home = (Path(__file__).resolve().parents[1] / ".ideer").resolve()

    assert test_home != production_home
    assert "ideer-pytest-" in test_home.name
