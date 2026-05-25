"""
intelligence/trend_detector.py
------------------------------
Data-driven 5-level trend classifier for Qual V3.3.

Combines technical features from features.py with macro regime context
from regime_detector.py to classify each ticker into:
  STRONG_UPTREND → UPTREND → SIDEWAYS → DOWNTREND → STRONG_DOWNTREND

Usage:
    python -m intelligence.trend_detector --ticker AAPL
    python -m intelligence.trend_detector --ticker RELIANCE.NS
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.features import FeatureEngine, TechnicalFeatures

logger = logging.getLogger(__name__)


# ── Trend Classification Schema ──────────────────────────────────────────────

TREND_LEVELS = {
    "STRONG_UPTREND": {
        "label": "Strong Uptrend ▲▲",
        "color": "green",
        "bias": "strongly_bullish",
        "description": "Price above all major MAs, strong momentum, volume confirming",
    },
    "UPTREND": {
        "label": "Uptrend ▲",
        "color": "light_green",
        "bias": "bullish",
        "description": "Price above key MAs, positive momentum, trend intact",
    },
    "SIDEWAYS": {
        "label": "Sideways ●",
        "color": "yellow",
        "bias": "neutral",
        "description": "No clear direction, price oscillating around MAs",
    },
    "DOWNTREND": {
        "label": "Downtrend ▼",
        "color": "orange",
        "bias": "bearish",
        "description": "Price below key MAs, negative momentum",
    },
    "STRONG_DOWNTREND": {
        "label": "Strong Downtrend ▼▼",
        "color": "red",
        "bias": "strongly_bearish",
        "description": "Price below all MAs, oversold, volume selling",
    },
}


@dataclass
class TrendResult:
    """Result of trend classification for a single ticker."""
    ticker: str
    trend: str                          # One of TREND_LEVELS keys
    label: str                          # Human-readable label
    bias: str                           # strongly_bullish → strongly_bearish
    confidence: str                     # HIGH / MEDIUM / LOW
    score: float                        # -1.0 (strong down) to +1.0 (strong up)
    description: str
    signals: List[str]                  # Contributing signals
    data_quality: str                   # GOOD / PARTIAL / INSUFFICIENT
    current_price: Optional[float] = None
    rsi: Optional[float] = None
    macd_histogram: Optional[float] = None


# ── Trend Detector ────────────────────────────────────────────────────────────

class TrendDetector:
    """Rule-based trend classifier using technical features."""

    def __init__(self) -> None:
        self.feature_engine = FeatureEngine()

    def classify(self, ticker: str) -> TrendResult:
        """
        Classify the trend for a given ticker.

        Uses a scoring approach:
          - Each rule contributes a weighted vote (+/-)
          - Final score determines the trend level
        """
        tech = self.feature_engine.compute_technical(ticker)

        # Data quality check
        if tech.data_points < 20:
            return TrendResult(
                ticker=ticker, trend="SIDEWAYS",
                label=TREND_LEVELS["SIDEWAYS"]["label"],
                bias="neutral", confidence="LOW", score=0.0,
                description="Insufficient price data for trend classification",
                signals=["data_insufficient"],
                data_quality="INSUFFICIENT",
            )

        data_quality = "GOOD" if tech.data_points >= 50 else "PARTIAL"
        score = 0.0
        signals: List[str] = []
        max_score = 0.0  # Track maximum possible score for normalization

        # ── Rule 1: Price vs SMA50 (weight: 2.0) ──
        if tech.price_vs_sma50 is not None:
            max_score += 2.0
            if tech.price_vs_sma50 > 3:
                score += 2.0
                signals.append(f"price {tech.price_vs_sma50:+.1f}% above SMA50")
            elif tech.price_vs_sma50 > 0:
                score += 1.0
                signals.append(f"price {tech.price_vs_sma50:+.1f}% above SMA50")
            elif tech.price_vs_sma50 < -3:
                score -= 2.0
                signals.append(f"price {tech.price_vs_sma50:+.1f}% below SMA50")
            else:
                score -= 1.0
                signals.append(f"price {tech.price_vs_sma50:+.1f}% below SMA50")

        # ── Rule 2: Price vs SMA200 (weight: 2.0) ──
        if tech.price_vs_sma200 is not None:
            max_score += 2.0
            if tech.price_vs_sma200 > 5:
                score += 2.0
                signals.append(f"price {tech.price_vs_sma200:+.1f}% above SMA200")
            elif tech.price_vs_sma200 > 0:
                score += 1.0
            elif tech.price_vs_sma200 < -5:
                score -= 2.0
                signals.append(f"price {tech.price_vs_sma200:+.1f}% below SMA200")
            else:
                score -= 1.0

        # ── Rule 3: SMA50 vs SMA200 (Golden/Death Cross) (weight: 1.5) ──
        if tech.sma_50 is not None and tech.sma_200 is not None:
            max_score += 1.5
            if tech.sma_50 > tech.sma_200:
                score += 1.5
                if tech.golden_cross:
                    signals.append("🔥 Golden Cross detected (SMA50 > SMA200)")
            else:
                score -= 1.5
                if tech.death_cross:
                    signals.append("⚠️ Death Cross detected (SMA50 < SMA200)")

        # ── Rule 4: RSI (weight: 1.5) ──
        if tech.rsi_14 is not None:
            max_score += 1.5
            if tech.rsi_14 > 70:
                score += 0.5  # Overbought — bullish but caution
                signals.append(f"RSI {tech.rsi_14:.0f} — overbought")
            elif tech.rsi_14 > 55:
                score += 1.5
                signals.append(f"RSI {tech.rsi_14:.0f} — bullish momentum")
            elif tech.rsi_14 > 45:
                score += 0.0  # Neutral
                signals.append(f"RSI {tech.rsi_14:.0f} — neutral")
            elif tech.rsi_14 > 30:
                score -= 1.5
                signals.append(f"RSI {tech.rsi_14:.0f} — bearish momentum")
            else:
                score -= 0.5  # Oversold — bearish but bounce potential
                signals.append(f"RSI {tech.rsi_14:.0f} — oversold")

        # ── Rule 5: MACD (weight: 1.5) ──
        if tech.macd_histogram is not None:
            max_score += 1.5
            if tech.macd_histogram > 0:
                score += 1.5
                signals.append(f"MACD histogram positive ({tech.macd_histogram:+.4f})")
            else:
                score -= 1.5
                signals.append(f"MACD histogram negative ({tech.macd_histogram:+.4f})")

        # ── Rule 6: Bollinger Band Position (weight: 1.0) ──
        if tech.bb_position is not None:
            max_score += 1.0
            if tech.bb_position > 0.8:
                score += 0.5  # Near upper band, bullish but stretched
                signals.append(f"BB position {tech.bb_position:.2f} — near upper band")
            elif tech.bb_position > 0.5:
                score += 1.0
            elif tech.bb_position > 0.2:
                score -= 1.0
            else:
                score -= 0.5  # Near lower band, bearish but oversold
                signals.append(f"BB position {tech.bb_position:.2f} — near lower band")

        # ── Rule 7: OBV Confirmation (weight: 1.0) ──
        if tech.obv_trend is not None:
            max_score += 1.0
            if tech.obv_trend == "rising":
                score += 1.0
                signals.append("OBV rising — volume confirms trend")
            elif tech.obv_trend == "falling":
                score -= 1.0
                signals.append("OBV falling — volume divergence warning")

        # ── Rule 8: Short-term momentum (5d return) (weight: 0.5) ──
        if tech.return_5d is not None:
            max_score += 0.5
            if tech.return_5d > 2:
                score += 0.5
            elif tech.return_5d < -2:
                score -= 0.5

        # ── Normalize to [-1, +1] ──
        if max_score > 0:
            normalized = score / max_score
        else:
            normalized = 0.0

        normalized = max(-1.0, min(1.0, normalized))

        # ── Map to Trend Level ──
        if normalized >= 0.6:
            trend = "STRONG_UPTREND"
        elif normalized >= 0.2:
            trend = "UPTREND"
        elif normalized <= -0.6:
            trend = "STRONG_DOWNTREND"
        elif normalized <= -0.2:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # Confidence based on data quality and signal agreement
        signal_count = len(signals)
        if data_quality == "GOOD" and signal_count >= 6:
            confidence = "HIGH"
        elif signal_count >= 4:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return TrendResult(
            ticker=ticker,
            trend=trend,
            label=TREND_LEVELS[trend]["label"],
            bias=TREND_LEVELS[trend]["bias"],
            confidence=confidence,
            score=round(normalized, 3),
            description=TREND_LEVELS[trend]["description"],
            signals=signals,
            data_quality=data_quality,
            current_price=tech.current_price,
            rsi=tech.rsi_14,
            macd_histogram=tech.macd_histogram,
        )

    def classify_batch(self, tickers: List[str]) -> List[TrendResult]:
        """Classify trends for multiple tickers."""
        results = []
        for t in tickers:
            try:
                results.append(self.classify(t))
            except Exception as e:
                logger.warning("[TrendDetector] Error classifying %s: %s", t, e)
        return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="V3.3 Trend Detector")
    parser.add_argument("--ticker", type=str, help="Single ticker to classify")
    parser.add_argument("--watchlist", action="store_true", help="Classify US + India watchlist")
    args = parser.parse_args()

    detector = TrendDetector()

    if args.ticker:
        result = detector.classify(args.ticker)
        print(json.dumps(asdict(result), indent=2, default=str))
    elif args.watchlist:
        from ingestion.market_data_feed import US_WATCHLIST, INDIA_STOCKS
        tickers = US_WATCHLIST + INDIA_STOCKS[:10]
        results = detector.classify_batch(tickers)
        print(f"\n{'═'*70}")
        print(f"  {'TICKER':<16} {'TREND':<22} {'SCORE':>6}  {'RSI':>5}  {'CONF':<6} SIGNALS")
        print(f"{'─'*70}")
        for r in results:
            top_signal = r.signals[0] if r.signals else ""
            print(f"  {r.ticker:<16} {r.label:<22} {r.score:>+.3f}  {(r.rsi or 0):>5.0f}  {r.confidence:<6} {top_signal}")
    else:
        result = detector.classify("AAPL")
        print(json.dumps(asdict(result), indent=2, default=str))


if __name__ == "__main__":
    main()
