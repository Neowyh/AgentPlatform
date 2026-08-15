from pathlib import Path
from types import SimpleNamespace

from ideer.agents.lead_agent.prompt import get_skills_prompt_section
from ideer.config.agents_config import AgentConfig
from ideer.skills.types import Skill


class NamedTool:
    def __init__(self, name: str):
        self.name = name


def _make_skill(name: str, allowed_tools: list[str] | None = None) -> Skill:
    return Skill(
        name=name,
        description=f"Description for {name}",
        license="MIT",
        skill_dir=Path(f"/tmp/{name}"),
        skill_file=Path(f"/tmp/{name}/SKILL.md"),
        relative_path=Path(name),
        category="public",
        allowed_tools=allowed_tools,
        enabled=True,
    )


def test_get_skills_prompt_section_returns_empty_when_no_skills_match(monkeypatch):
    skills = [_make_skill("skill1"), _make_skill("skill2")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)

    result = get_skills_prompt_section(available_skills={"non_existent_skill"})
    assert result == ""


def test_get_skills_prompt_section_returns_empty_when_available_skills_empty(monkeypatch):
    skills = [_make_skill("skill1"), _make_skill("skill2")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)

    result = get_skills_prompt_section(available_skills=set())
    assert result == ""


def test_get_skills_prompt_section_returns_skills(monkeypatch):
    skills = [_make_skill("skill1"), _make_skill("skill2")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)

    result = get_skills_prompt_section(available_skills={"skill1"})
    assert "skill1" in result
    assert "skill2" not in result
    assert "[built-in]" in result


def test_get_skills_prompt_section_returns_all_when_available_skills_is_none(monkeypatch):
    skills = [_make_skill("skill1"), _make_skill("skill2")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)

    result = get_skills_prompt_section(available_skills=None)
    assert "skill1" in result
    assert "skill2" in result


def test_get_skills_prompt_section_uses_only_frozen_run_skills_without_global_scan(monkeypatch):
    frozen = _make_skill("frozen-skill")
    monkeypatch.setattr(
        "ideer.agents.lead_agent.prompt.get_enabled_skills_for_config",
        lambda _config: (_ for _ in ()).throw(AssertionError("global skills must not be scanned")),
    )

    result = get_skills_prompt_section(
        resolved_skills=[frozen],
        container_base_path="/mnt/run-skills",
    )

    assert "frozen-skill" in result
    assert "/mnt/run-skills/public/frozen-skill/SKILL.md" in result


def test_get_skills_prompt_section_includes_self_evolution_rules(monkeypatch):
    skills = [_make_skill("skill1")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)
    monkeypatch.setattr(
        "ideer.config.get_app_config",
        lambda: SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=True),
        ),
    )

    result = get_skills_prompt_section(available_skills=None)
    assert "Skill Self-Evolution" in result


def test_get_skills_prompt_section_includes_self_evolution_rules_without_skills(monkeypatch):
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: [])
    monkeypatch.setattr(
        "ideer.config.get_app_config",
        lambda: SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=True),
        ),
    )

    result = get_skills_prompt_section(available_skills=None)
    assert "Skill Self-Evolution" in result


def test_get_skills_prompt_section_cache_respects_skill_evolution_toggle(monkeypatch):
    skills = [_make_skill("skill1")]
    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: skills)
    config = SimpleNamespace(
        skills=SimpleNamespace(container_path="/mnt/skills"),
        skill_evolution=SimpleNamespace(enabled=True),
    )
    monkeypatch.setattr("ideer.config.get_app_config", lambda: config)

    enabled_result = get_skills_prompt_section(available_skills=None)
    assert "Skill Self-Evolution" in enabled_result

    config.skill_evolution.enabled = False
    disabled_result = get_skills_prompt_section(available_skills=None)
    assert "Skill Self-Evolution" not in disabled_result


def test_get_skills_prompt_section_uses_explicit_config_for_enabled_skills(monkeypatch):
    explicit_config = SimpleNamespace(
        skills=SimpleNamespace(container_path="/mnt/alt-skills"),
        skill_evolution=SimpleNamespace(enabled=False),
    )

    def fail_get_app_config():
        raise AssertionError("ambient get_app_config() must not be used when app_config is explicit")

    monkeypatch.setattr("ideer.agents.lead_agent.prompt._get_enabled_skills", lambda: [_make_skill("global-skill")])
    monkeypatch.setattr("ideer.config.get_app_config", fail_get_app_config)
    monkeypatch.setattr(
        "ideer.agents.lead_agent.prompt.get_or_new_skill_storage",
        lambda app_config=None, **kwargs: __import__("types").SimpleNamespace(load_skills=lambda *, enabled_only: [_make_skill("explicit-skill")] if app_config is explicit_config else []),
    )

    result = get_skills_prompt_section(app_config=explicit_config)

    assert "explicit-skill" in result
    assert "global-skill" not in result


def test_make_lead_agent_empty_skills_passed_correctly(monkeypatch):
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module

    # Mock dependencies
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: MagicMock())
    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available_skills, *, app_config: [])
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    class MockModelConfig:
        supports_thinking = False

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = MockModelConfig()
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    captured_skills = []

    def mock_apply_prompt_template(**kwargs):
        captured_skills.append(kwargs.get("available_skills"))
        return "mock_prompt"

    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", mock_apply_prompt_template)

    # Case 1: Empty skills list
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=[]))
    lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})
    assert captured_skills[-1] == set()

    # Case 2: None skills list
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=None))
    lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})
    assert captured_skills[-1] is None

    # Case 3: Some skills list
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=["skill1"]))
    lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})
    assert captured_skills[-1] == {"skill1"}


def test_make_lead_agent_filters_tools_from_available_skills(monkeypatch):
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module

    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", lambda **kwargs: "mock_prompt")
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=["restricted", "legacy"]))
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available_skills, *, app_config: [_make_skill("restricted", ["read_file"]), _make_skill("legacy", None)])
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [NamedTool("bash"), NamedTool("read_file"), NamedTool("web_search")])

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    agent_kwargs = lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})

    assert [tool.name for tool in agent_kwargs["tools"]] == ["read_file"]


def test_canonical_lead_agent_uses_frozen_definition_skills_and_runner_tool_intersection(monkeypatch):
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module
    from ideer.resources.runtime import CanonicalAgentDefinition

    definition = CanonicalAgentDefinition(
        resource_id="11111111-1111-1111-1111-111111111111",
        version=3,
        content_hash="a" * 64,
        path=Path("/immutable/agent"),
        config=AgentConfig(name="Canonical Agent", skills=["frozen-skill"], tool_groups=["safe", "owner-only"]),
        soul="Frozen soul",
    )
    frozen_skill = _make_skill("frozen-skill", ["read_file"])
    monkeypatch.setattr(
        lead_agent_module,
        "load_agent_config",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy Agent config must not load")),
    )
    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    prompt_args = {}
    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", lambda **kwargs: prompt_args.update(kwargs) or "prompt")
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    captured_groups = []
    monkeypatch.setattr(
        "ideer.tools.get_available_tools",
        lambda **kwargs: captured_groups.append(kwargs.get("groups")) or [NamedTool("bash"), NamedTool("read_file")],
    )
    app_config = MagicMock()
    app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)

    factory = lead_agent_module.build_canonical_lead_agent_factory(
        definition,
        [frozen_skill],
        runner_tool_groups=frozenset({"safe"}),
    )
    agent_kwargs = factory({"configurable": {}}, app_config=app_config)

    assert captured_groups == [["safe"]]
    assert [tool.name for tool in agent_kwargs["tools"]] == ["read_file"]
    assert prompt_args["resolved_skills"] == [frozen_skill]
    assert prompt_args["soul_override"] == "Frozen soul"
    assert prompt_args["read_only"] is True
    assert prompt_args["agent_name"] == "Canonical Agent"


def test_make_lead_agent_all_legacy_skills_preserve_all_tools(monkeypatch):
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module

    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", lambda **kwargs: "mock_prompt")
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=None))
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available_skills, *, app_config: [_make_skill("legacy", None)])
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [NamedTool("bash"), NamedTool("read_file")])

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    agent_kwargs = lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})

    assert [tool.name for tool in agent_kwargs["tools"]] == ["bash", "read_file", "update_agent"]


def test_make_lead_agent_enforces_allowed_tools_when_skill_cache_is_cold(monkeypatch):
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module
    from ideer.agents.lead_agent import prompt as prompt_module

    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "apply_prompt_template", lambda **kwargs: "mock_prompt")
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=["restricted"]))
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [NamedTool("bash"), NamedTool("read_file"), NamedTool("web_search")])

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)
    mock_storage = SimpleNamespace(load_skills=lambda *, enabled_only: [_make_skill("restricted", ["read_file"])])

    with prompt_module._enabled_skills_lock:
        prompt_module._enabled_skills_cache = None
    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", lambda app_config=None, **kwargs: mock_storage)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    agent_kwargs = lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})

    assert [tool.name for tool in agent_kwargs["tools"]] == ["read_file"]


def test_make_lead_agent_fails_closed_when_skill_policy_load_fails(monkeypatch):
    from unittest.mock import MagicMock

    import pytest

    from ideer.agents.lead_agent import agent as lead_agent_module
    from ideer.agents.lead_agent import prompt as prompt_module

    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    create_agent_mock = MagicMock()
    monkeypatch.setattr(lead_agent_module, "create_agent", create_agent_mock)
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda x, **kwargs: AgentConfig(name="test", skills=["restricted"]))

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)

    def fail_storage(*args, **kwargs):
        raise RuntimeError("skill storage unavailable")

    monkeypatch.setattr(prompt_module, "get_or_new_skill_storage", fail_storage)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    with pytest.raises(RuntimeError, match="skill storage unavailable"):
        lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test"}})

    create_agent_mock.assert_not_called()


def test_make_lead_agent_shared_agent_loads_owner_config_and_hides_update_agent(monkeypatch):
    """A shared agent (agent_owner_id set) loads config/SOUL from the owner's
    directory and does not expose the update_agent tool to the runner."""
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module

    seen: dict = {}

    def mock_load_agent_config(name, *, user_id=None):
        seen["config_user_id"] = user_id
        return AgentConfig(name=name, skills=None)

    monkeypatch.setattr(lead_agent_module, "load_agent_config", mock_load_agent_config)
    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available_skills, *, app_config: [])
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [NamedTool("bash")])
    monkeypatch.setattr(
        lead_agent_module,
        "apply_prompt_template",
        lambda **kwargs: seen.update(agent_user_id=kwargs.get("agent_user_id")) or "mock_prompt",
    )

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    agent_kwargs = lead_agent_module.make_lead_agent({"configurable": {"agent_name": "test", "agent_owner_id": "owner-1"}})

    assert seen["config_user_id"] == "owner-1"
    assert seen["agent_user_id"] == "owner-1"
    assert [tool.name for tool in agent_kwargs["tools"]] == ["bash"]


def test_make_lead_agent_shared_agent_loads_from_owner_directory(monkeypatch, tmp_path):
    """Regression for the shared-agent run bug: running another user's public
    agent must load config/SOUL from the declaring owner's directory instead
    of raising FileNotFoundError against the runner's own directory."""
    from unittest.mock import MagicMock

    from ideer.agents.lead_agent import agent as lead_agent_module
    from ideer.config.paths import Paths

    owner_dir = tmp_path / "users" / "owner-1" / "agents" / "fault-zeroing"
    owner_dir.mkdir(parents=True)
    (owner_dir / "config.yaml").write_text("name: fault-zeroing\ndescription: shared agent\ntool_groups: []\n", encoding="utf-8")
    (owner_dir / "SOUL.md").write_text("# Shared SOUL", encoding="utf-8")
    runner_dir = tmp_path / "users" / "user-2" / "agents" / "fault-zeroing"
    assert not runner_dir.exists()

    seen: dict = {}
    monkeypatch.setattr(
        lead_agent_module,
        "apply_prompt_template",
        lambda **kwargs: seen.update(agent_user_id=kwargs.get("agent_user_id")) or "mock_prompt",
    )
    monkeypatch.setattr(lead_agent_module, "_resolve_model_name", lambda x=None, **kwargs: "default-model")
    monkeypatch.setattr(lead_agent_module, "create_chat_model", lambda **kwargs: "model")
    monkeypatch.setattr(lead_agent_module, "_build_middlewares", lambda *args, **kwargs: [])
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)
    monkeypatch.setattr(lead_agent_module, "_load_enabled_skills_for_tool_policy", lambda available_skills, *, app_config: [])
    monkeypatch.setattr("ideer.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr("ideer.config.agents_config.get_paths", lambda: Paths(str(tmp_path)))

    mock_app_config = MagicMock()
    mock_app_config.get_model_config.return_value = SimpleNamespace(supports_thinking=False, supports_vision=False)
    monkeypatch.setattr(lead_agent_module, "get_app_config", lambda: mock_app_config)

    agent_kwargs = lead_agent_module.make_lead_agent({"configurable": {"agent_name": "fault-zeroing", "agent_owner_id": "owner-1"}})

    assert seen["agent_user_id"] == "owner-1"
    assert agent_kwargs["system_prompt"] == "mock_prompt"
    assert agent_kwargs["tools"] == []
