"""
tests/test_rule_engine.py
"""
import pytest
from intelligence.rule_engine import RuleEngine, RuleDecision
from intelligence.signal_scorer import SignalResult, SignalBreakdown

def test_no_catching_falling_knives():
    engine = RuleEngine()
    signal = SignalResult(
        ticker="MOCK", score=0.8, action="STRONG_BUY", label="Mock",
        confidence="HIGH", description="", trend="STRONG_DOWNTREND",
        breakdown=SignalBreakdown(macro_regime="GOLDILOCKS")
    )
    decision = engine.evaluate(signal, sector="Technology")
    assert decision.final_action == "HOLD"
    assert "STRONG_DOWNTREND" in decision.vetoes[0]

def test_macro_cyclical_veto():
    engine = RuleEngine()
    signal = SignalResult(
        ticker="MOCK", score=0.8, action="BUY", label="Mock",
        confidence="HIGH", description="", trend="UPTREND",
        breakdown=SignalBreakdown(macro_regime="STAGFLATION")
    )
    decision = engine.evaluate(signal, sector="Technology")
    assert decision.final_action == "HOLD"
    assert "Cyclical sector" in decision.vetoes[0]

def test_macro_defensive_pass():
    engine = RuleEngine()
    signal = SignalResult(
        ticker="MOCK", score=0.8, action="BUY", label="Mock",
        confidence="HIGH", description="", trend="UPTREND",
        breakdown=SignalBreakdown(macro_regime="STAGFLATION")
    )
    decision = engine.evaluate(signal, sector="Healthcare")
    assert decision.final_action == "BUY"
    assert "Defensive sector" in decision.warnings[0]

def test_low_confidence_downgrade():
    engine = RuleEngine()
    signal = SignalResult(
        ticker="MOCK", score=0.8, action="STRONG_BUY", label="Mock",
        confidence="LOW", description="", trend="UPTREND",
        breakdown=SignalBreakdown(macro_regime="GOLDILOCKS")
    )
    decision = engine.evaluate(signal, sector="Healthcare")
    assert decision.final_action == "BUY"
