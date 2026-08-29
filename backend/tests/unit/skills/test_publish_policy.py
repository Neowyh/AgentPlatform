import pytest

from ideer.skills.publish_policy import SkillPublishDenied, SkillPublishPolicy


def test_skill_publish_policy_allows_legacy_and_non_blocking_results() -> None:
    policy = SkillPublishPolicy()

    policy.assert_publishable({})
    policy.assert_publishable({"decision": "allow"})
    policy.assert_publishable({"decision": "warn", "reason": "review suggested"})
    policy.assert_publishable({"status": "trusted_bundled_manifest"})


@pytest.mark.parametrize("value", ["block", "blocked", "reject", "denied"])
def test_skill_publish_policy_rejects_explicit_denials(value: str) -> None:
    with pytest.raises(SkillPublishDenied, match="unsafe content"):
        SkillPublishPolicy().assert_publishable({"decision": value, "reason": "unsafe content"})
