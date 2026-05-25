"""
intelligence/features.py
------------------------
Technical & fundamental feature engineering for Qual V3.3.

Computes quantitative indicators from OHLCV and fundamentals Parquet data:
  - Technical: RSI, SMA/EMA, MACD, Bollinger Bands, ATR, OBV, Returns, Drawdown
  - Fundamental: PE Percentile, Quality Score, Momentum Rank

All computations use DuckDB for fast columnar reads and pandas/numpy for calculations.

Usage:
    python -m intelligence.features --ticker AAPL
    python -m intelligence.features --ticker RELIANCE.NS
    python -m intelligence.features --all
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_DIR = os.path.join(BASE_DIR, "data", "chunks")


# ── Feature Output Schema ────────────────────────────────────────────────────

@dataclass
class TechnicalFeatures:
    """Computed technical indicators for a single ticker."""
    ticker: str
    date: str                          # Latest date in dataset
    data_points: int = 0               # Number of OHLCV rows used

    # Price moving averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None

    # Price position relative to MAs
    price_vs_sma20: Optional[float] = None   # % above/below
    price_vs_sma50: Optional[float] = None
    price_vs_sma200: Optional[float] = None

    # Momentum
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None

    # Volatility
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None         # (upper - lower) / sma20
    bb_position: Optional[float] = None      # 0 = at lower, 1 = at upper
    atr_14: Optional[float] = None
    atr_pct: Optional[float] = None          # ATR as % of price
    volatility_20d: Optional[float] = None   # 20-day rolling stdev of returns

    # Volume
    obv_trend: Optional[str] = None          # "rising", "falling", "flat"
    volume_sma_ratio: Optional[float] = None # current vol / 20d avg vol

    # Returns
    return_1d: Optional[float] = None
    return_5d: Optional[float] = None
    return_20d: Optional[float] = None
    return_60d: Optional[float] = None

    # Risk
    max_drawdown_60d: Optional[float] = None
    current_drawdown: Optional[float] = None

    # Cross signals
    golden_cross: Optional[bool] = None      # SMA50 > SMA200 (recently crossed)
    death_cross: Optional[bool] = None       # SMA50 < SMA200 (recently crossed)
    current_price: Optional[float] = None


@dataclass
class FundamentalFeatures:
    """Computed fundamental features for a single ticker."""
    ticker: str
    pe_percentile: Optional[float] = None    # 0-100 within sector
    quality_score: Optional[float] = None    # 0-1 composite
    momentum_rank: Optional[float] = None    # 0-1 (1 = best)
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    profit_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    debt_to_equity: Optional[float] = None


# ── Feature Engine ────────────────────────────────────────────────────────────

class FeatureEngine:
    """Computes technical and fundamental features from V3 Parquet storage."""

    def __init__(self) -> None:
        self.conn = duckdb.connect()

    def _load_ohlcv(self, ticker: str) -> pd.DataFrame:
        """Load OHLCV data for a ticker from Parquet."""
        parquet_path = os.path.join(CHUNKS_DIR, "market", "**", "*.parquet")
        try:
            df = self.conn.execute(f"""
                SELECT date, open, high, low, close, volume
                FROM read_parquet('{parquet_path}')
                WHERE ticker = '{ticker}'
                ORDER BY date ASC
            """).df()
            return df
        except Exception as e:
            logger.warning("[Features] Error loading OHLCV for %s: %s", ticker, e)
            return pd.DataFrame()

    def _load_fundamentals(self, ticker: str) -> dict:
        """Load latest fundamentals for a ticker."""
        parquet_path = os.path.join(CHUNKS_DIR, "fundamentals", "**", "*.parquet")
        try:
            df = self.conn.execute(f"""
                SELECT * FROM read_parquet('{parquet_path}')
                WHERE ticker = '{ticker}'
                ORDER BY date DESC LIMIT 1
            """).df()
            if df.empty:
                return {}
            return df.iloc[0].to_dict()
        except Exception:
            return {}

    def _load_all_fundamentals(self) -> pd.DataFrame:
        """Load all fundamentals for sector-relative calculations."""
        parquet_path = os.path.join(CHUNKS_DIR, "fundamentals", "**", "*.parquet")
        try:
            return self.conn.execute(f"""
                SELECT ticker, sector, pe_ratio, profit_margin, return_on_equity,
                       debt_to_equity, market_cap, current_price
                FROM read_parquet('{parquet_path}')
            """).df()
        except Exception:
            return pd.DataFrame()

    # ── Technical Indicators ─────────────────────────────────────────────────

    @staticmethod
    def _compute_rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
        """Compute RSI (Relative Strength Index)."""
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        # Use Wilder's smoothing after initial average
        for i in range(period, len(closes)):
            avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        # Where avg_loss was 0 (now NaN), the RSI is mathematically 100
        rsi = rsi.fillna(100)
        
        val = rsi.iloc[-1]
        return round(float(val), 2) if pd.notna(val) else None

    @staticmethod
    def _compute_ema(series: pd.Series, span: int) -> pd.Series:
        """Compute Exponential Moving Average."""
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Optional[float]:
        """Compute Average True Range."""
        if len(close) < period + 1:
            return None
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        val = atr.iloc[-1]
        return round(float(val), 4) if pd.notna(val) else None

    @staticmethod
    def _compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Compute On-Balance Volume."""
        direction = np.sign(close.diff()).fillna(0)
        return (direction * volume).cumsum()

    def compute_technical(self, ticker: str) -> TechnicalFeatures:
        """Compute all technical indicators for a ticker."""
        df = self._load_ohlcv(ticker)
        features = TechnicalFeatures(ticker=ticker, date="", data_points=len(df))

        if df.empty or len(df) < 20:
            logger.warning("[Features] Insufficient data for %s (%d rows)", ticker, len(df))
            return features

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)

        features.date = str(df["date"].iloc[-1])
        features.current_price = round(float(close.iloc[-1]), 2)
        features.data_points = len(df)

        # ── Moving Averages ──
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        ema12 = self._compute_ema(close, 12)
        ema26 = self._compute_ema(close, 26)

        features.sma_20 = round(float(sma20.iloc[-1]), 2) if pd.notna(sma20.iloc[-1]) else None
        features.sma_50 = round(float(sma50.iloc[-1]), 2) if pd.notna(sma50.iloc[-1]) else None
        features.sma_200 = round(float(sma200.iloc[-1]), 2) if pd.notna(sma200.iloc[-1]) else None
        features.ema_12 = round(float(ema12.iloc[-1]), 2) if pd.notna(ema12.iloc[-1]) else None
        features.ema_26 = round(float(ema26.iloc[-1]), 2) if pd.notna(ema26.iloc[-1]) else None

        # Price vs MAs (%)
        price = close.iloc[-1]
        if features.sma_20:
            features.price_vs_sma20 = round((price / features.sma_20 - 1) * 100, 2)
        if features.sma_50:
            features.price_vs_sma50 = round((price / features.sma_50 - 1) * 100, 2)
        if features.sma_200:
            features.price_vs_sma200 = round((price / features.sma_200 - 1) * 100, 2)

        # ── RSI ──
        features.rsi_14 = self._compute_rsi(close, 14)

        # ── MACD ──
        macd_line = ema12 - ema26
        macd_signal = self._compute_ema(macd_line, 9)
        features.macd = round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None
        features.macd_signal = round(float(macd_signal.iloc[-1]), 4) if pd.notna(macd_signal.iloc[-1]) else None
        if features.macd is not None and features.macd_signal is not None:
            features.macd_histogram = round(features.macd - features.macd_signal, 4)

        # ── Bollinger Bands ──
        if features.sma_20:
            std20 = close.rolling(20).std()
            s = float(std20.iloc[-1]) if pd.notna(std20.iloc[-1]) else 0
            features.bb_upper = round(features.sma_20 + 2 * s, 2)
            features.bb_lower = round(features.sma_20 - 2 * s, 2)
            if features.sma_20 > 0:
                features.bb_width = round((features.bb_upper - features.bb_lower) / features.sma_20, 4)
            if features.bb_upper != features.bb_lower:
                features.bb_position = round(
                    (price - features.bb_lower) / (features.bb_upper - features.bb_lower), 4
                )

        # ── ATR ──
        features.atr_14 = self._compute_atr(high, low, close, 14)
        if features.atr_14 and price > 0:
            features.atr_pct = round(features.atr_14 / price * 100, 2)

        # ── Volatility ──
        returns = close.pct_change()
        vol20 = returns.rolling(20).std()
        features.volatility_20d = round(float(vol20.iloc[-1]) * 100, 2) if pd.notna(vol20.iloc[-1]) else None

        # ── OBV ──
        obv = self._compute_obv(close, volume)
        if len(obv) >= 20:
            obv_sma = obv.rolling(20).mean()
            if pd.notna(obv.iloc[-1]) and pd.notna(obv_sma.iloc[-1]):
                ratio = obv.iloc[-1] / obv_sma.iloc[-1] if obv_sma.iloc[-1] != 0 else 1
                features.obv_trend = "rising" if ratio > 1.02 else ("falling" if ratio < 0.98 else "flat")

        # Volume vs 20d average
        vol_sma = volume.rolling(20).mean()
        if pd.notna(vol_sma.iloc[-1]) and vol_sma.iloc[-1] > 0:
            features.volume_sma_ratio = round(float(volume.iloc[-1] / vol_sma.iloc[-1]), 2)

        # ── Returns ──
        if len(close) >= 2:
            features.return_1d = round(float(returns.iloc[-1]) * 100, 2) if pd.notna(returns.iloc[-1]) else None
        if len(close) >= 6:
            features.return_5d = round((price / close.iloc[-6] - 1) * 100, 2)
        if len(close) >= 21:
            features.return_20d = round((price / close.iloc[-21] - 1) * 100, 2)
        if len(close) >= 61:
            features.return_60d = round((price / close.iloc[-61] - 1) * 100, 2)

        # ── Drawdown ──
        peak_60d = close.iloc[-min(61, len(close)):].cummax()
        dd_series = (close.iloc[-min(61, len(close)):] - peak_60d) / peak_60d
        features.max_drawdown_60d = round(float(dd_series.min()) * 100, 2) if len(dd_series) > 0 else None

        all_time_peak = close.cummax()
        features.current_drawdown = round(float((price - all_time_peak.iloc[-1]) / all_time_peak.iloc[-1]) * 100, 2)

        # ── Cross Signals ──
        if features.sma_50 and features.sma_200 and len(sma50) >= 5 and len(sma200) >= 5:
            prev_50 = sma50.iloc[-5] if pd.notna(sma50.iloc[-5]) else None
            prev_200 = sma200.iloc[-5] if pd.notna(sma200.iloc[-5]) else None
            if prev_50 and prev_200:
                was_below = prev_50 < prev_200
                now_above = features.sma_50 > features.sma_200
                features.golden_cross = was_below and now_above
                features.death_cross = (not was_below) and (not now_above) and (prev_50 > prev_200)

        return features

    # ── Fundamental Features ─────────────────────────────────────────────────

    def compute_fundamental(self, ticker: str) -> FundamentalFeatures:
        """Compute fundamental features with sector-relative rankings."""
        fund = self._load_fundamentals(ticker)
        features = FundamentalFeatures(ticker=ticker)

        if not fund:
            return features

        features.sector = fund.get("sector", "Unknown")
        features.market_cap = fund.get("market_cap")
        features.pe_ratio = fund.get("pe_ratio")
        features.profit_margin = fund.get("profit_margin")
        features.return_on_equity = fund.get("return_on_equity")
        features.debt_to_equity = fund.get("debt_to_equity")

        # Load all fundamentals for relative ranking
        all_fund = self._load_all_fundamentals()
        if all_fund.empty:
            return features

        # PE Percentile (within sector)
        sector = features.sector
        sector_df = all_fund[all_fund["sector"] == sector] if sector != "Unknown" else all_fund
        if not sector_df.empty and features.pe_ratio and features.pe_ratio > 0:
            valid_pe = sector_df["pe_ratio"].dropna()
            valid_pe = valid_pe[valid_pe > 0]
            if len(valid_pe) > 1:
                features.pe_percentile = round(
                    float((valid_pe < features.pe_ratio).sum() / len(valid_pe)) * 100, 1
                )

        # Quality Score: normalize(ROE) * normalize(Margin) * (1 - normalize(D/E))
        roe = features.return_on_equity or 0
        margin = features.profit_margin or 0
        de = features.debt_to_equity or 0

        # Clamp and normalize to 0-1
        roe_score = max(0, min(1, roe / 0.30))           # 30% ROE = perfect
        margin_score = max(0, min(1, margin / 0.25))     # 25% margin = perfect
        de_score = max(0, min(1, 1 - (de / 200)))        # 0 D/E = perfect, 200+ = 0

        features.quality_score = round((roe_score * 0.4 + margin_score * 0.4 + de_score * 0.2), 3)

        # Momentum Rank (60d return rank in universe)
        # This requires OHLCV data, compute from returns
        try:
            all_returns = self.conn.execute(f"""
                WITH latest AS (
                    SELECT ticker, close, date,
                           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                    FROM read_parquet('{CHUNKS_DIR}/market/**/*.parquet')
                ),
                current AS (SELECT ticker, close FROM latest WHERE rn = 1),
                past AS (SELECT ticker, close FROM latest WHERE rn = 60)
                SELECT c.ticker, (c.close / p.close - 1) as ret_60d
                FROM current c JOIN past p ON c.ticker = p.ticker
                WHERE p.close > 0
                ORDER BY ret_60d DESC
            """).df()
            if not all_returns.empty:
                total = len(all_returns)
                rank = all_returns[all_returns["ticker"] == ticker].index
                if len(rank) > 0:
                    features.momentum_rank = round(1 - (rank[0] / total), 3)
        except Exception:
            pass

        return features

    def compute_all(self, ticker: str) -> Dict[str, Any]:
        """Compute both technical and fundamental features."""
        tech = self.compute_technical(ticker)
        fund = self.compute_fundamental(ticker)
        return {
            "ticker": ticker,
            "technical": asdict(tech),
            "fundamental": asdict(fund),
        }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="V3.3 Feature Engineering")
    parser.add_argument("--ticker", type=str, help="Specific ticker to analyze")
    parser.add_argument("--all", action="store_true", help="Compute for all watchlist tickers")
    args = parser.parse_args()

    engine = FeatureEngine()

    if args.ticker:
        result = engine.compute_all(args.ticker)
        print(json.dumps(result, indent=2, default=str))
    elif args.all:
        from ingestion.market_data_feed import US_WATCHLIST, INDIA_STOCKS
        for t in US_WATCHLIST[:5] + INDIA_STOCKS[:5]:
            result = engine.compute_all(t)
            tech = result["technical"]
            fund = result["fundamental"]
            print(f"\n{'═'*50}")
            print(f"  {t} | Price: {tech.get('current_price')} | RSI: {tech.get('rsi_14')} | MACD: {tech.get('macd')}")
            print(f"  SMA20: {tech.get('price_vs_sma20')}% | SMA50: {tech.get('price_vs_sma50')}% | Vol: {tech.get('volatility_20d')}%")
            print(f"  Returns: 1d={tech.get('return_1d')}% 5d={tech.get('return_5d')}% 20d={tech.get('return_20d')}%")
            print(f"  Quality: {fund.get('quality_score')} | PE%ile: {fund.get('pe_percentile')} | Momentum: {fund.get('momentum_rank')}")
    else:
        # Default: show AAPL
        result = engine.compute_all("AAPL")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
