from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_external_shock_state(
    indicators: dict[str, Any],
    cross_asset: dict[str, Any],
    regime: dict[str, Any],
    event_stress_score: float = 0.0,
) -> dict[str, Any]:
    score = 0.0
    triggers: list[str] = []
    invalidations: list[str] = []

    vix = _to_float(indicators.get("vix"))
    credit_hy = _to_float(indicators.get("credit_hy"))
    yield_curve = _to_float(indicators.get("yield_curve"))
    dxy = _to_float(indicators.get("dxy"))
    oil_wti = _to_float(indicators.get("oil_wti"))

    alerts = cross_asset.get("alerts", []) if isinstance(cross_asset, dict) else []
    divergences = cross_asset.get("divergences", []) if isinstance(cross_asset, dict) else []
    overall_signal = str((cross_asset or {}).get("overall_signal", "") or "").upper()
    regime_conf = str((regime or {}).get("confidence", "") or "").upper()

    if vix is not None and vix >= 35:
        score += 28
        triggers.append("vix>=35")
    elif vix is not None and vix >= 25:
        score += 16
        triggers.append("vix>=25")

    if credit_hy is not None and credit_hy >= 700:
        score += 26
        triggers.append("credit_hy>=700bps")
    elif credit_hy is not None and credit_hy >= 500:
        score += 14
        triggers.append("credit_hy>=500bps")

    if yield_curve is not None and yield_curve <= -90:
        score += 14
        triggers.append("yield_curve<=-90bps")
    elif yield_curve is not None and yield_curve <= -40:
        score += 7
        triggers.append("yield_curve<=-40bps")

    if dxy is not None and dxy >= 108:
        score += 8
        triggers.append("dxy>=108")
    if oil_wti is not None and oil_wti >= 95:
        score += 10
        triggers.append("oil_wti>=95")

    score += min(len(alerts), 5) * 4
    score += min(len(divergences), 3) * 3
    if "ALIGNED_BEARISH" in overall_signal:
        score += 8
        triggers.append("cross_asset_aligned_bearish")
    if regime_conf == "LOW":
        score += 5
        triggers.append("regime_confidence_low")

    event_stress_score = max(0.0, min(float(event_stress_score or 0.0), 1.0))
    if event_stress_score > 0:
        score += event_stress_score * 20
        triggers.append(f"event_stress={event_stress_score:.2f}")

    normalized = max(0.0, min(score / 100.0, 1.0))
    if normalized >= 0.75:
        mode = "crisis"
    elif normalized >= 0.45:
        mode = "elevated"
    else:
        mode = "normal"

    if (vix is not None and vix <= 18) or (credit_hy is not None and credit_hy <= 350):
        invalidations.append("market_stress_normalized")
    if event_stress_score <= 0.25:
        invalidations.append("event_stress_subsided")
    if regime_conf == "HIGH" and not alerts:
        invalidations.append("regime_confidence_high_with_no_alerts")

    if mode == "crisis":
        confidence_degradation = {"score_penalty": 18, "band_penalty": 2, "scenario_range_widening": "high"}
        scenario_reweight = "defensive_risk_first"
        manual_review_required = normalized >= 0.9
    elif mode == "elevated":
        confidence_degradation = {"score_penalty": 8, "band_penalty": 1, "scenario_range_widening": "medium"}
        scenario_reweight = "hybrid_transition_weighted"
        manual_review_required = normalized >= 0.7
    else:
        confidence_degradation = {"score_penalty": 0, "band_penalty": 0, "scenario_range_widening": "none"}
        scenario_reweight = "rule_first"
        manual_review_required = False

    return {
        "external_shock_score": round(normalized, 3),
        "shock_mode": mode,
        "mode_thresholds": {"elevated": 0.45, "crisis": 0.75},
        "trigger_conditions": triggers[:10],
        "invalidation_conditions": invalidations[:10],
        "scenario_reweighting": scenario_reweight,
        "confidence_degradation": confidence_degradation,
        "manual_review_required": manual_review_required,
        "score_inputs": {
            "vix": vix,
            "credit_hy": credit_hy,
            "yield_curve": yield_curve,
            "dxy": dxy,
            "oil_wti": oil_wti,
            "alerts_count": len(alerts),
            "divergences_count": len(divergences),
            "overall_signal": overall_signal,
            "regime_confidence": regime_conf,
            "event_stress_score": round(event_stress_score, 3),
        },
    }
