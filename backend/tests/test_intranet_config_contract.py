from __future__ import annotations

from pathlib import Path

import yaml


def test_intranet_config_uses_deerflow_runtime_paths_and_default_deny_network() -> None:
    config_path = Path(__file__).resolve().parents[2] / "config.intranet.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["models"][0]["use"].startswith("deerflow.")
    assert config["sandbox"]["use"].startswith("deerflow.")
    assert config["sandbox"]["network"] == {
        "mode": "isolated",
        "allow_domains": [],
        "approval": "deny",
    }
    runtime_tool_paths = [tool["use"] for tool in config["tools"] if tool["name"] != "read_document"]
    assert runtime_tool_paths
    assert all(path.startswith("deerflow.") for path in runtime_tool_paths)
