"""
intelligence/risk_engine.py
---------------------------
Risk management layer for Qual V3.4.

Translates finalized trading decisions into specific capital allocation and
stop-loss metrics based on volatility (ATR) and macro context.

Features:
  - Volatility-adjusted position sizing (fractional Kelly concept based on ATR).
  - Trailing Stop-Loss calculation (Chandelier Exit style: High - N*ATR).
  - Macro scaling factor: Scales down overall portfolio heat (allocations)
    in bad macro regimes.

Usage:
    from intelligence.risk_engine import RiskEngine
    engine = RiskEngine(portfolio_value=100_000)
    risk_params = engine.calculate_risk(decision, current_price, atr, current_drawdown)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from intelligence.rule_engine import RuleDecision

logger = logging.getLogger(__name__)


@dataclass
class RiskParameters:
    """Sizing and stop-loss parameters for a specific ticker."""
    ticker: str
    action: str
    base_allocation_pct: float         # Raw target % based on action
    volatility_scaler: float           # ATR penalty multiplier
    macro_scaler: float                # Regime portfolio heat multiplier
    final_allocation_pct: float        # Final recommended portfolio %
    position_size_usd: float           # Absolute dollar recommendation
    
    stop_loss_price: Optional[float]   # Recommended trailing stop level
    stop_loss_pct: Optional[float]     # Percent distance to stop loss
    distance_to_max_drawdown: Optional[float] # Distance between current price and all-time high


class RiskEngine:
    """Calculates position sizing and stop losses for capital protection."""

    # Base allocations max cap per signal
    BASE_ALLOC_MAP = {
        "STRONG_BUY": 0.10,  # Max 10% of portfolio
        "BUY": 0.05,         # Max 5%
        "HOLD": 0.0,         # Hold current, don't allocate new
        "REDUCE": 0.0,
        "AVOID": 0.0,
    }

    # Macro heat multiplier
    # Controls how much overall risk the portfolio absorbs per regime
    MACRO_SCALER = {
        "GOLDILOCKS": 1.0,       # Full risk
        "EARLY_RECOVERY": 1.0,
        "REFLATION": 0.8,
        "TRANSITIONAL": 0.7,
        "LATE_CYCLE": 0.5,       # Half size positions
        "DEFLATION_RISK": 0.5,
        "STAGFLATION": 0.3,      # Tiny positions
        "RECESSION": 0.3,
    }

    def __init__(self, portfolio_value: float = 100_000.0) -> None:
        self.portfolio_value = portfolio_value

    def calculate_risk(
        self,
        decision: RuleDecision,
        current_price: Optional[float],
        atr_14: Optional[float],
        current_drawdown: Optional[float] = 0.0
    ) -> RiskParameters:
        """
        Calculate sizing and stop levels for a finalized decision.
        """
        # Base Allocation
        base_alloc = self.BASE_ALLOC_MAP.get(decision.final_action, 0.0)
        
        # Volatility Sizing (ATR Penalty)
        # Average market ATR% is ~1.5 - 2.5%. If ATR% is higher, size goes down.
        vol_scaler = 1.0
        stop_price = None
        stop_pct = None

        if current_price and current_price > 0 and atr_14 and atr_14 > 0:
            atr_pct = atr_14 / current_price
            
            # Baseline is 2% ATR. If ATR is 4%, allocation is halved (0.02 / 0.04 = 0.5)
            # Cap the multiplier between 0.2 and 1.5
            vol_scaler = max(0.2, min(1.5, 0.02 / atr_pct))

            # Stop Loss (Chandelier-style trailing stop)
            # Use 3x ATR for normal hold/buy, tighter stops if confident but volatile
            stop_multiplier = 3.0
            if decision.final_action == "STRONG_BUY":
                stop_multiplier = 3.5  # Give winners more breathing room
            
            stop_price = round(current_price - (atr_14 * stop_multiplier), 2)
            # Ensure stop price doesn't go below 0
            stop_price = max(0.01, stop_price)
            stop_pct = round(((current_price - stop_price) / current_price) * 100, 2)

        # Macro Regime Sizing
        macro_scaler = self.MACRO_SCALER.get(decision.macro_regime, 0.5)

        # Final %
        final_pct = base_alloc * vol_scaler * macro_scaler
        
        # Max cap any single position at 15% absolutely
        final_pct = min(0.15, final_pct)
        # Round to 1 decimal place (e.g. 5.4%)
        final_pct = round(final_pct * 100, 1) / 100.0

        pos_usd = round(self.portfolio_value * final_pct, 2)

        return RiskParameters(
            ticker=decision.ticker,
            action=decision.final_action,
            base_allocation_pct=round(base_alloc * 100, 1),
            volatility_scaler=round(vol_scaler, 2),
            macro_scaler=round(macro_scaler, 2),
            final_allocation_pct=round(final_pct * 100, 1),
            position_size_usd=pos_usd,
            stop_loss_price=stop_price,
            stop_loss_pct=stop_pct,
            distance_to_max_drawdown=round(current_drawdown, 2) if current_drawdown else None
        )


if __name__ == "__main__":
    dummy_decision = RuleDecision("MOCK", "BUY", "BUY", "Buy ▲", macro_regime="LATE_CYCLE")
    engine = RiskEngine()
    print("Calculating risk for MOCK ($100, ATR $5) in LATE_CYCLE...")
    risk = engine.calculate_risk(dummy_decision, current_price=100.0, atr_14=5.0)
    print(f"Base Alloc:    {risk.base_allocation_pct}%")
    print(f"Vol Multiplier: {risk.volatility_scaler}x (High Vol)")
    print(f"Macro Multiplier: {risk.macro_scaler}x (Late Cycle)")
    print(f"Final Alloc:   {risk.final_allocation_pct}% (${risk.position_size_usd})")
    print(f"Stop Loss:     ${risk.stop_loss_price} (-{risk.stop_loss_pct}%)")
