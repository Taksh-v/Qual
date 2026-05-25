from __future__ import annotations
from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field, validator
from datetime import datetime

class MarketData(BaseModel):
    """Schema for OHLCV market data."""
    ticker: str = Field(..., description="Ticker symbol (e.g., AAPL)")
    date: str = Field(..., description="ISO date or timestamp")
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str = Field("1d", description="Data interval (1m, 5m, 1d, etc.)")

class FinancialRatios(BaseModel):
    """Core financial ratios for fundamental analysis."""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    profit_margin: Optional[float] = None
    revenue_growth: Optional[float] = None

class FundamentalData(BaseModel):
    """Schema for company fundamentals and corporate actions."""
    ticker: str
    date: str
    ratios: FinancialRatios
    earnings_date: Optional[str] = None
    dividend_yield: Optional[float] = None

class SentimentAnalysis(BaseModel):
    """Structured sentiment output from the NLP layer."""
    label: str  # positive, negative, neutral
    score: float = Field(..., ge=-1.0, le=1.0)
    magnitude: str = "neutral"  # strong, moderate, mild, neutral
    signals: List[str] = []

class TextPayload(BaseModel):
    """Schema for raw text ingestion (News, Filings, Transcripts)."""
    source: str
    url: Optional[str] = None
    title: str
    raw_text: str
    date: str
    extracted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data_type: str = Field(..., description="e.g., news, sec, macro, earnings_transcript")
    sentiment: Optional[SentimentAnalysis] = None
    entities: Dict[str, List[str]] = Field(default_factory=dict)
    provenance_id: str = Field(..., description="Unique ID linking to raw archive")

class ProcessedChunk(BaseModel):
    """Final chunk schema stored in the vector/metadata DB."""
    chunk_id: str
    provenance_id: str
    text: str
    metadata: Dict[str, Any]
    quality_score: float = Field(1.0, ge=0.0, le=1.0)
    indexed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
