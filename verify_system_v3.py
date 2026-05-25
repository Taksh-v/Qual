"""
verify_system_v3.py
-------------------
End-to-end verification of the Qual V3 Quantitative Intelligence Pipeline.
Chains V3.3 Signal Scorer -> V3.4 Rule Engine -> V3.4 Risk Engine.
"""
import json
from dataclasses import asdict
from intelligence.signal_scorer import SignalScorer
from intelligence.rule_engine import RuleEngine
from intelligence.risk_engine import RiskEngine
from intelligence.features import FeatureEngine

def run_pipeline(tickers):
    scorer = SignalScorer()
    rules = RuleEngine()
    risk = RiskEngine(portfolio_value=1_000_000) # $1M portfolio
    features = FeatureEngine()
    
    print(f"\n{'='*100}")
    print(f"  QUANTUM V3 SYSTEM PIPELINE VERIFICATION")
    print(f"{'='*100}")
    
    for tk in tickers:
        print(f"\n[1] Scoring {tk}...")
        sig = scorer.score(tk)
        
        # Get sector & ATR
        fund = features.compute_fundamental(tk)
        tech = features.compute_technical(tk)
        sector = fund.sector or "Unknown"
        
        print(f"    Raw Signal: {sig.action} ({sig.score}) | Trend: {sig.trend}")
        print(f"    Macro: {sig.breakdown.macro_regime} | Sector: {sector}")
        
        print(f"[2] Applying Rules...")
        decision = rules.evaluate(sig, sector)
        
        for w in decision.warnings: print(f"    {w}")
        for v in decision.vetoes: print(f"    {v}")
        if decision.is_downgraded:
            print(f"    => DOWNGRADED to {decision.final_action}")
        else:
            print(f"    => RETAINED as {decision.final_action}")
            
        print(f"[3] Calculating Risk Parameters...")
        rparams = risk.calculate_risk(
            decision, 
            current_price=tech.current_price, 
            atr_14=tech.atr_14, 
            current_drawdown=tech.current_drawdown
        )
        
        print(f"    Position Size: {rparams.final_allocation_pct}% (${rparams.position_size_usd:,.2f})")
        print(f"    Stop Loss: ${rparams.stop_loss_price} (-{rparams.stop_loss_pct}%)")
        print(f"    Volatility Scaler: {rparams.volatility_scaler}x | Macro Scaler: {rparams.macro_scaler}x")
        print("-" * 100)

if __name__ == "__main__":
    test_universe = ["AAPL", "NVDA", "XOM", "RELIANCE.NS", "TSLA", "ITC.NS"]
    run_pipeline(test_universe)
