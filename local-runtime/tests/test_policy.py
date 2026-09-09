from core.policy import LocalPolicy, PolicyDecision


def test_local_deny_overrides_server_allow() -> None:
    policy = LocalPolicy(denied_capabilities=frozenset({"echo"}))

    assert policy.authorize("echo", {"server_allowed": True}) == PolicyDecision.DENY
