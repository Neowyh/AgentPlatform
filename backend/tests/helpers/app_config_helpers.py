from __future__ import annotations

import json
from pathlib import Path

import yaml

from ideer.config.acp_config import load_acp_config_from_dict
from ideer.config.app_config import reset_app_config
from ideer.config.checkpointer_config import load_checkpointer_config_from_dict
from ideer.config.guardrails_config import load_guardrails_config_from_dict
from ideer.config.memory_config import load_memory_config_from_dict
from ideer.config.stream_bridge_config import load_stream_bridge_config_from_dict
from ideer.config.subagents_config import load_subagents_config_from_dict
from ideer.config.summarization_config import load_summarization_config_from_dict
from ideer.config.title_config import load_title_config_from_dict
from ideer.config.tool_search_config import load_tool_search_config_from_dict
from ideer.runtime.checkpointer import reset_checkpointer
from ideer.runtime.store import reset_store


def _reset_config_singletons() -> None:
    load_title_config_from_dict({})
    load_summarization_config_from_dict({})
    load_memory_config_from_dict({})
    load_subagents_config_from_dict({})
    load_tool_search_config_from_dict({})
    load_guardrails_config_from_dict({})
    load_checkpointer_config_from_dict(None)
    load_stream_bridge_config_from_dict(None)
    load_acp_config_from_dict({})
    reset_checkpointer()
    reset_store()
    reset_app_config()


def _write_config(path: Path, *, model_name: str, supports_thinking: bool) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "sandbox": {"use": "ideer.sandbox.local:LocalSandboxProvider"},
                "models": [
                    {
                        "name": model_name,
                        "use": "langchain_openai:ChatOpenAI",
                        "model": "gpt-test",
                        "supports_thinking": supports_thinking,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_extensions_config(path: Path) -> None:
    path.write_text(json.dumps({"mcpServers": {}, "skills": {}}), encoding="utf-8")
