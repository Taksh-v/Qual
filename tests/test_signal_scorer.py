"""
tests/test_signal_scorer.py
"""
import pytest
from unittest.mock import patch, MagicMock
from intelligence.signal_scorer import SignalScorer, SignalBreakdown, SignalResult

def test_composite_score_calc():
    """Verify the weighted math for the composite score."""
    scorer = SignalScorer()
    
    # Mock individual dimension scorers to return known values
    scorer._score_technical = MagicMock(return_value=(0.8, ["tech ok"]))
    scorer._score_sentiment = MagicMock(return_value=(0.6, "positive"))
    scorer._score_fundamental = MagicMock(return_value=(0.9, ["fund ok"]))
    scorer._score_macro = MagicMock(return_value=(0.5, "TRANSITIONAL"))
    
    # Mock the trend detector so it doesn't try to connect to DB for 'trend'
    scorer.trend_detector = MagicMock()
    mock_trend = MagicMock()
    mock_trend.trend = "UPTREND"
    mock_trend.current_price = 100.0
    scorer.trend_detector.classify.return_value = mock_trend

    result = scorer.score("MOCK")
    
    # Weights: Tech(0.35), Sent(0.25), Fund(0.20), Macro(0.20)
    # 0.8 * 0.35 = 0.28
    # 0.6 * 0.25 = 0.15
    # 0.9 * 0.20 = 0.18
    # 0.5 * 0.20 = 0.10
    # Expected composite = 0.71
    assert abs(result.score - 0.71) < 0.01

def test_action_mapping():
    """Verify raw scores map to correct action labels."""
    scorer = SignalScorer()
    scorer._score_technical = MagicMock(); scorer._score_sentiment = MagicMock()
    scorer._score_fundamental = MagicMock(); scorer._score_macro = MagicMock()
    
    scorer.trend_detector = MagicMock()
    scorer.trend_detector.classify.return_value = MagicMock(trend="SIDEWAYS", current_price=0.0)

    # Force composite to 0.85 -> STRONG_BUY
    scorer._score_technical.return_value = (0.85, [])
    scorer._score_sentiment.return_value = (0.85, "")
    scorer._score_fundamental.return_value = (0.85, [])
    scorer._score_macro.return_value = (0.85, "")
    assert scorer.score("MOCK").action == "STRONG_BUY"

    # Force composite to 0.15 -> AVOID
    scorer._score_technical.return_value = (0.15, [])
    scorer._score_sentiment.return_value = (0.15, "")
    scorer._score_fundamental.return_value = (0.15, [])
    scorer._score_macro.return_value = (0.15, "")
    assert scorer.score("MOCK").action == "AVOID"

