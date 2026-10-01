from report_test_lane_summary import summarize


def test_summary_fails_when_a_selected_lane_is_skipped() -> None:
    plan = {
        "channels": ["governance", "backend-standard"],
        "reasons": {"governance": ["always"], "backend-standard": ["backend change"]},
    }
    needs = {
        "test-contracts": {"result": "success"},
        "backend-unit-tests": {"result": "skipped"},
    }

    summary = summarize(plan, needs)

    assert summary["ok"] is False
    assert summary["channels"]["backend-standard"]["status"] == "missing-required-result"


def test_summary_distinguishes_unrequired_and_delegated_checks() -> None:
    plan = {"channels": ["governance"], "reasons": {"governance": ["docs"]}}
    needs = {"test-contracts": {"result": "success"}}

    summary = summarize(plan, needs)

    assert summary["ok"] is True
    assert summary["channels"]["backend-standard"]["status"] == "not-required"
    assert summary["channels"]["real-e2e"]["status"] == "not-required"


def test_summary_requires_external_real_e2e_gate_when_selected() -> None:
    plan = {"channels": ["governance", "real-e2e"], "reasons": {"governance": ["always"], "real-e2e": ["auth"]}}
    needs = {"test-contracts": {"result": "success"}}

    summary = summarize(plan, needs)

    assert summary["ok"] is True
    assert summary["channels"]["real-e2e"]["status"] == "delegated"


def test_summary_marks_cancelled_selected_lane_as_failure() -> None:
    plan = {"channels": ["governance", "frontend-standard"], "reasons": {"governance": ["always"], "frontend-standard": ["frontend"]}}
    needs = {
        "test-contracts": {"result": "success"},
        "frontend-unit-tests": {"result": "cancelled"},
    }

    summary = summarize(plan, needs)

    assert summary["ok"] is False
    assert summary["channels"]["frontend-standard"]["status"] == "cancelled"
