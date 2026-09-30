"""The fault-zeroing Expert agent binds the code toolgroup (ticket 04).

T4 design decision 3 (leftover from ticket 01-03): the归零 Expert's declared
``tool_groups`` must include the ``code`` group so the evidence_collection
node can actually call ``analyze_code_evidence`` — the scanner-status
disclosure chain starts with this agent being able to run the scan.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deerflow.config.app_config import AppConfig
from deerflow.tools.tools import get_available_tools

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_CONFIG = REPO_ROOT / "resources" / "agents" / "fault-zeroing" / "config.yaml"


def test_fault_zeroing_agent_declares_the_code_toolgroup() -> None:
    config = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8"))

    assert "code" in config["tool_groups"]


def test_fault_zeroing_agent_assembled_toolset_includes_code_evidence_tools() -> None:
    """装配后工具集含 analyze_code_evidence / read_binary_hex / code_interpreter。"""

    config_example_path = REPO_ROOT / "config.example.yaml"
    app_config = AppConfig.model_validate(yaml.safe_load(config_example_path.read_text(encoding="utf-8")))
    agent_config = yaml.safe_load(AGENT_CONFIG.read_text(encoding="utf-8"))

    tools = get_available_tools(groups=list(agent_config["tool_groups"]), include_mcp=False, app_config=app_config)
    names = {tool.name for tool in tools}

    assert {"analyze_code_evidence", "read_binary_hex", "code_interpreter"} <= names
