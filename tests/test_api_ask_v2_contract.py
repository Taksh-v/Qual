import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
	api_app = importlib.import_module("api.app")
	monkeypatch.setattr(api_app, "_VALID_API_KEYS", set(), raising=False)
	monkeypatch.setattr(api_app, "log_query", lambda **kwargs: None)
	api_app._ask_guard.cache.invalidate()
	with TestClient(api_app.app) as tc:
		yield tc
	api_app._ask_guard.cache.invalidate()


def test_ask_includes_response_contract_metadata(client: TestClient, monkeypatch) -> None:
	api_app = importlib.import_module("api.app")

	async def _fake_ask_rag(question: str) -> dict:
		return {
			"question": question,
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
			"sources": [],
		}

	monkeypatch.setattr(api_app, "ask_rag", _fake_ask_rag)

	response = client.post("/ask", json={"question": "test question"})
	assert response.status_code == 200
	payload = response.json()
	assert "_response_contract" in payload
	assert payload["_response_contract"]["schema_version"] == "v2"
	assert isinstance(payload["_response_contract"]["validation_ok"], bool)
	assert "evidence_integrity" in payload["_response_contract"]
	assert "regime_warning" in payload["_response_contract"]
	assert "decision_stub" in payload["_response_contract"]
	assert "counterfactual_result" in payload["_response_contract"]
	assert "personalization" in payload["_response_contract"]


def test_ask_fallback_still_has_response_contract(client: TestClient, monkeypatch) -> None:
	api_app = importlib.import_module("api.app")

	async def _failing_ask_rag(question: str) -> dict:
		raise RuntimeError("forced failure")

	monkeypatch.setattr(api_app, "ask_rag", _failing_ask_rag)

	response = client.post("/ask", json={"question": "test failure"})
	assert response.status_code == 200
	payload = response.json()
	assert "_response_contract" in payload
	assert payload["_response_contract"]["schema_version"] == "v2"


def test_ask_preserves_optional_contract_blocks(client: TestClient, monkeypatch) -> None:
	api_app = importlib.import_module("api.app")

	async def _fake_ask_rag(question: str) -> dict:
		return {
			"question": question,
			"answer": "Direct answer: A\nData snapshot: B\nCausal chain: C\n",
			"sources": [],
			"evidence_integrity": {"status": "warning", "unsupported_claim_count": 1},
			"regime_warning": {"warning_tier": "watch", "transition_probability": 0.4},
			"decision_stub": {"decision_id": "d-1", "horizon": "7-30d"},
			"counterfactual_result": {"requested": False},
			"personalization": {"enforcement_mode": "advisory"},
		}

	monkeypatch.setattr(api_app, "ask_rag", _fake_ask_rag)

	response = client.post("/ask", json={"question": "test question"})
	assert response.status_code == 200
	payload = response.json()
	contract = payload["_response_contract"]
	assert contract["evidence_integrity"]["status"] == "warning"
	assert contract["regime_warning"]["warning_tier"] == "watch"
	assert contract["decision_stub"]["decision_id"] == "d-1"
	assert contract["counterfactual_result"]["requested"] is False
	assert contract["personalization"]["enforcement_mode"] == "advisory"

