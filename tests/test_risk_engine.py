"""
tests/test_risk_engine.py
"""
import pytest
from intelligence.risk_engine import RiskEngine, RiskParameters
from intelligence.rule_engine import RuleDecision

def test_volatility_scaling():
    engine = RiskEngine(portfolio_value=100_000)
    decision = RuleDecision("MOCK", "BUY", "BUY", "Buy", macro_regime="GOLDILOCKS", sector="Tech")
    
    # 5% ATR (high vol)
    risk_high_vol = engine.calculate_risk(decision, current_price=100.0, atr_14=5.0)
    # Expected base=5%, multiplier=0.02/0.05=0.4x -> 2.0%
    assert risk_high_vol.volatility_scaler == 0.4
    assert risk_high_vol.final_allocation_pct == 2.0
    
    # 1% ATR (low vol)
    risk_low_vol = engine.calculate_risk(decision, current_price=100.0, atr_14=1.0)
    # Expected base=5%, multiplier=0.02/0.01=2.0x -> max capped at 1.5x -> 7.5%
    assert risk_low_vol.volatility_scaler == 1.5
    assert risk_low_vol.final_allocation_pct == 7.5

def test_macro_scaling():
    engine = RiskEngine(portfolio_value=100_000)
    decision = RuleDecision("MOCK", "BUY", "BUY", "Buy", macro_regime="STAGFLATION")
    
    # Normal vol, stagflation regime
    risk = engine.calculate_risk(decision, current_price=100.0, atr_14=2.0)
    # Expected: Base 5%, Vol 1.0x, Macro 0.3x -> 1.5%
    assert risk.macro_scaler == 0.3
    assert risk.final_allocation_pct == 1.5

def test_stop_loss_calculation():
    engine = RiskEngine(portfolio_value=100_000)
    decision = RuleDecision("MOCK", "STRONG_BUY", "STRONG_BUY", "Strong Buy", macro_regime="GOLDILOCKS")
    
    # STRONG_BUY allows wider stop multiplier (3.5x)
    risk = engine.calculate_risk(decision, current_price=100.0, atr_14=2.0)
    # Expected stop = 100 - (2 * 3.5) = 93.0
    assert risk.stop_loss_price == 93.0
    assert risk.stop_loss_pct == 7.0
