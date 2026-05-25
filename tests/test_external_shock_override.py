import importlib

from intelligence.external_shock import compute_external_shock_state


def test_external_shock_state_crisis_classification() -> None:
    indicators = {
        "vix": 38,
        "credit_hy": 760,
        "yield_curve": -110,
        "dxy": 109,
        "oil_wti": 102,
    }
    cross_asset = {"overall_signal": "ALIGNED_BEARISH", "alerts": ["a1", "a2", "a3"], "divergences": ["d1"]}
    regime = {"regime": "LATE_CYCLE", "confidence": "LOW"}

    out = compute_external_shock_state(indicators, cross_asset, regime, event_stress_score=0.8)
    assert out["shock_mode"] in {"elevated", "crisis"}
    assert out["external_shock_score"] >= 0.45
    assert isinstance(out["trigger_conditions"], list)
    assert isinstance(out.get("score_inputs"), dict)
    assert "mode_thresholds" in out


def test_payload_adapts_confidence_when_shock_enabled(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_EXTERNAL_SHOCK_OVERRIDE", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON", "alerts": [], "divergences": []},
        "evidence_coverage": {"context_chunks": 2, "has_overrides": False, "sources": []},
        "external_shock": {
            "external_shock_score": 0.82,
            "shock_mode": "crisis",
            "trigger_conditions": ["vix>=35"],
            "invalidation_conditions": ["market_stress_normalized"],
            "scenario_reweighting": "defensive_risk_first",
            "confidence_degradation": {"score_penalty": 18, "band_penalty": 2, "scenario_range_widening": "high"},
            "manual_review_required": True,
        },
    }

    payload = api_app._make_structured_payload(
        snapshot,
        "Direct answer: Keep risk balanced.\nConfidence: HIGH - stable backdrop.\n",
        model_used="unit-test",
        response_mode="brief",
        question="test",
        persist_decision=False,
    )

    assert payload.get("external_shock", {}).get("shock_mode") == "crisis"
    assert payload.get("quality", {}).get("score") <= 80
    assert "Adaptive confidence mode" in payload.get("response_text", "")
    assert payload.get("quality", {}).get("scenario_reweighting") == "defensive_risk_first"
    assert payload.get("quality", {}).get("manual_review_required") is True


def test_track_external_shock_transition_marks_mode_changes() -> None:
    api_app = importlib.import_module("api.app")

    api_app._SHOCK_MODE_STATE["snapshot"] = "normal"
    entered = api_app._track_external_shock_transition(
        "snapshot",
        {"shock_mode": "elevated", "external_shock_score": 0.6, "score_inputs": {}},
    )
    assert entered is not None
    assert entered.get("mode_transition") == "entered_shock_mode"
    assert entered.get("previous_shock_mode") == "normal"

    exited = api_app._track_external_shock_transition(
        "snapshot",
        {"shock_mode": "normal", "external_shock_score": 0.2, "score_inputs": {}},
    )
    assert exited is not None
    assert exited.get("mode_transition") == "exited_shock_mode"
