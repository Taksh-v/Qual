# Great Analyst

## What Makes an Analyst Great
- Strong signal extraction: separates noise from market-moving information.
- Causal reasoning: explains transmission channels, not just direction.
- Probabilistic thinking: works with scenarios and base rates, not single-point certainty.
- Risk framing: defines triggers, invalidations, and downside asymmetry.
- Behavioral awareness: reads sentiment, crowding, panic/greed, and reflexivity.
- Adaptability: updates stance quickly when evidence changes.
- Outcome learning: measures forecast accuracy and improves from misses.
- Communication quality: concise, evidence-backed, decision-useful outputs.

---

## Capability Mapping for Current System

### Included (Strong)
- Regime + cross-asset core analysis is implemented.
  - `/home/kali/Downloads/Qual/intelligence/regime_detector.py`
  - `/home/kali/Downloads/Qual/intelligence/cross_asset_analyzer.py`
  - `/home/kali/Downloads/Qual/intelligence/macro_reasoner.py`
- Structured decision-style outputs (scenarios, triggers, invalidations) are present.
  - `/home/kali/Downloads/Qual/intelligence/response_schema.py`
  - `/home/kali/Downloads/Qual/intelligence/prompt_templates.py`
- Streaming/live adaptivity exists through SSE and live indicator updates.
  - `/home/kali/Downloads/Qual/api/app.py`
  - `/home/kali/Downloads/Qual/intelligence/live_market_data.py`
- Response consistency and quality checks exist.
  - `/home/kali/Downloads/Qual/intelligence/response_enhancer.py`
  - `/home/kali/Downloads/Qual/intelligence/response_validator.py`

### Included (Partial)
- Psychology/sentiment is present but mostly proxy-based.
  - `/home/kali/Downloads/Qual/intelligence/sentiment_analyzer.py`
  - `/home/kali/Downloads/Qual/intelligence/agentic_rag/orchestrator.py`
- Confidence handling exists, but stress-time degradation logic can be stronger.
  - `/home/kali/Downloads/Qual/intelligence/response_schema.py`
  - `/home/kali/Downloads/Qual/intelligence/macro_engine.py`

### Not Yet Fully Implemented
- Full behavioral-finance engine (crowding/reflexivity/contagion as first-class state).
- Outcome calibration loop tied to realized market outcomes at scale.
- Portfolio construction layer (position sizing, risk budget, execution/slippage constraints).
- Robust shock-mode policy that auto-switches to risk-first behavior under external events.
- Durable user-specific playbook memory beyond session-level context.

---

## Priority Gaps to Close
1. Behavioral State Engine (panic/greed/crowding/reflexivity scoring).
2. Decision-to-Outcome calibration tracking (hit-rate, confidence calibration, regret).
3. External Shock Override mode with adaptive confidence and escalation.

These three upgrades create the biggest jump from "good analysis UI" to a genuinely differentiated analyst-grade system.
