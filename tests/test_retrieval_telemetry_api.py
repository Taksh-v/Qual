from api import app as api_app


def test_build_snapshot_includes_retrieval_telemetry(monkeypatch):
    monkeypatch.setenv("FEATURE_REGIME_EARLY_WARNING", "0")
    monkeypatch.setenv("FEATURE_EXTERNAL_SHOCK_OVERRIDE", "0")

    req = api_app.IntelligenceRequest(question="How is inflation evolving?")

    telemetry = {
        "cache_hit": False,
        "hybrid_enabled": True,
        "rrf_applied": True,
        "fallback_reason": "none",
        "final_count": 4,
    }

    monkeypatch.setattr(api_app, "classify_question", lambda q: "macro")
    monkeypatch.setattr(
        api_app,
        "_collect_indicator_inputs",
        lambda _req: ({"cpi_yoy": 3.1}, [{"metadata": {"title": "T1", "source": "s", "date": "d"}, "text": "x"}], {}, telemetry),
    )
    monkeypatch.setattr(api_app, "get_regime_inputs_from_indicators", lambda x: {})
    monkeypatch.setattr(api_app, "detect_regime", lambda **kwargs: {"regime": "GOLDILOCKS", "confidence": "MEDIUM"})
    monkeypatch.setattr(api_app, "analyze_cross_asset", lambda x: {"overall_signal": "MIXED"})

    snapshot = api_app._build_snapshot(req)

    rc = snapshot.get("evidence_coverage", {}).get("retrieval_telemetry", {})
    assert rc.get("hybrid_enabled") is True
    assert rc.get("rrf_applied") is True
    assert rc.get("fallback_reason") == "none"


def test_structured_payload_quality_includes_retrieval_telemetry():
    snapshot = {
        "evidence_coverage": {
            "context_chunks": 2,
            "sources": [],
            "retrieval_telemetry": {
                "hybrid_enabled": True,
                "rrf_applied": False,
                "fallback_reason": "none",
            },
        }
    }

    payload = api_app._make_structured_payload(
        snapshot=snapshot,
        response_text="Direct answer: stable [S1]",
        model_used="unit-test",
        response_mode="brief",
        question="test?",
        persist_decision=False,
    )

    quality = payload.get("quality", {})
    assert "retrieval_telemetry" in quality
    assert quality["retrieval_telemetry"]["hybrid_enabled"] is True
    assert quality["retrieval_telemetry"]["fallback_reason"] == "none"
