"""
intelligence/bloomberg_formatter.py
-------------------------------------
Bloomberg Terminal-style output formatter for the Finance AI System.

Transforms structured AgentState or raw response text into Bloomberg-grade
analytical output in multiple format modes:

  1. morning_note   — Full Bloomberg Morning Note format (default for detailed mode)
  2. risk_matrix    — Probability × Impact risk/opportunity grid
  3. trade_idea     — Actionable setup with entry/target/stop/R:R
  4. brief          — Compact single-section summary (backward compatible)

Usage:
    from intelligence.bloomberg_formatter import BloombergFormatter
    formatter = BloombergFormatter()
    output = formatter.morning_note(state)
    output = formatter.format(state, mode="morning_note")
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from intelligence.agentic_rag.agent_state import AgentState


class BloombergFormatter:
    """
    Formats analytical output in Bloomberg Terminal-grade styles.

    All methods accept either an AgentState (full agentic run) or a plain dict
    (for backward-compatible use with the existing pipeline output).
    """

    # ── Visual markers (Bloomberg terminal style) ─────────────────────────────

    DIVIDER = "━" * 68
    THIN_DIV = "─" * 68
    UP = "▲"
    DOWN = "▼"
    FLAT = "●"
    BULLET = "•"

    # Box drawing characters
    TL = "╔"
    TR = "╗"
    BL = "╚"
    BR = "╝"
    H  = "═"
    V  = "║"
    T  = "╦"
    BT = "╩"
    C  = "╬"

    # Regime → display badge
    _REGIME_BADGES: dict[str, str] = {
        "RISK_ON": "🟢 RISK ON",
        "RISK_OFF": "🔴 RISK OFF",
        "STAGFLATION": "🟠 STAGFLATION",
        "RECESSION": "🔴 RECESSION",
        "RECOVERY": "🟡 RECOVERY",
        "REFLATION": "🟢 REFLATION",
        "UNKNOWN": "⚪ REGIME UNKNOWN",
    }

    # Signal → color emoji
    _SIGNAL_EMOJIS: dict[str, str] = {
        "STRONG_BUY": "🟢 ▲▲",
        "BUY": "🟢 ▲",
        "HOLD": "🟡 ●",
        "REDUCE": "🟠 ▼",
        "AVOID": "🔴 ▼▼",
        "MIXED": "⚪ ●",
    }

    # ── Indicator table builder ────────────────────────────────────────────────

    def _build_indicator_table(self, indicators: dict[str, float]) -> str:
        """Build a high-density Markdown table for indicators."""
        INDICATOR_LABELS: dict[str, tuple[str, str]] = {
            "sp500": ("S&P 500", "pts"),
            "nasdaq": ("Nasdaq", "pts"),
            "vix": ("VIX", "vol"),
            "yield_10y": ("US 10Y Yield", "%"),
            "yield_2y": ("US 2Y Yield", "%"),
            "yield_curve": ("Yield Curve", "bps"),
            "dxy": ("DXY Index", "pts"),
            "oil_wti": ("WTI Crude", r"\$/b"),
            "gold": ("Gold", r"\$/oz"),
            "inflation_cpi": ("CPI Inflation", "%"),
            "fed_funds_rate": ("Fed Funds", "%"),
            "btc": ("Bitcoin", r"\$"),
        }

        header = "| INDICATOR | VALUE | UNIT | TREND |\n|:---|:---:|:---:|:---:|"
        rows: list[str] = []
        for key, (label, unit) in INDICATOR_LABELS.items():
            val = indicators.get(key)
            if val is None:
                continue
            
            # Simple trend logic
            trend = self.FLAT
            if key == "vix":
                trend = "🔴 ▲" if val > 20 else "🟢 ▼"
            elif key == "yield_curve":
                 trend = "🟢 ▲" if val > 0 else "🔴 ▼"
            else:
                 # Default logic for generic indicators
                 trend = self.FLAT
            
            val_str = f"**{val:,.2f}**" if abs(val) >= 100 else f"**{val:.2f}**"
            rows.append(f"| {label} | {val_str} | {unit} | {trend} |")

        if not rows:
            return "  [No live market data available]"
        
        return header + "\n" + "\n".join(rows)

    # ── Public formatting methods ──────────────────────────────────────────────

    def morning_note(
        self,
        state: "AgentState | None" = None,
        *,
        answer: str = "",
        indicators: dict[str, float] | None = None,
        regime: dict[str, Any] | None = None,
        cross_asset: dict[str, Any] | None = None,
        question: str = "",
        geography: str = "US",
        horizon: str = "MEDIUM_TERM",
        model_used: str = "",
    ) -> str:
        """Render a Terminal-grade Morning Note."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d %H:%M UTC")

        # Extract from AgentState if provided
        if state is not None:
            answer = answer or state.final_answer or state.draft_answer
            indicators = indicators or state.live_indicators
            regime = regime or state.live_meta.get("regime", {})
            cross_asset = cross_asset or state.live_meta.get("cross_asset", {})
            question = question or state.question
            geography = state.geography
            horizon = state.horizon
            agreeing, total = state.agent_agreement_score()
            agent_agreement_str = f"{agreeing}/{total} agents agree"
        else:
            agent_agreement_str = "N/A"

        indicators = indicators or {}
        regime = regime or {}
        cross_asset = cross_asset or {}

        reg_name = (regime.get("regime") or "UNKNOWN").upper()
        regime_badge = self._REGIME_BADGES.get(reg_name, "⚪ UNKNOWN")
        
        raw_signal = (cross_asset.get("overall_signal") or "MIXED").upper()
        signal_emoji = self._SIGNAL_EMOJIS.get(raw_signal, "⚪ ●")

        # Parse structured fields
        fields = self._parse_answer_fields(answer)

        sections: list[str] = []

        # 1. Terminal Header Block
        hdr_line = self.H * 64
        sections.append(
            f"{self.TL}{hdr_line}{self.TR}\n"
            f"{self.V}  **QUAL NEWS INTELLIGENCE TERMINAL** {date_str:>23}  {self.V}\n"
            f"{self.V}  {geography:<10} | {horizon.replace('_', ' '):<14} | {regime_badge:<18} | {self.V}\n"
            f"{self.V}  SIGNAL: {signal_emoji:<15} | AGENT CONSENSUS: {agent_agreement_str:<12} {self.V}\n"
            f"{self.BL}{hdr_line}{self.BR}"
        )

        # 2. Query
        sections.append(f"\n> **QUERY:** _{question}_\n")

        # 3. Executive Summary (BLUF)
        exec_summary = fields.get("executive_summary") or fields.get("direct_answer") or ""
        if exec_summary:
            sections.append(f"### ⚡ EXECUTIVE SUMMARY\n{exec_summary}\n")

        # 4. Structured Data Layer (V4.2)
        # Attempt to combine sub-tables if the parent sdl field is weak/empty
        sdl = fields.get("structured_data_layer", "").strip()
        sub_tables = []
        for tb in ["events_table", "market_data_table", "macro_indicators_table"]:
            if fields.get(tb):
                sub_tables.append(fields[tb])
        
        full_sdl = sdl
        if sub_tables and len(sdl) < 20: # If parent is just a header/junk, use sub-tables
            full_sdl = "\n\n".join(sub_tables)

        if full_sdl:
            sections.append(f"### 🧱 STRUCTURED DATA LAYER\n{full_sdl}\n")
        else:
            # Fallback to separate sections or legacy news
            news_brief = next((ao.brief for ao in state.agent_outputs if ao.agent_name == "NewsSpecialist"), "") if state else ""
            if news_brief:
                sections.append(f"### 📰 LATEST DEVELOPMENTS\n{news_brief}\n")

        # 6. Scenario Matrix
        scenarios = fields.get("scenarios", "")
        if scenarios:
            sections.append(f"### 🧭 SCENARIO MATRIX\n{scenarios}\n")

        # 7. Causal Transmission Analysis (V4.2)
        causal = fields.get("causal_transmission", fields.get("causal_chain", ""))
        if causal:
            sections.append(f"### 🔗 CAUSAL TRANSMISSION ANALYSIS\n{causal}\n")

        # 8. Geopolitical & Systemic Risk (V4.2)
        geo_context = fields.get("geopolitical_risk", fields.get("geopolitical_context", ""))
        if geo_context:
            sections.append(f"### 🌏 GEOPOLITICAL & SYSTEMIC RISK\n{geo_context}\n")

        # 9. Cross-Asset Impact
        market_impact = fields.get("market_impact", "")
        if market_impact:
            sections.append(f"### 📊 CROSS-ASSET IMPACT\n{market_impact}\n")

        # 10. Risk Dashboard (V4.0)
        risk_dash = fields.get("risk_dashboard", "")
        if risk_dash:
            sections.append(f"### 🛡️ RISK DASHBOARD\n{risk_dash}\n")

        # 11. Institutional Positioning & Strategy (V4.2)
        strategy = fields.get("institutional_strategy", fields.get("suggested_strategy", ""))
        if strategy:
            sections.append(f"### 💰 INSTITUTIONAL POSITIONING & STRATEGY\n{strategy}\n")

        # 12. Confidence & Uncertainty (V4.2)
        uncertainty = fields.get("uncertainty", "")
        if uncertainty:
            sections.append(f"### ❓ CONFIDENCE & UNCERTAINTY\n{uncertainty}\n")

        # 12. Terminal Footer
        conf_score = fields.get("confidence") or "MEDIUM"
        source_count = len(state.retrieved_chunks) if state else 0
        footer_parts = [
            f"Confidence Score: **{conf_score}**",
            f"Evidence: **{source_count} chunks**"
        ]
        if model_used:
            footer_parts.append(f"Model: `{model_used}`")
        footer_str = " | ".join(footer_parts)
        
        sections.append(f"{self.THIN_DIV}")
        sections.append(f"  {footer_str}")
        sections.append(f"  **DATA FRESHNESS:** LIVE (Aggregated {now.strftime('%H:%M:%S UTC')})")
        sections.append(f"{self.THIN_DIV}")
        
        sections.append(f"\n> [!NOTE]\n> This is AI-generated analysis and not financial advice. Market conditions change rapidly.")

        return "\n".join(sections)

    def risk_matrix(
        self,
        state: "AgentState | None" = None,
        *,
        answer: str = "",
        indicators: dict[str, float] | None = None,
        question: str = "",
    ) -> str:
        """
        Render a Risk/Opportunity Matrix with Probability × Impact assessment.
        """
        if state is not None:
            answer = answer or state.final_answer
            indicators = indicators or state.live_indicators
            question = question or state.question

        indicators = indicators or {}
        fields = self._parse_answer_fields(answer)

        vix = indicators.get("vix")
        hy_spreads = indicators.get("credit_hy")
        yield_curve = indicators.get("yield_curve")

        # Infer risk level from market data
        risk_level = "MODERATE"
        if vix is not None:
            if vix > 30:
                risk_level = "HIGH"
            elif vix < 15:
                risk_level = "LOW"

        sections: list[str] = [
            f"{self.DIVIDER}",
            f"  RISK MATRIX | {question[:60]}",
            f"{self.DIVIDER}",
            f"",
            f"  Market Stress Indicators:",
            f"  {'VIX':<20} {f'{vix:.1f}' if vix else 'N/A':>8}  {'(ELEVATED)' if vix and vix > 20 else '(NORMAL)'}",
            f"  {'HY Spread (bps)':<20} {f'{hy_spreads:.0f}' if hy_spreads else 'N/A':>8}  {'(WIDE)' if hy_spreads and hy_spreads > 450 else '(TIGHT)'}",
            f"  {'Yield Curve (bps)':<20} {f'{yield_curve:.0f}' if yield_curve else 'N/A':>8}  {'(INVERTED)' if yield_curve and yield_curve < 0 else '(NORMAL)'}",
            f"",
            f"  Overall Risk Level: {risk_level}",
            f"",
            f"  Scenario Probability Breakdown:",
        ]

        # Parse scenarios from answer
        answer_lower = answer.lower()
        base_pct = self._extract_probability(answer_lower, "base")
        bull_pct = self._extract_probability(answer_lower, "bull")
        bear_pct = self._extract_probability(answer_lower, "bear")

        sections.append(f"  {'Base Case':<20} {base_pct or '~55%':>8}  Most likely path")
        sections.append(f"  {'Bull Case':<20} {bull_pct or '~25%':>8}  Upside scenario")
        sections.append(f"  {'Bear Case':<20} {bear_pct or '~20%':>8}  Tail risk")
        sections.append(f"")

        risks = fields.get("consequences") or fields.get("main_risks") or ""
        if risks:
            sections.append(f"  Key Risks:")
            sections.append(f"  {risks}")

        sections.append(f"{self.DIVIDER}\n")
        return "\n".join(sections)

    def trade_idea(
        self,
        state: "AgentState | None" = None,
        *,
        answer: str = "",
        indicators: dict[str, float] | None = None,
        question: str = "",
    ) -> str:
        """
        Render an actionable Trade Idea format.
        Extracts direction, rationale, and key levels from the answer.
        """
        if state is not None:
            answer = answer or state.final_answer
            indicators = indicators or state.live_indicators
            question = question or state.question

        fields = self._parse_answer_fields(answer)
        summary = fields.get("executive_summary") or fields.get("direct_answer") or answer[:200]

        sections = [
            f"{self.DIVIDER}",
            f"  TRADE IDEA / ACTIONABLE VIEW",
            f"{self.DIVIDER}",
            f"",
            f"  Thesis: {summary[:200]}",
            f"",
            f"  Setup: Based on {question[:80]}",
            f"  Rationale: {fields.get('causal_chain', fields.get('what_is_happening', 'See full analysis'))[:200]}",
            f"",
            f"  Key risks: {fields.get('consequences', fields.get('main_risks', 'See risk matrix'))[:150]}",
            f"  What to watch: {fields.get('watch_next', 'Key data releases and policy decisions')[:150]}",
            f"",
            f"  Confidence: {fields.get('confidence', 'See analysis')}",
            f"{self.DIVIDER}\n",
        ]
        return "\n".join(sections)

    def brief(
        self,
        answer: str,
        *,
        question: str = "",
        model_used: str = "",
    ) -> str:
        """
        Compact brief format — backward compatible with existing pipeline output.
        Just adds a Bloomberg-style header/footer around the existing answer.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = f"{self.DIVIDER}\n  MACRO AI [{now}]\n{self.DIVIDER}\n"
        footer = f"\n{self.DIVIDER}" + (f"\n  Model: {model_used}" if model_used else "") + f"\n{self.DIVIDER}\n"
        return header + answer + footer

    def format(
        self,
        state: "AgentState | None" = None,
        mode: str = "morning_note",
        **kwargs: Any,
    ) -> str:
        """
        Unified entry point — dispatch to the appropriate format method.

        Args:
            state: AgentState from the agentic pipeline, or None
            mode: "morning_note" | "risk_matrix" | "trade_idea" | "brief"
            **kwargs: For non-agentic usage (answer, indicators, question, etc.)
        """
        if mode == "morning_note":
            return self.morning_note(state, **kwargs)
        if mode == "risk_matrix":
            return self.risk_matrix(state, **kwargs)
        if mode == "trade_idea":
            return self.trade_idea(state, **kwargs)
        return self.brief(kwargs.get("answer", ""), **{k: v for k, v in kwargs.items() if k != "answer"})

    # ── Internal parsers ───────────────────────────────────────────────────────

    def _parse_answer_fields(self, text: str) -> dict[str, str]:
        """Extract structured fields from a free-text LLM answer or parsed JSON."""
        try:
            import json
            data = json.loads(text)
            fields: dict[str, str] = {}
            fields["executive_summary"] = data.get("executive_summary", "")
            fields["direct_answer"] = data.get("direct_answer", "")
            fields["data_snapshot"] = data.get("data_snapshot", "")
            fields["causal_chain"] = data.get("causal_chain", "")
            
            wih = data.get("what_is_happening", [])
            fields["what_is_happening"] = "\n  ".join(f"{item}" for item in wih) if isinstance(wih, list) else str(wih)
            
            cai = data.get("cross_asset_impacts", [])
            if isinstance(cai, list) and cai and isinstance(cai[0], dict):
                fields["market_impact"] = "\n  ".join(f"{item.get('asset_class', '')}: {item.get('direction', '')} — {item.get('mechanism', '')}" for item in cai)
            else:
                fields["market_impact"] = str(data.get("market_impact", ""))
                
            scenarios = data.get("scenarios", [])
            if isinstance(scenarios, list) and scenarios and isinstance(scenarios[0], dict):
                fields["scenarios"] = "\n  ".join(f"{item.get('name', '')} (~{item.get('probability_pct', '')}%): {item.get('narrative', '')}" for item in scenarios)
            else:
                fields["scenarios"] = str(data.get("scenarios", ""))
                
            wtw = data.get("what_to_watch", [])
            fields["watch_next"] = "\n  ".join(f"{item}" for item in wtw) if isinstance(wtw, list) else str(wtw)
            
            risks = data.get("main_risks", [])
            fields["main_risks"] = "\n  ".join(f"{item}" for item in risks) if isinstance(risks, list) else str(risks)
            
            fields["confidence"] = data.get("confidence", "")
            fields["consequences"] = fields["main_risks"]
            fields["market_map"] = fields["market_impact"]
            fields["why_likely"] = fields["what_is_happening"]
            return fields
        except Exception:
            pass # Fall back to regex parser

        fields: dict[str, str] = {
            "executive_summary": "",
            "direct_answer": "",
            "data_snapshot": "",
            "causal_chain": "",
            "what_is_happening": "",
            "market_impact": "",
            "scenarios": "",
            "consequences": "",
            "main_risks": "",
            "watch_next": "",
            "why_likely": "",
            "market_map": "",
            "confidence": "",
        }
        current_field: str | None = None
        buffer: list[str] = []

        field_map: dict[str, str] = {
            "bluf": "executive_summary",
            "executive summary": "executive_summary",
            "direct answer": "direct_answer",
            "bottom line": "direct_answer",
            "structured data layer": "structured_data_layer",
            "events:": "events_table",
            "market data:": "market_data_table",
            "macro indicators:": "macro_indicators_table",
            "news developments": "news_developments",
            "latest developments": "news_developments",
            "scenario matrix": "scenarios",
            "scenario probability matrix": "scenarios",
            "cross-asset impact": "market_impact",
            "causal transmission analysis": "causal_transmission",
            "causal chain analysis": "causal_transmission",
            "causal logic": "causal_transmission",
            "geopolitical & systemic risk": "geopolitical_risk",
            "geopolitical risk": "geopolitical_risk",
            "geopolitical context": "geopolitical_risk",
            "risk dashboard": "risk_dashboard",
            "institutional positioning & strategy": "institutional_strategy",
            "suggested strategy": "institutional_strategy",
            "confidence & uncertainty": "uncertainty",
            "confidence": "confidence",
            "confidence score": "confidence",
        }

        def _flush():
            if current_field and buffer:
                fields[current_field] = "\n".join(buffer).strip()
            buffer.clear()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
                
            # Most robust approach: Check for keywords in a "likely header" line
            # (starts with # or * or emoji, or is all caps)
            is_potential_header = line.startswith(('#', '*', '⚡', '⭐', '🧭', '🌏', '🔗', '🛡️', '💰', '⚠️')) or line.isupper()
            
            matched = False
            if is_potential_header:
                clean_line = line.lower().replace('*', '').replace('#', '').strip()
                for keyword, fname in field_map.items():
                    if keyword in clean_line:
                        _flush()
                        current_field = fname
                        matched = True
                        # Capture trailing content on same line but skip the divider chars
                        if ':' in line:
                            val = line.split(':', 1)[-1].strip()
                            val = val.strip('*# ')
                            if val and val.lower() not in keyword:
                                buffer.append(val)
                        break
            
            if not matched and current_field:
                buffer.append(line)

        _flush()

        # Aliases
        if not fields["market_map"]:
            fields["market_map"] = fields["market_impact"]
        if not fields["why_likely"] and fields["what_is_happening"]:
            fields["why_likely"] = fields["what_is_happening"]

        return fields

    def _extract_probability(self, text: str, scenario: str) -> str:
        """Extract probability string for a named scenario case."""
        pattern = rf"{re.escape(scenario)}[^%]{{0,30}}?(\d{{1,3}}%)"
        m = re.search(pattern, text)
        return m.group(1) if m else ""
