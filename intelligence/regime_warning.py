from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_regime_warning(regime: dict[str, Any], cross_asset: dict[str, Any], indicators: dict[str, Any]) -> dict[str, Any]:
    score = 0
    triggers: list[str] = []
    invalidations: list[str] = []

    regime_name = str(regime.get("regime", "") or "").upper()
    regime_conf = str(regime.get("confidence", "") or "").upper()
    overall_signal = str(cross_asset.get("overall_signal", "") or "").upper()
    alerts = cross_asset.get("alerts", []) if isinstance(cross_asset.get("alerts"), list) else []
    divergences = cross_asset.get("divergences", []) if isinstance(cross_asset.get("divergences"), list) else []

    yield_curve = _to_float(indicators.get("yield_curve"))
    credit_hy = _to_float(indicators.get("credit_hy"))
    vix = _to_float(indicators.get("vix"))
    inflation = _to_float(indicators.get("inflation_cpi"))
    gdp_growth = _to_float(indicators.get("gdp_growth"))

    if regime_name in {"TRANSITIONAL", "LATE_CYCLE", "DEFLATION_RISK"}:
        score += 18
        triggers.append(f"regime={regime_name}")

    if regime_conf == "LOW":
        score += 15
        triggers.append("regime_confidence=LOW")

    if "BEARISH" in overall_signal:
        score += 22
        triggers.append(f"cross_asset_signal={overall_signal}")
    elif "DIVERGENT" in overall_signal or "CONFLICTED" in overall_signal:
        score += 14
        triggers.append(f"cross_asset_signal={overall_signal}")

    score += min(len(alerts), 5) * 6
    score += min(len(divergences), 3) * 5

    if yield_curve is not None and yield_curve <= -50:
        score += 14
        triggers.append("yield_curve<=-50bps")
    elif yield_curve is not None and yield_curve < 0:
        score += 7
        triggers.append("yield_curve<0")

    if credit_hy is not None and credit_hy >= 600:
        score += 18
        triggers.append("credit_hy>=600bps")
    elif credit_hy is not None and credit_hy >= 450:
        score += 10
        triggers.append("credit_hy>=450bps")

    if vix is not None and vix >= 30:
        score += 14
        triggers.append("vix>=30")
    elif vix is not None and vix >= 24:
        score += 7
        triggers.append("vix>=24")

    if inflation is not None and inflation >= 4.0 and (gdp_growth is None or gdp_growth <= 1.0):
        score += 10
        triggers.append("inflation>=4_with_soft_growth")

    probability = max(0.0, min(score / 100.0, 0.99))

    if probability >= 0.75:
        tier = "imminent"
    elif probability >= 0.45:
        tier = "elevated"
    else:
        tier = "watch"

    if yield_curve is not None and yield_curve >= 0:
        invalidations.append("yield_curve_normalizes_non_negative")
    if credit_hy is not None and credit_hy <= 350:
        invalidations.append("credit_spreads_tighten_below_350bps")
    if vix is not None and vix <= 18:
        invalidations.append("vix_reverts_below_18")
    if regime_conf == "HIGH" and regime_name in {"GOLDILOCKS", "EARLY_RECOVERY", "REFLATION"}:
        invalidations.append("regime_confidence_high_in_stable_regime")

    likely_next_regime = regime_name
    if tier in {"elevated", "imminent"}:
        if regime_name in {"GOLDILOCKS", "EARLY_RECOVERY", "REFLATION", "TRANSITIONAL"}:
            likely_next_regime = "LATE_CYCLE"
        elif regime_name in {"LATE_CYCLE", "DEFLATION_RISK"}:
            likely_next_regime = "RECESSION"
        elif regime_name == "STAGFLATION":
            likely_next_regime = "RECESSION"

    return {
        "warning_tier": tier,
        "transition_probability": round(probability, 3),
        "likely_next_regime": likely_next_regime,
        "triggers": triggers[:8],
        "invalidations": invalidations[:8],
    }
