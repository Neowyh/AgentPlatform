from core.policy import LocalPolicy, PolicyDecision, RiskLevel
from core.settings import CapabilityRule, RuntimeSettings, load_settings


def test_settings_round_trip_keeps_identity_roots_and_policy(tmp_path) -> None:
    settings = RuntimeSettings(
        server_url="https://intranet.example",
        device_name="工作站",
        user_name="alice",
        roots=[{"logical_root": "/projects", "physical_root": str(tmp_path)}],
    )
    path = tmp_path / "runtime.json"

    settings.save(path)
    loaded = load_settings(path)

    assert loaded.device_name == "工作站"
    assert [root.logical_root for root in loaded.file_roots()] == ["/projects"]
    assert loaded.server_url == "https://intranet.example"


def test_a_deny_rule_vetoes_even_a_level_one_capability(tmp_path) -> None:
    settings = RuntimeSettings()
    settings.set_rule("local.python", CapabilityRule.DENY)
    policy = settings.policy()

    assert policy.risk_level("local.python", {}) is RiskLevel.LEVEL_1
    assert policy.authorize("local.python", {}) is PolicyDecision.DENY


def test_ask_first_and_always_allow_rules_drive_local_policy(tmp_path) -> None:
    settings = RuntimeSettings()
    settings.set_rule("local.mcp.git.commit", CapabilityRule.ASK_FIRST)
    settings.set_rule("local.files.write", CapabilityRule.ALWAYS_ALLOW)

    policy = settings.policy()

    assert policy.authorize("local.mcp.git.commit", {}) is PolicyDecision.CONSENT_REQUIRED
    assert policy.authorize("local.files.write", {}) is PolicyDecision.ALLOW


def test_an_always_allow_rule_can_never_silence_a_level_two_capability() -> None:
    settings = RuntimeSettings()
    settings.set_rule("system.config.set", CapabilityRule.ALWAYS_ALLOW)

    policy = settings.policy()

    assert policy.risk_level("system.config.set", {}) is RiskLevel.LEVEL_2
    assert policy.authorize("system.config.set", {}) is PolicyDecision.DENY


def test_policy_hash_changes_when_a_rule_changes() -> None:
    settings = RuntimeSettings()
    before = settings.policy_hash()

    settings.set_rule("local.files.write", CapabilityRule.ALWAYS_ALLOW)

    assert settings.policy_hash() != before
    assert len(settings.policy_hash()) == 64


def test_unlisted_dangerous_capability_defaults_to_level_two() -> None:
    policy = LocalPolicy()

    assert policy.risk_level("local.delete.registry", {}) is RiskLevel.LEVEL_2
    assert policy.authorize("local.delete.registry", {}, consent=True) is PolicyDecision.DENY


def test_server_url_becomes_the_runtime_websocket_address() -> None:
    https = RuntimeSettings(server_url="https://intranet.example")
    plain = RuntimeSettings(server_url="http://intranet.example:8000")
    already = RuntimeSettings(server_url="wss://intranet.example/other")

    assert https.websocket_url() == "wss://intranet.example/api/devices/ws"
    assert plain.websocket_url() == "ws://intranet.example:8000/api/devices/ws"
    assert already.websocket_url() == "wss://intranet.example/other"
