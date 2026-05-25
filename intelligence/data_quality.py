from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def evaluate_vector_store_health(index_ntotal: int, metadata: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    count = len(metadata)

    if index_ntotal <= 0:
        issues.append("Vector index has zero entries.")
    if count == 0:
        issues.append("Metadata store is empty.")
    if index_ntotal > 0 and count > 0 and abs(index_ntotal - count) > max(50, int(0.05 * count)):
        issues.append(
            f"Index/metadata mismatch is high (index={index_ntotal}, metadata={count})."
        )

    missing_text = sum(1 for m in metadata if not (m.get("text") or "").strip()) if metadata else 0
    missing_ratio = (missing_text / count) if count else 1.0
    if missing_ratio > 0.1:
        issues.append(f"Too many empty chunks in metadata ({missing_ratio:.1%}).")

    lengths = []
    for m in metadata[: min(5000, count)]:
        text = (m.get("text") or "").strip()
        if text:
            lengths.append(len(text.split()))

    median_len = sorted(lengths)[len(lengths) // 2] if lengths else 0
    if lengths and median_len < 40:
        issues.append(
            f"Median chunk length appears too short ({median_len} words), likely hurting retrieval quality."
        )

    status = "GOOD" if not issues else ("WARN" if len(issues) <= 2 else "BAD")
    return {
        "status": status,
        "issues": issues,
        "index_ntotal": index_ntotal,
        "metadata_count": count,
        "missing_text_ratio": round(missing_ratio, 4),
        "median_chunk_words": median_len,
    }


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) > 2}


def evaluate_retrieval_quality(question: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    q_tokens = _tokenize(question)
    if not chunks:
        return {
            "status": "BAD",
            "score": 0,
            "issues": ["No chunks retrieved."],
            "chunk_count": 0,
            "avg_token_overlap": 0.0,
        }

    overlaps: list[float] = []
    for c in chunks:
        c_tokens = _tokenize(c.get("text", ""))
        if not q_tokens or not c_tokens:
            overlaps.append(0.0)
            continue
        overlap = len(q_tokens.intersection(c_tokens)) / max(1, len(q_tokens))
        overlaps.append(overlap)

    avg_overlap = sum(overlaps) / len(overlaps)
    issues = []
    if len(chunks) < 3:
        issues.append("Too few retrieved chunks (<3).")
    if avg_overlap < 0.08:
        issues.append("Low lexical overlap between question and retrieved chunks.")

    score = 100
    score -= max(0, 3 - len(chunks)) * 15
    score -= int(max(0.0, 0.08 - avg_overlap) * 300)
    score = max(5, min(98, score))

    status = "GOOD" if score >= 70 else ("WARN" if score >= 45 else "BAD")
    return {
        "status": status,
        "score": score,
        "issues": issues,
        "chunk_count": len(chunks),
        "avg_token_overlap": round(avg_overlap, 4),
    }


_SECTION_HEADERS = {
    "executive summary:",
    "direct answer:",
    "data snapshot:",
    "causal chain:",
    "what is happening:",
    "market impact:",
    "cross-asset impact:",
    "predicted events:",
    "scenarios",
    "what to watch:",
    "confidence:",
}


def _parse_source_date_days_ago(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw or raw.lower().startswith("unknown"):
        return None
    txt = raw.replace("Z", "+00:00")
    parsed: datetime | None = None
    for candidate in (txt, txt[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)


def _freshness_score_from_days(days_ago: float) -> float:
    if days_ago <= 1:
        return 1.0
    if days_ago <= 7:
        return 0.8
    if days_ago <= 30:
        return 0.6
    if days_ago <= 90:
        return 0.35
    return 0.15


def evaluate_evidence_integrity(response_text: str, evidence_coverage: dict[str, Any]) -> dict[str, Any]:
    text = response_text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    claim_lines: list[str] = []
    for line in lines:
        lower = line.lower()
        if lower in _SECTION_HEADERS:
            continue
        if lower.startswith("━━━") or lower.startswith("▸"):
            continue
        if line.startswith("-"):
            candidate = line[1:].strip()
        else:
            candidate = line
        if candidate and any(ch.isalpha() for ch in candidate):
            claim_lines.append(candidate)

    cited_claims = sum(1 for c in claim_lines if re.search(r"\[S\d+\]", c))
    total_claims = len(claim_lines)
    unsupported_claim_count = max(0, total_claims - cited_claims)

    if total_claims == 0:
        support_score = 0.0
    else:
        support_score = round((cited_claims / total_claims) * 100.0, 2)

    sources = evidence_coverage.get("sources", []) if isinstance(evidence_coverage, dict) else []
    source_names = [str(s.get("source", "")).strip() for s in sources if isinstance(s, dict)]
    non_empty_sources = [s for s in source_names if s]
    unique_sources = len(set(non_empty_sources))
    total_sources = len(non_empty_sources)

    if total_sources == 0:
        diversity_score = 0.0
    else:
        diversity_score = round(unique_sources / total_sources, 3)

    dated_scores: list[float] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        days_ago = _parse_source_date_days_ago(str(src.get("date", "")))
        if days_ago is not None:
            dated_scores.append(_freshness_score_from_days(days_ago))
    freshness_score = round(sum(dated_scores) / len(dated_scores), 3) if dated_scores else 0.0

    if support_score >= 75 and unsupported_claim_count <= 3:
        status = "pass"
        warning_level = "low"
    elif support_score >= 45 and unsupported_claim_count <= 8:
        status = "warning"
        warning_level = "medium"
    else:
        status = "review_required"
        warning_level = "high"

    return {
        "support_score": support_score,
        "unsupported_claim_count": unsupported_claim_count,
        "source_freshness_score": freshness_score,
        "source_diversity_score": diversity_score,
        "status": status,
        "warning_level": warning_level,
        "claim_count": total_claims,
        "cited_claim_count": cited_claims,
    }


def evaluate_ingestion_quality(metadata: list[dict[str, Any]], stale_days: int = 120) -> dict[str, Any]:
    total = len(metadata or [])
    if total == 0:
        return {
            "status": "BAD",
            "issues": ["Metadata store is empty."],
            "total_docs": 0,
            "empty_text_ratio": 1.0,
            "duplicate_ratio": 0.0,
            "stale_ratio": 1.0,
            "bad_metadata_ratio": 1.0,
        }

    now = datetime.now(timezone.utc)
    stale_cutoff_days = max(1, int(stale_days))

    empty_text = 0
    duplicates = 0
    stale = 0
    bad_meta = 0
    seen_keys: set[str] = set()

    for row in metadata:
        text = (row.get("text") or "").strip()
        md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

        if not text:
            empty_text += 1

        dedup_key = (
            str(md.get("chunk_id") or row.get("chunk_id") or "").strip()
            or str(md.get("fingerprint") or row.get("fingerprint") or "").strip()
            or text[:160].lower()
        )
        if dedup_key in seen_keys:
            duplicates += 1
        else:
            seen_keys.add(dedup_key)

        date_raw = (
            md.get("indexed_at")
            or md.get("extracted_at")
            or md.get("date")
            or row.get("indexed_at")
            or row.get("extracted_at")
            or row.get("date")
            or ""
        )
        days_ago = _parse_source_date_days_ago(str(date_raw))
        if days_ago is None or days_ago > stale_cutoff_days:
            stale += 1

        source = (md.get("source") or row.get("source") or "").strip()
        data_type = (md.get("data_type") or row.get("data_type") or "").strip()
        region = (md.get("region") or row.get("region") or "").strip()
        if not source or not data_type or not region:
            bad_meta += 1

    empty_ratio = empty_text / total
    duplicate_ratio = duplicates / total
    stale_ratio = stale / total
    bad_meta_ratio = bad_meta / total

    issues: list[str] = []
    if empty_ratio > 0.02:
        issues.append(f"Too many empty-text chunks ({empty_ratio:.1%}).")
    if duplicate_ratio > 0.15:
        issues.append(f"Duplicate chunk ratio too high ({duplicate_ratio:.1%}).")
    if stale_ratio > 0.40:
        issues.append(f"Stale timestamp ratio too high ({stale_ratio:.1%}, threshold={stale_cutoff_days}d).")
    if bad_meta_ratio > 0.05:
        issues.append(f"Missing critical metadata ratio too high ({bad_meta_ratio:.1%}).")

    status = "GOOD" if not issues else ("WARN" if len(issues) <= 2 else "BAD")
    return {
        "status": status,
        "issues": issues,
        "total_docs": total,
        "empty_text_ratio": round(empty_ratio, 4),
        "duplicate_ratio": round(duplicate_ratio, 4),
        "stale_ratio": round(stale_ratio, 4),
        "bad_metadata_ratio": round(bad_meta_ratio, 4),
        "stale_days_threshold": stale_cutoff_days,
    }
