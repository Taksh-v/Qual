"""
intelligence/signal_scorer.py
-----------------------------
Composite signal scoring for Qual V3.3.

Combines four dimensions into a single 0-1 confidence score:
  - Technical (35%): RSI, MACD, Trend, Moving Averages
  - Sentiment (25%): News sentiment from sentiment_analyzer.py
  - Fundamental (20%): Quality Score, PE Percentile
  - Macro (20%): Regime alignment from regime_detector.py

Output: { "score": 0.73, "label": "BUY", "confidence": "HIGH", "breakdown": {...} }

Usage:
    python -m intelligence.signal_scorer --ticker AAPL
    python -m intelligence.signal_scorer --watchlist
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.features import FeatureEngine
from intelligence.trend_detector import TrendDetector
from intelligence.sentiment_analyzer import sentiment_summary
from intelligence.regime_detector import detect_regime

logger = logging.getLogger(__name__)


# ── Action Labels ─────────────────────────────────────────────────────────────

ACTION_MAP = [
    (0.80, "STRONG_BUY",  "Strong Buy ▲▲",  "High conviction — strong technical + fundamental alignment"),
    (0.65, "BUY",         "Buy ▲",           "Favorable setup — trend, sentiment, and value align"),
    (0.50, "HOLD",        "Hold ●",          "Mixed signals — wait for clearer direction"),
    (0.35, "REDUCE",      "Reduce ▼",        "Deteriorating setup — consider trimming"),
    (0.00, "AVOID",       "Avoid ▼▼",        "Unfavorable across multiple dimensions"),
]


@dataclass
class SignalBreakdown:
    """Detailed breakdown of scoring dimensions."""
    technical_score: float = 0.0
    technical_weight: float = 0.35
    technical_signals: List[str] = field(default_factory=list)

    sentiment_score: float = 0.5
    sentiment_weight: float = 0.25
    sentiment_label: str = "neutral"

    fundamental_score: float = 0.5
    fundamental_weight: float = 0.20
    fundamental_signals: List[str] = field(default_factory=list)

    macro_score: float = 0.5
    macro_weight: float = 0.20
    macro_regime: str = "TRANSITIONAL"


@dataclass
class SignalResult:
    """Final composite signal for a ticker."""
    ticker: str
    score: float                        # 0.0 to 1.0
    action: str                         # STRONG_BUY, BUY, HOLD, REDUCE, AVOID
    label: str                          # Human-readable label
    confidence: str                     # HIGH / MEDIUM / LOW
    description: str
    breakdown: SignalBreakdown = field(default_factory=SignalBreakdown)
    trend: str = "SIDEWAYS"
    current_price: Optional[float] = None


# ── Signal Scorer ─────────────────────────────────────────────────────────────

class SignalScorer:
    """Composite signal scorer combining all analysis dimensions."""

    def __init__(self) -> None:
        self.feature_engine = FeatureEngine()
        self.trend_detector = TrendDetector()

    def _score_technical(self, ticker: str) -> tuple[float, List[str]]:
        """
        Score technical dimension (0-1).

        Components:
          - Trend score (from trend detector): 40% of technical
          - RSI normalized: 20%
          - MACD direction: 20%
          - MA alignment: 20%
        """
        trend_result = self.trend_detector.classify(ticker)
        tech = self.feature_engine.compute_technical(ticker)
        signals: List[str] = []

        # Trend score: map [-1, +1] to [0, 1]
        trend_score = (trend_result.score + 1) / 2  # 0 to 1
        signals.append(f"Trend: {trend_result.label} ({trend_result.score:+.2f})")

        # RSI score: 50 = neutral (0.5), 30 = oversold potential buy (0.6), 70 = overbought (0.4)
        rsi_score = 0.5
        if tech.rsi_14 is not None:
            if tech.rsi_14 >= 80:
                rsi_score = 0.2   # Extreme overbought
            elif tech.rsi_14 >= 70:
                rsi_score = 0.4   # Overbought
            elif tech.rsi_14 >= 55:
                rsi_score = 0.7   # Bullish momentum
            elif tech.rsi_14 >= 45:
                rsi_score = 0.5   # Neutral
            elif tech.rsi_14 >= 30:
                rsi_score = 0.3   # Bearish
            else:
                rsi_score = 0.55  # Oversold — bounce potential
            signals.append(f"RSI: {tech.rsi_14:.0f}")

        # MACD score
        macd_score = 0.5
        if tech.macd_histogram is not None:
            if tech.macd_histogram > 0:
                macd_score = min(0.8, 0.5 + abs(tech.macd_histogram) * 100)
            else:
                macd_score = max(0.2, 0.5 - abs(tech.macd_histogram) * 100)

        # MA alignment score
        ma_score = 0.5
        ma_count = 0
        if tech.price_vs_sma20 is not None:
            ma_count += 1
            if tech.price_vs_sma20 > 0:
                ma_score += 0.15
            else:
                ma_score -= 0.15
        if tech.price_vs_sma50 is not None:
            ma_count += 1
            if tech.price_vs_sma50 > 0:
                ma_score += 0.15
            else:
                ma_score -= 0.15
        if tech.price_vs_sma200 is not None:
            ma_count += 1
            if tech.price_vs_sma200 > 0:
                ma_score += 0.2
            else:
                ma_score -= 0.2
        ma_score = max(0.0, min(1.0, ma_score))

        # Weighted combination
        final = (trend_score * 0.40 + rsi_score * 0.20 + macd_score * 0.20 + ma_score * 0.20)
        return max(0.0, min(1.0, final)), signals

    def _score_sentiment(self, ticker: str) -> tuple[float, str]:
        """
        Score sentiment dimension (0-1).

        Fetches recent news chunks mentioning the ticker and aggregates sentiment.
        Falls back to 0.5 (neutral) if no data.
        """
        try:
            import duckdb
            conn = duckdb.connect()
            chunks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chunks")
            parquet_path = os.path.join(chunks_dir, "news", "**", "*.parquet")

            # Search for news mentioning the ticker (strip .NS, .L etc.)
            clean_ticker = ticker.split(".")[0]
            df = conn.execute(f"""
                SELECT text FROM read_parquet('{parquet_path}')
                WHERE lower(text) LIKE '%{clean_ticker.lower()}%'
                ORDER BY date DESC LIMIT 20
            """).df()

            if df.empty:
                return 0.5, "neutral"

            chunks = [{"text": t} for t in df["text"].tolist()]
            summary = sentiment_summary(chunks)

            # Map avg_score [-1, +1] to [0, 1]
            score = (summary["avg_score"] + 1) / 2
            return max(0.0, min(1.0, score)), summary["overall_label"]

        except Exception as e:
            logger.debug("[SignalScorer] Sentiment error for %s: %s", ticker, e)
            return 0.5, "neutral"

    def _score_fundamental(self, ticker: str) -> tuple[float, List[str]]:
        """
        Score fundamental dimension (0-1).

        Components:
          - Quality Score (50%)
          - PE Percentile (30%) — lower percentile = cheaper = better
          - Momentum Rank (20%)
        """
        fund = self.feature_engine.compute_fundamental(ticker)
        signals: List[str] = []

        quality = fund.quality_score or 0.5
        signals.append(f"Quality: {quality:.2f}")

        # PE — lower percentile is better (cheaper)
        pe_score = 0.5
        if fund.pe_percentile is not None:
            pe_score = 1.0 - (fund.pe_percentile / 100)  # Invert: low PE = high score
            signals.append(f"PE %ile: {fund.pe_percentile:.0f}")

        momentum = fund.momentum_rank or 0.5
        signals.append(f"Momentum rank: {momentum:.2f}")

        final = quality * 0.50 + pe_score * 0.30 + momentum * 0.20
        return max(0.0, min(1.0, final)), signals

    def _score_macro(self) -> tuple[float, str]:
        """
        Score macro dimension (0-1) using regime_detector.

        Regime-to-score mapping:
          GOLDILOCKS: 0.85   — best environment for risk assets
          EARLY_RECOVERY: 0.75
          REFLATION: 0.60
          TRANSITIONAL: 0.50
          LATE_CYCLE: 0.35
          DEFLATION_RISK: 0.30
          STAGFLATION: 0.15
          RECESSION: 0.10
        """
        regime_data = detect_regime()
        regime = regime_data["regime"]

        regime_scores = {
            "GOLDILOCKS": 0.85,
            "EARLY_RECOVERY": 0.75,
            "REFLATION": 0.60,
            "TRANSITIONAL": 0.50,
            "LATE_CYCLE": 0.35,
            "DEFLATION_RISK": 0.30,
            "STAGFLATION": 0.15,
            "RECESSION": 0.10,
        }

        score = regime_scores.get(regime, 0.50)
        return score, regime

    def score(self, ticker: str) -> SignalResult:
        """Compute composite signal score for a ticker."""

        # Compute each dimension
        tech_score, tech_signals = self._score_technical(ticker)
        sent_score, sent_label = self._score_sentiment(ticker)
        fund_score, fund_signals = self._score_fundamental(ticker)
        macro_score, macro_regime = self._score_macro()

        # Build breakdown
        breakdown = SignalBreakdown(
            technical_score=round(tech_score, 3),
            technical_signals=tech_signals,
            sentiment_score=round(sent_score, 3),
            sentiment_label=sent_label,
            fundamental_score=round(fund_score, 3),
            fundamental_signals=fund_signals,
            macro_score=round(macro_score, 3),
            macro_regime=macro_regime,
        )

        # Weighted composite
        composite = (
            tech_score * breakdown.technical_weight +
            sent_score * breakdown.sentiment_weight +
            fund_score * breakdown.fundamental_weight +
            macro_score * breakdown.macro_weight
        )
        composite = round(max(0.0, min(1.0, composite)), 3)

        # Map to action
        action = "AVOID"
        label = "Avoid ▼▼"
        description = "Unfavorable across multiple dimensions"
        for threshold, act, lbl, desc in ACTION_MAP:
            if composite >= threshold:
                action = act
                label = lbl
                description = desc
                break

        # Confidence from signal consistency
        scores = [tech_score, sent_score, fund_score, macro_score]
        variance = sum((s - composite) ** 2 for s in scores) / len(scores)
        if variance < 0.02:
            confidence = "HIGH"
        elif variance < 0.05:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Get trend and price
        trend_result = self.trend_detector.classify(ticker)

        return SignalResult(
            ticker=ticker,
            score=composite,
            action=action,
            label=label,
            confidence=confidence,
            description=description,
            breakdown=breakdown,
            trend=trend_result.trend,
            current_price=trend_result.current_price,
        )

    def score_batch(self, tickers: List[str]) -> List[SignalResult]:
        """Score multiple tickers."""
        results = []
        for t in tickers:
            try:
                results.append(self.score(t))
            except Exception as e:
                logger.warning("[SignalScorer] Error scoring %s: %s", t, e)
        return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="V3.3 Signal Scorer")
    parser.add_argument("--ticker", type=str, help="Single ticker to score")
    parser.add_argument("--watchlist", action="store_true", help="Score US + India watchlist")
    args = parser.parse_args()

    scorer = SignalScorer()

    if args.ticker:
        result = scorer.score(args.ticker)
        print(json.dumps(asdict(result), indent=2, default=str))
    elif args.watchlist:
        from ingestion.market_data_feed import US_WATCHLIST, INDIA_STOCKS
        tickers = US_WATCHLIST + INDIA_STOCKS[:10]
        results = scorer.score_batch(tickers)

        print(f"\n{'═'*80}")
        print(f"  {'TICKER':<16} {'ACTION':<15} {'SCORE':>5}  {'TECH':>5}  {'SENT':>5}  {'FUND':>5}  {'MACRO':>5}  {'CONF':<6}")
        print(f"{'─'*80}")
        for r in results:
            b = r.breakdown
            print(f"  {r.ticker:<16} {r.label:<15} {r.score:>.3f}  "
                  f"{b.technical_score:>.3f}  {b.sentiment_score:>.3f}  "
                  f"{b.fundamental_score:>.3f}  {b.macro_score:>.3f}  {r.confidence:<6}")
        print(f"{'═'*80}")
        print(f"  Macro Regime: {results[0].breakdown.macro_regime if results else 'N/A'}")
    else:
        result = scorer.score("AAPL")
        print(json.dumps(asdict(result), indent=2, default=str))


if __name__ == "__main__":
    main()
