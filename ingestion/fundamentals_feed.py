"""
ingestion/fundamentals_feed.py
------------------------------
Company fundamentals ingestion using yfinance.

Fetches P/E, P/B, EPS, Revenue, Margins, Debt/Equity and other
key ratios for watchlist tickers. Validates through the FundamentalData
schema and exports to Parquet.

Usage:
    python -m ingestion.fundamentals_feed
    python -m ingestion.fundamentals_feed --tickers AAPL MSFT GOOGL
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Dict, Optional

import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.schemas import FundamentalData, FinancialRatios
from ingestion.provenance import save_raw_payload
from ingestion.storage_manager import StorageManager

logger = logging.getLogger(__name__)

# Core tickers to track fundamentals for
FUNDAMENTAL_TICKERS_US = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META",
    "BRK-B", "JPM", "V", "JNJ", "UNH", "XOM", "PG", "MA",
    "NFLX", "CRM", "AVGO", "COST", "WMT", "HD", "DIS",
    "BAC", "GS", "INTC", "AMD", "PYPL", "ADBE", "CSCO", "PEP",
]

# India blue-chip fundamentals
FUNDAMENTAL_TICKERS_INDIA = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "WIPRO.NS", "HCLTECH.NS", "BAJFINANCE.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "TATAMTRDVR.NS", "ADANIENT.NS",
    "ONGC.NS", "NTPC.NS", "TATASTEEL.NS", "DRREDDY.NS", "NESTLEIND.NS",
]

# Europe blue-chip fundamentals
FUNDAMENTAL_TICKERS_EUROPE = [
    "NESN.SW", "ROG.SW", "NOVN.SW", "ASML.AS", "MC.PA",
    "SAP.DE", "SIE.DE", "AZN.L", "SHEL.L", "ULVR.L",
    "TTE.PA", "OR.PA", "HSBA.L", "ALV.DE", "BAS.DE",
]

# Asia-Pacific blue-chip fundamentals
FUNDAMENTAL_TICKERS_APAC = [
    "7203.T", "6758.T", "9984.T",       # Japan
    "0700.HK", "9988.HK", "1299.HK",    # Hong Kong
    "005930.KS", "2330.TW",              # Korea, Taiwan
    "BHP.AX", "CBA.AX", "D05.SI",       # Australia, Singapore
]

# LatAm blue-chip fundamentals
FUNDAMENTAL_TICKERS_LATAM = [
    "VALE3.SA", "PETR4.SA", "ITUB4.SA", # Brazil
    "2222.SR",                            # Saudi Arabia
]

FUNDAMENTAL_TICKERS = (
    FUNDAMENTAL_TICKERS_US + FUNDAMENTAL_TICKERS_INDIA +
    FUNDAMENTAL_TICKERS_EUROPE + FUNDAMENTAL_TICKERS_APAC + FUNDAMENTAL_TICKERS_LATAM
)


class FundamentalsFeed:
    """Fetches and stores company fundamentals from yfinance."""

    def __init__(self) -> None:
        self.storage = StorageManager()

    def _safe_get(self, info: dict, key: str, default: Any = None) -> Any:
        """Safely extract a value from yfinance info dict."""
        val = info.get(key, default)
        if val is None or val == "Infinity" or val == "NaN":
            return default
        try:
            return float(val) if isinstance(val, (int, float, str)) and val != "" else default
        except (ValueError, TypeError):
            return default

    def fetch_fundamentals(
        self,
        tickers: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch fundamental data for the given tickers.

        Args:
            tickers: List of ticker symbols. Defaults to FUNDAMENTAL_TICKERS.

        Returns:
            List of validated FundamentalData dicts.
        """
        tickers = tickers or FUNDAMENTAL_TICKERS
        all_records: List[Dict[str, Any]] = []
        failed: List[str] = []
        now = datetime.now(timezone.utc).isoformat()

        logger.info("[Fundamentals] Fetching fundamentals for %d tickers...", len(tickers))

        for ticker_sym in tickers:
            try:
                ticker = yf.Ticker(ticker_sym)
                info = ticker.info or {}

                if not info or info.get("regularMarketPrice") is None:
                    logger.warning("[Fundamentals] No data for %s", ticker_sym)
                    failed.append(ticker_sym)
                    continue

                # Archive raw payload
                # Filter out non-serializable fields
                safe_info = {}
                for k, v in info.items():
                    try:
                        import json
                        json.dumps(v)
                        safe_info[k] = v
                    except (TypeError, ValueError):
                        safe_info[k] = str(v)

                provenance_id = save_raw_payload(
                    safe_info, source="yfinance", data_type=f"fundamentals_{ticker_sym}"
                )

                # Build financial ratios
                ratios = FinancialRatios(
                    pe_ratio=self._safe_get(info, "trailingPE"),
                    pb_ratio=self._safe_get(info, "priceToBook"),
                    debt_to_equity=self._safe_get(info, "debtToEquity"),
                    profit_margin=self._safe_get(info, "profitMargins"),
                    revenue_growth=self._safe_get(info, "revenueGrowth"),
                )

                # Build earnings date string
                earnings_dates = info.get("earningsTimestamp")
                earnings_date_str = None
                if earnings_dates:
                    try:
                        earnings_date_str = datetime.fromtimestamp(
                            earnings_dates, tz=timezone.utc
                        ).isoformat()
                    except Exception:
                        pass

                # Validate through schema
                fundamental = FundamentalData(
                    ticker=ticker_sym,
                    date=now,
                    ratios=ratios,
                    earnings_date=earnings_date_str,
                    dividend_yield=self._safe_get(info, "dividendYield"),
                )

                rec = fundamental.model_dump()
                # Flatten ratios for Parquet compatibility
                ratio_data = rec.pop("ratios", {})
                rec.update(ratio_data)
                rec["provenance_id"] = provenance_id
                rec["data_type"] = "fundamentals"
                rec["source"] = "yfinance"

                # Add extra fields not in schema but valuable
                rec["market_cap"] = self._safe_get(info, "marketCap")
                rec["enterprise_value"] = self._safe_get(info, "enterpriseValue")
                rec["forward_pe"] = self._safe_get(info, "forwardPE")
                rec["peg_ratio"] = self._safe_get(info, "pegRatio")
                rec["ev_to_ebitda"] = self._safe_get(info, "enterpriseToEbitda")
                rec["ev_to_revenue"] = self._safe_get(info, "enterpriseToRevenue")
                rec["return_on_equity"] = self._safe_get(info, "returnOnEquity")
                rec["return_on_assets"] = self._safe_get(info, "returnOnAssets")
                rec["operating_margin"] = self._safe_get(info, "operatingMargins")
                rec["gross_margin"] = self._safe_get(info, "grossMargins")
                rec["revenue"] = self._safe_get(info, "totalRevenue")
                rec["net_income"] = self._safe_get(info, "netIncomeToCommon")
                rec["free_cash_flow"] = self._safe_get(info, "freeCashflow")
                rec["total_debt"] = self._safe_get(info, "totalDebt")
                rec["total_cash"] = self._safe_get(info, "totalCash")
                rec["current_ratio"] = self._safe_get(info, "currentRatio")
                rec["beta"] = self._safe_get(info, "beta")
                rec["fifty_two_week_high"] = self._safe_get(info, "fiftyTwoWeekHigh")
                rec["fifty_two_week_low"] = self._safe_get(info, "fiftyTwoWeekLow")
                rec["current_price"] = self._safe_get(info, "regularMarketPrice")
                rec["sector"] = info.get("sector", "Unknown")
                rec["industry"] = info.get("industry", "Unknown")
                rec["company_name"] = info.get("longName", ticker_sym)

                all_records.append(rec)
                logger.info("[Fundamentals] ✅ %s: P/E=%.1f, P/B=%.1f, Margin=%.1f%%",
                            ticker_sym,
                            ratios.pe_ratio or 0,
                            ratios.pb_ratio or 0,
                            (ratios.profit_margin or 0) * 100)

            except Exception as exc:
                logger.warning("[Fundamentals] Error fetching %s: %s", ticker_sym, exc)
                failed.append(ticker_sym)

        # Export to Parquet in one consolidated write
        if all_records:
            self.storage.export_to_parquet(all_records, data_type="fundamentals")
            logger.info("[Fundamentals] ✅ Exported %d records to Parquet", len(all_records))

        if failed:
            logger.warning("[Fundamentals] ⚠ Failed tickers (%d): %s",
                           len(failed), ", ".join(failed))

        logger.info("[Fundamentals] Complete: %d succeeded, %d failed",
                    len(all_records), len(failed))
        return all_records


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Fundamentals Data Feed")
    parser.add_argument("--tickers", nargs="+", default=None, help="Specific tickers")
    args = parser.parse_args()

    feed = FundamentalsFeed()
    feed.fetch_fundamentals(tickers=args.tickers)


if __name__ == "__main__":
    main()
