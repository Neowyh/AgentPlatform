"""T4: chat-model construction cache in ideer.models.factory.

Same effective settings share one instance (attach_tracing=False path only);
any settings difference — including a config edit — builds fresh (#3107-safe).
attach_tracing=True never shares, so per-call callback attachment cannot
accumulate on a shared instance.
"""

from __future__ import annotations

import pytest
from langchain.chat_models import BaseChatModel

from ideer.config.app_config import AppConfig
from ideer.config.model_config import ModelConfig
from ideer.config.sandbox_config import SandboxConfig
from ideer.models import factory as factory_module
from ideer.models.factory import clear_chat_model_cache, create_chat_model


def _make_app_config(models: list[ModelConfig]) -> AppConfig:
    return AppConfig(
        models=models,
        sandbox=SandboxConfig(use="ideer.sandbox.local:LocalSandboxProvider"),
    )


def _make_model(
    name: str = "test-model",
    *,
    max_tokens: int | None = None,
    when_thinking_enabled: dict | None = None,
) -> ModelConfig:
    return ModelConfig(
        name=name,
        display_name=name,
        description=None,
        use="langchain_openai:ChatOpenAI",
        model=name,
        max_tokens=max_tokens,
        supports_thinking=when_thinking_enabled is not None,
        supports_reasoning_effort=False,
        when_thinking_enabled=when_thinking_enabled,
        when_thinking_disabled=None,
        thinking=None,
        supports_vision=False,
    )


class FakeChatModel(BaseChatModel):
    """Minimal BaseChatModel stub."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError

    def _stream(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch):
    monkeypatch.setattr(factory_module, "resolve_class", lambda path, base: FakeChatModel)
    monkeypatch.setattr(factory_module, "build_tracing_callbacks", lambda: [])
    clear_chat_model_cache()
    yield
    clear_chat_model_cache()


def _patch_config(monkeypatch, app_config: AppConfig) -> None:
    monkeypatch.setattr(factory_module, "get_app_config", lambda: app_config)


def test_identical_calls_share_instance(monkeypatch):
    _patch_config(monkeypatch, _make_app_config([_make_model()]))
    first = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    second = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    assert second is first


def test_thinking_flag_splits_cache(monkeypatch):
    _patch_config(
        monkeypatch,
        _make_app_config([_make_model(when_thinking_enabled={"max_tokens": 222})]),
    )
    plain = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    thinking = create_chat_model(name="test-model", thinking_enabled=True, attach_tracing=False)
    assert thinking is not plain


def test_config_edit_busts_cache(monkeypatch):
    _patch_config(monkeypatch, _make_app_config([_make_model(max_tokens=100)]))
    before = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    _patch_config(monkeypatch, _make_app_config([_make_model(max_tokens=200)]))
    after = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    assert after is not before


def test_attach_tracing_true_never_shares(monkeypatch):
    _patch_config(monkeypatch, _make_app_config([_make_model()]))
    first = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=True)
    second = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=True)
    assert second is not first


def test_clear_chat_model_cache_resets(monkeypatch):
    _patch_config(monkeypatch, _make_app_config([_make_model()]))
    before = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    clear_chat_model_cache()
    after = create_chat_model(name="test-model", thinking_enabled=False, attach_tracing=False)
    assert after is not before
