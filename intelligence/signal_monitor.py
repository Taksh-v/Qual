"""
intelligence/signal_monitor.py
------------------------------
Keyword Watchdog: scans incoming chunks for high-impact market events.

Detects patterns like "FDA Approval", "CEO Resignation", "Trading Halted",
"M&A", "Bankruptcy", etc. and emits structured alert objects that can be
consumed by the dashboard or a notification system.

Usage:
    from intelligence.signal_monitor import SignalMonitor
    monitor = SignalMonitor()
    alerts = monitor.scan_chunks(chunk_list)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERTS_LOG = os.path.join(BASE_DIR, "data", "pulse_alerts.jsonl")

# ── Alert Definitions ────────────────────────────────────────────────────────

@dataclass
class PulseAlert:
    """A structured alert emitted when a keyword pattern is matched."""
    alert_type: str          # e.g. "FDA_APPROVAL", "CEO_CHANGE", "TRADING_HALT"
    severity: str            # "critical" | "high" | "medium" | "low"
    headline: str            # Short human-readable summary
    matched_keyword: str     # The exact keyword or pattern that triggered
    source: str              # Feed source label
    url: str                 # Link to original article
    date: str                # ISO timestamp
    chunk_text: str          # Excerpt of the matching chunk (first 500 chars)
    tickers: list[str] = field(default_factory=list)  # Extracted ticker symbols
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Keyword Pattern Registry ────────────────────────────────────────────────

# Each entry: (compiled_regex, alert_type, severity)
_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # ── Critical (Market-Moving) ──
    (re.compile(r"\btrading\s+halt(?:ed)?\b", re.I),            "TRADING_HALT",     "critical"),
    (re.compile(r"\bFDA\s+approv(?:al|ed|es)\b", re.I),         "FDA_APPROVAL",     "critical"),
    (re.compile(r"\bFDA\s+reject(?:ion|ed|s)\b", re.I),         "FDA_REJECTION",    "critical"),
    (re.compile(r"\bbankruptcy\b", re.I),                        "BANKRUPTCY",       "critical"),
    (re.compile(r"\bdefault(?:ed|s)?\s+on\s+debt\b", re.I),     "DEBT_DEFAULT",     "critical"),
    (re.compile(r"\bstock\s+split\b", re.I),                     "STOCK_SPLIT",      "critical"),

    # ── High (Strategic) ──
    (re.compile(r"\b(?:M&A|merger|acquisition|acquir(?:ed|es|ing))\b", re.I),  "M_AND_A",    "high"),
    (re.compile(r"\bCEO\s+(?:resign|step(?:ped|s)?\s+down|fired|replaced)\b", re.I), "CEO_CHANGE", "high"),
    (re.compile(r"\bCFO\s+(?:resign|step(?:ped|s)?\s+down|fired|replaced)\b", re.I), "CFO_CHANGE", "high"),
    (re.compile(r"\b(?:layoff|laid\s+off|workforce\s+reduction|mass\s+firing)\b", re.I), "LAYOFFS", "high"),
    (re.compile(r"\b(?:rate\s+(?:hike|cut)|interest\s+rate)\b", re.I),         "RATE_DECISION", "high"),
    (re.compile(r"\bearnings\s+(?:beat|miss|surprise)\b", re.I),               "EARNINGS_SURPRISE", "high"),
    (re.compile(r"\bguidance\s+(?:raised|lowered|cut)\b", re.I),               "GUIDANCE_CHANGE", "high"),
    (re.compile(r"\b(?:tariff|sanction|embargo|trade\s+war)\b", re.I),         "TRADE_POLICY", "high"),

    # ── Medium (Notable) ──
    (re.compile(r"\b(?:IPO|initial\s+public\s+offering)\b", re.I),             "IPO",          "medium"),
    (re.compile(r"\b(?:buyback|share\s+repurchase)\b", re.I),                  "BUYBACK",      "medium"),
    (re.compile(r"\bdividend\s+(?:increase|cut|suspend)\b", re.I),             "DIVIDEND_CHANGE", "medium"),
    (re.compile(r"\b(?:downgrade|upgrade)\b", re.I),                           "RATING_CHANGE", "medium"),
    (re.compile(r"\b(?:recall|product\s+recall)\b", re.I),                     "PRODUCT_RECALL", "medium"),
    (re.compile(r"\b(?:SEC\s+investigation|regulatory\s+probe)\b", re.I),      "REGULATORY_PROBE", "medium"),

    # ── Low (Informational) ──
    (re.compile(r"\b(?:partnership|strategic\s+alliance|joint\s+venture)\b", re.I), "PARTNERSHIP", "low"),
    (re.compile(r"\b(?:contract\s+(?:win|award|loss))\b", re.I),               "CONTRACT",    "low"),
    (re.compile(r"\b(?:patent\s+(?:granted|filed|infringement))\b", re.I),     "PATENT",      "low"),
]

# Simple ticker extraction: $AAPL or standalone 2-5 letter uppercase words
_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")


# ── Signal Monitor ───────────────────────────────────────────────────────────

class SignalMonitor:
    """
    Scans incoming text chunks for high-impact keyword patterns and emits alerts.
    """

    def __init__(self, patterns: list[tuple[re.Pattern, str, str]] | None = None) -> None:
        self.patterns = patterns or _PATTERNS
        os.makedirs(os.path.dirname(ALERTS_LOG), exist_ok=True)

    def scan_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[PulseAlert]:
        """Scan a single text string for keyword matches."""
        alerts: list[PulseAlert] = []
        md = metadata or {}

        for pattern, alert_type, severity in self.patterns:
            match = pattern.search(text)
            if match:
                tickers = _TICKER_RE.findall(text)
                alert = PulseAlert(
                    alert_type=alert_type,
                    severity=severity,
                    headline=md.get("title", text[:120].strip()),
                    matched_keyword=match.group(0),
                    source=md.get("source", "unknown"),
                    url=md.get("url", ""),
                    date=md.get("date", ""),
                    chunk_text=text[:500],
                    tickers=tickers,
                )
                alerts.append(alert)

        return alerts

    def scan_chunks(self, chunks: list[dict[str, Any]]) -> list[PulseAlert]:
        """
        Scan a batch of chunks and return all triggered alerts.

        Args:
            chunks: List of chunk dicts with 'text' and optional 'metadata'.

        Returns:
            List of PulseAlert objects.
        """
        all_alerts: list[PulseAlert] = []
        for chunk in chunks:
            text = chunk.get("text", "")
            md = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), dict) else {}
            alerts = self.scan_text(text, metadata=md)
            all_alerts.extend(alerts)

        if all_alerts:
            self._persist_alerts(all_alerts)
            self._log_summary(all_alerts)

        return all_alerts

    def _persist_alerts(self, alerts: list[PulseAlert]) -> None:
        """Append alerts to the JSONL log for downstream consumption."""
        try:
            with open(ALERTS_LOG, "a", encoding="utf-8") as f:
                for alert in alerts:
                    f.write(json.dumps(asdict(alert), ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("[SignalMonitor] Failed to persist alerts: %s", exc)

    def _log_summary(self, alerts: list[PulseAlert]) -> None:
        """Log a concise summary of detected alerts."""
        by_severity: dict[str, int] = {}
        for a in alerts:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

        summary_parts = [f"{sev}: {count}" for sev, count in sorted(by_severity.items())]
        logger.info(
            "[SignalMonitor] ⚡ %d alerts detected (%s)",
            len(alerts),
            " | ".join(summary_parts),
        )
        for alert in alerts:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(alert.severity, "⚪")
            logger.info("  %s [%s] %s — %s", icon, alert.alert_type, alert.headline[:80], alert.source)


if __name__ == "__main__":
    # Quick demo / test
    logging.basicConfig(level=logging.INFO)
    monitor = SignalMonitor()

    test_chunks = [
        {"text": "FDA Approval: $MRNA receives full approval for its updated vaccine. Trading volume surged.",
         "metadata": {"title": "MRNA FDA Approval", "source": "SEC EDGAR 8-K", "date": "2026-04-10"}},
        {"text": "CEO resigned effective immediately amid accounting irregularities at $ENPH.",
         "metadata": {"title": "ENPH CEO Change", "source": "BusinessWire", "date": "2026-04-10"}},
        {"text": "Market update: S&P 500 gained 0.5% today on tech strength.",
         "metadata": {"title": "Market Recap", "source": "CNBC", "date": "2026-04-10"}},
        {"text": "$GOOGL announces $70B share buyback program and dividend increase.",
         "metadata": {"title": "GOOGL Buyback", "source": "PR Newswire", "date": "2026-04-10"}},
    ]

    alerts = monitor.scan_chunks(test_chunks)
    print(f"\nTotal alerts: {len(alerts)}")
    for a in alerts:
        print(f"  [{a.severity.upper()}] {a.alert_type}: {a.headline}")
