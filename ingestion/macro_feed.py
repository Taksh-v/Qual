import os
import requests
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from ingestion.schemas import TextPayload, SentimentAnalysis
from ingestion.provenance import save_raw_payload
from ingestion.storage_manager import StorageManager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Key Macro Series IDs — expanded for comprehensive coverage
SERIES_IDS = {
    # ── Interest Rates & Monetary Policy ──
    "FEDFUNDS":   "Federal Funds Effective Rate",
    "DFF":        "Federal Funds Rate (Daily)",
    "DGS10":      "10-Year Treasury Yield",
    "DGS2":       "2-Year Treasury Yield",
    "T10Y2Y":     "10Y-2Y Treasury Spread (Yield Curve)",

    # ── Inflation ──
    "CPIAUCSL":   "Consumer Price Index (CPI)",
    "CPILFESL":   "Core CPI (Ex Food & Energy)",
    "PCE":        "Personal Consumption Expenditures",
    "PCEPI":      "PCE Price Index",

    # ── Employment ──
    "UNRATE":     "Civilian Unemployment Rate",
    "PAYEMS":     "Total Nonfarm Payrolls",
    "ICSA":       "Initial Jobless Claims (Weekly)",

    # ── Output & Growth ──
    "GDP":        "Gross Domestic Product",
    "INDPRO":     "Industrial Production Index",
    "RSAFS":      "Retail Sales (Total)",

    # ── Housing ──
    "HOUST":      "Housing Starts",
    "CSUSHPISA":  "Case-Shiller Home Price Index",

    # ── Manufacturing ──
    "MANEMP":     "Manufacturing Employment",

    # ── Money Supply ──
    "M2SL":       "M2 Money Supply",
}

class MacroFeed:
    def __init__(self):
        self.storage = StorageManager()

    def fetch_series(self, series_id: str, label: str) -> List[Dict[str, Any]]:
        """Fetch latest observations for a FRED series."""
        if not FRED_API_KEY:
            logger.error("FRED_API_KEY not found in .env")
            return []

        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10
        }

        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            observations = data.get("observations", [])
            
            # Save raw payload for provenance
            provenance_id = save_raw_payload(data, source="FRED", data_type=f"macro_{series_id}")
            
            processed_data = []
            for obs in observations:
                val = obs.get("value")
                if val == ".": continue # Handle missing data
                
                date = obs.get("date")
                # Create a pseudo-text payload for the RAG system to consume
                text_content = f"Macro Indicator: {label} ({series_id}). Value: {val} for date {date}."
                
                payload = TextPayload(
                    source="FRED",
                    title=f"{label} Update",
                    raw_text=text_content,
                    date=date,
                    data_type="macro",
                    provenance_id=provenance_id,
                    entities={"source": ["FRED"]}  # Non-empty to avoid Parquet error
                )
                processed_data.append(payload.dict())
            
            # Remove the inner export call to consolidate at the end
            # self.storage.export_to_parquet(processed_data, data_type="macro")
            return processed_data

        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return []

    def fetch_all_macro(self):
        """Fetch all configured macro series."""
        all_data = []
        for sid, label in SERIES_IDS.items():
            logger.info(f"Fetching macro data for {label} ({sid})...")
            data = self.fetch_series(sid, label)
            all_data.extend(data)
        
        if all_data:
            self.storage.export_to_parquet(all_data, data_type="macro")
            
        logger.info(f"Macro ingestion complete. Total observations: {len(all_data)}")
        return all_data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    feed = MacroFeed()
    feed.fetch_all_macro()
