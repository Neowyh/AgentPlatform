from core.consent import ConsentStore, request_hash
from core.policy import LocalPolicy, PolicyDecision


def test_reads_are_level_zero_and_writes_require_consent() -> None:
    policy = LocalPolicy()
    assert policy.authorize("local.files.read", {}) is PolicyDecision.ALLOW
    assert policy.authorize("local.files.write", {}) is PolicyDecision.CONSENT_REQUIRED


def test_consent_is_bound_to_payload_hash_and_can_be_always_allowed() -> None:
    store = ConsentStore()
    payload = {"path": "/projects/a.txt", "content": "one"}
    digest = request_hash(payload)
    store.approve("local.files.write", digest)
    assert store.consume("local.files.write", digest) is True
    assert store.consume("local.files.write", request_hash({**payload, "content": "two"})) is False
    store.set_always_allow("local.files.write")
    assert store.consume("local.files.write", "different") is True
