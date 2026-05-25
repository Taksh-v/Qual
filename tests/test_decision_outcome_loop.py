import importlib


def test_structured_payload_persists_decision_stub_when_enabled(monkeypatch, tmp_path) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_DECISION_OUTCOME_LOOP", "1")
    monkeypatch.setattr(api_app, "_DECISION_OUTCOME_PATH", str(tmp_path / "decision_outcome_log.jsonl"))

    snapshot = {
        "regime": {"regime": "SOFT_LANDING", "confidence": "MEDIUM"},
        "cross_asset": {"overall_signal": "RISK_ON"},
        "evidence_coverage": {"context_chunks": 1, "has_overrides": False, "sources": []},
    }
    response_text = "Direct answer: Stay selective in risk assets.\nWhat to watch: CPI and payrolls.\n"
    payload = api_app._make_structured_payload(
        snapshot,
        response_text,
        model_used="unit-test",
        response_mode="brief",
        question="What should I do with risk assets?",
        persist_decision=True,
    )

    assert "decision_stub" in payload
    assert payload["decision_stub"]["status"] == "open"
    entries = api_app._read_jsonl(api_app._DECISION_OUTCOME_PATH, api_app._decision_outcome_lock)
    assert len(entries) == 1
    assert entries[0]["status"] == "open"


def test_feedback_closes_open_decision_record(monkeypatch, tmp_path) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_DECISION_OUTCOME_LOOP", "1")
    monkeypatch.setattr(api_app, "_DECISION_OUTCOME_PATH", str(tmp_path / "decision_outcome_log.jsonl"))
    monkeypatch.setattr(api_app, "_FEEDBACK_PATH", str(tmp_path / "feedback_log.jsonl"))

    api_app._append_jsonl(
        api_app._DECISION_OUTCOME_PATH,
        api_app._decision_outcome_lock,
        {
            "ts": "2026-04-01T00:00:00.000Z",
            "question": "Will yields rise?",
            "decision_id": "d-1",
            "recommendation": "Reduce duration",
            "horizon": "7-30d",
            "trigger": "Hot CPI",
            "invalidation": "Soft CPI",
            "confidence": "MEDIUM",
            "confidence_score": 0.6,
            "status": "open",
        },
    )

    response = api_app.submit_feedback(
        api_app.FeedbackRequest(
            question="Will yields rise?",
            answer_snippet="Reduce duration",
            rating=5,
            comment="Worked as expected",
        )
    )
    assert response["decision_outcome_updates"] == 1

    entries = api_app._read_jsonl(api_app._DECISION_OUTCOME_PATH, api_app._decision_outcome_lock)
    assert entries[0]["status"] == "closed"
    assert entries[0]["realized_outcome"] == "hit"


def test_metrics_includes_decision_outcomes_when_enabled(monkeypatch, tmp_path) -> None:
    api_app = importlib.import_module("api.app")
    monkeypatch.setenv("FEATURE_DECISION_OUTCOME_LOOP", "1")
    monkeypatch.setattr(api_app, "_DECISION_OUTCOME_PATH", str(tmp_path / "decision_outcome_log.jsonl"))
    monkeypatch.setattr(api_app, "_FEEDBACK_PATH", str(tmp_path / "feedback_log.jsonl"))
    monkeypatch.setattr(api_app, "read_recent", lambda n=2000: [])

    api_app._append_jsonl(
        api_app._DECISION_OUTCOME_PATH,
        api_app._decision_outcome_lock,
        {
            "ts": "2026-04-01T00:00:00.000Z",
            "question": "Q1",
            "decision_id": "d-1",
            "status": "closed",
            "confidence_score": 0.7,
            "realized_accuracy": 1.0,
            "realized_outcome": "hit",
        },
    )

    api_app._append_jsonl(
        api_app._FEEDBACK_PATH,
        api_app._feedback_lock,
        {
            "ts": "2026-04-01T00:00:00.000Z",
            "question": "Q1",
            "answer_snippet": "snippet",
            "rating": 5,
            "comment": "great",
        },
    )

    metrics = api_app.get_metrics()
    assert "decision_outcomes" in metrics
    assert metrics["decision_outcomes"]["closed"] == 1
    assert metrics["decision_outcomes"]["feedback_count"] == 1
    assert metrics["decision_outcomes"]["linked_feedback_count"] >= 1
    assert metrics["decision_outcomes"]["avg_feedback_rating_for_closed"] == 5.0
