from intelligence.data_quality import evaluate_ingestion_quality


def test_ingestion_quality_flags_bad_dataset():
    metadata = [
        {
            "text": "",
            "metadata": {"chunk_id": "a", "source": "", "data_type": "", "region": "", "date": "2020-01-01"},
        },
        {
            "text": "duplicate body",
            "metadata": {"chunk_id": "dup", "source": "Reuters", "data_type": "news", "region": "US", "date": "2020-01-01"},
        },
        {
            "text": "duplicate body",
            "metadata": {"chunk_id": "dup", "source": "Reuters", "data_type": "news", "region": "US", "date": "2020-01-01"},
        },
    ]

    out = evaluate_ingestion_quality(metadata, stale_days=30)

    assert out["status"] in {"WARN", "BAD"}
    assert out["empty_text_ratio"] > 0
    assert out["duplicate_ratio"] > 0
    assert out["stale_ratio"] > 0
    assert out["bad_metadata_ratio"] > 0


def test_ingestion_quality_passes_clean_dataset():
    metadata = [
        {
            "text": "Macro conditions remain stable with moderate inflation.",
            "metadata": {
                "chunk_id": "c1",
                "source": "Reuters",
                "data_type": "news",
                "region": "US",
                "date": "2026-03-30",
            },
        },
        {
            "text": "Energy prices eased while credit spreads were range-bound.",
            "metadata": {
                "chunk_id": "c2",
                "source": "Bloomberg",
                "data_type": "news",
                "region": "Europe",
                "date": "2026-03-31",
            },
        },
    ]

    out = evaluate_ingestion_quality(metadata, stale_days=365)

    assert out["status"] == "GOOD"
    assert out["issues"] == []
