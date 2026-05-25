"""
ingestion/pulse_monitor.py
--------------------------
Quantum Pulse: High-frequency feed poller for SEC filings and breaking news.

Polls PULSE_FEEDS every 60 seconds, fetches new articles, and routes them
through the standard chunking → embedding → MetadataStore pipeline.

Usage:
    python -m ingestion.pulse_monitor              # run indefinitely
    python -m ingestion.pulse_monitor --once       # single pass, then exit
    python -m ingestion.pulse_monitor --interval 30  # custom interval (seconds)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.rss_sources import PULSE_FEEDS
from ingestion.rss_fetcher import fetch_all_feeds
from ingestion.chunker import chunk_text
from ingestion.embeddings import get_embeddings
from ingestion.metadata_store import MetadataStore
from intelligence.signal_monitor import SignalMonitor

import numpy as np

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "data", "vector_db", "news.index")

# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_faiss_index(path: str):
    """Load an existing FAISS index from disk."""
    try:
        import faiss
        return faiss.read_index(path)
    except Exception as exc:
        logger.warning("[Pulse] Could not load FAISS index: %s", exc)
        return None


def _create_faiss_index(dim: int):
    """Create a new FAISS IndexFlatIP."""
    try:
        import faiss
        return faiss.IndexFlatIP(dim)
    except Exception as exc:
        logger.error("[Pulse] Could not create FAISS index: %s", exc)
        return None


def _save_faiss_index(index, path: str) -> None:
    """Persist FAISS index to disk."""
    import faiss
    os.makedirs(os.path.dirname(path), exist_ok=True)
    faiss.write_index(index, path)


# ── Core Pipeline ────────────────────────────────────────────────────────────

def build_chunks(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chunk articles into sentence windows suitable for embedding."""
    chunks: list[dict[str, Any]] = []
    for art in articles:
        raw = (art.get("raw_text") or "").strip()
        title = (art.get("title") or "").strip()

        if not raw or len(raw) < 100:  # Lower threshold for SEC filings
            continue
        if title and raw.lower() == title.lower():
            continue

        base_meta = {
            "title": art.get("title", ""),
            "source": art.get("source", ""),
            "category": art.get("category", ""),
            "url": art.get("url", ""),
            "date": art.get("date", ""),
            "extracted_at": art.get("extracted_at", ""),
            "company": art.get("company", "Unknown"),
            "doc_type": "SEC Filing" if "SEC" in art.get("source", "") else "Breaking News",
            "data_type": "filing" if "SEC" in art.get("source", "") else "news",
            "pulse": True,  # Tag for real-time origin
        }
        chunk_items = chunk_text(
            raw,
            chunk_size=1500,
            overlap=200,
            with_metadata=True,
            extra_metadata={"metadata": base_meta},
        )
        total = len(chunk_items)
        for i, chunk in enumerate(chunk_items):
            text = chunk.get("text", "")
            if not text.strip():
                continue
            md = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), dict) else {}
            md["chunk_index"] = i
            md["chunk_total"] = total
            chunk["metadata"] = md
            chunks.append(chunk)
    return chunks


def ingest_pulse(articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Chunk, embed, and upsert a batch of articles into the index."""
    stats: dict[str, Any] = {"articles": len(articles), "chunks": 0, "embedded": 0, "skipped": 0, "alerts": 0}

    if not articles:
        return stats

    chunks = build_chunks(articles)
    stats["chunks"] = len(chunks)

    if not chunks:
        return stats

    # ── Signal Watchdog: scan for market-moving keywords BEFORE embedding ──
    signal_monitor = SignalMonitor()
    alerts = signal_monitor.scan_chunks(chunks)
    stats["alerts"] = len(alerts)
    if alerts:
        logger.info("[Pulse] ⚡ %d signal alerts detected!", len(alerts))

    # Load or create FAISS index
    index = _load_faiss_index(INDEX_PATH) if os.path.exists(INDEX_PATH) else None
    store = MetadataStore()
    new_vecs: list[np.ndarray] = []
    chunks_to_upsert: list[dict[str, Any]] = []

    batch_size = 20
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]
        vecs = get_embeddings(texts, data_type="news", normalize=True, role="passage")

        for chunk, vec in zip(batch, vecs):
            if vec is None:
                stats["skipped"] += 1
                continue
            if index is None:
                index = _create_faiss_index(len(vec))
            if index is None:
                break
            new_vecs.append(vec)
            chunks_to_upsert.append(chunk)
            stats["embedded"] += 1

    if new_vecs and index is not None:
        start_rowid = index.ntotal
        mat = np.stack(new_vecs, axis=0)
        index.add(mat)
        _save_faiss_index(index, INDEX_PATH)
        store.upsert_chunks(chunks_to_upsert, start_rowid=start_rowid)
        logger.info("[Pulse] Indexed %d new vectors (total: %d)", len(new_vecs), index.ntotal)

    return stats


# ── Main Loop ────────────────────────────────────────────────────────────────

def pulse_loop(interval: int = 60, once: bool = False) -> None:
    """
    High-frequency polling loop.

    Args:
        interval: Seconds between polls (default 60).
        once:     If True, run a single pass and exit.
    """
    logger.info("═" * 60)
    logger.info("  QUANTUM PULSE MONITOR STARTED")
    logger.info("  Interval: %ds | Feeds: %d | Mode: %s",
                interval, len(PULSE_FEEDS), "single-pass" if once else "continuous")
    logger.info("═" * 60)

    cycle = 0
    while True:
        cycle += 1
        t0 = time.time()
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        logger.info("[Pulse #%d] Scanning at %s...", cycle, ts)

        try:
            articles = fetch_all_feeds(PULSE_FEEDS, skip_seen=True)
            if articles:
                logger.info("[Pulse #%d] Found %d new articles — ingesting...", cycle, len(articles))
                stats = ingest_pulse(articles)
                logger.info("[Pulse #%d] Done: %d articles → %d chunks → %d embedded",
                            cycle, stats["articles"], stats["chunks"], stats["embedded"])
            else:
                logger.info("[Pulse #%d] No new articles.", cycle)
        except Exception as exc:
            logger.error("[Pulse #%d] Error: %s", cycle, exc, exc_info=True)

        elapsed = round(time.time() - t0, 1)
        logger.info("[Pulse #%d] Completed in %.1fs", cycle, elapsed)

        if once:
            break

        sleep_time = max(1, interval - elapsed)
        logger.debug("[Pulse] Sleeping %.1fs...", sleep_time)
        time.sleep(sleep_time)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Quantum Pulse: real-time feed monitor")
    parser.add_argument("--once", action="store_true", help="Single pass, then exit")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default: 60)")
    args = parser.parse_args()

    pulse_loop(interval=args.interval, once=args.once)


if __name__ == "__main__":
    main()
