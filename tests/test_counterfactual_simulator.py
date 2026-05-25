import importlib


def test_counterfactual_result_is_deterministic() -> None:
    api_app = importlib.import_module("api.app")
    snapshot = {
        "regime": {"regime": "GOLDILOCKS", "confidence": "HIGH"},
        "cross_asset": {"overall_signal": "ALIGNED_BULLISH", "alerts": [], "divergences": []},
        "detected_indicators": {
            "gdp_growth": 2.4,
            "inflation_cpi": 2.2,
            "credit_hy": 280,
            "yield_curve": 20,
            "vix": 14,
        },
    }
    shocks = {"inflation_cpi": 4.2, "yield_curve": -80, "credit_hy": 620, "vix": 32}

    a = api_app._compute_counterfactual_result(snapshot, shocks)
    b = api_app._compute_counterfactual_result(snapshot, shocks)

    assert a == b
    assert a is not None
    assert a["requested"] is True
    assert "delta_summary" in a
    assert len(a["delta_summary"]["indicator_deltas"]) == len(shocks)
    assert isinstance(a["delta_summary"]["quality_delta"], dict)
    assert a["delta_summary"]["quality_delta"]["retrieval_reused"] is True


def test_counterfactual_payload_included_when_feature_enabled(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_COUNTERFACTUAL_SIMULATOR", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "NEUTRAL / INSUFFICIENT_DATA", "alerts": [], "divergences": []},
        "detected_indicators": {
            "gdp_growth": 1.8,
            "inflation_cpi": 2.8,
            "credit_hy": 350,
            "yield_curve": -10,
            "vix": 19,
        },
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }

    cf = api_app._compute_counterfactual_result(snapshot, {"yield_curve": -70, "credit_hy": 500})
    payload = api_app._make_structured_payload(
        snapshot,
        "Direct answer: Example.\n",
        model_used="unit-test",
        response_mode="brief",
        question="what if",
        persist_decision=False,
        counterfactual_result=cf,
    )

    assert payload.get("counterfactual_result", {}).get("requested") is True
    assert payload.get("_response_contract", {}).get("counterfactual_result", {}).get("requested") is True
