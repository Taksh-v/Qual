"""
tests/test_v4_2_format.py
--------------------------------
Simulates a V4.2 'Macro Intelligence Engine' response to verify the new 
structured data layer and transmission channel rendering.
"""

import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from intelligence.bloomberg_formatter import BloombergFormatter

def test_v4_2_rendering():
    formatter = BloombergFormatter()
    
    # Mock V4.2 LLM response text
    answer = """
1. **BLUF (Bottom-Line Upfront):** 
The escalation of Middle East conflict is set to drive crude prices above $95/bbl, creating a systemic inflation shock that will force the Fed to maintain a restrictive posture. We expect 10Y yields to break 4.5% on this news.

2. **STRUCTURED DATA LAYER:** 
- **EVENTS:** 
  | ID | Headline | Market Impact | Risk Signal [Sx] |
  |:---|:---|:---|:---|
  | [E1] | Hormuz Transit Delay | ▲ Oil +3% | Systemic Supply Shock [S1] |
  | [E2] | US-Iran Sanction Talk | ▲ DXY +0.5% | Geopolitical Escalation [S2] |

- **MARKET DATA:** 
  | Instrument | Value | Direction (▲/▼/●) | Context |
  |:---|:---|:---|:---|
  | S&P 500 | 4850 | ▼ | Contagion from Energy Costs |
  | WTI Crude | $86.40 | ▲ | Supply Chain Friction |
  | DXY | 103.5 | ▲ | Safe Haven Inflow |

- **MACRO INDICATORS:** 
  | Metric | Current | Prev | Implication |
  |:---|:---|:---|:---|
  | Core CPI | 3.8% | 3.6% | Sticky Inflation Pressure |
  | 10Y Yield | 4.35% | 4.15% | Term Premium Re-pricing |

3. **SCENARIO PROBABILITY MATRIX:**
| Scenario | Prob | Trigger Event | Asset Impact |
|:---|:---|:---|:---|
| Base (55%) | Sustained Conflict | Brent > $100 | S&P -5% |
| Bull (25%) | Ceasefire Deal | De-escalation | S&P +3% |
| Bear (20%) | Regional War | Blockade | S&P -15% |

4. **CAUSAL TRANSMISSION ANALYSIS:**
`Strait Closure` \u2192 `Energy Transmission Channel` \u2192 `Input Cost Spike` \u2192 `Restrictive Policy Response` \u2192 `Asset Valuation Compression`.

5. **GEOPOLITICAL & SYSTEMIC RISK:**
High risk of spillover into Lebanese-Israeli theater. Shipping premiums (War Risk) currently at 3-year highs.

6. **INSTITUTIONAL POSITIONING & STRATEGY:**
- **Instrument:** XLE (Energy Select Sector SPDR)
- **Action:** Long
- **Confidence:** 85%
- **Rationale:** Direct proxy for supply-side energy inflation.
- **Entry/Exit Levels:** Entry $85, Target $105, Stop $78.

7. **CONFIDENCE & UNCERTAINTY:** 
High confidence in direction; low confidence in exact escalation timing due to black-box diplomatic channels.
"""

    mock_indicators = {
        "sp500": 4850.0,
        "oil_wti": 86.40,
        "dxy": 103.5,
        "vix": 22.0,
        "yield_10y": 4.35
    }

    # Format the note
    output = formatter.morning_note(
        answer=answer,
        indicators=mock_indicators,
        question="What is the market impact of the Strait of Hormuz conflict?",
        geography="Global",
        horizon="Short-term"
    )

    print(output)

if __name__ == "__main__":
    test_v4_2_rendering()
