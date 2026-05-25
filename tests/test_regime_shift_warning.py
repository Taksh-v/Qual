import importlib

from intelligence.regime_warning import compute_regime_warning


def test_regime_warning_tier_deterministic() -> None:
    regime = {"regime": "LATE_CYCLE", "confidence": "LOW"}
    cross_asset = {
        "overall_signal": "ALIGNED_BEARISH",
        "alerts": ["a1", "a2", "a3"],
        "divergences": ["d1"],
    }
    indicators = {
        "yield_curve": -80,
        "credit_hy": 650,
        "vix": 32,
        "inflation_cpi": 4.2,
        "gdp_growth": 0.5,
    }

    out = compute_regime_warning(regime, cross_asset, indicators)
    assert out["warning_tier"] in {"watch", "elevated", "imminent"}
    assert out["warning_tier"] in {"elevated", "imminent"}
    assert 0.0 <= out["transition_probability"] <= 0.99
    assert isinstance(out["triggers"], list)
    assert isinstance(out["invalidations"], list)


def test_build_snapshot_includes_regime_warning_when_flag_enabled(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_REGIME_EARLY_WARNING", "1")
    monkeypatch.setattr(api_app, "classify_question", lambda q: {"primary": "macro"})
    monkeypatch.setattr(
        api_app,
        "_collect_indicator_inputs",
        lambda req: (
            {
                "yield_curve": -55,
                "credit_hy": 520,
                "vix": 26,
                "inflation_cpi": 3.8,
                "gdp_growth": 1.1,
            },
            [],
            {},
        ),
    )

    req = api_app.IntelligenceRequest(question="test", geography="US", horizon="MEDIUM_TERM")
    snapshot = api_app._build_snapshot(req)
    assert "regime_warning" in snapshot
    assert snapshot["regime_warning"]["warning_tier"] in {"watch", "elevated", "imminent"}


def test_structured_payload_carries_regime_warning_from_snapshot(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_REGIME_EARLY_WARNING", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON"},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
        "regime_warning": {
            "warning_tier": "watch",
            "transition_probability": 0.2,
            "likely_next_regime": "LATE_CYCLE",
            "triggers": ["x"],
            "invalidations": ["y"],
        },
    }
    payload = api_app._make_structured_payload(snapshot, "Direct answer: ok", "unit-test", "brief")
    assert payload.get("regime_warning", {}).get("warning_tier") == "watch"
    assert payload.get("_response_contract", {}).get("regime_warning", {}).get("warning_tier") == "watch"


def test_warning_hysteresis_holds_short_downgrade() -> None:
    api_app = importlib.import_module("api.app")

    previous = {
        "warning_tier": "imminent",
        "transition_probability": 0.82,
        "likely_next_regime": "RECESSION",
        "triggers": ["vix>=30"],
        "invalidations": ["vix_reverts_below_18"],
    }
    current = {
        "warning_tier": "elevated",
        "transition_probability": 0.74,
        "likely_next_regime": "LATE_CYCLE",
        "triggers": ["credit_hy>=450bps"],
        "invalidations": ["credit_spreads_tighten_below_350bps"],
    }

    merged = api_app._merge_regime_warning(previous, current)
    assert merged is not None
    assert merged["warning_tier"] == "imminent"
    assert merged["transition_probability"] >= 0.74

