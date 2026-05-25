"""
tests/test_trend_detector.py
"""
import pytest
from unittest.mock import patch, MagicMock
from intelligence.trend_detector import TrendDetector, TrendResult
from intelligence.features import TechnicalFeatures

@patch('intelligence.trend_detector.FeatureEngine')
def test_strong_uptrend_classification(MockFeatureEngine):
    mock_engine = MockFeatureEngine.return_value
    
    # Mock a perfectly bullish technical state
    mock_tech = TechnicalFeatures(
        ticker="MOCK",
        date="2026-04-10",
        data_points=60,
        sma_20=100,
        sma_50=95,
        sma_200=80,
        price_vs_sma50=5.0,
        price_vs_sma200=10.0,
        rsi_14=65.0,
        macd_histogram=0.5,
        bb_position=0.9,
        obv_trend="rising",
        return_5d=3.0,
        golden_cross=True
    )
    mock_engine.compute_technical.return_value = mock_tech
    
    detector = TrendDetector()
    detector.feature_engine = mock_engine
    
    result = detector.classify("MOCK")
    
    assert result.trend == "STRONG_UPTREND"
    assert result.confidence == "HIGH"
    assert result.score > 0.6

@patch('intelligence.trend_detector.FeatureEngine')
def test_strong_downtrend_classification(MockFeatureEngine):
    mock_engine = MockFeatureEngine.return_value
    
    # Mock a perfectly bearish technical state
    mock_tech = TechnicalFeatures(
        ticker="MOCK",
        date="2026-04-10",
        data_points=60,
        sma_20=80,
        sma_50=90,
        sma_200=100,
        price_vs_sma50=-5.0,
        price_vs_sma200=-10.0,
        rsi_14=25.0,
        macd_histogram=-0.5,
        bb_position=0.1,
        obv_trend="falling",
        return_5d=-3.0,
        death_cross=True
    )
    mock_engine.compute_technical.return_value = mock_tech
    
    detector = TrendDetector()
    detector.feature_engine = mock_engine
    
    result = detector.classify("MOCK")
    
    assert result.trend == "STRONG_DOWNTREND"
    assert result.confidence in ["HIGH", "MEDIUM"]
    assert result.score < -0.6

@patch('intelligence.trend_detector.FeatureEngine')
def test_insufficient_data(MockFeatureEngine):
    mock_engine = MockFeatureEngine.return_value
    mock_tech = TechnicalFeatures(ticker="MOCK", date="2026-04-10", data_points=10) # < 20
    mock_engine.compute_technical.return_value = mock_tech
    
    detector = TrendDetector()
    detector.feature_engine = mock_engine
    
    result = detector.classify("MOCK")
    
    assert result.trend == "SIDEWAYS"
    assert result.data_quality == "INSUFFICIENT"
    assert result.score == 0.0

