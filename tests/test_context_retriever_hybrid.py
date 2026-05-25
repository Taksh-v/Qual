import numpy as np

from intelligence import context_retriever as cr


class _DummyIndex:
    def __init__(self, indices):
        self.ntotal = max(max(indices) + 1, 1)
        self._indices = indices

    def search(self, qvec, k):
        dists = np.array([[0.9 for _ in self._indices]], dtype="float32")
        idxs = np.array([self._indices], dtype="int64")
        return dists, idxs


class _DummyBM25:
    def __init__(self, results):
        self._results = results

    def search(self, query, top_k=10):
        return self._results[:top_k]


def _metadata():
    return [
        {
            "doc_type": "news",
            "title": "Alpha growth accelerates",
            "summary": "alpha alpha trend",
            "published": "2025-01-02T00:00:00Z",
            "source": "unit",
            "text": "alpha trend and demand",
        },
        {
            "doc_type": "news",
            "title": "Beta guidance maintained",
            "summary": "beta outlook",
            "published": "2025-01-01T00:00:00Z",
            "source": "unit",
            "text": "beta fundamentals",
        },
        {
            "doc_type": "news",
            "title": "Gamma supply squeeze",
            "summary": "gamma event",
            "published": "2025-01-03T00:00:00Z",
            "source": "unit",
            "text": "gamma disruption relevance",
        },
    ]


def test_hybrid_rrf_applied_when_enabled(monkeypatch):
    meta = _metadata()
    rrf_called = {"value": False}

    monkeypatch.setattr(cr, "_INTEL_CONTEXT_CACHE", False)
    monkeypatch.setattr(cr, "_INTEL_HYBRID_RETRIEVAL", True)
    monkeypatch.setattr(cr, "_USE_RERANKER", False)
    monkeypatch.setattr(cr, "_extract_filters", lambda q, geography=None: {"hard": {}, "soft": {}})
    monkeypatch.setattr(cr, "_load_index_cached", lambda: _DummyIndex([0, 1]))
    monkeypatch.setattr(cr, "_load_metadata_cached", lambda: meta)
    monkeypatch.setattr(cr, "embed_query", lambda q: np.array([0.1, 0.2], dtype="float32"))
    monkeypatch.setattr(cr, "_load_bm25_cached", lambda: _DummyBM25([(meta[2], 9.0)]))

    def _fake_rrf(semantic_pairs, bm25_pairs, k=60, semantic_weight=0.55, bm25_weight=0.45):
        rrf_called["value"] = True
        return [meta[2], meta[0], meta[1]]

    monkeypatch.setattr(cr, "_rrf", _fake_rrf)

    out = cr.retrieve_relevant_context("alpha trend", top_k=2, keep_latest=2)
    telemetry = cr.get_last_retrieval_telemetry()

    assert rrf_called["value"] is True
    assert len(out) == 2
    assert any(item.get("title") == "Gamma supply squeeze" for item in out)
    assert telemetry.get("rrf_applied") is True
    assert telemetry.get("hybrid_enabled") is True
    assert telemetry.get("fallback_reason") == "none"
    assert isinstance(telemetry.get("top_chunks"), list)
    assert len(telemetry.get("top_chunks", [])) >= 1


def test_hybrid_bypassed_when_disabled(monkeypatch):
    meta = _metadata()

    monkeypatch.setattr(cr, "_INTEL_CONTEXT_CACHE", False)
    monkeypatch.setattr(cr, "_INTEL_HYBRID_RETRIEVAL", False)
    monkeypatch.setattr(cr, "_USE_RERANKER", False)
    monkeypatch.setattr(cr, "_extract_filters", lambda q, geography=None: {"hard": {}, "soft": {}})
    monkeypatch.setattr(cr, "_load_index_cached", lambda: _DummyIndex([0, 1]))
    monkeypatch.setattr(cr, "_load_metadata_cached", lambda: meta)
    monkeypatch.setattr(cr, "embed_query", lambda q: np.array([0.1, 0.2], dtype="float32"))

    def _rrf_should_not_be_called(*args, **kwargs):
        raise AssertionError("RRF should not be called when hybrid retrieval is disabled")

    monkeypatch.setattr(cr, "_rrf", _rrf_should_not_be_called)

    out = cr.retrieve_relevant_context("alpha trend", top_k=2, keep_latest=2)
    telemetry = cr.get_last_retrieval_telemetry()

    titles = [item.get("title") for item in out]
    assert "Alpha growth accelerates" in titles
    assert "Beta guidance maintained" in titles
    assert "Gamma supply squeeze" not in titles
    assert telemetry.get("hybrid_enabled") is False
    assert telemetry.get("rrf_applied") is False


def test_extract_filters_enforces_geography_and_source_hard_filters():
    filters = cr._extract_filters("What is Reuters saying about rates?", geography="US")

    hard = filters.get("hard", {})
    assert "regions" in hard
    assert "US" in hard["regions"]
    assert "sources" in hard
    assert "Reuters" in hard["sources"]
