"""
test_v3_edge_cases.py
---------------------
Tests the V3 pipeline extensively against edge cases:
- Missing fundamentals
- Missing market data (e.g. delisted stock)
- Extremely high volatility behavior
- Handling of 'Unknown' sectors
"""
import sys
import logging
from dataclasses import asdict
from intelligence.features import FeatureEngine
from intelligence.trend_detector import TrendDetector
from intelligence.signal_scorer import SignalScorer
from intelligence.rule_engine import RuleEngine
from intelligence.risk_engine import RiskEngine

logging.basicConfig(level=logging.WARNING)

def run_edge_cases():
    scorer = SignalScorer()
    rules = RuleEngine()
    risk = RiskEngine(portfolio_value=1_000_000)
    features = FeatureEngine()

    test_cases = [
        "AAPL",              # Standard US big tech
        "TATAMTRDVR.NS",     # Known failed / delisted / no OHLCV data
        "NON_EXISTENT",      # Completely fake ticker
        "VIX",               # High volatility index (no fundamentals)
    ]

    print("Running Edge Cases...\n")
    for tk in test_cases:
        print(f"--- Ticker: {tk} ---")
        try:
            # 1. Feature Engine Tolerance
            tech = features.compute_technical(tk)
            fund = features.compute_fundamental(tk)
            sector = fund.sector or "Unknown"

            # 2. Scorer Tolerance
            sig = scorer.score(tk)
            print(f"Scorer: Action={sig.action}, Conf={sig.confidence}, Score={sig.score}")

            # 3. Rule Engine Tolerance
            decision = rules.evaluate(sig, sector)
            print(f"Rules: Final Action={decision.final_action}, Vetoes={len(decision.vetoes)}")

            # 4. Risk Engine Tolerance
            rparams = risk.calculate_risk(
                decision,
                current_price=tech.current_price,
                atr_14=tech.atr_14,
                current_drawdown=tech.current_drawdown
            )
            print(f"Risk: Alloc={rparams.final_allocation_pct}%, StopLoss={rparams.stop_loss_price}")
            print("Status: ✅ Handled gracefully")
        except Exception as e:
            print(f"Status: ❌ CRASH: {e}")
        print("\n")

if __name__ == "__main__":
    run_edge_cases()
