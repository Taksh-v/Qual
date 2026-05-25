import json
import os
import argparse
from pathlib import Path
from statistics import median

import faiss

from intelligence.data_quality import evaluate_vector_store_health, evaluate_ingestion_quality

ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "data" / "vector_db" / "news.index"
METADATA_PATH = ROOT / "data" / "vector_db" / "metadata.json"
REPORT_PATH = ROOT / "data" / "vector_db" / "quality_report.json"


def _chunk_word_stats(metadata: list[dict]) -> dict:
    lengths = [len((m.get("text") or "").split()) for m in metadata if (m.get("text") or "").strip()]
    if not lengths:
        return {"count": 0, "min": 0, "median": 0, "max": 0}
    return {
        "count": len(lengths),
        "min": min(lengths),
        "median": int(median(lengths)),
        "max": max(lengths),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run vector + ingestion quality audit.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when any quality block is BAD.")
    parser.add_argument("--stale-days", type=int, default=120, help="Staleness threshold in days.")
    args = parser.parse_args()

    if not INDEX_PATH.exists() or not METADATA_PATH.exists():
        print("❌ Missing index or metadata in data/vector_db. Run embedding pipeline first.")
        return 1

    index = faiss.read_index(str(INDEX_PATH))
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    health = evaluate_vector_store_health(index.ntotal, metadata)
    ingestion = evaluate_ingestion_quality(metadata, stale_days=max(1, int(args.stale_days)))
    stats = _chunk_word_stats(metadata)
    report = {
        "vector_store_health": health,
        "ingestion_quality": ingestion,
        "chunk_word_stats": stats,
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("✅ Data quality audit complete")
    print(json.dumps(report, indent=2))
    print(f"\nReport saved to: {REPORT_PATH}")

    if args.strict and (health.get("status") == "BAD" or ingestion.get("status") == "BAD"):
        print("❌ Strict mode: quality audit failed.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
