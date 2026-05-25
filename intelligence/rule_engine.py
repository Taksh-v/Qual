"""
intelligence/rule_engine.py
---------------------------
Rule-based decision layer for Qual V3.4.

This module acts as a gatekeeper. It takes the raw signal from `signal_scorer.py`
and applies strict rule-based filters (Macro, Trend, and Quality filters) to
finalize the trading decision.

Features:
  - Block buying in strong downtrends (no catching falling knives).
  - Downgrade cyclical sectors during Stagflation/Recession.
  - Demand higher confidence for entries during transitional regimes.

Usage:
    from intelligence.rule_engine import RuleEngine
    engine = RuleEngine()
    decision = engine.evaluate(signal_result)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from intelligence.signal_scorer import SignalResult, ACTION_MAP

logger = logging.getLogger(__name__)


@dataclass
class RuleDecision:
    """The finalized decision after applying rules to the raw signal."""
    ticker: str
    original_action: str
    final_action: str
    final_label: str
    vetoes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    macro_regime: str = "UNKNOWN"
    sector: str = "UNKNOWN"
    is_downgraded: bool = False


class RuleEngine:
    """Evaluates constraints against raw signals to output final decisions."""

    # Sectors highly sensitive to economic contraction
    CYCLICAL_SECTORS = {"Technology", "Consumer Discretionary", "Industrials", "Materials"}
    
    # Sectors that generally hold up well in contraction/stagflation
    DEFENSIVE_SECTORS = {"Consumer Defensive", "Healthcare", "Utilities"}

    def __init__(self) -> None:
        pass

    def evaluate(self, signal: SignalResult, sector: str = "Unknown") -> RuleDecision:
        """
        Evaluate a SignalResult and apply business logic rules.
        """
        decision = RuleDecision(
            ticker=signal.ticker,
            original_action=signal.action,
            final_action=signal.action,
            final_label=signal.label,
            macro_regime=signal.breakdown.macro_regime,
            sector=sector,
        )

        # Skip logic if action is already AVOID or REDUCE
        if decision.original_action in {"AVOID", "REDUCE"}:
            return decision

        # ── Rule 1: No Catching Falling Knives ──
        # Block buying if the trend is strongly down
        if decision.original_action in {"BUY", "STRONG_BUY"} and signal.trend == "STRONG_DOWNTREND":
            decision.vetoes.append("VETO: Trend is STRONG_DOWNTREND. Buying blocked.")
            self._downgrade_to(decision, "HOLD")

        # ── Rule 2: Low Confidence Filter ──
        if decision.original_action == "STRONG_BUY" and signal.confidence == "LOW":
            decision.warnings.append("WARNING: Low signal coincidence. Downgrading to BUY.")
            self._downgrade_to(decision, "BUY")
        elif decision.original_action == "BUY" and signal.confidence == "LOW":
            decision.warnings.append("WARNING: Low signal coincidence. Downgrading to HOLD.")
            self._downgrade_to(decision, "HOLD")

        # ── Rule 3: Macro Regime vs Sector ──
        regime = decision.macro_regime
        if regime in {"STAGFLATION", "RECESSION"}:
            if sector in self.CYCLICAL_SECTORS:
                if decision.final_action in {"BUY", "STRONG_BUY"}:
                    decision.vetoes.append(f"VETO: Cyclical sector ({sector}) in {regime} regime.")
                    self._downgrade_to(decision, "HOLD")
            elif sector in self.DEFENSIVE_SECTORS:
                decision.warnings.append(f"NOTE: Defensive sector ({sector}) preferred in {regime}.")
        
        elif regime == "DEFLATION_RISK" and sector == "Financial Services":
             if decision.final_action in {"BUY", "STRONG_BUY"}:
                 decision.vetoes.append("VETO: Financials perform poorly in Deflation/Low Rates.")
                 self._downgrade_to(decision, "HOLD")

        # ── Rule 4: Valuation Extreme Filter ──
        fund_score = signal.breakdown.fundamental_score
        if decision.final_action in {"BUY", "STRONG_BUY"} and fund_score < 0.2:
            decision.vetoes.append(f"VETO: Fundamental score too low ({fund_score:.2f}) for entry.")
            self._downgrade_to(decision, "HOLD")

        return decision

    def _downgrade_to(self, decision: RuleDecision, new_action: str) -> None:
        """Helper to downgrade action, respecting hierarchy."""
        hierarchy = {"STRONG_BUY": 4, "BUY": 3, "HOLD": 2, "REDUCE": 1, "AVOID": 0}
        
        current_rank = hierarchy.get(decision.final_action, -1)
        new_rank = hierarchy.get(new_action, -1)
        
        if new_rank < current_rank:
            decision.final_action = new_action
            decision.is_downgraded = True
            
            # Find the label mapping
            for _, act, lbl, _ in ACTION_MAP:
                if act == new_action:
                    decision.final_label = lbl
                    break


if __name__ == "__main__":
    from intelligence.signal_scorer import SignalBreakdown
    # Simple test scenario
    dummy_signal = SignalResult(
        ticker="MOCK",
        score=0.8,
        action="STRONG_BUY",
        label="Strong Buy ▲▲",
        confidence="MEDIUM",
        description="...",
        trend="STRONG_DOWNTREND",
        breakdown=SignalBreakdown(macro_regime="STAGFLATION")
    )
    engine = RuleEngine()
    print("Evaluating MOCK Tech stock in Stagflation & Strong Downtrend...")
    d = engine.evaluate(dummy_signal, sector="Technology")
    print(f"Original: {d.original_action}")
    print(f"Final:    {d.final_action} ({d.final_label})")
    print("Vetoes:")
    for v in d.vetoes: print(f" - {v}")
