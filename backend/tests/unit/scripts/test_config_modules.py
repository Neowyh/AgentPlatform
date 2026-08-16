"""Parameterized unit tests for config modules without direct tests.

Covers: default values, field types, constraint validation, and boundary
conditions for each untested config in ideer.config.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ideer.config.acp_config import (
    ACPAgentConfig,
    get_acp_agents,
    load_acp_config_from_dict,
)

# ---------------------------------------------------------------------------
# CheckpointerConfig
# ---------------------------------------------------------------------------
from ideer.config.checkpointer_config import (
    CheckpointerConfig,
    get_checkpointer_config,
    load_checkpointer_config_from_dict,
    set_checkpointer_config,
)
from ideer.config.database_config import DatabaseConfig
from ideer.config.guardrails_config import (
    GuardrailProviderConfig,
    GuardrailsConfig,
    get_guardrails_config,
    load_guardrails_config_from_dict,
    reset_guardrails_config,
)

# ---------------------------------------------------------------------------
# New config modules
# ---------------------------------------------------------------------------
from ideer.config.loop_detection_config import LoopDetectionConfig, ToolFreqOverride
from ideer.config.memory_config import (
    MemoryConfig,
    get_memory_config,
    load_memory_config_from_dict,
    set_memory_config,
)
from ideer.config.model_config import ModelConfig
from ideer.config.network_mode import NetworkMode, get_network_mode, is_offline
from ideer.config.run_events_config import RunEventsConfig
from ideer.config.safety_finish_reason_config import (
    SafetyDetectorConfig,
    SafetyFinishReasonConfig,
)
from ideer.config.sandbox_config import SandboxConfig, VolumeMountConfig
from ideer.config.skill_evolution_config import SkillEvolutionConfig
from ideer.config.skills_config import SkillsConfig
from ideer.config.stream_bridge_config import (
    StreamBridgeConfig,
    get_stream_bridge_config,
    load_stream_bridge_config_from_dict,
    set_stream_bridge_config,
)
from ideer.config.subagents_config import (
    CustomSubagentConfig,
    SubagentOverrideConfig,
    SubagentsAppConfig,
)
from ideer.config.summarization_config import (
    ContextSize,
    SummarizationConfig,
    get_summarization_config,
    load_summarization_config_from_dict,
    set_summarization_config,
)
from ideer.config.title_config import (
    TitleConfig,
    get_title_config,
    load_title_config_from_dict,
    reset_title_config,
    set_title_config,
)
from ideer.config.tool_config import ToolConfig, ToolGroupConfig
from ideer.config.tool_search_config import (
    ToolSearchConfig,
    get_tool_search_config,
    load_tool_search_config_from_dict,
)
from ideer.config.tracing_config import (
    LangfuseTracingConfig,
    LangSmithTracingConfig,
    TracingConfig,
    reset_tracing_config,
)

# ===================================================================
# CheckpointerConfig
# ===================================================================


class TestCheckpointerConfig:
    @pytest.mark.parametrize(
        "conn",
        [
            pytest.param(None, id="default-none"),
            pytest.param("sqlite:///test.db", id="sqlite-dsn"),
            pytest.param("postgresql://user:pass@localhost/db", id="postgres-dsn"),
        ],
    )
    def test_connection_string_variants(self, conn):
        cfg = CheckpointerConfig(type="memory", connection_string=conn)
        assert cfg.connection_string == conn

    def test_default_connection_string_is_none(self):
        cfg = CheckpointerConfig(type="memory")
        assert cfg.connection_string is None

    @pytest.mark.parametrize(
        "ctp",
        [
            pytest.param("memory", id="memory"),
            pytest.param("sqlite", id="sqlite"),
            pytest.param("postgres", id="postgres"),
        ],
    )
    def test_valid_type_literals(self, ctp):
        cfg = CheckpointerConfig(type=ctp)
        assert cfg.type == ctp

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            CheckpointerConfig(type="redis")

    def test_singleton_get_set(self):
        original = get_checkpointer_config()
        try:
            set_checkpointer_config(CheckpointerConfig(type="sqlite"))
            assert get_checkpointer_config().type == "sqlite"
            set_checkpointer_config(None)
            assert get_checkpointer_config() is None
        finally:
            set_checkpointer_config(original)

    def test_load_from_dict(self):
        original = get_checkpointer_config()
        try:
            load_checkpointer_config_from_dict({"type": "postgres"})
            assert get_checkpointer_config().type == "postgres"
            load_checkpointer_config_from_dict(None)
            assert get_checkpointer_config() is None
        finally:
            set_checkpointer_config(original)


# ===================================================================
# DatabaseConfig
# ===================================================================


class TestDatabaseConfig:
    def test_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.backend == "memory"
        assert cfg.sqlite_dir == ".ideer/data"
        assert cfg.postgres_url == ""
        assert cfg.echo_sql is False
        assert cfg.pool_size == 5

    @pytest.mark.parametrize(
        "backend",
        [
            pytest.param("memory", id="memory"),
            pytest.param("sqlite", id="sqlite"),
            pytest.param("postgres", id="postgres"),
        ],
    )
    def test_valid_backend_literals(self, backend):
        cfg = DatabaseConfig(backend=backend)
        assert cfg.backend == backend

    def test_invalid_backend_rejected(self):
        with pytest.raises(ValidationError):
            DatabaseConfig(backend="redis")

    @pytest.mark.parametrize(
        "pool_size",
        [
            pytest.param(1, id="min-valid"),
            pytest.param(100, id="large"),
        ],
    )
    def test_pool_size_valid(self, pool_size):
        cfg = DatabaseConfig(pool_size=pool_size)
        assert cfg.pool_size == pool_size

    def test_pool_size_zero_rejected_by_ge_constraint(self):
        # pool_size has ge=1 constraint, so 0 is rejected
        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=0)

    def test_pool_size_negative_rejected(self):
        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=-1)

    def test_sqlite_path_construction(self):
        cfg = DatabaseConfig(sqlite_dir="/tmp/db")
        assert cfg.sqlite_path.endswith("ideer.db")

    def test_app_sqlalchemy_url_memory_raises(self):
        cfg = DatabaseConfig(backend="memory")
        with pytest.raises(ValueError, match="No SQLAlchemy URL"):
            _ = cfg.app_sqlalchemy_url

    def test_app_sqlalchemy_url_sqlite(self):
        cfg = DatabaseConfig(backend="sqlite", sqlite_dir="/tmp/db")
        url = cfg.app_sqlalchemy_url
        assert url.startswith("sqlite+aiosqlite:///")

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("postgres://u:p@host/db", id="postgres-scheme"),
            pytest.param("postgresql://u:p@host/db", id="postgresql-scheme"),
        ],
    )
    def test_app_sqlalchemy_url_postgres_rewrites(self, raw):
        cfg = DatabaseConfig(backend="postgres", postgres_url=raw)
        url = cfg.app_sqlalchemy_url
        assert "asyncpg" in url

    def test_backward_compat_aliases(self):
        cfg = DatabaseConfig(sqlite_dir="/tmp")
        assert cfg.checkpointer_sqlite_path == cfg.sqlite_path
        assert cfg.app_sqlite_path == cfg.sqlite_path


# ===================================================================
# GuardrailsConfig
# ===================================================================


class TestGuardrailsConfig:
    def test_defaults(self):
        cfg = GuardrailsConfig()
        assert cfg.enabled is False
        assert cfg.fail_closed is True
        assert cfg.passport is None
        assert cfg.provider is None

    def test_provider_config(self):
        prov = GuardrailProviderConfig(
            use="some.module:Provider",
            config={"key": "val"},
        )
        cfg = GuardrailsConfig(enabled=True, provider=prov)
        assert cfg.provider.use == "some.module:Provider"
        assert cfg.provider.config == {"key": "val"}

    def test_provider_default_config_is_empty_dict(self):
        prov = GuardrailProviderConfig(use="mod:Cls")
        assert prov.config == {}

    def test_guardrails_config_providers_none(self):
        cfg = GuardrailsConfig(enabled=True, fail_closed=False)
        assert cfg.provider is None

    def test_singleton_behavior(self):
        original = get_guardrails_config()
        try:
            reset_guardrails_config()
            cfg = get_guardrails_config()
            assert cfg.enabled is False  # default
            load_guardrails_config_from_dict({"enabled": True, "fail_closed": False})
            assert get_guardrails_config().enabled is True
        finally:
            reset_guardrails_config()
            # restore original
            import ideer.config.guardrails_config as mod

            mod._guardrails_config = original


# ===================================================================
# MemoryConfig
# ===================================================================


class TestMemoryConfig:
    def test_defaults(self):
        cfg = MemoryConfig()
        assert cfg.enabled is True
        assert cfg.storage_path == ""
        assert cfg.debounce_seconds == 30
        assert cfg.model_name is None
        assert cfg.max_facts == 100
        assert cfg.fact_confidence_threshold == pytest.approx(0.7)
        assert cfg.injection_enabled is True
        assert cfg.max_injection_tokens == 2000

    def test_debounce_seconds_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            MemoryConfig(debounce_seconds=0)  # < ge=1
        # Above upper bound
        with pytest.raises(ValidationError):
            MemoryConfig(debounce_seconds=301)  # > le=300
        # Boundary: ge=1
        cfg = MemoryConfig(debounce_seconds=1)
        assert cfg.debounce_seconds == 1
        # Boundary: le=300
        cfg = MemoryConfig(debounce_seconds=300)
        assert cfg.debounce_seconds == 300

    def test_max_facts_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            MemoryConfig(max_facts=9)  # < ge=10
        # Above upper bound
        with pytest.raises(ValidationError):
            MemoryConfig(max_facts=501)  # > le=500
        # Boundary: ge=10
        cfg = MemoryConfig(max_facts=10)
        assert cfg.max_facts == 10
        # Boundary: le=500
        cfg = MemoryConfig(max_facts=500)
        assert cfg.max_facts == 500

    def test_fact_confidence_threshold_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            MemoryConfig(fact_confidence_threshold=-0.1)
        # Above upper bound
        with pytest.raises(ValidationError):
            MemoryConfig(fact_confidence_threshold=1.1)
        # Boundary: ge=0.0
        cfg = MemoryConfig(fact_confidence_threshold=0.0)
        assert cfg.fact_confidence_threshold == pytest.approx(0.0)
        # Boundary: le=1.0
        cfg = MemoryConfig(fact_confidence_threshold=1.0)
        assert cfg.fact_confidence_threshold == pytest.approx(1.0)

    def test_max_injection_tokens_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            MemoryConfig(max_injection_tokens=99)
        # Above upper bound
        with pytest.raises(ValidationError):
            MemoryConfig(max_injection_tokens=8001)
        # Boundary: ge=100
        cfg = MemoryConfig(max_injection_tokens=100)
        assert cfg.max_injection_tokens == 100
        # Boundary: le=8000
        cfg = MemoryConfig(max_injection_tokens=8000)
        assert cfg.max_injection_tokens == 8000

    def test_storage_class_default(self):
        cfg = MemoryConfig()
        assert "FileMemoryStorage" in cfg.storage_class

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("", id="empty-defaults-per-user"),
            pytest.param("/abs/path/memory.json", id="absolute"),
            pytest.param("relative/path", id="relative"),
        ],
    )
    def test_storage_path_variants(self, path):
        cfg = MemoryConfig(storage_path=path)
        assert cfg.storage_path == path

    def test_singleton_get_set(self):
        original = get_memory_config()
        try:
            set_memory_config(MemoryConfig(enabled=False))
            assert get_memory_config().enabled is False
        finally:
            set_memory_config(original)

    def test_load_from_dict(self):
        original = get_memory_config()
        try:
            load_memory_config_from_dict({"enabled": False, "max_facts": 50})
            cfg = get_memory_config()
            assert cfg.enabled is False
            assert cfg.max_facts == 50
        finally:
            set_memory_config(original)


# ===================================================================
# RunEventsConfig
# ===================================================================


class TestRunEventsConfig:
    def test_defaults(self):
        cfg = RunEventsConfig()
        assert cfg.backend == "memory"
        assert cfg.max_trace_content == 10240
        assert cfg.track_token_usage is True

    @pytest.mark.parametrize(
        "backend",
        [
            pytest.param("memory", id="memory"),
            pytest.param("db", id="db"),
            pytest.param("jsonl", id="jsonl"),
        ],
    )
    def test_valid_backends(self, backend):
        cfg = RunEventsConfig(backend=backend)
        assert cfg.backend == backend

    def test_invalid_backend_rejected(self):
        with pytest.raises(ValidationError):
            RunEventsConfig(backend="s3")

    def test_max_trace_content_positive(self):
        cfg = RunEventsConfig(max_trace_content=1)
        assert cfg.max_trace_content == 1


# ===================================================================
# SafetyFinishReasonConfig
# ===================================================================


class TestSafetyFinishReasonConfig:
    def test_defaults(self):
        cfg = SafetyFinishReasonConfig()
        assert cfg.enabled is True
        assert cfg.detectors is None

    def test_custom_detectors(self):
        det = SafetyDetectorConfig(use="mod:Det", config={"a": 1})
        cfg = SafetyFinishReasonConfig(enabled=False, detectors=[det])
        assert len(cfg.detectors) == 1
        assert cfg.detectors[0].use == "mod:Det"

    def test_detector_default_config_empty_dict(self):
        det = SafetyDetectorConfig(use="mod:Det")
        assert det.config == {}

    def test_empty_detectors_list(self):
        cfg = SafetyFinishReasonConfig(detectors=[])
        assert cfg.detectors == []

    def test_detector_use_required(self):
        with pytest.raises(ValidationError):
            SafetyDetectorConfig()


# ===================================================================
# SandboxConfig
# ===================================================================


class TestSandboxConfig:
    def test_minimal(self):
        cfg = SandboxConfig(use="mod:Sandbox")
        assert cfg.use == "mod:Sandbox"
        assert cfg.allow_host_bash is False
        assert cfg.image is None
        assert cfg.port is None
        assert cfg.replicas is None
        assert cfg.mounts == []
        assert cfg.environment == {}

    def test_use_is_required(self):
        with pytest.raises(ValidationError):
            SandboxConfig()

    def test_volume_mount(self):
        vm = VolumeMountConfig(host_path="/a", container_path="/b", read_only=True)
        cfg = SandboxConfig(use="mod:Sandbox", mounts=[vm])
        assert cfg.mounts[0].read_only is True
        assert cfg.mounts[0].host_path == "/a"

    def test_volume_mount_defaults(self):
        vm = VolumeMountConfig(host_path="/x", container_path="/y")
        assert vm.read_only is False

    def test_volume_mount_paths_required(self):
        with pytest.raises(ValidationError):
            VolumeMountConfig(host_path="/x")
        with pytest.raises(ValidationError):
            VolumeMountConfig(container_path="/y")

    def test_bash_output_max_chars_bounds(self):
        with pytest.raises(ValidationError):
            SandboxConfig(use="mod:Sandbox", bash_output_max_chars=-1)

    def test_read_file_output_max_chars_default(self):
        cfg = SandboxConfig(use="mod:Sandbox")
        assert cfg.read_file_output_max_chars == 50000

    def test_ls_output_max_chars_default(self):
        cfg = SandboxConfig(use="mod:Sandbox")
        assert cfg.ls_output_max_chars == 20000

    def test_extra_fields_allowed(self):
        cfg = SandboxConfig(use="mod:Sandbox", custom_key="custom_val")
        assert cfg.custom_key == "custom_val"


# ===================================================================
# StreamBridgeConfig
# ===================================================================


class TestStreamBridgeConfig:
    def test_defaults(self):
        cfg = StreamBridgeConfig()
        assert cfg.type == "memory"
        assert cfg.redis_url is None
        assert cfg.queue_maxsize == 256

    @pytest.mark.parametrize(
        "bridge_type",
        [
            pytest.param("memory", id="memory"),
            pytest.param("redis", id="redis"),
        ],
    )
    def test_valid_types(self, bridge_type):
        cfg = StreamBridgeConfig(type=bridge_type)
        assert cfg.type == bridge_type

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            StreamBridgeConfig(type="kafka")

    def test_singleton_get_set(self):
        original = get_stream_bridge_config()
        try:
            set_stream_bridge_config(StreamBridgeConfig(type="redis", redis_url="redis://x"))
            assert get_stream_bridge_config().type == "redis"
            set_stream_bridge_config(None)
            assert get_stream_bridge_config() is None
        finally:
            set_stream_bridge_config(original)

    def test_load_from_dict_none(self):
        original = get_stream_bridge_config()
        try:
            load_stream_bridge_config_from_dict(None)
            assert get_stream_bridge_config() is None
        finally:
            set_stream_bridge_config(original)

    def test_load_from_dict(self):
        original = get_stream_bridge_config()
        try:
            load_stream_bridge_config_from_dict({"type": "memory", "queue_maxsize": 512})
            cfg = get_stream_bridge_config()
            assert cfg.type == "memory"
            assert cfg.queue_maxsize == 512
        finally:
            set_stream_bridge_config(original)


# ===================================================================
# SubagentsAppConfig
# ===================================================================


class TestSubagentsAppConfig:
    def test_defaults(self):
        cfg = SubagentsAppConfig()
        assert cfg.timeout_seconds == 900
        assert cfg.max_turns is None
        assert cfg.agents == {}
        assert cfg.custom_agents == {}

    def test_timeout_bounds(self):
        with pytest.raises(ValidationError):
            SubagentsAppConfig(timeout_seconds=0)  # < ge=1
        cfg = SubagentsAppConfig(timeout_seconds=1)
        assert cfg.timeout_seconds == 1

    def test_max_turns_bounds(self):
        with pytest.raises(ValidationError):
            SubagentsAppConfig(max_turns=0)  # < ge=1

    def test_get_timeout_for_unknown_agent_returns_default(self):
        cfg = SubagentsAppConfig(timeout_seconds=123)
        assert cfg.get_timeout_for("nonexistent") == 123

    def test_get_timeout_for_override(self):
        override = SubagentOverrideConfig(timeout_seconds=42)
        cfg = SubagentsAppConfig(
            timeout_seconds=900,
            agents={"my_agent": override},
        )
        assert cfg.get_timeout_for("my_agent") == 42

    def test_get_model_for_unknown_returns_none(self):
        cfg = SubagentsAppConfig()
        assert cfg.get_model_for("unknown") is None

    def test_get_model_for_override(self):
        override = SubagentOverrideConfig(model="gpt-4o")
        cfg = SubagentsAppConfig(agents={"a": override})
        assert cfg.get_model_for("a") == "gpt-4o"

    def test_get_max_turns_fallback_chain(self):
        # No overrides anywhere → builtin default
        cfg = SubagentsAppConfig()
        assert cfg.get_max_turns_for("a", builtin_default=25) == 25

    def test_get_max_turns_global_override(self):
        cfg = SubagentsAppConfig(max_turns=10)
        assert cfg.get_max_turns_for("a", builtin_default=25) == 10

    def test_get_max_turns_per_agent_override(self):
        override = SubagentOverrideConfig(max_turns=3)
        cfg = SubagentsAppConfig(max_turns=10, agents={"a": override})
        assert cfg.get_max_turns_for("a", builtin_default=25) == 3

    def test_get_skills_for_unknown_returns_none(self):
        cfg = SubagentsAppConfig()
        assert cfg.get_skills_for("a") is None

    def test_get_skills_for_override(self):
        override = SubagentOverrideConfig(skills=["tool1"])
        cfg = SubagentsAppConfig(agents={"a": override})
        assert cfg.get_skills_for("a") == ["tool1"]

    def test_custom_subagent_config(self):
        custom = CustomSubagentConfig(
            description="A custom agent",
            system_prompt="Be helpful",
        )
        assert custom.model == "inherit"
        assert custom.max_turns == 50
        assert custom.timeout_seconds == 900
        assert "task" in custom.disallowed_tools

    def test_custom_subagent_config_description_and_prompt_required(self):
        with pytest.raises(ValidationError):
            CustomSubagentConfig(description="only desc")
        with pytest.raises(ValidationError):
            CustomSubagentConfig(system_prompt="only prompt")


# ===================================================================
# SummarizationConfig
# ===================================================================


class TestSummarizationConfig:
    def test_defaults(self):
        cfg = SummarizationConfig()
        assert cfg.enabled is False
        assert cfg.model_name is None
        assert cfg.trigger is None
        assert cfg.keep.type == "messages"
        assert cfg.keep.value == 20
        assert cfg.trim_tokens_to_summarize == 4000
        assert cfg.preserve_recent_skill_count == 5
        assert cfg.preserve_recent_skill_tokens == 25000
        assert cfg.preserve_recent_skill_tokens_per_skill == 5000

    def test_context_size_to_tuple(self):
        cs = ContextSize(type="tokens", value=3000)
        assert cs.to_tuple() == ("tokens", 3000)

    @pytest.mark.parametrize(
        "ctype",
        [
            pytest.param("fraction", id="fraction"),
            pytest.param("tokens", id="tokens"),
            pytest.param("messages", id="messages"),
        ],
    )
    def test_valid_context_size_types(self, ctype):
        cs = ContextSize(type=ctype, value=10)
        assert cs.type == ctype

    def test_invalid_context_size_type(self):
        with pytest.raises(ValidationError):
            ContextSize(type="bytes", value=10)

    def test_trigger_as_list(self):
        trigger = [
            ContextSize(type="messages", value=50),
            ContextSize(type="tokens", value=4000),
        ]
        cfg = SummarizationConfig(trigger=trigger)
        assert len(cfg.trigger) == 2

    def test_preserve_recent_skill_count_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            SummarizationConfig(preserve_recent_skill_count=-1)
        # Boundary: ge=0
        cfg = SummarizationConfig(preserve_recent_skill_count=0)
        assert cfg.preserve_recent_skill_count == 0

    def test_skill_file_read_tool_names_default(self):
        cfg = SummarizationConfig()
        assert "read_file" in cfg.skill_file_read_tool_names
        assert "read" in cfg.skill_file_read_tool_names

    def test_summary_prompt_custom(self):
        cfg = SummarizationConfig(summary_prompt="Summarize: {messages}")
        assert "Summarize" in cfg.summary_prompt

    def test_singleton_get_set(self):
        original = get_summarization_config()
        try:
            set_summarization_config(SummarizationConfig(enabled=True))
            assert get_summarization_config().enabled is True
        finally:
            set_summarization_config(original)

    def test_load_from_dict(self):
        original = get_summarization_config()
        try:
            load_summarization_config_from_dict({"enabled": True, "model_name": "gpt-4o"})
            cfg = get_summarization_config()
            assert cfg.enabled is True
            assert cfg.model_name == "gpt-4o"
        finally:
            set_summarization_config(original)


# ===================================================================
# TitleConfig
# ===================================================================


class TestTitleConfig:
    def test_defaults(self):
        cfg = TitleConfig()
        assert cfg.enabled is True
        assert cfg.max_words == 6
        assert cfg.max_chars == 60
        assert cfg.model_name is None
        assert "max_words" in cfg.prompt_template

    def test_max_words_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            TitleConfig(max_words=0)  # < ge=1
        # Above upper bound
        with pytest.raises(ValidationError):
            TitleConfig(max_words=21)  # > le=20
        # Boundary: ge=1
        cfg = TitleConfig(max_words=1)
        assert cfg.max_words == 1
        # Boundary: le=20
        cfg = TitleConfig(max_words=20)
        assert cfg.max_words == 20

    def test_max_chars_bounds(self):
        # Below lower bound
        with pytest.raises(ValidationError):
            TitleConfig(max_chars=9)  # < ge=10
        # Above upper bound
        with pytest.raises(ValidationError):
            TitleConfig(max_chars=201)  # > le=200
        # Boundary: ge=10
        cfg = TitleConfig(max_chars=10)
        assert cfg.max_chars == 10
        # Boundary: le=200
        cfg = TitleConfig(max_chars=200)
        assert cfg.max_chars == 200

    @pytest.mark.parametrize(
        "words,chars",
        [
            pytest.param(1, 10, id="min-bound"),
            pytest.param(20, 200, id="max-bound"),
        ],
    )
    def test_boundary_valid(self, words, chars):
        cfg = TitleConfig(max_words=words, max_chars=chars)
        assert cfg.max_words == words
        assert cfg.max_chars == chars

    def test_singleton_get_set(self):
        original = get_title_config()
        try:
            set_title_config(TitleConfig(enabled=False))
            assert get_title_config().enabled is False
        finally:
            set_title_config(original)

    def test_load_from_dict(self):
        original = get_title_config()
        try:
            load_title_config_from_dict({"enabled": False, "max_words": 3})
            cfg = get_title_config()
            assert cfg.enabled is False
            assert cfg.max_words == 3
        finally:
            set_title_config(original)

    def test_reset_title_config(self):
        set_title_config(TitleConfig(enabled=False, max_words=10))
        reset_title_config()
        cfg = get_title_config()
        assert cfg.enabled is True
        assert cfg.max_words == 6


# ===================================================================
# ToolConfig / ToolGroupConfig
# ===================================================================


class TestToolConfig:
    def test_minimal(self):
        cfg = ToolConfig(name="bash", group="core", use="mod:bash_tool")
        assert cfg.name == "bash"
        assert cfg.group == "core"
        assert cfg.requires_network is False
        assert cfg.description == ""

    def test_name_group_use_required(self):
        with pytest.raises(ValidationError):
            ToolConfig(name="x", group="y")
        with pytest.raises(ValidationError):
            ToolConfig(name="x", use="mod:x")
        with pytest.raises(ValidationError):
            ToolConfig(group="y", use="mod:y")

    def test_requires_network_true(self):
        cfg = ToolConfig(name="web", group="net", use="mod:web", requires_network=True)
        assert cfg.requires_network is True

    def test_extra_fields_allowed(self):
        cfg = ToolConfig(name="t", group="g", use="mod:t", custom="val")
        assert cfg.custom == "val"


class TestToolGroupConfig:
    def test_minimal(self):
        cfg = ToolGroupConfig(name="core")
        assert cfg.name == "core"

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ToolGroupConfig()

    def test_extra_fields_allowed(self):
        cfg = ToolGroupConfig(name="g", extra_field="v")
        assert cfg.extra_field == "v"


# ===================================================================
# ToolSearchConfig
# ===================================================================


class TestToolSearchConfig:
    def test_default(self):
        cfg = ToolSearchConfig()
        assert cfg.enabled is False

    def test_enabled(self):
        cfg = ToolSearchConfig(enabled=True)
        assert cfg.enabled is True

    def test_singleton_behavior(self):
        from ideer.config import tool_search_config as mod

        original = mod._tool_search_config
        try:
            # get_tool_search_config returns default if None
            mod._tool_search_config = None
            cfg = get_tool_search_config()
            assert cfg.enabled is False

            load_tool_search_config_from_dict({"enabled": True})
            assert get_tool_search_config().enabled is True
        finally:
            mod._tool_search_config = original


# ===================================================================
# SkillEvolutionConfig
# ===================================================================


class TestSkillEvolutionConfig:
    def test_defaults(self):
        cfg = SkillEvolutionConfig()
        assert cfg.enabled is False
        assert cfg.moderation_model_name is None

    def test_enabled(self):
        cfg = SkillEvolutionConfig(enabled=True, moderation_model_name="gpt-4o")
        assert cfg.enabled is True
        assert cfg.moderation_model_name == "gpt-4o"

    def test_empty_construction(self):
        cfg = SkillEvolutionConfig(enabled=False)
        assert cfg.moderation_model_name is None


# ===================================================================
# LoopDetectionConfig
# ===================================================================


class TestToolFreqOverride:
    def test_valid(self):
        o = ToolFreqOverride(warn=5, hard_limit=10)
        assert o.warn == 5
        assert o.hard_limit == 10

    def test_warn_and_hard_limit_equal(self):
        o = ToolFreqOverride(warn=3, hard_limit=3)
        assert o.warn == o.hard_limit

    def test_hard_limit_less_than_warn_rejected(self):
        with pytest.raises(ValidationError, match="hard_limit"):
            ToolFreqOverride(warn=10, hard_limit=5)

    def test_warn_zero_rejected(self):
        with pytest.raises(ValidationError):
            ToolFreqOverride(warn=0, hard_limit=1)

    def test_hard_limit_zero_rejected(self):
        with pytest.raises(ValidationError):
            ToolFreqOverride(warn=1, hard_limit=0)


class TestLoopDetectionConfig:
    def test_defaults(self):
        cfg = LoopDetectionConfig()
        assert cfg.enabled is True
        assert cfg.warn_threshold == 3
        assert cfg.hard_limit == 5
        assert cfg.window_size == 20
        assert cfg.max_tracked_threads == 100
        assert cfg.tool_freq_warn == 30
        assert cfg.tool_freq_hard_limit == 50
        assert cfg.tool_freq_overrides == {}

    def test_disabled(self):
        cfg = LoopDetectionConfig(enabled=False)
        assert cfg.enabled is False

    def test_valid_custom_values(self):
        cfg = LoopDetectionConfig(
            warn_threshold=2,
            hard_limit=10,
            window_size=50,
            max_tracked_threads=500,
            tool_freq_warn=20,
            tool_freq_hard_limit=100,
        )
        assert cfg.warn_threshold == 2
        assert cfg.hard_limit == 10

    def test_hard_limit_less_than_warn_threshold_rejected(self):
        with pytest.raises(ValidationError, match="hard_limit must be greater than or equal to warn_threshold"):
            LoopDetectionConfig(warn_threshold=10, hard_limit=5)

    def test_hard_limit_equal_warn_threshold_accepted(self):
        cfg = LoopDetectionConfig(warn_threshold=5, hard_limit=5)
        assert cfg.hard_limit == cfg.warn_threshold

    def test_tool_freq_hard_limit_less_than_warn_rejected(self):
        with pytest.raises(ValidationError, match="tool_freq_hard_limit must be greater than or equal to tool_freq_warn"):
            LoopDetectionConfig(tool_freq_warn=50, tool_freq_hard_limit=10)

    def test_tool_freq_hard_limit_equal_warn_accepted(self):
        cfg = LoopDetectionConfig(tool_freq_warn=30, tool_freq_hard_limit=30)
        assert cfg.tool_freq_hard_limit == cfg.tool_freq_warn

    def test_warn_threshold_zero_rejected(self):
        with pytest.raises(ValidationError):
            LoopDetectionConfig(warn_threshold=0)

    def test_hard_limit_zero_rejected(self):
        with pytest.raises(ValidationError):
            LoopDetectionConfig(hard_limit=0)

    def test_window_size_zero_rejected(self):
        with pytest.raises(ValidationError):
            LoopDetectionConfig(window_size=0)

    def test_max_tracked_threads_zero_rejected(self):
        with pytest.raises(ValidationError):
            LoopDetectionConfig(max_tracked_threads=0)

    def test_tool_freq_overrides(self):
        overrides = {
            "bash": ToolFreqOverride(warn=100, hard_limit=200),
            "read": ToolFreqOverride(warn=10, hard_limit=20),
        }
        cfg = LoopDetectionConfig(tool_freq_overrides=overrides)
        assert cfg.tool_freq_overrides["bash"].warn == 100
        assert cfg.tool_freq_overrides["read"].hard_limit == 20

    def test_tool_freq_override_invalid_rejected(self):
        # ToolFreqOverride itself validates hard_limit >= warn
        with pytest.raises(ValidationError):
            ToolFreqOverride(warn=10, hard_limit=5)


# ===================================================================
# TracingConfig
# ===================================================================


class TestTracingConfig:
    def test_langsmith_config(self):
        cfg = LangSmithTracingConfig(
            enabled=True,
            api_key="test-key",
            project="my-project",
            endpoint="https://example.com",
        )
        assert cfg.enabled is True
        assert cfg.api_key == "test-key"
        assert cfg.is_configured is True

    def test_langsmith_not_configured_when_disabled(self):
        cfg = LangSmithTracingConfig(
            enabled=False,
            api_key=None,
            project="proj",
            endpoint="https://x",
        )
        assert cfg.is_configured is False

    def test_langsmith_not_configured_when_no_api_key(self):
        cfg = LangSmithTracingConfig(
            enabled=True,
            api_key=None,
            project="proj",
            endpoint="https://x",
        )
        assert cfg.is_configured is False

    def test_langsmith_validate_enabled_without_key_raises(self):
        cfg = LangSmithTracingConfig(
            enabled=True,
            api_key=None,
            project="proj",
            endpoint="https://x",
        )
        with pytest.raises(ValueError, match="LANGSMITH_API_KEY"):
            cfg.validate()

    def test_langsmith_validate_disabled_ok(self):
        cfg = LangSmithTracingConfig(
            enabled=False,
            api_key=None,
            project="proj",
            endpoint="https://x",
        )
        cfg.validate()  # no error

    def test_langfuse_config(self):
        cfg = LangfuseTracingConfig(
            enabled=True,
            public_key="pk",
            secret_key="sk",
            host="https://langfuse.example.com",
        )
        assert cfg.is_configured is True

    def test_langfuse_not_configured_when_disabled(self):
        cfg = LangfuseTracingConfig(
            enabled=False,
            public_key=None,
            secret_key=None,
            host="https://x",
        )
        assert cfg.is_configured is False

    def test_langfuse_not_configured_when_missing_keys(self):
        cfg = LangfuseTracingConfig(
            enabled=True,
            public_key=None,
            secret_key="sk",
            host="https://x",
        )
        assert cfg.is_configured is False

    def test_langfuse_validate_missing_public_key(self):
        cfg = LangfuseTracingConfig(
            enabled=True,
            public_key=None,
            secret_key="sk",
            host="https://x",
        )
        with pytest.raises(ValueError, match="LANGFUSE_PUBLIC_KEY"):
            cfg.validate()

    def test_langfuse_validate_missing_secret_key(self):
        cfg = LangfuseTracingConfig(
            enabled=True,
            public_key="pk",
            secret_key=None,
            host="https://x",
        )
        with pytest.raises(ValueError, match="LANGFUSE_SECRET_KEY"):
            cfg.validate()

    def test_langfuse_validate_disabled_ok(self):
        cfg = LangfuseTracingConfig(
            enabled=False,
            public_key=None,
            secret_key=None,
            host="https://x",
        )
        cfg.validate()  # no error

    def test_tracing_config_defaults(self):
        ls = LangSmithTracingConfig(enabled=False, api_key=None, project="p", endpoint="e")
        lf = LangfuseTracingConfig(enabled=False, public_key=None, secret_key=None, host="h")
        cfg = TracingConfig(langsmith=ls, langfuse=lf)
        assert cfg.is_configured is False
        assert cfg.enabled_providers == []
        assert cfg.explicitly_enabled_providers == []

    def test_tracing_config_explicitly_enabled(self):
        ls = LangSmithTracingConfig(enabled=True, api_key=None, project="p", endpoint="e")
        lf = LangfuseTracingConfig(enabled=False, public_key=None, secret_key=None, host="h")
        cfg = TracingConfig(langsmith=ls, langfuse=lf)
        assert cfg.explicitly_enabled_providers == ["langsmith"]
        assert cfg.enabled_providers == []  # not fully configured

    def test_tracing_config_both_configured(self):
        ls = LangSmithTracingConfig(enabled=True, api_key="key", project="p", endpoint="e")
        lf = LangfuseTracingConfig(enabled=True, public_key="pk", secret_key="sk", host="h")
        cfg = TracingConfig(langsmith=ls, langfuse=lf)
        assert cfg.enabled_providers == ["langsmith", "langfuse"]
        assert cfg.is_configured is True

    def test_reset_tracing_config(self):
        reset_tracing_config()
        # Should not raise, next get_tracing_config rebuilds from env
        reset_tracing_config()


# ===================================================================
# ACPAgentConfig
# ===================================================================


class TestACPAgentConfig:
    def test_minimal(self):
        cfg = ACPAgentConfig(command="my-agent", description="A test agent")
        assert cfg.command == "my-agent"
        assert cfg.description == "A test agent"
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.model is None
        assert cfg.auto_approve_permissions is False

    def test_full_config(self):
        cfg = ACPAgentConfig(
            command="run",
            args=["--verbose", "--port", "8080"],
            env={"API_KEY": "secret", "$HOST_VAR": "$HOST_VALUE"},
            description="Full agent",
            model="gpt-4o",
            auto_approve_permissions=True,
        )
        assert cfg.args == ["--verbose", "--port", "8080"]
        assert cfg.env["API_KEY"] == "secret"
        assert cfg.model == "gpt-4o"
        assert cfg.auto_approve_permissions is True

    def test_command_required(self):
        with pytest.raises(ValidationError):
            ACPAgentConfig(description="no command")

    def test_description_required(self):
        with pytest.raises(ValidationError):
            ACPAgentConfig(command="cmd")

    def test_get_acp_agents_default_empty(self):
        # Save and restore
        from ideer.config import acp_config as mod

        original = mod._acp_agents.copy()
        try:
            mod._acp_agents = {}
            assert get_acp_agents() == {}
        finally:
            mod._acp_agents = original

    def test_load_acp_config_from_dict(self):
        from ideer.config import acp_config as mod

        original = mod._acp_agents.copy()
        try:
            load_acp_config_from_dict(
                {
                    "agent1": {"command": "run", "description": "First"},
                    "agent2": {"command": "run2", "description": "Second", "model": "gpt-4o"},
                }
            )
            agents = get_acp_agents()
            assert len(agents) == 2
            assert agents["agent1"].command == "run"
            assert agents["agent2"].model == "gpt-4o"
        finally:
            mod._acp_agents = original

    def test_load_acp_config_none(self):
        from ideer.config import acp_config as mod

        original = mod._acp_agents.copy()
        try:
            load_acp_config_from_dict(None)
            assert get_acp_agents() == {}
        finally:
            mod._acp_agents = original

    def test_load_acp_config_invalid_raises(self):
        from ideer.config import acp_config as mod

        original = mod._acp_agents.copy()
        try:
            # Missing required 'command' field
            with pytest.raises(ValidationError):
                load_acp_config_from_dict({"bad": {"description": "d"}})
        finally:
            mod._acp_agents = original


# ===================================================================
# ModelConfig
# ===================================================================


class TestModelConfig:
    def test_minimal(self):
        cfg = ModelConfig(
            name="gpt-4o",
            display_name=None,
            description=None,
            use="langchain_openai.ChatOpenAI",
            model="gpt-4o",
        )
        assert cfg.name == "gpt-4o"
        assert cfg.use == "langchain_openai.ChatOpenAI"
        assert cfg.model == "gpt-4o"
        assert cfg.supports_thinking is False
        assert cfg.supports_reasoning_effort is False
        assert cfg.supports_vision is False
        assert cfg.use_responses_api is None
        assert cfg.output_version is None
        assert cfg.when_thinking_enabled is None
        assert cfg.when_thinking_disabled is None
        assert cfg.thinking is None

    def test_full_config(self):
        cfg = ModelConfig(
            name="o3",
            display_name="O3",
            description="Reasoning model",
            use="langchain_openai.ChatOpenAI",
            model="o3",
            use_responses_api=True,
            output_version="responses/v1",
            supports_thinking=True,
            supports_reasoning_effort=True,
            supports_vision=True,
            when_thinking_enabled={"reasoning_effort": "high"},
            when_thinking_disabled={"reasoning_effort": "low"},
            thinking={"budget_tokens": 10000},
        )
        assert cfg.use_responses_api is True
        assert cfg.supports_thinking is True
        assert cfg.supports_vision is True
        assert cfg.thinking == {"budget_tokens": 10000}

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ModelConfig(
                display_name="x",
                description=None,
                use="mod:x",
                model="m",
            )

    def test_use_required(self):
        with pytest.raises(ValidationError):
            ModelConfig(
                name="n",
                display_name=None,
                description=None,
                model="m",
            )

    def test_model_required(self):
        with pytest.raises(ValidationError):
            ModelConfig(
                name="n",
                display_name=None,
                description=None,
                use="mod:x",
            )

    def test_extra_fields_allowed(self):
        cfg = ModelConfig(
            name="m",
            display_name=None,
            description=None,
            use="mod:x",
            model="m",
            temperature=0.7,
            max_tokens=4096,
        )
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096

    def test_display_name_none_default(self):
        cfg = ModelConfig(
            name="m",
            display_name=None,
            description=None,
            use="mod:x",
            model="m",
        )
        assert cfg.display_name is None

    def test_description_none_default(self):
        cfg = ModelConfig(
            name="m",
            display_name=None,
            description=None,
            use="mod:x",
            model="m",
        )
        assert cfg.description is None


# ===================================================================
# SkillsConfig
# ===================================================================


class TestSkillsConfig:
    def test_defaults(self):
        cfg = SkillsConfig()
        assert cfg.use == "ideer.skills.storage.local_skill_storage:LocalSkillStorage"
        assert cfg.path is None
        assert cfg.container_path == "/mnt/skills"

    def test_custom_use(self):
        cfg = SkillsConfig(use="custom.module:Storage")
        assert cfg.use == "custom.module:Storage"

    def test_custom_path(self):
        cfg = SkillsConfig(path="/opt/skills")
        assert cfg.path == "/opt/skills"

    def test_custom_container_path(self):
        cfg = SkillsConfig(container_path="/container/skills")
        assert cfg.container_path == "/container/skills"

    def test_get_skill_container_path(self):
        cfg = SkillsConfig(container_path="/mnt/skills")
        assert cfg.get_skill_container_path("my-skill") == "/mnt/skills/public/my-skill"
        assert cfg.get_skill_container_path("custom-skill", category="custom") == "/mnt/skills/custom/custom-skill"

    def test_get_skills_path_with_explicit_path(self, tmp_path):
        cfg = SkillsConfig(path=str(tmp_path))
        result = cfg.get_skills_path()
        assert result == tmp_path.resolve()

    def test_get_skills_path_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("IDEER_SKILLS_PATH", str(tmp_path))
        cfg = SkillsConfig()
        result = cfg.get_skills_path()
        assert result == tmp_path.resolve()

    def test_get_skills_path_fallback_to_project_root(self, tmp_path, monkeypatch):
        monkeypatch.delenv("IDEER_SKILLS_PATH", raising=False)
        # Create a fake project root with a skills directory so project_default.is_dir() is True
        fake_root = tmp_path / "project"
        fake_root.mkdir()
        (fake_root / "skills").mkdir()
        monkeypatch.setattr("ideer.config.runtime_paths.project_root", lambda: fake_root)
        monkeypatch.setattr("ideer.config.skills_config.project_root", lambda: fake_root)
        cfg = SkillsConfig()
        result = cfg.get_skills_path()
        assert result == (fake_root / "skills").resolve()


# ===================================================================
# NetworkMode
# ===================================================================


class TestNetworkMode:
    def test_default_is_online(self, monkeypatch):
        monkeypatch.delenv("IDEER_NETWORK_MODE", raising=False)
        assert get_network_mode() == NetworkMode.ONLINE
        assert is_offline() is False

    def test_explicit_online(self, monkeypatch):
        monkeypatch.setenv("IDEER_NETWORK_MODE", "online")
        assert get_network_mode() == NetworkMode.ONLINE
        assert is_offline() is False

    def test_explicit_offline(self, monkeypatch):
        monkeypatch.setenv("IDEER_NETWORK_MODE", "offline")
        assert get_network_mode() == NetworkMode.OFFLINE
        assert is_offline() is True

    def test_empty_string_defaults_online(self, monkeypatch):
        monkeypatch.setenv("IDEER_NETWORK_MODE", "")
        assert get_network_mode() == NetworkMode.ONLINE

    def test_unrecognized_value_defaults_online(self, monkeypatch):
        monkeypatch.setenv("IDEER_NETWORK_MODE", "unknown")
        assert get_network_mode() == NetworkMode.ONLINE

    def test_network_mode_enum_values(self):
        assert NetworkMode.ONLINE == "online"
        assert NetworkMode.OFFLINE == "offline"
