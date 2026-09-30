"""The ``code`` toolgroup loads its tools from config.example.yaml.

Ticket 01: ``analyze_code_evidence``, ``code_interpreter`` (group ``code``)
and ``data_analyzer`` (group ``knowledge``) are declared through the config
``tools[]`` mechanism, so agents that declare the groups get them without any
hard-coded tool list.  Ticket 03 adds ``read_binary_hex`` (group ``code``)
for the whitelisted binary evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deerflow.config.app_config import AppConfig
from deerflow.tools.tools import get_available_tools


@pytest.fixture(scope="module")
def config_example() -> AppConfig:
    config_example_path = Path(__file__).resolve().parents[4] / "config.example.yaml"
    return AppConfig.model_validate(yaml.safe_load(config_example_path.read_text(encoding="utf-8")))


def test_code_group_declares_analyze_code_evidence_and_code_interpreter(config_example: AppConfig) -> None:
    assert any(group.name == "code" for group in config_example.tool_groups)

    tools = get_available_tools(groups=["code"], include_mcp=False, app_config=config_example)
    names = {tool.name for tool in tools}

    assert {"analyze_code_evidence", "code_interpreter", "read_binary_hex"} <= names


def test_read_binary_hex_exposes_only_file_path_and_paging_parameters(config_example: AppConfig) -> None:
    tools = get_available_tools(groups=["code"], include_mcp=False, app_config=config_example)
    read_hex = next(tool for tool in tools if tool.name == "read_binary_hex")

    assert set(read_hex.args) == {"file_path", "offset", "length"}


def test_knowledge_group_declares_data_analyzer(config_example: AppConfig) -> None:
    tools = get_available_tools(groups=["knowledge"], include_mcp=False, app_config=config_example)

    assert "data_analyzer" in {tool.name for tool in tools}


def test_analyze_code_evidence_exposes_only_the_package_root_parameter(config_example: AppConfig) -> None:
    tools = get_available_tools(groups=["code"], include_mcp=False, app_config=config_example)
    analyze = next(tool for tool in tools if tool.name == "analyze_code_evidence")

    assert set(analyze.args) == {"package_root"}
