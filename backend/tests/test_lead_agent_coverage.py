"""Extended coverage tests for ideer.agents.lead_agent.agent and prompt modules.

Targets uncovered lines in _get_runtime_config, _resolve_model_name edge cases,
_available_skill_names, _create_summarization_middleware config branches,
_build_middlewares various config states, _create_todo_list_middleware,
bootstrap agent path, and prompt module helper functions.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ideer.agents.lead_agent import agent as lead_mod
from ideer.agents.lead_agent import prompt as prompt_mod
from ideer.config.app_config import AppConfig
from ideer.config.memory_config import MemoryConfig
from ideer.config.model_config import ModelConfig
from ideer.config.sandbox_config import SandboxConfig
from ideer.config.summarization_config import SummarizationConfig


def _make_app_config(**overrides):
    defaults = dict(
        sandbox=SandboxConfig(use="ideer.sandbox.local:LocalSandboxProvider"),
        models=[
            ModelConfig(
                name="default-model",
                display_name="Default",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="default-model",
                supports_thinking=False,
            )
        ],
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_model(name, supports_thinking=False, supports_vision=False):
    return ModelConfig(
        name=name,
        display_name=name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        supports_thinking=supports_thinking,
        supports_vision=supports_vision,
    )


# ---------------------------------------------------------------------------
# _get_runtime_config
# ---------------------------------------------------------------------------


class TestGetRuntimeConfig:
    def test_merges_configurable_and_context(self):
        config = {
            "configurable": {"key1": "val1"},
            "context": {"key2": "val2"},
        }
        result = lead_mod._get_runtime_config(config)
        assert result["key1"] == "val1"
        assert result["key2"] == "val2"

    def test_missing_configurable(self):
        result = lead_mod._get_runtime_config({})
        assert isinstance(result, dict)

    def test_none_configurable(self):
        result = lead_mod._get_runtime_config({"configurable": None})
        assert isinstance(result, dict)

    def test_none_context(self):
        result = lead_mod._get_runtime_config({"configurable": {}, "context": None})
        assert isinstance(result, dict)

    def test_non_dict_context(self):
        result = lead_mod._get_runtime_config({"configurable": {}, "context": "not-a-dict"})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _resolve_model_name edge cases
# ---------------------------------------------------------------------------


class TestResolveModelNameEdge:
    def test_valid_requested_model_returned(self):
        app_config = _make_app_config(models=[_make_model("gpt-4"), _make_model("other")])
        result = lead_mod._resolve_model_name("gpt-4", app_config=app_config)
        assert result == "gpt-4"

    def test_same_name_as_default_does_not_warn(self, caplog):
        app_config = _make_app_config(models=[_make_model("default-model")])
        with caplog.at_level("WARNING"):
            result = lead_mod._resolve_model_name("default-model", app_config=app_config)
        assert result == "default-model"
        assert "fallback" not in caplog.text


# ---------------------------------------------------------------------------
# _available_skill_names
# ---------------------------------------------------------------------------


class TestAvailableSkillNames:
    def test_bootstrap_returns_bootstrap_set(self):
        agent_config = MagicMock()
        result = lead_mod._available_skill_names(agent_config, is_bootstrap=True)
        assert result == {"bootstrap"}

    def test_agent_config_with_skills(self):
        agent_config = SimpleNamespace(skills=["skill1", "skill2"])
        result = lead_mod._available_skill_names(agent_config, is_bootstrap=False)
        assert result == {"skill1", "skill2"}

    def test_agent_config_with_none_skills(self):
        agent_config = SimpleNamespace(skills=None)
        result = lead_mod._available_skill_names(agent_config, is_bootstrap=False)
        assert result is None

    def test_no_agent_config(self):
        result = lead_mod._available_skill_names(None, is_bootstrap=False)
        assert result is None


# ---------------------------------------------------------------------------
# _create_todo_list_middleware
# ---------------------------------------------------------------------------


class TestCreateTodoListMiddleware:
    def test_returns_none_when_not_plan_mode(self):
        result = lead_mod._create_todo_list_middleware(False)
        assert result is None

    def test_returns_middleware_when_plan_mode(self):
        result = lead_mod._create_todo_list_middleware(True)
        assert result is not None


# ---------------------------------------------------------------------------
# _create_summarization_middleware config branches
# ---------------------------------------------------------------------------


class TestCreateSummarizationMiddlewareBranches:
    def test_returns_none_when_disabled(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=False)
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert result is None

    def test_trigger_none(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=True, trigger=None)
        app_config.memory = MemoryConfig(enabled=False)

        fake_model = MagicMock()
        fake_model.with_config.return_value = fake_model

        monkeypatch.setattr(lead_mod, "create_chat_model", lambda **kw: fake_model)
        monkeypatch.setattr(lead_mod, "IDeerSummarizationMiddleware", lambda **kw: kw)

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert result is not None
        assert result["trigger"] is None

    def test_trim_tokens_to_summarize_set(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(
            enabled=True,
            trigger=None,
            trim_tokens_to_summarize=5000,
        )
        app_config.memory = MemoryConfig(enabled=False)

        fake_model = MagicMock()
        fake_model.with_config.return_value = fake_model

        monkeypatch.setattr(lead_mod, "create_chat_model", lambda **kw: fake_model)
        monkeypatch.setattr(lead_mod, "IDeerSummarizationMiddleware", lambda **kw: kw)

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert result["trim_tokens_to_summarize"] == 5000

    def test_summary_prompt_set(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(
            enabled=True,
            trigger=None,
            summary_prompt="Custom prompt",
        )
        app_config.memory = MemoryConfig(enabled=False)

        fake_model = MagicMock()
        fake_model.with_config.return_value = fake_model

        monkeypatch.setattr(lead_mod, "create_chat_model", lambda **kw: fake_model)
        monkeypatch.setattr(lead_mod, "IDeerSummarizationMiddleware", lambda **kw: kw)

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert result["summary_prompt"] == "Custom prompt"

    def test_memory_enabled_adds_flush_hook(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=True, trigger=None)
        app_config.memory = MemoryConfig(enabled=True)

        fake_model = MagicMock()
        fake_model.with_config.return_value = fake_model

        monkeypatch.setattr(lead_mod, "create_chat_model", lambda **kw: fake_model)
        monkeypatch.setattr(lead_mod, "IDeerSummarizationMiddleware", lambda **kw: kw)
        monkeypatch.setattr(lead_mod, "memory_flush_hook", MagicMock())

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert len(result["before_summarization"]) > 0

    def test_model_name_configured(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(
            enabled=True,
            model_name="custom-model",
            trigger=None,
        )
        app_config.memory = MemoryConfig(enabled=False)

        fake_model = MagicMock()
        fake_model.with_config.return_value = fake_model

        captured = {}

        def fake_create_chat_model(*, name=None, thinking_enabled, **kwargs):
            captured["name"] = name
            return fake_model

        monkeypatch.setattr(lead_mod, "create_chat_model", fake_create_chat_model)
        monkeypatch.setattr(lead_mod, "IDeerSummarizationMiddleware", lambda **kw: kw)

        lead_mod._create_summarization_middleware(app_config=app_config)
        assert captured["name"] == "custom-model"


# ---------------------------------------------------------------------------
# _build_middlewares - subagent path
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresSubagent:
    def test_subagent_limit_middleware_added(self, monkeypatch):
        app_config = _make_app_config()
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        mock_subagent_mw = MagicMock()
        monkeypatch.setattr(lead_mod, "SubagentLimitMiddleware", lambda max_concurrent: mock_subagent_mw)

        middlewares = lead_mod._build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": True, "max_concurrent_subagents": 5}},
            model_name="default-model",
            app_config=app_config,
        )

        assert mock_subagent_mw in middlewares


# ---------------------------------------------------------------------------
# _build_middlewares - tool_search enabled
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresToolSearch:
    def test_deferred_tool_filter_middleware_added(self, monkeypatch):
        app_config = _make_app_config()
        app_config.tool_search = SimpleNamespace(enabled=True)
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        # Need to mock DeferredToolFilterMiddleware
        mock_dtf = MagicMock()
        mock_dtf_cls = MagicMock(return_value=mock_dtf)

        with patch.dict("sys.modules", {"ideer.agents.middlewares.deferred_tool_filter_middleware": SimpleNamespace(DeferredToolFilterMiddleware=mock_dtf_cls)}):
            middlewares = lead_mod._build_middlewares(
                {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
                model_name="default-model",
                app_config=app_config,
            )

        assert mock_dtf in middlewares


# ---------------------------------------------------------------------------
# _build_middlewares - token usage
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresTokenUsage:
    def test_token_usage_middleware_added(self, monkeypatch):
        app_config = _make_app_config()
        app_config.token_usage = SimpleNamespace(enabled=True)
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        middlewares = lead_mod._build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
            model_name="default-model",
            app_config=app_config,
        )

        from ideer.agents.middlewares.token_usage_middleware import TokenUsageMiddleware

        assert any(isinstance(m, TokenUsageMiddleware) for m in middlewares)


# ---------------------------------------------------------------------------
# prompt module - helper functions
# ---------------------------------------------------------------------------


class TestPromptBuildSelfUpdateSection:
    def test_empty_for_none(self):
        assert prompt_mod._build_self_update_section(None) == ""

    def test_contains_agent_name(self):
        result = prompt_mod._build_self_update_section("test-agent")
        assert "test-agent" in result
        assert "<self_update>" in result


class TestPromptGetAgentSoul:
    def test_returns_empty_for_none(self):
        with patch("ideer.agents.lead_agent.prompt.load_agent_soul", return_value=None):
            result = prompt_mod.get_agent_soul(None)
        assert result == ""

    def test_wraps_soul_in_tags(self):
        with patch("ideer.agents.lead_agent.prompt.load_agent_soul", return_value="My soul"):
            result = prompt_mod.get_agent_soul("agent-a")
        assert "<soul>" in result
        assert "My soul" in result


class TestPromptBuildSkillEvolutionSection:
    def test_empty_when_disabled(self):
        assert prompt_mod._build_skill_evolution_section(False) == ""

    def test_contains_text_when_enabled(self):
        result = prompt_mod._build_skill_evolution_section(True)
        assert "Skill Self-Evolution" in result


class TestPromptBuildAcpSection:
    def test_empty_when_no_agents(self):
        config = SimpleNamespace(acp_agents={})
        result = prompt_mod._build_acp_section(app_config=config)
        assert result == ""

    def test_empty_when_agents_none(self):
        config = SimpleNamespace(acp_agents=None)
        result = prompt_mod._build_acp_section(app_config=config)
        assert result == ""

    def test_contains_acp_text(self):
        config = SimpleNamespace(acp_agents={"codex": object()})
        result = prompt_mod._build_acp_section(app_config=config)
        assert "ACP Agent Tasks" in result


class TestPromptBuildCustomMountsSection:
    def test_empty_when_no_mounts(self):
        config = SimpleNamespace(sandbox=SimpleNamespace(mounts=[]))
        result = prompt_mod._build_custom_mounts_section(app_config=config)
        assert result == ""

    def test_empty_when_mounts_none(self):
        config = SimpleNamespace(sandbox=SimpleNamespace(mounts=None))
        result = prompt_mod._build_custom_mounts_section(app_config=config)
        assert result == ""


class TestPromptGetDeferredToolsSection:
    def test_empty_when_disabled(self):
        config = SimpleNamespace(tool_search=SimpleNamespace(enabled=False))
        result = prompt_mod.get_deferred_tools_prompt_section(app_config=config)
        assert result == ""

    def test_empty_when_no_deferred(self, monkeypatch):
        config = SimpleNamespace(tool_search=SimpleNamespace(enabled=True))

        def _fake_get_deferred_registry():
            return None  # Falsy value triggers the `if not registry: return ""` path

        # The function does a local import: from ideer.tools.builtins.tool_search import get_deferred_registry
        # We need to patch the function at the source module level so the local import picks it up
        import ideer.tools.builtins.tool_search as ts_mod

        original = ts_mod.get_deferred_registry
        ts_mod.get_deferred_registry = _fake_get_deferred_registry
        try:
            result = prompt_mod.get_deferred_tools_prompt_section(app_config=config)
        finally:
            ts_mod.get_deferred_registry = original
        assert result == ""


class TestPromptGetMemoryContext:
    def test_returns_empty_when_disabled(self):
        config = SimpleNamespace(memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000))
        result = prompt_mod._get_memory_context(app_config=config)
        assert result == ""

    def test_returns_empty_when_injection_disabled(self):
        config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=False, max_injection_tokens=2000))
        result = prompt_mod._get_memory_context(app_config=config)
        assert result == ""

    def test_returns_empty_on_exception(self):
        config = SimpleNamespace(memory=SimpleNamespace(enabled=True, injection_enabled=True, max_injection_tokens=2000))
        with patch("ideer.agents.memory.get_memory_data", side_effect=RuntimeError("boom")):
            result = prompt_mod._get_memory_context(app_config=config)
        assert result == ""


class TestPromptApplyPromptTemplate:
    def test_basic_template(self, monkeypatch):
        config = SimpleNamespace(
            sandbox=SimpleNamespace(mounts=[]),
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
            tool_search=SimpleNamespace(enabled=False),
            memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
            acp_agents={},
        )
        monkeypatch.setattr("ideer.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_agent_soul", lambda agent_name=None: "")
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(app_config=config)
        assert "iDeer 2.0" in result
        assert "<role>" in result

    def test_custom_agent_name(self, monkeypatch):
        config = SimpleNamespace(
            sandbox=SimpleNamespace(mounts=[]),
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
            tool_search=SimpleNamespace(enabled=False),
            memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
            acp_agents={},
        )
        monkeypatch.setattr("ideer.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_agent_soul", lambda agent_name=None: "<soul>Custom soul</soul>")
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(agent_name="custom-agent", app_config=config)
        assert "custom-agent" in result
        assert "Custom soul" in result

    def test_subagent_enabled(self, monkeypatch):
        config = SimpleNamespace(
            sandbox=SimpleNamespace(use="ideer.sandbox.local:LocalSandboxProvider", allow_host_bash=False, mounts=[]),
            subagents=SimpleNamespace(custom_agents={}),
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
            tool_search=SimpleNamespace(enabled=False),
            memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
            acp_agents={},
        )
        monkeypatch.setattr("ideer.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_agent_soul", lambda agent_name=None: "")
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(subagent_enabled=True, max_concurrent_subagents=5, app_config=config)
        assert "SUBAGENT MODE ACTIVE" in result
        assert "5" in result
        assert "Orchestrator Mode" in result


# ---------------------------------------------------------------------------
# get_skills_prompt_section edge cases
# ---------------------------------------------------------------------------


class TestGetSkillsPromptSection:
    def test_empty_when_no_skills_and_no_evolution(self, monkeypatch):
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
        )
        monkeypatch.setattr(prompt_mod, "get_enabled_skills_for_config", lambda app_config=None: [])

        result = prompt_mod.get_skills_prompt_section(app_config=config)
        assert result == ""

    def test_empty_when_available_skills_no_match(self, monkeypatch):
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
        )

        skill = SimpleNamespace(
            name="real-skill",
            description="desc",
            category="custom",
            get_container_file_path=lambda base: f"{base}/real-skill/SKILL.md",
        )
        monkeypatch.setattr(prompt_mod, "get_enabled_skills_for_config", lambda app_config=None: [skill])

        result = prompt_mod.get_skills_prompt_section(available_skills={"other-skill"}, app_config=config)
        assert result == ""

    def test_empty_when_skills_list_but_available_key_empty_tuple(self, monkeypatch):
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
        )

        skill = SimpleNamespace(
            name="real-skill",
            description="desc",
            category="custom",
            get_container_file_path=lambda base: f"{base}/real-skill/SKILL.md",
        )
        monkeypatch.setattr(prompt_mod, "get_enabled_skills_for_config", lambda app_config=None: [skill])
        prompt_mod._get_cached_skills_prompt_section.cache_clear()

        result = prompt_mod.get_skills_prompt_section(available_skills=set(), app_config=config)
        assert result == ""
