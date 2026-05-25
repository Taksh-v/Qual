import importlib

from intelligence.data_quality import evaluate_evidence_integrity


def test_evidence_integrity_scores_supported_claims() -> None:
    response_text = (
        "Direct answer: Inflation is easing [S1].\n"
        "Market impact:\n"
        "- Equities remain supported [S2].\n"
        "- Credit spreads are stable.\n"
    )
    coverage = {
        "sources": [
            {"source": "Reuters", "date": "2026-03-30"},
            {"source": "Bloomberg", "date": "2026-03-29"},
        ]
    }

    out = evaluate_evidence_integrity(response_text, coverage)
    assert out["support_score"] > 0
    assert out["unsupported_claim_count"] >= 0
    assert out["status"] in {"pass", "warning", "review_required"}


def test_evidence_integrity_handles_missing_sources() -> None:
    response_text = "Direct answer: Macro risk is high.\nWhat to watch:\n- Payrolls print.\n"
    out = evaluate_evidence_integrity(response_text, {"sources": []})
    assert out["source_freshness_score"] == 0.0
    assert out["source_diversity_score"] == 0.0


def test_analyze_payload_includes_integrity_when_flag_enabled(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_EVIDENCE_INTEGRITY", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON"},
        "evidence_coverage": {
            "context_chunks": 2,
            "has_overrides": False,
            "sources": [{"source": "Reuters", "date": "2026-03-31"}],
        },
    }
    response_text = "Direct answer: Growth is stable [S1].\nMarket impact:\n- Equities supported [S1].\n"
    payload = api_app._make_structured_payload(snapshot, response_text, "unit-test", "brief")
    assert "evidence_integrity" in payload
    assert payload["evidence_integrity"]["status"] in {"pass", "warning", "review_required"}


def test_integrity_warning_propagates_to_quality_and_contract(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_EVIDENCE_INTEGRITY", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON"},
        "evidence_coverage": {
            "context_chunks": 2,
            "has_overrides": False,
            "sources": [{"source": "Reuters", "date": "2026-03-31"}],
        },
    }
    response_text = "Direct answer: Growth is stable.\nMarket impact:\n- Equities supported.\n"
    payload = api_app._make_structured_payload(snapshot, response_text, "unit-test", "brief")

    quality_warnings = payload.get("quality", {}).get("warnings", [])
    contract_warnings = payload.get("_response_contract", {}).get("validation_warnings", [])
    assert isinstance(quality_warnings, list)
    assert any("Evidence integrity" in w for w in quality_warnings)
    assert any("Evidence integrity" in w for w in contract_warnings)
