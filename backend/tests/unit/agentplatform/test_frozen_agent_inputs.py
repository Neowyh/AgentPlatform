"""Frozen canonical Agent inputs entering the DeerFlow lead assembly.

AgentPlatform freezes a canonical resource closure (UUID / version / hash)
before a Run starts.  The assembly must build the lead graph from that frozen
closure — never from mutable on-disk agent state — must intersect the frozen
tool groups with the caller's runner groups, and must withhold agent
self-mutation for read-only enterprise resources.
"""

from __future__ import annotations

import pytest

import deerflow.tools as tools_module
from deerflow.agents.lead_agent import agent as lead_agent_module
from deerflow.agents.lead_agent.agent import FrozenAgentInputs, assemble_lead_agent
from deerflow.config.agents_config import AgentConfig
from deerflow.config.app_config import AppConfig
from deerflow.config.loop_detection_config import LoopDetectionConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.skills.types import Skill


def _make_app_config() -> AppConfig:
    return AppConfig(
        models=[
            ModelConfig(
                name="safe-model",
                display_name="safe-model",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="safe-model",
                supports_thinking=False,
                supports_vision=False,
            )
        ],
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
        loop_detection=LoopDetectionConfig(),
    )


def _make_skill(name: str, *, allowed_tools: tuple[str, ...] | None = None) -> Skill:
    return Skill(
        name=name,
        description=f"{name} skill",
        category="document",
        enabled=True,
        license="MIT",
        skill_dir=f"/mnt/skills/{name}",
        skill_file=f"/mnt/skills/{name}/SKILL.md",
        relative_path=f"{name}/SKILL.md",
        allowed_tools=allowed_tools,
    )


def _frozen_inputs(**overrides) -> FrozenAgentInputs:
    values = {
        "agent_name": "0f7d8709-0000-0000-0000-000000000001",
        "config": AgentConfig(name="canonical-agent"),
        "soul": "frozen soul",
        "skills": [_make_skill("srs-writing")],
        "runner_tool_groups": frozenset({"files", "web"}),
        "resource": {
            "resource_id": "0f7d8709-0000-0000-0000-000000000001",
            "version": 3,
            "content_hash": "abc123",
        },
    }
    values.update(overrides)
    return FrozenAgentInputs(**values)


def _patch_assembly(monkeypatch, captured: dict) -> None:
    monkeypatch.setattr(lead_agent_module, "build_middlewares", lambda config, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", lambda **kwargs: "system prompt")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: object())
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "build_tracing_callbacks", lambda: [])
    # Sentinel replacing the real ``update_agent`` builtin: if the harness
    # appends it to the graph tools for a frozen run, this object shows up.
    sentinel = type("UpdateAgentSentinel", (), {"name": "update_agent-builtin"})()
    import deerflow.tools.builtins as builtins_module

    monkeypatch.setattr(builtins_module, "update_agent", sentinel)
    monkeypatch.setattr(
        tools_module,
        "get_available_tools",
        lambda **kwargs: (
            captured.setdefault("tools_calls", []).append(kwargs)
            or [
                type("T", (), {"name": "read_file"})(),
            ]
        ),
    )


def test_assemble_lead_agent_builds_from_frozen_inputs(monkeypatch):
    """The frozen closure replaces on-disk agent config, skills and soul."""
    app_config = _make_app_config()
    captured: dict = {}
    _patch_assembly(monkeypatch, captured)

    def _fail_load_agent_config(name, *, user_id=None):
        raise AssertionError("load_agent_config must not be called for frozen runs")

    def _fail_load_skills(available_skills, *, app_config, user_id=None):
        raise AssertionError("_load_enabled_available_skills must not be called for frozen runs")

    monkeypatch.setattr(lead_agent_module, "load_agent_config", _fail_load_agent_config)
    monkeypatch.setattr(lead_agent_module, "_load_enabled_available_skills", _fail_load_skills)

    result = assemble_lead_agent(
        {"configurable": {}},
        app_config=app_config,
        frozen=_frozen_inputs(),
    )

    graph = result.graph
    # Tools resolved with the frozen AgentConfig's tool groups.
    assert captured["tools_calls"], "get_available_tools must be called"
    # Self-mutation is withheld for read-only frozen resources: the real
    # update_agent builtin is never appended to the graph tools.
    tool_names = [tool.name for tool in graph["tools"]]
    assert "update_agent-builtin" not in tool_names
    assert result.descriptor is None  # no observers registered


def test_assemble_lead_agent_freezes_skill_tool_policy(monkeypatch):
    """Frozen skills narrow the assembled tools to their allowed set."""
    app_config = _make_app_config()
    captured: dict = {}
    _patch_assembly(monkeypatch, captured)

    skill = _make_skill("srs-writing", allowed_tools=("read_file",))

    result = assemble_lead_agent(
        {"configurable": {}},
        app_config=app_config,
        frozen=_frozen_inputs(skills=[skill]),
    )

    tool_names = sorted(tool.name for tool in result.graph["tools"])
    assert tool_names == ["read_file"]


def test_assemble_lead_agent_records_resource_identity_in_policies(monkeypatch):
    """The assembly descriptor policies carry the frozen resource identity."""
    app_config = _make_app_config()
    captured: dict = {}
    _patch_assembly(monkeypatch, captured)

    seen: dict = {}

    real_complete = lead_agent_module._complete_assembly

    def _capture_complete(**kwargs):
        seen["policies"] = kwargs["effective_policies"]
        return real_complete(**kwargs)

    monkeypatch.setattr(lead_agent_module, "_complete_assembly", _capture_complete)

    assemble_lead_agent(
        {"configurable": {}},
        app_config=app_config,
        frozen=_frozen_inputs(),
    )

    assert seen["policies"]["resource"] == {
        "resource_id": "0f7d8709-0000-0000-0000-000000000001",
        "version": 3,
        "content_hash": "abc123",
    }


def test_frozen_inputs_cannot_run_in_bootstrap_mode():
    with pytest.raises(ValueError, match="bootstrap"):
        assemble_lead_agent(
            {"configurable": {"is_bootstrap": True}},
            app_config=_make_app_config(),
            frozen=_frozen_inputs(),
        )
