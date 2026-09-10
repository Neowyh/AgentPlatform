from core.policy import LocalPolicy, PolicyDecision


def test_local_deny_overrides_server_allow() -> None:
    policy = LocalPolicy(denied_capabilities=frozenset({"echo"}))

    assert policy.authorize("echo", {"server_allowed": True}) == PolicyDecision.DENY


def test_file_reads_are_level_zero_even_when_other_capabilities_need_consent() -> None:
    policy = LocalPolicy(consent_required_capabilities=frozenset({"local.files.read"}))

    assert policy.authorize("local.files.read", {"path": "/projects/a.txt"}) == PolicyDecision.ALLOW
