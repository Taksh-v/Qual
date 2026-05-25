"""
ingestion/market_data_feed.py
-----------------------------
OHLCV price data ingestion using yfinance.

Fetches daily OHLCV data for watchlist tickers and major indices,
validates through the MarketData schema, archives raw payloads,
and exports to Parquet via StorageManager.

Usage:
    python -m ingestion.market_data_feed                   # all tickers
    python -m ingestion.market_data_feed --tickers AAPL MSFT  # specific tickers
    python -m ingestion.market_data_feed --period 1mo       # custom period
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Dict

import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.schemas import MarketData
from ingestion.provenance import save_raw_payload
from ingestion.storage_manager import StorageManager

logger = logging.getLogger(__name__)

# ── Ticker Universe ──────────────────────────────────────────────────────────

# ── US Indices & Benchmarks ──
US_INDICES = [
    "^GSPC",   # S&P 500
    "^DJI",    # Dow Jones
    "^IXIC",   # NASDAQ Composite
    "^VIX",    # CBOE Volatility Index
    "^RUT",    # Russell 2000
    "DX-Y.NYB",# US Dollar Index (DXY)
    "^TNX",    # 10-Year Treasury Yield
]

# ── Europe Indices ──
EUROPE_INDICES = [
    "^FTSE",   # FTSE 100 (UK)
    "^GDAXI",  # DAX 40 (Germany)
    "^FCHI",   # CAC 40 (France)
    "^STOXX50E",# Euro Stoxx 50
    "^AEX",    # AEX (Netherlands)
    "^IBEX",   # IBEX 35 (Spain)
    "^SSMI",   # SMI (Switzerland)
    "FTSEMIB.MI",# FTSE MIB (Italy)
]

# ── Asia-Pacific Indices ──
APAC_INDICES = [
    "^N225",   # Nikkei 225 (Japan)
    "^HSI",    # Hang Seng (Hong Kong)
    "000001.SS",# Shanghai Composite (China)
    "399001.SZ",# Shenzhen Component (China)
    "^KS11",   # KOSPI (South Korea)
    "^TWII",   # TAIEX (Taiwan)
    "^AXJO",   # ASX 200 (Australia)
    "^STI",    # STI (Singapore)
    "^JKSE",   # Jakarta Composite (Indonesia)
    "^SET.BK", # SET Index (Thailand)
]

# ── India Indices ──
INDIA_INDICES = [
    "^NSEI",   # NIFTY 50
    "^BSESN",  # BSE SENSEX
    "^NSEBANK",# NIFTY Bank
    "^CNXIT",  # NIFTY IT
    "^CNXFIN", # NIFTY Financial Services
    "^CNXPHARMA",# NIFTY Pharma
    "^CNXAUTO",# NIFTY Auto
    "^CNXMETAL",# NIFTY Metal
    "^CNXREALTY",# NIFTY Realty
    "^CNXENERGY",# NIFTY Energy
]

# ── LatAm & MENA Indices ──
LATAM_MENA_INDICES = [
    "^BVSP",   # Bovespa (Brazil)
    "^MXX",    # IPC (Mexico)
    "^MERV",   # MERVAL (Argentina)
    "^TA125.TA",# TA-125 (Israel)
    "^TASI.SR",# Tadawul (Saudi Arabia)
]

# ── NIFTY 50 Top Constituents ──
INDIA_STOCKS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "WIPRO.NS", "HCLTECH.NS", "ADANIENT.NS",
    "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "TATAMTRDVR.NS",
    "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TATASTEEL.NS", "COALINDIA.NS",
    "DRREDDY.NS", "TECHM.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "JSWSTEEL.NS",
]

# ── US Core Watchlist ──
US_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META",
    "BRK-B", "JPM", "V", "JNJ", "UNH", "XOM", "PG", "MA",
]

# ── Europe Blue-Chips ──
EUROPE_STOCKS = [
    "NESN.SW",  # Nestle (Switzerland)
    "ROG.SW",   # Roche (Switzerland)
    "NOVN.SW",  # Novartis (Switzerland)
    "ASML.AS",  # ASML (Netherlands)
    "MC.PA",    # LVMH (France)
    "SAP.DE",   # SAP (Germany)
    "SIE.DE",   # Siemens (Germany)
    "AZN.L",    # AstraZeneca (UK)
    "SHEL.L",   # Shell (UK)
    "ULVR.L",   # Unilever (UK)
    "TTE.PA",   # TotalEnergies (France)
    "OR.PA",    # L'Oreal (France)
    "BAS.DE",   # BASF (Germany)
    "ALV.DE",   # Allianz (Germany)
    "HSBA.L",   # HSBC (UK)
]

# ── Asia-Pacific Blue-Chips ──
APAC_STOCKS = [
    "7203.T",   # Toyota (Japan)
    "6758.T",   # Sony (Japan)
    "9984.T",   # SoftBank (Japan)
    "6861.T",   # Keyence (Japan)
    "9433.T",   # KDDI (Japan)
    "0700.HK",  # Tencent (Hong Kong)
    "9988.HK",  # Alibaba (Hong Kong)
    "1299.HK",  # AIA Group (Hong Kong)
    "005930.KS",# Samsung (South Korea)
    "2330.TW",  # TSMC (Taiwan)
    "BHP.AX",   # BHP Group (Australia)
    "CBA.AX",   # Commonwealth Bank (Australia)
    "D05.SI",   # DBS Group (Singapore)
]

# ── LatAm/MENA Blue-Chips ──
LATAM_STOCKS = [
    "VALE3.SA", # Vale (Brazil)
    "PETR4.SA", # Petrobras (Brazil)
    "ITUB4.SA", # Itau Unibanco (Brazil)
    "AMXL.MX",  # America Movil (Mexico)
    "2222.SR",  # Saudi Aramco (Saudi Arabia)
]

# ── FX Major Pairs ──
FX_PAIRS = [
    "EURUSD=X",  # EUR/USD
    "GBPUSD=X",  # GBP/USD
    "USDJPY=X",  # USD/JPY
    "USDCNH=X",  # USD/CNH (Offshore Yuan)
    "AUDUSD=X",  # AUD/USD
    "USDCHF=X",  # USD/CHF
    "USDCAD=X",  # USD/CAD
    "USDINR=X",  # USD/INR
    "USDBRL=X",  # USD/BRL
    "USDMXN=X",  # USD/MXN
    "USDKRW=X",  # USD/KRW
    "USDSGD=X",  # USD/SGD
]

# ── Commodities & Futures ──
COMMODITIES = [
    "GC=F",     # Gold Futures
    "SI=F",     # Silver Futures
    "CL=F",     # Crude Oil WTI
    "BZ=F",     # Brent Crude
    "NG=F",     # Natural Gas
    "HG=F",     # Copper
    "ZW=F",     # Wheat
    "ZC=F",     # Corn
    "ZS=F",     # Soybeans
    "CT=F",     # Cotton
]

# ── Sector & Country ETFs ──
SECTOR_ETFS = [
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE",
    "GLD", "USO", "TLT",
]
COUNTRY_ETFS = [
    "INDA",  # India
    "EWJ",   # Japan
    "FXI",   # China Large-Cap
    "EWG",   # Germany
    "EWU",   # UK
    "EWZ",   # Brazil
    "EWY",   # South Korea
    "EWT",   # Taiwan
    "EWA",   # Australia
    "EWC",   # Canada
    "EWQ",   # France
    "VWO",   # Emerging Markets
    "VEA",   # Developed Int'l
    "IEMG",  # Emerging Markets (Core)
]

ALL_TICKERS = (
    US_INDICES + EUROPE_INDICES + APAC_INDICES + INDIA_INDICES + LATAM_MENA_INDICES +
    INDIA_STOCKS + US_WATCHLIST + EUROPE_STOCKS + APAC_STOCKS + LATAM_STOCKS +
    FX_PAIRS + COMMODITIES + SECTOR_ETFS + COUNTRY_ETFS
)


# ── Market Data Feed ─────────────────────────────────────────────────────────

class MarketDataFeed:
    """Fetches and stores OHLCV price data from yfinance."""

    def __init__(self) -> None:
        self.storage = StorageManager()

    def _process_ticker(
        self,
        ticker: str,
        df: pd.DataFrame,
        interval: str,
        period: str,
    ) -> List[Dict[str, Any]]:
        """Process a single ticker DataFrame into validated MarketData records."""
        records: List[Dict[str, Any]] = []
        df = df.dropna(subset=["Close"])
        if df.empty:
            return records

        raw_payload = {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "rows": len(df),
            "date_range": f"{df.index[0].isoformat()} to {df.index[-1].isoformat()}",
        }
        provenance_id = save_raw_payload(
            raw_payload, source="yfinance", data_type=f"ohlcv_{ticker}"
        )

        for idx, row in df.iterrows():
            try:
                record = MarketData(
                    ticker=ticker,
                    date=idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                    open=float(row.get("Open", 0)),
                    high=float(row.get("High", 0)),
                    low=float(row.get("Low", 0)),
                    close=float(row.get("Close", 0)),
                    volume=int(row.get("Volume", 0)) if pd.notna(row.get("Volume")) else 0,
                    interval=interval,
                )
                rec_dict = record.model_dump()
                rec_dict["provenance_id"] = provenance_id
                rec_dict["data_type"] = "market"
                rec_dict["source"] = "yfinance"
                records.append(rec_dict)
            except Exception as e:
                logger.debug("[MarketData] Schema error for %s/%s: %s", ticker, idx, e)

        return records

    def fetch_ohlcv(
        self,
        tickers: List[str] | None = None,
        period: str = "3mo",
        interval: str = "1d",
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV data for the given tickers.

        Uses batch download first, then retries failed tickers individually
        (handles .NS suffixed tickers that fail in batch mode).
        """
        tickers = tickers or ALL_TICKERS
        all_records: List[Dict[str, Any]] = []
        failed: List[str] = []

        logger.info("[MarketData] Fetching %d tickers (period=%s, interval=%s)...",
                    len(tickers), period, interval)

        # ── Phase 1: Batch download ──
        try:
            data = yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:
            logger.error("[MarketData] Batch download failed: %s", exc)
            data = pd.DataFrame()

        for ticker in tickers:
            try:
                if data.empty:
                    failed.append(ticker)
                    continue

                if len(tickers) == 1:
                    df = data.copy()
                else:
                    if ticker not in data.columns.get_level_values(0):
                        failed.append(ticker)
                        continue
                    df = data[ticker].copy()

                records = self._process_ticker(ticker, df, interval, period)
                if records:
                    all_records.extend(records)
                else:
                    failed.append(ticker)
            except Exception as exc:
                logger.debug("[MarketData] Batch error for %s: %s", ticker, exc)
                failed.append(ticker)

        # ── Phase 2: Individual fallback for failed tickers ──
        if failed:
            logger.info("[MarketData] Retrying %d failed tickers individually...", len(failed))
            still_failed: List[str] = []
            for ticker in failed:
                try:
                    t = yf.Ticker(ticker)
                    df = t.history(period=period, interval=interval, auto_adjust=True)
                    if df.empty:
                        still_failed.append(ticker)
                        continue
                    records = self._process_ticker(ticker, df, interval, period)
                    if records:
                        all_records.extend(records)
                        logger.info("[MarketData] ✅ Recovered %s (%d records)", ticker, len(records))
                    else:
                        still_failed.append(ticker)
                except Exception as exc:
                    logger.warning("[MarketData] Individual fetch failed for %s: %s", ticker, exc)
                    still_failed.append(ticker)
            failed = still_failed

        # ── Export ──
        if all_records:
            self.storage.export_to_parquet(all_records, data_type="market")
            logger.info("[MarketData] ✅ Exported %d records for %d tickers to Parquet",
                        len(all_records), len(tickers) - len(failed))

        if failed:
            logger.warning("[MarketData] ⚠ Failed tickers (%d): %s", len(failed), ", ".join(failed))

        return all_records


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="OHLCV Market Data Feed")
    parser.add_argument("--tickers", nargs="+", default=None, help="Specific tickers to fetch")
    parser.add_argument("--period", default="3mo", help="yfinance period (default: 3mo)")
    parser.add_argument("--interval", default="1d", help="Data interval (default: 1d)")
    args = parser.parse_args()

    feed = MarketDataFeed()
    records = feed.fetch_ohlcv(tickers=args.tickers, period=args.period, interval=args.interval)
    logger.info("[MarketData] Total records: %d", len(records))


if __name__ == "__main__":
    main()
