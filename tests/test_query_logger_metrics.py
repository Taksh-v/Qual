from intelligence.query_logger import compute_metrics


def test_compute_metrics_includes_retrieval_telemetry_stats():
    entries = [
        {
            "latency_ms": 120,
            "quality_score": 75,
            "quality_band": "MEDIUM",
            "model_used": "m1",
            "cache_hit": False,
            "retrieval_hybrid_enabled": True,
            "retrieval_rrf_applied": True,
            "retrieval_fallback_reason": "none",
            "retrieval_top_chunks": [{"chunk_id": "c1", "score": 9.1}],
            "decision_id": "d1",
        },
        {
            "latency_ms": 150,
            "quality_score": 82,
            "quality_band": "HIGH",
            "model_used": "m1",
            "cache_hit": False,
            "retrieval_hybrid_enabled": False,
            "retrieval_rrf_applied": False,
            "retrieval_fallback_reason": "dense_error_lexical",
        },
        {
            "latency_ms": 100,
            "quality_score": 68,
            "quality_band": "MEDIUM",
            "model_used": "m2",
            "cache_hit": True,
        },
    ]

    out = compute_metrics(entries)

    assert out["retrieval_hybrid_rate_pct"] == 50.0
    assert out["retrieval_rrf_rate_pct"] == 50.0
    assert out["retrieval_fallback_dist"]["none"] == 1
    assert out["retrieval_fallback_dist"]["dense_error_lexical"] == 1
