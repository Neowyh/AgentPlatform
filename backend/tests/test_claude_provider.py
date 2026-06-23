"""Comprehensive tests for ideer.models.claude_provider.ClaudeChatModel.

Covers all public and private methods: model_post_init, credential loading
paths, OAuth detection, prompt caching, thinking budget, billing injection,
retry logic with backoff, and sync/async generate overrides.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from pydantic import SecretStr

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OAUTH_TOKEN = "sk-ant-oat01-abc123"
API_KEY = "sk-ant-api03-realkey123"


def _make_model(**overrides: Any):
    """Construct a ClaudeChatModel with sensible defaults for testing.

    We patch ``ChatAnthropic.model_post_init`` so that no real Anthropic
    client is created.  The caller can still control ``_is_oauth`` and other
    private attrs afterwards.
    """
    from ideer.models.claude_provider import ClaudeChatModel

    defaults: dict[str, Any] = {
        "model": "claude-sonnet-4-6",
        "anthropic_api_key": API_KEY,
        "max_tokens": 8192,
    }
    defaults.update(overrides)

    with patch.object(ClaudeChatModel, "model_post_init", lambda self, ctx: None):
        obj = ClaudeChatModel(**defaults)

    # Reset private attrs that the skipped model_post_init would have set
    obj._is_oauth = False
    obj._oauth_access_token = ""
    # Provide stub clients so _patch_client_oauth can run without a real SDK
    obj._client = MagicMock()
    obj._client.api_key = API_KEY
    obj._client.auth_token = None
    obj._async_client = MagicMock()
    obj._async_client.api_key = API_KEY
    obj._async_client.auth_token = None
    return obj


# ===================================================================
# Module-level constants
# ===================================================================


class TestModuleConstants:
    def test_max_retries(self):
        from ideer.models.claude_provider import MAX_RETRIES

        assert MAX_RETRIES == 3

    def test_thinking_budget_ratio(self):
        from ideer.models.claude_provider import THINKING_BUDGET_RATIO

        assert THINKING_BUDGET_RATIO == 0.8

    def test_oauth_billing_header_default(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        assert "cc_version=" in OAUTH_BILLING_HEADER

    def test_oauth_billing_header_env_override(self):
        """Env var override is picked up when the module is (re)loaded."""
        import importlib
        import os

        import ideer.models.claude_provider as mod

        old_val = os.environ.get("ANTHROPIC_BILLING_HEADER")
        os.environ["ANTHROPIC_BILLING_HEADER"] = "custom-header"
        try:
            importlib.reload(mod)
            assert mod.OAUTH_BILLING_HEADER == "custom-header"
        finally:
            if old_val is None:
                os.environ.pop("ANTHROPIC_BILLING_HEADER", None)
            else:
                os.environ["ANTHROPIC_BILLING_HEADER"] = old_val
            importlib.reload(mod)


# ===================================================================
# _validate_retry_config
# ===================================================================


class TestValidateRetryConfig:
    def test_valid_config(self):
        model = _make_model(retry_max_attempts=5)
        model._validate_retry_config()  # should not raise

    def test_zero_attempts_raises(self):
        model = _make_model(retry_max_attempts=0)
        with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
            model._validate_retry_config()

    def test_negative_attempts_raises(self):
        model = _make_model(retry_max_attempts=-1)
        with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
            model._validate_retry_config()


# ===================================================================
# model_post_init  (credential loading + OAuth detection)
# ===================================================================


class TestModelPostInit:
    """Test the real model_post_init with mocked credential_loader."""

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential", return_value=None)
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_standard_api_key(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """Plain API key passes through without OAuth setup."""
        from ideer.models.claude_provider import ClaudeChatModel

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key=API_KEY)
        assert model._is_oauth is False
        assert model._oauth_access_token == ""
        mock_super_init.assert_called_once()

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=True)
    def test_oauth_token_detected(self, mock_is_oauth, mock_super_init):
        """OAuth token triggers _is_oauth, sets headers, disables caching."""
        from ideer.models.claude_provider import ClaudeChatModel

        # Provide stub clients after super().model_post_init
        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key=OAUTH_TOKEN)
        # Simulate what super().model_post_init would create
        model._client = MagicMock()
        model._async_client = MagicMock()

        # Manually run model_post_init to test the real logic
        with patch.object(model, "_patch_client_oauth"):
            model.model_post_init(None)

        assert model._is_oauth is True
        assert model._oauth_access_token == OAUTH_TOKEN
        assert model.enable_prompt_caching is False
        assert "anthropic-beta" in model.default_headers

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential")
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=True)
    def test_fallback_to_claude_code_credential(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """When api_key is empty, loads credential from Claude Code CLI."""
        from ideer.models.claude_provider import ClaudeChatModel

        cred = SimpleNamespace(access_token=OAUTH_TOKEN, source="claude-cli-env")
        mock_load_cred.return_value = cred
        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="")
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        assert model._is_oauth is True
        mock_load_cred.assert_called_once()

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential")
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_placeholder_key_falls_back(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """Placeholder key 'your-anthropic-api-key' triggers credential lookup."""
        from ideer.models.claude_provider import ClaudeChatModel

        cred = SimpleNamespace(access_token=API_KEY, source="claude-cli-env")
        mock_load_cred.return_value = cred
        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="your-anthropic-api-key")
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        mock_load_cred.assert_called_once()

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential", return_value=None)
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_no_key_no_credential_logs_warning(self, mock_is_oauth, mock_load_cred, mock_super_init, caplog):
        """When no key and no credential, logs a warning."""
        import logging

        from ideer.models.claude_provider import ClaudeChatModel

        mock_super_init.side_effect = lambda ctx: None

        with caplog.at_level(logging.WARNING):
            model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="")
            model._client = MagicMock()
            model._async_client = MagicMock()
            model.model_post_init(None)

        assert "No Anthropic API key" in caplog.text

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential", return_value=None)
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_string_api_key_converted_to_secretstr(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """A plain string api_key is wrapped in SecretStr."""
        from ideer.models.claude_provider import ClaudeChatModel

        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="plain-string-key")
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        assert isinstance(model.anthropic_api_key, SecretStr)

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential")
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=True)
    def test_oauth_patches_both_clients(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """OAuth path calls _patch_client_oauth on both sync and async clients."""
        from ideer.models.claude_provider import ClaudeChatModel

        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key=OAUTH_TOKEN)
        sync_client = MagicMock()
        async_client = MagicMock()
        model._client = sync_client
        model._async_client = async_client

        with patch.object(model, "_patch_client_oauth") as mock_patch:
            model.model_post_init(None)

        assert mock_patch.call_count == 2
        mock_patch.assert_any_call(sync_client)
        mock_patch.assert_any_call(async_client)


# ===================================================================
# _patch_client_oauth
# ===================================================================


class TestPatchClientOauth:
    def test_swaps_api_key_for_auth_token(self):
        model = _make_model()
        model._oauth_access_token = OAUTH_TOKEN

        client = MagicMock()
        client.api_key = "old-key"
        client.auth_token = None

        model._patch_client_oauth(client)

        assert client.api_key is None
        assert client.auth_token == OAUTH_TOKEN

    def test_noop_when_attrs_missing(self):
        """If the client doesn't have api_key/auth_token, it's a no-op."""
        model = _make_model()
        model._oauth_access_token = OAUTH_TOKEN

        client = SimpleNamespace()  # no api_key or auth_token
        model._patch_client_oauth(client)  # should not raise


# ===================================================================
# _apply_oauth_billing
# ===================================================================


class TestApplyOauthBilling:
    def test_injects_billing_into_empty_system(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model()
        payload: dict[str, Any] = {}
        model._apply_oauth_billing(payload)

        assert isinstance(payload["system"], list)
        assert payload["system"][0]["text"] == OAUTH_BILLING_HEADER

    def test_injects_billing_into_list_system(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model()
        existing = {"type": "text", "text": "You are helpful."}
        payload: dict[str, Any] = {"system": [existing]}
        model._apply_oauth_billing(payload)

        assert len(payload["system"]) == 2
        assert payload["system"][0]["text"] == OAUTH_BILLING_HEADER

    def test_deduplicates_existing_billing_in_list(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model()
        billing = {"type": "text", "text": OAUTH_BILLING_HEADER}
        other = {"type": "text", "text": "You are helpful."}
        payload: dict[str, Any] = {"system": [billing, other]}
        model._apply_oauth_billing(payload)

        # Should have exactly one billing block + the other block
        assert len(payload["system"]) == 2
        billing_blocks = [b for b in payload["system"] if b.get("text") == OAUTH_BILLING_HEADER]
        assert len(billing_blocks) == 1

    def test_injects_billing_into_string_system_without_existing(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model()
        payload: dict[str, Any] = {"system": "You are helpful."}
        model._apply_oauth_billing(payload)

        assert isinstance(payload["system"], list)
        assert len(payload["system"]) == 2
        assert payload["system"][0]["text"] == OAUTH_BILLING_HEADER
        assert payload["system"][1]["text"] == "You are helpful."

    def test_injects_billing_into_string_system_with_existing(self):
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model()
        payload: dict[str, Any] = {"system": f"prefix {OAUTH_BILLING_HEADER} suffix"}
        model._apply_oauth_billing(payload)

        assert isinstance(payload["system"], list)
        assert len(payload["system"]) == 1

    def test_creates_metadata_with_user_id(self):
        model = _make_model()
        payload: dict[str, Any] = {}
        model._apply_oauth_billing(payload)

        assert "metadata" in payload
        assert "user_id" in payload["metadata"]
        user_id = json.loads(payload["metadata"]["user_id"])
        assert "device_id" in user_id
        assert user_id["account_uuid"] == "ideer"
        assert "session_id" in user_id

    def test_preserves_existing_metadata_user_id(self):
        model = _make_model()
        payload: dict[str, Any] = {"metadata": {"user_id": "existing-user"}}
        model._apply_oauth_billing(payload)

        assert payload["metadata"]["user_id"] == "existing-user"

    def test_preserves_existing_metadata_without_user_id(self):
        model = _make_model()
        payload: dict[str, Any] = {"metadata": {"other_key": "value"}}
        model._apply_oauth_billing(payload)

        assert payload["metadata"]["other_key"] == "value"
        assert "user_id" in payload["metadata"]

    def test_device_id_is_stable_per_hostname(self):
        """device_id should be deterministic for the same hostname."""
        model = _make_model()
        payload1: dict[str, Any] = {}
        payload2: dict[str, Any] = {}
        model._apply_oauth_billing(payload1)
        model._apply_oauth_billing(payload2)

        id1 = json.loads(payload1["metadata"]["user_id"])["device_id"]
        id2 = json.loads(payload2["metadata"]["user_id"])["device_id"]
        assert id1 == id2


# ===================================================================
# _apply_prompt_caching
# ===================================================================


class TestApplyPromptCaching:
    def test_system_string_converted_to_list(self):
        model = _make_model()
        payload: dict[str, Any] = {"system": "You are helpful.", "messages": []}
        model._apply_prompt_caching(payload)

        assert isinstance(payload["system"], list)
        assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_system_list_blocks_cached(self):
        model = _make_model()
        payload: dict[str, Any] = {
            "system": [{"type": "text", "text": "You are helpful."}],
            "messages": [],
        }
        model._apply_prompt_caching(payload)

        assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_recent_messages_get_cache_control(self):
        model = _make_model(prompt_cache_size=2)
        payload: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": "old message"},
                {"role": "assistant", "content": "reply"},
                {"role": "user", "content": "new message"},
            ],
        }
        model._apply_prompt_caching(payload)

        # Only last 2 messages should be considered for caching.
        # String content is converted to list-of-dicts with cache_control on the block.
        # First message (outside cache window) stays as a plain string.
        assert isinstance(payload["messages"][0]["content"], str)
        # Last two messages have their content converted to list with cache_control
        for idx in (1, 2):
            content = payload["messages"][idx]["content"]
            assert isinstance(content, list)
            assert content[0].get("cache_control") == {"type": "ephemeral"}

    def test_string_content_converted_to_list(self):
        model = _make_model(prompt_cache_size=1)
        payload: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": "hello"},
            ],
        }
        model._apply_prompt_caching(payload)

        assert isinstance(payload["messages"][0]["content"], list)
        assert payload["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    def test_empty_string_content_not_converted(self):
        model = _make_model(prompt_cache_size=1)
        payload: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": ""},
            ],
        }
        model._apply_prompt_caching(payload)

        # Empty string should stay as-is (not converted)
        assert payload["messages"][0]["content"] == ""

    def test_last_tool_gets_cache_control(self):
        model = _make_model()
        payload: dict[str, Any] = {
            "messages": [],
            "tools": [
                {"name": "tool1", "description": "first"},
                {"name": "tool2", "description": "last"},
            ],
        }
        model._apply_prompt_caching(payload)

        assert "cache_control" not in payload["tools"][0]
        assert payload["tools"][1]["cache_control"] == {"type": "ephemeral"}

    def test_max_cache_breakpoints_limit(self):
        """Only the last 4 candidates get cache_control."""
        model = _make_model(prompt_cache_size=10)
        system_blocks = [{"type": "text", "text": f"block {i}"} for i in range(5)]
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(5)]
        payload: dict[str, Any] = {
            "system": system_blocks,
            "messages": messages,
            "tools": [{"name": "t1"}, {"name": "t2"}],
        }
        model._apply_prompt_caching(payload)

        # Count total cache_control markers across all sections
        count = 0
        for b in system_blocks:
            if "cache_control" in b:
                count += 1
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):
                for block in c:
                    if isinstance(block, dict) and "cache_control" in block:
                        count += 1
            elif isinstance(c, str) and c:
                count += 1  # would have been converted
        for t in payload["tools"]:
            if "cache_control" in t:
                count += 1

        assert count <= 4

    def test_non_dict_messages_skipped(self):
        model = _make_model(prompt_cache_size=2)
        payload: dict[str, Any] = {
            "messages": [
                "not-a-dict",
                {"role": "user", "content": "hello"},
            ],
        }
        model._apply_prompt_caching(payload)
        # Should not raise; non-dict message is skipped

    def test_list_content_blocks_cached(self):
        model = _make_model(prompt_cache_size=1)
        payload: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "part1"},
                        {"type": "text", "text": "part2"},
                    ],
                },
            ],
        }
        model._apply_prompt_caching(payload)

        # Only last MAX_CACHE_BREAKPOINTS candidates get cache_control
        for block in payload["messages"][0]["content"]:
            assert "cache_control" in block

    def test_no_system_no_messages(self):
        """Empty payload should not raise."""
        model = _make_model()
        payload: dict[str, Any] = {}
        model._apply_prompt_caching(payload)

    def test_non_list_non_string_system(self):
        """Integer system value is ignored."""
        model = _make_model()
        payload: dict[str, Any] = {"system": 42, "messages": []}
        model._apply_prompt_caching(payload)

    def test_non_text_type_blocks_in_system_skipped(self):
        """Non-text type blocks are not added as cache candidates."""
        model = _make_model()
        payload: dict[str, Any] = {
            "system": [
                {"type": "image", "source": {"data": "abc"}},
                {"type": "text", "text": "hello"},
            ],
            "messages": [],
        }
        model._apply_prompt_caching(payload)

        assert "cache_control" not in payload["system"][0]
        assert payload["system"][1]["cache_control"] == {"type": "ephemeral"}


# ===================================================================
# _apply_thinking_budget
# ===================================================================


class TestApplyThinkingBudget:
    def test_auto_budget_when_thinking_enabled(self):
        model = _make_model(max_tokens=10000)
        payload: dict[str, Any] = {
            "thinking": {"type": "enabled"},
            "max_tokens": 10000,
        }
        model._apply_thinking_budget(payload)

        assert payload["thinking"]["budget_tokens"] == 8000

    def test_no_budget_when_thinking_not_present(self):
        model = _make_model()
        payload: dict[str, Any] = {"max_tokens": 10000}
        model._apply_thinking_budget(payload)

        assert "thinking" not in payload

    def test_no_budget_when_thinking_not_enabled(self):
        model = _make_model()
        payload: dict[str, Any] = {
            "thinking": {"type": "disabled"},
        }
        model._apply_thinking_budget(payload)

        assert "budget_tokens" not in payload["thinking"]

    def test_no_budget_when_already_set(self):
        model = _make_model()
        payload: dict[str, Any] = {
            "thinking": {"type": "enabled", "budget_tokens": 5000},
        }
        model._apply_thinking_budget(payload)

        assert payload["thinking"]["budget_tokens"] == 5000

    def test_no_budget_when_thinking_is_none(self):
        model = _make_model()
        payload: dict[str, Any] = {"thinking": None}
        model._apply_thinking_budget(payload)

    def test_no_budget_when_thinking_is_string(self):
        model = _make_model()
        payload: dict[str, Any] = {"thinking": "invalid"}
        model._apply_thinking_budget(payload)

    def test_default_max_tokens_used(self):
        model = _make_model()
        payload: dict[str, Any] = {
            "thinking": {"type": "enabled"},
        }
        model._apply_thinking_budget(payload)

        assert payload["thinking"]["budget_tokens"] == int(8192 * 0.8)

    def test_budget_ratio_applied_correctly(self):
        model = _make_model(max_tokens=1000)
        payload: dict[str, Any] = {
            "thinking": {"type": "enabled"},
            "max_tokens": 1000,
        }
        model._apply_thinking_budget(payload)

        assert payload["thinking"]["budget_tokens"] == 800


# ===================================================================
# _strip_cache_control
# ===================================================================


class TestStripCacheControl:
    def test_strips_from_system_list(self):
        payload: dict[str, Any] = {
            "system": [
                {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}},
            ],
        }
        from ideer.models.claude_provider import ClaudeChatModel

        ClaudeChatModel._strip_cache_control(payload)
        assert "cache_control" not in payload["system"][0]

    def test_strips_from_message_content_blocks(self):
        payload: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}},
                    ],
                },
            ],
        }
        from ideer.models.claude_provider import ClaudeChatModel

        ClaudeChatModel._strip_cache_control(payload)
        assert "cache_control" not in payload["messages"][0]["content"][0]

    def test_strips_from_tools(self):
        payload: dict[str, Any] = {
            "tools": [
                {"name": "t1", "cache_control": {"type": "ephemeral"}},
            ],
        }
        from ideer.models.claude_provider import ClaudeChatModel

        ClaudeChatModel._strip_cache_control(payload)
        assert "cache_control" not in payload["tools"][0]

    def test_noop_on_empty_payload(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_list_system(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"system": "string system"}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_list_messages(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"messages": "string messages"}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_dict_items_in_system(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"system": ["string-item", 42]}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_dict_items_in_messages(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"messages": ["string-item"]}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_dict_content_blocks(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": ["string-block", 42]},
            ],
        }
        ClaudeChatModel._strip_cache_control(payload)

    def test_strips_from_non_list_content(self):
        """When content is not a list, dict items still get cache_control stripped at the item level."""
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {
            "messages": [
                {"role": "user", "content": "plain string"},
            ],
        }
        # content is a string, not a list, so no nested blocks to strip
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_list_tools(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"tools": "not a list"}
        ClaudeChatModel._strip_cache_control(payload)

    def test_skips_non_dict_tools(self):
        from ideer.models.claude_provider import ClaudeChatModel

        payload: dict[str, Any] = {"tools": ["string-tool", 42]}
        ClaudeChatModel._strip_cache_control(payload)


# ===================================================================
# _get_request_payload
# ===================================================================


class TestGetRequestPayload:
    def test_calls_all_three_appliers_when_enabled(self):
        model = _make_model(enable_prompt_caching=True, auto_thinking_budget=True)
        model._is_oauth = True

        with (
            patch.object(model, "_apply_oauth_billing") as mock_billing,
            patch.object(model, "_apply_prompt_caching") as mock_caching,
            patch.object(model, "_apply_thinking_budget") as mock_thinking,
            patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value={"test": True}),
        ):
            model._get_request_payload("hello")

        mock_billing.assert_called_once()
        mock_caching.assert_called_once()
        mock_thinking.assert_called_once()

    def test_skips_billing_when_not_oauth(self):
        model = _make_model(enable_prompt_caching=True, auto_thinking_budget=True)
        model._is_oauth = False

        with (
            patch.object(model, "_apply_oauth_billing") as mock_billing,
            patch.object(model, "_apply_prompt_caching"),
            patch.object(model, "_apply_thinking_budget"),
            patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value={"test": True}),
        ):
            model._get_request_payload("hello")

        mock_billing.assert_not_called()

    def test_skips_caching_when_disabled(self):
        model = _make_model(enable_prompt_caching=False, auto_thinking_budget=False)
        model._is_oauth = False

        with (
            patch.object(model, "_apply_oauth_billing") as mock_billing,
            patch.object(model, "_apply_prompt_caching") as mock_caching,
            patch.object(model, "_apply_thinking_budget") as mock_thinking,
            patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value={"test": True}),
        ):
            model._get_request_payload("hello")

        mock_billing.assert_not_called()
        mock_caching.assert_not_called()
        mock_thinking.assert_not_called()

    def test_skips_thinking_when_disabled(self):
        model = _make_model(enable_prompt_caching=False, auto_thinking_budget=False)
        model._is_oauth = False

        with (
            patch.object(model, "_apply_thinking_budget") as mock_thinking,
            patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value={"test": True}),
        ):
            model._get_request_payload("hello")

        mock_thinking.assert_not_called()


# ===================================================================
# _create / _acreate (sync + async)
# ===================================================================


class TestCreateMethods:
    def test_create_strips_cache_control_when_oauth(self):
        model = _make_model()
        model._is_oauth = True

        with (
            patch.object(model, "_strip_cache_control") as mock_strip,
            patch("ideer.models.claude_provider.ChatAnthropic._create", return_value="result"),
        ):
            result = model._create({"test": True})

        mock_strip.assert_called_once()
        assert result == "result"

    def test_create_does_not_strip_when_not_oauth(self):
        model = _make_model()
        model._is_oauth = False

        with (
            patch.object(model, "_strip_cache_control") as mock_strip,
            patch("ideer.models.claude_provider.ChatAnthropic._create", return_value="result"),
        ):
            model._create({"test": True})

        mock_strip.assert_not_called()

    @pytest.mark.asyncio
    async def test_acreate_strips_cache_control_when_oauth(self):
        model = _make_model()
        model._is_oauth = True

        with (
            patch.object(model, "_strip_cache_control") as mock_strip,
            patch("ideer.models.claude_provider.ChatAnthropic._acreate", new_callable=AsyncMock, return_value="result"),
        ):
            result = await model._acreate({"test": True})

        mock_strip.assert_called_once()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_acreate_does_not_strip_when_not_oauth(self):
        model = _make_model()
        model._is_oauth = False

        with (
            patch.object(model, "_strip_cache_control") as mock_strip,
            patch("ideer.models.claude_provider.ChatAnthropic._acreate", new_callable=AsyncMock, return_value="result"),
        ):
            await model._acreate({"test": True})

        mock_strip.assert_not_called()


# ===================================================================
# _calc_backoff_ms
# ===================================================================


class TestCalcBackoffMs:
    def test_attempt_1(self):
        from ideer.models.claude_provider import ClaudeChatModel

        error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        # 2000 * (1 << 0) + 20% = 2000 + 400 = 2400
        assert ms == 2400

    def test_attempt_2(self):
        from ideer.models.claude_provider import ClaudeChatModel

        error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(2, error)
        # 2000 * (1 << 1) + 20% = 4000 + 800 = 4800
        assert ms == 4800

    def test_attempt_3(self):
        from ideer.models.claude_provider import ClaudeChatModel

        error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(3, error)
        # 2000 * (1 << 2) + 20% = 8000 + 1600 = 9600
        assert ms == 9600

    def test_retry_after_header_overrides(self):
        from ideer.models.claude_provider import ClaudeChatModel

        resp = MagicMock()
        resp.headers = {"Retry-After": "10"}
        error = anthropic.RateLimitError(
            message="rate limited",
            response=resp,
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        assert ms == 10000

    def test_retry_after_invalid_value_ignored(self):
        from ideer.models.claude_provider import ClaudeChatModel

        resp = MagicMock()
        resp.headers = {"Retry-After": "not-a-number"}
        error = anthropic.RateLimitError(
            message="rate limited",
            response=resp,
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        # Falls back to exponential: 2400
        assert ms == 2400

    def test_no_retry_after_header(self):
        from ideer.models.claude_provider import ClaudeChatModel

        error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        assert ms == 2400

    def test_error_without_response_attr(self):
        from ideer.models.claude_provider import ClaudeChatModel

        error = Exception("generic error")
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        assert ms == 2400

    def test_error_with_none_response_attr(self):
        """Error whose .response attribute is None (not an anthropic SDK error)."""
        from ideer.models.claude_provider import ClaudeChatModel

        error = Exception("generic")
        error.response = None  # type: ignore[attr-defined]
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        assert ms == 2400

    def test_retry_after_none_value_ignored(self):
        from ideer.models.claude_provider import ClaudeChatModel

        resp = MagicMock()
        resp.headers = {"Retry-After": None}
        error = anthropic.RateLimitError(
            message="rate limited",
            response=resp,
            body=None,
        )
        ms = ClaudeChatModel._calc_backoff_ms(1, error)
        assert ms == 2400


# ===================================================================
# _generate (sync) with retry logic
# ===================================================================


class TestGenerateSync:
    def test_success_on_first_attempt(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        with patch("ideer.models.claude_provider.ChatAnthropic._generate", return_value="ok") as mock_gen:
            result = model._generate(messages)

        assert result == "ok"
        assert mock_gen.call_count == 1

    def test_retries_on_rate_limit_then_succeeds(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch("ideer.models.claude_provider.ChatAnthropic._generate", side_effect=[rate_error, "ok"]) as mock_gen,
            patch("time.sleep"),
        ):
            result = model._generate(messages)

        assert result == "ok"
        assert mock_gen.call_count == 2

    def test_retries_on_server_error_then_succeeds(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        server_error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch("ideer.models.claude_provider.ChatAnthropic._generate", side_effect=[server_error, "ok"]) as mock_gen,
            patch("time.sleep"),
        ):
            result = model._generate(messages)

        assert result == "ok"
        assert mock_gen.call_count == 2

    def test_raises_after_max_retries_rate_limit(self):
        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch("ideer.models.claude_provider.ChatAnthropic._generate", side_effect=rate_error),
            patch("time.sleep"),
            pytest.raises(anthropic.RateLimitError),
        ):
            model._generate(messages)

    def test_raises_after_max_retries_server_error(self):
        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        server_error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch("ideer.models.claude_provider.ChatAnthropic._generate", side_effect=server_error),
            patch("time.sleep"),
            pytest.raises(anthropic.InternalServerError),
        ):
            model._generate(messages)

    def test_patches_oauth_client_before_generate(self):
        model = _make_model(retry_max_attempts=1)
        model._is_oauth = True
        messages = [MagicMock()]

        with (
            patch.object(model, "_patch_client_oauth") as mock_patch,
            patch("ideer.models.claude_provider.ChatAnthropic._generate", return_value="ok"),
        ):
            model._generate(messages)

        mock_patch.assert_called_once_with(model._client)

    def test_does_not_patch_when_not_oauth(self):
        model = _make_model(retry_max_attempts=1)
        model._is_oauth = False
        messages = [MagicMock()]

        with (
            patch.object(model, "_patch_client_oauth") as mock_patch,
            patch("ideer.models.claude_provider.ChatAnthropic._generate", return_value="ok"),
        ):
            model._generate(messages)

        mock_patch.assert_not_called()

    def test_non_retryable_error_raises_immediately(self):
        """Errors that are not RateLimitError or InternalServerError are not retried."""
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._generate",
                side_effect=ValueError("bad input"),
            ),
            pytest.raises(ValueError, match="bad input"),
        ):
            model._generate(messages)

    def test_retry_loop_logs_warning(self, caplog):
        import logging

        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch("ideer.models.claude_provider.ChatAnthropic._generate", side_effect=[rate_error, "ok"]),
            patch("time.sleep"),
            caplog.at_level(logging.WARNING),
        ):
            model._generate(messages)

        assert "Rate limited, retrying" in caplog.text


# ===================================================================
# _agenerate (async) with retry logic
# ===================================================================


class TestGenerateAsync:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        with patch("ideer.models.claude_provider.ChatAnthropic._agenerate", new_callable=AsyncMock, return_value="ok") as mock_gen:
            result = await model._agenerate(messages)

        assert result == "ok"
        assert mock_gen.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_then_succeeds(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=[rate_error, "ok"],
            ) as mock_gen,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await model._agenerate(messages)

        assert result == "ok"
        assert mock_gen.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_server_error_then_succeeds(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        server_error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=[server_error, "ok"],
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await model._agenerate(messages)

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_rate_limit(self):
        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=rate_error,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(anthropic.RateLimitError),
        ):
            await model._agenerate(messages)

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_server_error(self):
        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        server_error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=server_error,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(anthropic.InternalServerError),
        ):
            await model._agenerate(messages)

    @pytest.mark.asyncio
    async def test_patches_oauth_async_client(self):
        model = _make_model(retry_max_attempts=1)
        model._is_oauth = True
        messages = [MagicMock()]

        with (
            patch.object(model, "_patch_client_oauth") as mock_patch,
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                return_value="ok",
            ),
        ):
            await model._agenerate(messages)

        mock_patch.assert_called_once_with(model._async_client)

    @pytest.mark.asyncio
    async def test_does_not_patch_when_not_oauth(self):
        model = _make_model(retry_max_attempts=1)
        model._is_oauth = False
        messages = [MagicMock()]

        with (
            patch.object(model, "_patch_client_oauth") as mock_patch,
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                return_value="ok",
            ),
        ):
            await model._agenerate(messages)

        mock_patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self):
        model = _make_model(retry_max_attempts=3)
        messages = [MagicMock()]

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=ValueError("bad input"),
            ),
            pytest.raises(ValueError, match="bad input"),
        ):
            await model._agenerate(messages)

    @pytest.mark.asyncio
    async def test_retry_logs_warning(self, caplog):
        import logging

        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        rate_error = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=[rate_error, "ok"],
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            caplog.at_level(logging.WARNING),
        ):
            await model._agenerate(messages)

        assert "Rate limited, retrying" in caplog.text

    @pytest.mark.asyncio
    async def test_server_error_logs_warning(self, caplog):
        import logging

        model = _make_model(retry_max_attempts=2)
        messages = [MagicMock()]

        server_error = anthropic.InternalServerError(
            message="server error",
            response=MagicMock(headers={}),
            body=None,
        )

        with (
            patch(
                "ideer.models.claude_provider.ChatAnthropic._agenerate",
                new_callable=AsyncMock,
                side_effect=[server_error, "ok"],
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            caplog.at_level(logging.WARNING),
        ):
            await model._agenerate(messages)

        assert "Server error, retrying" in caplog.text


# ===================================================================
# Integration: _apply_oauth_billing + _apply_prompt_caching together
# ===================================================================


class TestIntegratedPayload:
    def test_full_payload_pipeline_oauth(self):
        """OAuth + caching disabled + thinking = billing + thinking budget."""
        from ideer.models.claude_provider import OAUTH_BILLING_HEADER

        model = _make_model(enable_prompt_caching=False, auto_thinking_budget=True, max_tokens=10000)
        model._is_oauth = True

        payload: dict[str, Any] = {
            "system": "You are helpful.",
            "messages": [{"role": "user", "content": "hello"}],
            "thinking": {"type": "enabled"},
            "max_tokens": 10000,
        }

        with patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value=payload):
            result = model._get_request_payload("hello")

        # Billing should be injected
        assert isinstance(result["system"], list)
        assert any(b.get("text") == OAUTH_BILLING_HEADER for b in result["system"])

        # Thinking budget should be set
        assert result["thinking"]["budget_tokens"] == 8000

    def test_full_payload_pipeline_non_oauth_caching(self):
        """Non-OAuth + caching enabled + thinking disabled."""
        model = _make_model(enable_prompt_caching=True, auto_thinking_budget=False)
        model._is_oauth = False

        payload: dict[str, Any] = {
            "system": [{"type": "text", "text": "You are helpful."}],
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        }

        with patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value=payload):
            result = model._get_request_payload("hello")

        # Cache control should be applied to system blocks
        assert result["system"][0].get("cache_control") == {"type": "ephemeral"}

    def test_all_disabled(self):
        """Everything disabled: payload passes through unchanged."""
        model = _make_model(enable_prompt_caching=False, auto_thinking_budget=False)
        model._is_oauth = False

        payload: dict[str, Any] = {"system": "test"}

        with patch("ideer.models.claude_provider.ChatAnthropic._get_request_payload", return_value=payload):
            result = model._get_request_payload("hello")

        assert result == {"system": "test"}


# ===================================================================
# Edge cases for model_post_init with SecretStr
# ===================================================================


class TestSecretStrHandling:
    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential", return_value=None)
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_secretstr_key_extracted(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """SecretStr api_key is properly extracted for credential check."""
        from ideer.models.claude_provider import ClaudeChatModel

        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key=SecretStr(API_KEY))
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        # Should NOT have called load_claude_code_credential because key is valid
        mock_load_cred.assert_not_called()

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential", return_value=None)
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=False)
    def test_empty_string_api_key_triggers_credential_lookup(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """When api_key is empty string, credential lookup is triggered."""
        from ideer.models.claude_provider import ClaudeChatModel

        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="")
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        # model_post_init is called once in the constructor and once manually
        assert mock_load_cred.call_count >= 1

    @patch("ideer.models.claude_provider.ChatAnthropic.model_post_init")
    @patch("ideer.models.credential_loader.load_claude_code_credential")
    @patch("ideer.models.credential_loader.is_oauth_token", return_value=True)
    def test_credential_access_token_set_as_api_key(self, mock_is_oauth, mock_load_cred, mock_super_init):
        """When credential is loaded, its access_token becomes the api_key."""
        from ideer.models.claude_provider import ClaudeChatModel

        cred = SimpleNamespace(access_token=OAUTH_TOKEN, source="claude-cli-env")
        mock_load_cred.return_value = cred
        mock_super_init.side_effect = lambda ctx: None

        model = ClaudeChatModel(model="claude-sonnet-4-6", anthropic_api_key="")
        model._client = MagicMock()
        model._async_client = MagicMock()
        model.model_post_init(None)

        assert isinstance(model.anthropic_api_key, SecretStr)
        assert model.anthropic_api_key.get_secret_value() == OAUTH_TOKEN
