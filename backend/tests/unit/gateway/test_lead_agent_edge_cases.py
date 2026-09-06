"""Extended coverage tests for deerflow.agents.lead_agent.agent and prompt modules.

Targets uncovered lines in _get_runtime_config, _resolve_model_name edge cases,
_available_skill_names, _create_summarization_middleware config branches,
_build_middlewares various config states, _create_todo_list_middleware,
bootstrap agent path, and prompt module helper functions.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from deerflow.agents.lead_agent import agent as lead_mod
from deerflow.agents.lead_agent import prompt as prompt_mod
from deerflow.config.app_config import AppConfig
from deerflow.config.memory_config import MemoryConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.config.summarization_config import SummarizationConfig


def _make_app_config(**overrides):
    defaults = dict(
        sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"),
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

    def test_forwards_run_model_name_and_extensions(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=True, trigger=None)
        app_config.memory = MemoryConfig(enabled=False)

        captured = {}
        sentinel = object()

        def fake_factory(**kw):
            captured.update(kw)
            return sentinel

        monkeypatch.setattr(lead_mod, "create_summarization_middleware", fake_factory)
        extensions = object()

        result = lead_mod._create_summarization_middleware(app_config=app_config, run_model_name="run-model", extensions=extensions)
        assert result is sentinel
        assert captured["app_config"] is app_config
        assert captured["run_model_name"] == "run-model"
        assert captured["extensions"] is extensions

    def test_returns_none_when_factory_returns_none(self, monkeypatch):
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=True)

        monkeypatch.setattr(lead_mod, "create_summarization_middleware", lambda **kw: None)
        assert lead_mod._create_summarization_middleware(app_config=app_config) is None

    def test_memory_enabled_still_forwards_to_factory(self, monkeypatch):
        """Memory flush hook wiring is the factory's job (skip_memory_flush=False on the lead path)."""
        app_config = _make_app_config()
        app_config.summarization = SummarizationConfig(enabled=True, trigger=None)
        app_config.memory = MemoryConfig(enabled=True)

        captured = {}
        sentinel = object()

        def fake_factory(**kw):
            captured.update(kw)
            return sentinel

        monkeypatch.setattr(lead_mod, "create_summarization_middleware", fake_factory)

        result = lead_mod._create_summarization_middleware(app_config=app_config)
        assert result is sentinel
        assert captured["app_config"] is app_config


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
        captured = {}

        def fake_limit_middleware(**kw):
            captured.update(kw)
            return mock_subagent_mw

        monkeypatch.setattr(lead_mod, "SubagentLimitMiddleware", fake_limit_middleware)

        middlewares = lead_mod.build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": True, "max_concurrent_subagents": 5}},
            model_name="default-model",
            app_config=app_config,
        )

        assert mock_subagent_mw in middlewares
        # Upstream clamps the configured concurrency to the process execution
        # capacity (subagent_runtime.max_running, default 3), so a request of 5
        # resolves to 3 for both the middleware and the advertised prompt limits.
        assert captured["max_concurrent"] == 3
        assert captured["max_total"] >= 1


# ---------------------------------------------------------------------------
# build_middlewares - deferred tool search
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresToolSearch:
    def test_deferred_tool_filter_middleware_added(self, monkeypatch):
        """A deferred setup with names attaches the real DeferredToolFilterMiddleware."""
        app_config = _make_app_config()
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        deferred_setup = SimpleNamespace(deferred_names=frozenset({"t1"}), catalog_hash="hash-1")
        middlewares = lead_mod.build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
            model_name="default-model",
            app_config=app_config,
            deferred_setup=deferred_setup,
        )

        from deerflow.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware

        assert any(isinstance(m, DeferredToolFilterMiddleware) for m in middlewares)

    def test_no_deferred_filter_without_setup(self, monkeypatch):
        app_config = _make_app_config()
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)

        middlewares = lead_mod.build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
            model_name="default-model",
            app_config=app_config,
        )

        from deerflow.agents.middlewares.deferred_tool_filter_middleware import DeferredToolFilterMiddleware

        assert not any(isinstance(m, DeferredToolFilterMiddleware) for m in middlewares)


# ---------------------------------------------------------------------------
# build_middlewares - token usage
# ---------------------------------------------------------------------------


class TestBuildMiddlewaresTokenUsage:
    def test_token_usage_middleware_added(self, monkeypatch):
        app_config = _make_app_config()
        monkeypatch.setattr(lead_mod, "get_app_config", lambda: app_config)
        monkeypatch.setattr(lead_mod, "build_lead_runtime_middlewares", lambda **kw: [])
        monkeypatch.setattr(lead_mod, "_create_summarization_middleware", lambda **kw: None)
        monkeypatch.setattr(lead_mod, "_create_todo_list_middleware", lambda is_plan_mode: None)
        app_config.token_usage = SimpleNamespace(enabled=True)

        middlewares = lead_mod.build_middlewares(
            {"configurable": {"is_plan_mode": False, "subagent_enabled": False}},
            model_name="default-model",
            app_config=app_config,
        )

        from deerflow.agents.middlewares.token_usage_middleware import TokenUsageMiddleware

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
    """Upstream renders the section from an explicit deferred-name set computed at
    agent build time; there is no app_config parameter and no registry lookup."""

    def test_empty_when_no_deferred(self):
        assert prompt_mod.get_deferred_tools_prompt_section(deferred_names=frozenset()) == ""

    def test_lists_names_when_deferred_present(self):
        result = prompt_mod.get_deferred_tools_prompt_section(deferred_names=frozenset({"mcp_tool_a"}))
        assert "<available-deferred-tools>" in result
        assert "mcp_tool_a" in result


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
        with patch("app.agentplatform.legacy.memory.get_memory_data", side_effect=RuntimeError("boom")):
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
        monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(app_config=config)
        assert "DeerFlow 2.0" in result
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
        monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(agent_name="custom-agent", soul_override="Custom soul", app_config=config)
        assert "custom-agent" in result
        assert "Custom soul" in result

    def test_subagent_enabled(self, monkeypatch):
        config = SimpleNamespace(
            sandbox=SimpleNamespace(use="deerflow.sandbox.local:LocalSandboxProvider", allow_host_bash=False, mounts=[]),
            subagents=SimpleNamespace(custom_agents={}),
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
            tool_search=SimpleNamespace(enabled=False),
            memory=SimpleNamespace(enabled=False, injection_enabled=True, max_injection_tokens=2000),
            acp_agents={},
        )
        monkeypatch.setattr("deerflow.config.get_app_config", lambda: config)
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda **kw: SimpleNamespace(load_skills=lambda enabled_only=True: []))
        monkeypatch.setattr(prompt_mod, "get_deferred_tools_prompt_section", lambda **kw: "")
        monkeypatch.setattr(prompt_mod, "_build_acp_section", lambda **kw: "")

        result = prompt_mod.apply_prompt_template(subagent_enabled=True, max_concurrent_subagents=5, app_config=config)
        # Upstream renders a <subagent_system> section; the requested concurrency
        # of 5 is clamped to the process execution capacity (default 3).
        assert "<subagent_system>" in result
        assert "HARD LIMITS" in result
        assert "max 3 `task` calls per response" in result


# ---------------------------------------------------------------------------
# get_skills_prompt_section edge cases
# ---------------------------------------------------------------------------


class TestGetSkillsPromptSection:
    def _patch_storage(self, monkeypatch, skills=()):
        monkeypatch.setattr(prompt_mod, "get_enabled_skills_for_config", lambda app_config=None, user_id=None: list(skills))
        monkeypatch.setattr(prompt_mod, "get_or_new_skill_storage", lambda app_config=None: SimpleNamespace(load_skills=lambda enabled_only: list(skills)))
        monkeypatch.setattr(prompt_mod, "get_or_new_user_skill_storage", lambda user_id=None, app_config=None: SimpleNamespace(load_skills=lambda enabled_only: list(skills)))
        prompt_mod._get_cached_skills_prompt_section.cache_clear()

    def test_empty_when_no_skills_and_no_evolution(self, monkeypatch):
        config = SimpleNamespace(
            skills=SimpleNamespace(container_path="/mnt/skills"),
            skill_evolution=SimpleNamespace(enabled=False),
        )
        self._patch_storage(monkeypatch)

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
            enabled=True,
            get_container_file_path=lambda base: f"{base}/real-skill/SKILL.md",
        )
        self._patch_storage(monkeypatch, skills=[skill])

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
            enabled=True,
            get_container_file_path=lambda base: f"{base}/real-skill/SKILL.md",
        )
        self._patch_storage(monkeypatch, skills=[skill])

        result = prompt_mod.get_skills_prompt_section(available_skills=set(), app_config=config)
        assert result == ""
