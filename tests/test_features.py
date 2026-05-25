"""
tests/test_features.py
"""
import pytest
import pandas as pd
import numpy as np
from intelligence.features import FeatureEngine

def test_rsi_calculation():
    """Verify RSI calculation against known mathematical bounds."""
    # Create an upward trending dummy series
    closes = pd.Series([100 + i for i in range(20)])
    rsi = FeatureEngine._compute_rsi(closes, period=14)
    assert rsi is not None
    assert 0 <= rsi <= 100
    assert rsi > 50  # Should be bullish given constant uptrend

def test_atr_calculation():
    """Verify ATR logic."""
    high = pd.Series([105, 106, 107])
    low = pd.Series([95, 96, 97])
    close = pd.Series([100, 101, 102])
    
    # Needs at least period+1 length, so with period=2
    atr = FeatureEngine._compute_atr(high, low, close, period=2)
    assert atr is not None
    assert atr > 0

def test_ema_calculation():
    """Verify EMA smoothing."""
    closes = pd.Series([100] * 50) # Flat
    ema = FeatureEngine._compute_ema(closes, span=12)
    assert round(ema.iloc[-1], 2) == 100.00
