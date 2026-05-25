import logging
import yfinance as yf
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from ingestion.schemas import TextPayload
from ingestion.provenance import save_raw_payload
from ingestion.storage_manager import StorageManager

logger = logging.getLogger(__name__)

# Portfolio/Watchlist tickers to track
TICKERS_TO_TRACK = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BRK-B", "JPM", "V"]

class EarningsCalendarFeed:
    def __init__(self):
        self.storage = StorageManager()

    def fetch_earnings(self, tickers: List[str]):
        """Fetch upcoming earnings dates for a list of tickers."""
        all_events = []
        for ticker_sym in tickers:
            try:
                ticker = yf.Ticker(ticker_sym)
                calendar = ticker.calendar
                if calendar is None:
                    continue
                
                # yfinance returns a DataFrame or dict
                if isinstance(calendar, dict):
                    dates = calendar.get('Earnings Date')
                    raw_payload = calendar
                else:
                    if calendar.empty:
                        continue
                    dates = calendar.get('Earnings Date')
                    raw_payload = calendar.to_dict() if hasattr(calendar, 'to_dict') else str(calendar)

                if dates is None:
                    continue
                
                provenance_id = save_raw_payload({"calendar": raw_payload}, source="yfinance", data_type=f"earnings_{ticker_sym}")
                
                for dt in dates:
                    date_iso = dt.isoformat()
                    text_content = f"Earnings Event: {ticker_sym} scheduled for {date_iso}."
                    
                    payload = TextPayload(
                        source="yfinance",
                        title=f"{ticker_sym} Earnings Calendar",
                        raw_text=text_content,
                        date=date_iso,
                        data_type="earnings_calendar",
                        provenance_id=provenance_id,
                        entities={"tickers": [ticker_sym]}
                    )
                    all_events.append(payload.dict())
                    
            except Exception as e:
                logger.warning(f"Error fetching earnings for {ticker_sym}: {e}")
        
        if all_events:
            self.storage.export_to_parquet(all_events, data_type="earnings")
            logger.info(f"Earnings calendar ingestion complete. Total events: {len(all_events)}")
        
        return all_events

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    feed = EarningsCalendarFeed()
    feed.fetch_earnings(TICKERS_TO_TRACK)
