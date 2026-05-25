from intelligence.response_middleware import normalize_api_payload


def test_optional_blocks_mirrored_to_contract_metadata() -> None:
    payload = {
        "question": "q",
        "answer": (
            "Direct answer: A\n"
            "Data snapshot: B\n"
            "Causal chain: C\n"
            "What is happening:\n"
            "- x\n"
            "Market impact:\n"
            "- y\n"
            "Predicted events:\n"
            "- Event 1 (7-30d, 50%): n; trigger: t; invalidation: i.\n"
            "Scenarios (probabilities must add to 100%):\n"
            "- Base (~50%): a\n"
            "- Bull (~30%): b\n"
            "- Bear (~20%): c\n"
            "What to watch:\n"
            "- z\n"
            "Confidence: MEDIUM - m"
        ),
        "evidence_integrity": {"status": "warning", "unsupported_claim_count": 1},
    }

    out = normalize_api_payload(payload)

    assert out.get("evidence_integrity", {}).get("status") == "warning"
    assert out.get("_response_contract", {}).get("evidence_integrity", {}).get("status") == "warning"


def test_invalid_optional_block_type_does_not_break_contract() -> None:
    payload = {
        "question": "q",
        "answer": "Direct answer: A\nData snapshot: B\nCausal chain: C\n",
        "evidence_integrity": "invalid-shape",
    }

    out = normalize_api_payload(payload)

    assert out.get("evidence_integrity") == "invalid-shape"
    assert out.get("_response_contract", {}).get("evidence_integrity") is None
