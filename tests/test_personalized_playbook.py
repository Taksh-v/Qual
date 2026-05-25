import importlib


def test_personalization_advisory_keeps_text_but_reports_adjustments(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_PERSONALIZED_PLAYBOOK", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON", "alerts": [], "divergences": []},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }
    response_text = "Direct answer: Overweight XLE and reduce duration.\n"
    payload = api_app._make_structured_payload(
        snapshot,
        response_text,
        model_used="unit-test",
        response_mode="brief",
        question="How to position?",
        persist_decision=False,
        user_profile={"banned_assets": ["XLE"], "profile_version": "p-1"},
        profile_enforcement_mode="advisory",
    )

    assert "XLE" in payload.get("response_text", "")
    p = payload.get("personalization", {})
    assert p.get("enforcement_mode") == "advisory"
    assert len(p.get("recommendation_adjustments", [])) >= 1


def test_personalization_strict_removes_banned_lines(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_PERSONALIZED_PLAYBOOK", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON", "alerts": [], "divergences": []},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }
    response_text = "Direct answer: Overweight XLE and reduce duration.\nMarket impact: XLE outperforms.\n"
    payload = api_app._make_structured_payload(
        snapshot,
        response_text,
        model_used="unit-test",
        response_mode="brief",
        question="How to position?",
        persist_decision=False,
        user_profile={"banned_assets": ["XLE"], "constraints": ["no energy exposure"]},
        profile_enforcement_mode="strict",
    )

    assert "XLE" not in payload.get("response_text", "")
    assert "Removed due to profile constraint" in payload.get("response_text", "")
    p = payload.get("personalization", {})
    assert p.get("enforcement_mode") == "strict"
    assert payload.get("_response_contract", {}).get("personalization", {}).get("enforcement_mode") == "strict"


def test_personalization_strict_respects_allowed_instruments(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_PERSONALIZED_PLAYBOOK", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON", "alerts": [], "divergences": []},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }
    response_text = "Direct answer: Long XLE and add TLT while trimming XLV.\n"
    payload = api_app._make_structured_payload(
        snapshot,
        response_text,
        model_used="unit-test",
        response_mode="brief",
        question="How to position?",
        persist_decision=False,
        user_profile={"allowed_instruments": ["TLT"], "profile_version": "p-2"},
        profile_enforcement_mode="strict",
    )

    assert "Removed due to allowed instrument constraint" in payload.get("response_text", "")
    p = payload.get("personalization", {})
    assert p.get("profile_version") == "p-2"
    assert len(p.get("recommendation_adjustments", [])) >= 1


def test_personalization_strict_limits_recommendation_count(monkeypatch) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_PERSONALIZED_PLAYBOOK", "1")

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON", "alerts": [], "divergences": []},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }
    response_text = (
        "Direct answer: Overweight TLT.\n"
        "Action plan: Add GLD, Long IEF, Reduce HYG.\n"
    )
    payload = api_app._make_structured_payload(
        snapshot,
        response_text,
        model_used="unit-test",
        response_mode="brief",
        question="How to position?",
        persist_decision=False,
        user_profile={"limits": {"max_recommendations": 1}},
        profile_enforcement_mode="strict",
    )

    assert "Removed due to max recommendation limit" in payload.get("response_text", "")
    p = payload.get("personalization", {})
    assert any("max recommendation limit" in x.lower() for x in p.get("recommendation_adjustments", []))
