from __future__ import annotations

from dataclasses import asdict
from typing import Any

from intelligence.response_normalizer import normalize_text_response
from intelligence.response_schema import StructuredResponse
from intelligence.response_validator import validate_structured_response


def _normalize_contract_block(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return None


def normalize_api_payload(payload: dict[str, Any], mode: str = "brief") -> dict[str, Any]:
    """
    Non-breaking middleware helper:
    - keeps existing payload shape intact
    - attaches optional structured response metadata under `_response_contract`
    """
    answer = str(payload.get("answer", "") or "")
    structured: StructuredResponse = normalize_text_response(answer, mode=mode)
    report = validate_structured_response(structured)

    evidence_integrity = _normalize_contract_block(payload.get("evidence_integrity"))
    regime_warning = _normalize_contract_block(payload.get("regime_warning"))
    decision_stub = _normalize_contract_block(payload.get("decision_stub"))
    counterfactual_result = _normalize_contract_block(payload.get("counterfactual_result"))
    personalization = _normalize_contract_block(payload.get("personalization"))

    if evidence_integrity is None and structured.evidence_integrity is not None:
        evidence_integrity = asdict(structured.evidence_integrity)
    if regime_warning is None and structured.regime_warning is not None:
        regime_warning = asdict(structured.regime_warning)
    if decision_stub is None and structured.decision_stub is not None:
        decision_stub = asdict(structured.decision_stub)
    if counterfactual_result is None and structured.counterfactual_result is not None:
        counterfactual_result = asdict(structured.counterfactual_result)
    if personalization is None and structured.personalization is not None:
        personalization = asdict(structured.personalization)

    metadata = dict(payload.get("_response_contract", {}))
    metadata.update(
        {
            "mode": structured.metadata.mode,
            "validation_ok": report.ok,
            "validation_warnings": report.warnings,
            "schema_version": "v2",
            "evidence_integrity": evidence_integrity,
            "regime_warning": regime_warning,
            "decision_stub": decision_stub,
            "counterfactual_result": counterfactual_result,
            "personalization": personalization,
        }
    )

    out = dict(payload)
    if evidence_integrity is not None and out.get("evidence_integrity") is None:
        out["evidence_integrity"] = evidence_integrity
    if regime_warning is not None and out.get("regime_warning") is None:
        out["regime_warning"] = regime_warning
    if decision_stub is not None and out.get("decision_stub") is None:
        out["decision_stub"] = decision_stub
    if counterfactual_result is not None and out.get("counterfactual_result") is None:
        out["counterfactual_result"] = counterfactual_result
    if personalization is not None and out.get("personalization") is None:
        out["personalization"] = personalization
    out["_response_contract"] = metadata
    return out
