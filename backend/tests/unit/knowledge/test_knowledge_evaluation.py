from app.agentplatform.knowledge.evaluation import calculate_retrieval_metrics


def test_metrics_deduplicate_chunks_before_ranking_and_count_multiple_expected_documents() -> None:
    metrics = calculate_retrieval_metrics(["doc-a", "doc-a", "doc-b", "doc-c"], ["doc-a", "doc-c"])

    assert metrics == {"expected_hit": True, "recall_at_k": 1.0, "mrr_at_k": 1.0}


def test_metrics_are_zero_for_a_successful_zero_hit_and_support_fewer_than_k() -> None:
    assert calculate_retrieval_metrics(["doc-z"], ["doc-a"]) == {
        "expected_hit": False,
        "recall_at_k": 0.0,
        "mrr_at_k": 0.0,
    }
    assert calculate_retrieval_metrics([], ["doc-a", "doc-b"]) == {
        "expected_hit": False,
        "recall_at_k": 0.0,
        "mrr_at_k": 0.0,
    }
