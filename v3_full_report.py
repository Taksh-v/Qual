"""
v3_full_report.py
-----------------
The ultimate end-to-end report generator for Qual V3.
Chains: V3.3 Scoring -> V3.4 Rules -> V3.4 Risk -> Agentic Synthesis.
"""
import asyncio
import os
import sys
import logging
from intelligence.signal_scorer import SignalScorer
from intelligence.rule_engine import RuleEngine
from intelligence.risk_engine import RiskEngine
from intelligence.features import FeatureEngine
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator
from intelligence.bloomberg_formatter import BloombergFormatter

# Suppress noisy logs
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("full_report")

async def generate_integrated_report(ticker: str):
    scorer = SignalScorer()
    rules = RuleEngine()
    risk = RiskEngine(portfolio_value=1_000_000)
    features = FeatureEngine()
    orchestrator = AgenticOrchestrator()
    formatter = BloombergFormatter()

    # 1. Quantitative Layer (The Math)
    sig = scorer.score(ticker)
    fund = features.compute_fundamental(ticker)
    tech = features.compute_technical(ticker)
    sector = fund.sector or "Technology"
    
    decision = rules.evaluate(sig, sector)
    rparams = risk.calculate_risk(
        decision, 
        current_price=tech.current_price, 
        atr_14=tech.atr_14, 
        current_drawdown=tech.current_drawdown
    )

    # 2. Intelligence Layer (The Strategic Analysis)
    question = f"What is the outlook for {ticker} given current macro trends and its underlying fundamentals?"
    print(f"\n[Agentic RAG] Analyzing: {question}")
    
    final_answer = ""
    print("  > Synthesis Streaming:", end="", flush=True)
    async for event in orchestrator.run_async(question):
        if event.stage == "token":
            text = event.data.get("text", "")
            final_answer += text
            print(text, end="", flush=True)
        elif event.stage != "token":
            # Just print the transition
            if event.stage == "synthesis":
                print(f"\n  > Stage: {event.stage:<15}", end=" ", flush=True)
            else:
                pass

    if not final_answer:
        final_answer = "Intelligence synthesis timeout or failed. Check local LLM status."

    # 3. Final Bloomberg Integration
    print("\n\n" + "="*80)
    print("  FINAL INTEGRATED INSTITUTIONAL REPORT")
    print("="*80)
    
    output_meta = {
        "indicators": {"sp500": 5150, "vix": 18.2, "yield_10y": 4.35, "credit_hy": 340},
        "regime": {"regime": sig.breakdown.macro_regime},
        "cross_asset": {"overall_signal": "MIXED"},
        "question": f"{ticker} INSTITUTIONAL OUTLOOK",
        "geography": "Global",
        "horizon": "Medium-Term"
    }

    print(formatter.morning_note(
        answer=final_answer,
        **output_meta
    ))

    # 4. Final Verification Table (The Execution Plan)
    print("="*68)
    print("  QUANTITATIVE EXECUTION PARAMETERS (V3.4)")
    print("="*68)
    print(f"  Ticker:     {ticker:<10} Sector:     {sector}")
    print(f"  Decision:   {decision.final_label:<10} Confidence: {sig.confidence}")
    print(f"  Alloc:      {rparams.final_allocation_pct}%  ($ {rparams.position_size_usd:,.2f})")
    print(f"  Stop price: ${rparams.stop_loss_price}  ({rparams.stop_loss_pct}%)")
    
    if decision.vetoes:
        print("-" * 68)
        print("  SYSTEM CONSTRAINTS:")
        for v in decision.vetoes: print(f"  • {v}")
    print("="*68 + "\n")

if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    asyncio.run(generate_integrated_report(ticker))
