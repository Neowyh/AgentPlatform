import os
from pathlib import Path


def test_backend_suite_bootstraps_a_private_runtime_config() -> None:
    config_path = Path(os.environ["DEER_FLOW_CONFIG_PATH"])

    assert config_path.is_file()
    assert config_path.name == "config.yaml"
