"""Unit tests for guardrail provider and builtin modules."""

from __future__ import annotations

import asyncio

from ideer.guardrails.builtin import AllowlistProvider
from ideer.guardrails.provider import GuardrailDecision, GuardrailProvider, GuardrailReason, GuardrailRequest

# ---------------------------------------------------------------------------
# GuardrailRequest
# ---------------------------------------------------------------------------


class TestGuardrailRequest:
    def test_minimal_construction(self):
        req = GuardrailRequest(tool_name="bash", tool_input={})
        assert req.tool_name == "bash"
        assert req.tool_input == {}
        assert req.agent_id is None
        assert req.thread_id is None
        assert req.is_subagent is False
        assert req.timestamp == ""

    def test_full_construction(self):
        req = GuardrailRequest(
            tool_name="web_search",
            tool_input={"query": "test"},
            agent_id="agent-1",
            thread_id="thread-42",
            is_subagent=True,
            timestamp="2025-01-01T00:00:00Z",
        )
        assert req.tool_name == "web_search"
        assert req.tool_input == {"query": "test"}
        assert req.agent_id == "agent-1"
        assert req.thread_id == "thread-42"
        assert req.is_subagent is True
        assert req.timestamp == "2025-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# GuardrailReason
# ---------------------------------------------------------------------------


class TestGuardrailReason:
    def test_construction(self):
        reason = GuardrailReason(code="oap.denied", message="blocked")
        assert reason.code == "oap.denied"
        assert reason.message == "blocked"

    def test_default_message(self):
        reason = GuardrailReason(code="oap.allowed")
        assert reason.message == ""


# ---------------------------------------------------------------------------
# GuardrailDecision
# ---------------------------------------------------------------------------


class TestGuardrailDecision:
    def test_allow_decision(self):
        d = GuardrailDecision(allow=True)
        assert d.allow is True
        assert d.reasons == []
        assert d.policy_id is None
        assert d.metadata == {}

    def test_deny_decision(self):
        d = GuardrailDecision(allow=False)
        assert d.allow is False

    def test_decision_with_reasons(self):
        reasons = [GuardrailReason(code="oap.tool_not_allowed", message="blocked")]
        d = GuardrailDecision(allow=False, reasons=reasons)
        assert len(d.reasons) == 1
        assert d.reasons[0].code == "oap.tool_not_allowed"
        assert d.reasons[0].message == "blocked"

    def test_decision_with_policy_id(self):
        d = GuardrailDecision(allow=True, policy_id="policy.v2")
        assert d.policy_id == "policy.v2"

    def test_decision_with_metadata(self):
        meta = {"score": 0.95, "tags": ["security"]}
        d = GuardrailDecision(allow=True, metadata=meta)
        assert d.metadata == meta

    def test_multiple_reasons(self):
        reasons = [
            GuardrailReason(code="oap.r1", message="first"),
            GuardrailReason(code="oap.r2", message="second"),
        ]
        d = GuardrailDecision(allow=False, reasons=reasons)
        assert len(d.reasons) == 2
        assert d.reasons[1].code == "oap.r2"

    def test_decision_is_dataclass(self):
        """GuardrailDecision supports standard dataclass equality."""
        d1 = GuardrailDecision(allow=True, reasons=[GuardrailReason(code="x")])
        d2 = GuardrailDecision(allow=True, reasons=[GuardrailReason(code="x")])
        assert d1 == d2


# ---------------------------------------------------------------------------
# AllowlistProvider
# ---------------------------------------------------------------------------


class TestAllowlistProvider:
    def test_name(self):
        assert AllowlistProvider().name == "allowlist"

    def test_no_restrictions_allows_all(self):
        provider = AllowlistProvider()
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is True
        assert decision.reasons[0].code == "oap.allowed"

    def test_tool_in_allowlist_allowed(self):
        provider = AllowlistProvider(allowed_tools=["bash", "web_search"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        assert provider.evaluate(req).allow is True

    def test_tool_not_in_allowlist_denied(self):
        provider = AllowlistProvider(allowed_tools=["web_search"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is False
        assert decision.reasons[0].code == "oap.tool_not_allowed"
        assert "not in allowlist" in decision.reasons[0].message

    def test_empty_list_treated_as_no_allowlist(self):
        """Empty allowed_tools list is falsy, so treated as None (no restrictions)."""
        provider = AllowlistProvider(allowed_tools=[])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is True

    def test_tool_in_denylist_denied(self):
        provider = AllowlistProvider(denied_tools=["bash"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is False
        assert decision.reasons[0].code == "oap.tool_not_allowed"
        assert "denied" in decision.reasons[0].message

    def test_tool_not_in_denylist_allowed(self):
        provider = AllowlistProvider(denied_tools=["bash"])
        req = GuardrailRequest(tool_name="web_search", tool_input={})
        assert provider.evaluate(req).allow is True

    def test_empty_denylist_allows_all(self):
        provider = AllowlistProvider(denied_tools=[])
        req = GuardrailRequest(tool_name="anything", tool_input={})
        assert provider.evaluate(req).allow is True

    def test_denylist_overrides_allowlist(self):
        provider = AllowlistProvider(allowed_tools=["bash", "web_search"], denied_tools=["bash"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is False
        assert "denied" in decision.reasons[0].message

    def test_allowlist_plus_denylist_tool_allowed(self):
        """Tool in allowlist but not in denylist should be allowed."""
        provider = AllowlistProvider(allowed_tools=["bash", "web_search"], denied_tools=["bash"])
        req = GuardrailRequest(tool_name="web_search", tool_input={})
        decision = provider.evaluate(req)
        assert decision.allow is True
        assert decision.reasons[0].code == "oap.allowed"

    def test_case_sensitivity(self):
        provider = AllowlistProvider(allowed_tools=["Bash"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        assert provider.evaluate(req).allow is False

        req_upper = GuardrailRequest(tool_name="Bash", tool_input={})
        assert provider.evaluate(req_upper).allow is True

    def test_case_sensitivity_denied(self):
        provider = AllowlistProvider(denied_tools=["Bash"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        assert provider.evaluate(req).allow is True

        req_upper = GuardrailRequest(tool_name="Bash", tool_input={})
        assert provider.evaluate(req_upper).allow is False

    def test_empty_string_tool_name(self):
        provider = AllowlistProvider(allowed_tools=["bash"])
        req = GuardrailRequest(tool_name="", tool_input={})
        assert provider.evaluate(req).allow is False

    def test_empty_string_tool_name_denied(self):
        provider = AllowlistProvider(denied_tools=["bash"])
        req = GuardrailRequest(tool_name="", tool_input={})
        assert provider.evaluate(req).allow is True

    def test_async_delegates_to_sync(self):
        provider = AllowlistProvider(allowed_tools=["bash"])
        req = GuardrailRequest(tool_name="web_search", tool_input={})
        decision = asyncio.run(provider.aevaluate(req))
        assert decision.allow is False

        req_allowed = GuardrailRequest(tool_name="bash", tool_input={})
        decision_allowed = asyncio.run(provider.aevaluate(req_allowed))
        assert decision_allowed.allow is True

    def test_async_denylist(self):
        """aevaluate works correctly with denylist."""
        provider = AllowlistProvider(denied_tools=["bash"])
        req = GuardrailRequest(tool_name="bash", tool_input={})
        decision = asyncio.run(provider.aevaluate(req))
        assert decision.allow is False
        assert "denied" in decision.reasons[0].message

        req_allowed = GuardrailRequest(tool_name="web_search", tool_input={})
        decision_allowed = asyncio.run(provider.aevaluate(req_allowed))
        assert decision_allowed.allow is True

    def test_protocol_satisfaction(self):
        """AllowlistProvider satisfies GuardrailProvider protocol at runtime."""
        provider = AllowlistProvider()
        assert isinstance(provider, GuardrailProvider)

    def test_request_attributes_forwarded(self):
        """Provider sees all fields from the request."""
        captured = {}

        class CapturingProvider:
            name = "capture"

            def evaluate(self, request):
                captured["tool_name"] = request.tool_name
                captured["tool_input"] = request.tool_input
                captured["agent_id"] = request.agent_id
                captured["thread_id"] = request.thread_id
                captured["is_subagent"] = request.is_subagent
                captured["timestamp"] = request.timestamp
                return GuardrailDecision(allow=True)

            async def aevaluate(self, request):
                return self.evaluate(request)

        provider = CapturingProvider()
        req = GuardrailRequest(
            tool_name="bash",
            tool_input={"cmd": "ls"},
            agent_id="agent-99",
            thread_id="t-1",
            is_subagent=True,
            timestamp="2025-01-01T00:00:00Z",
        )
        provider.evaluate(req)
        assert captured["tool_name"] == "bash"
        assert captured["tool_input"] == {"cmd": "ls"}
        assert captured["agent_id"] == "agent-99"
        assert captured["thread_id"] == "t-1"
        assert captured["is_subagent"] is True
        assert captured["timestamp"] == "2025-01-01T00:00:00Z"
