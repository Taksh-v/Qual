"""
question_classifier.py
-----------------------
Classifies the user's macro question to:
  1. Determine the PRIMARY question type (drives prompt emphasis)
  2. Extract any mentioned assets, geographies, or time horizons
  3. Set analysis depth (quick read vs. deep dive)
  4. Flag if the question contains embedded data to extract

Question types:
  RATE_POLICY     — Fed / ECB / BOJ / central bank questions
  INFLATION       — CPI, PCE, price dynamics
  GROWTH          — GDP, recession, PMI, labor market
  GEOPOLITICAL    — Wars, sanctions, trade wars, elections
  CURRENCY        — FX, dollar, EM currencies
  CREDIT          — Spreads, defaults, banking, leverage
  COMMODITY       — Oil, gold, metals, food
  EQUITY          — Stock market, sectors, valuations
  MULTI_FACTOR    — Broad macro / portfolio strategy questions
  DATA_PASTE      — User has pasted in actual data/numbers
"""

import re
from typing import Optional


QUESTION_TYPE_PATTERNS = {
    "RATE_POLICY": [
        r"\b(fed|federal reserve|ecb|boj|central bank|rate cut|rate hike|monetary policy|fomc|pivot)\b"
    ],
    "INFLATION": [
        r"\b(inflation|cpi|pce|core|deflation|stagflation|price|purchasing power)\b"
    ],
    "GROWTH": [
        r"\b(gdp|recession|growth|pmi|manufacturing|labor|jobs|unemployment|consumer spending)\b"
    ],
    "GEOPOLITICAL": [
        r"\b(war|conflict|sanction|election|trade war|tariff|geopolit|ukraine|china|taiwan|oil embargo)\b"
    ],
    "CURRENCY": [
        r"\b(dollar|dxy|fx|forex|currency|yen|euro|pound|yuan|EM|emerging market|devaluation)\b"
    ],
    "CREDIT": [
        r"\b(credit|spread|default|high yield|hy|investment grade|ig|leverage|debt|bank|financial stress)\b"
    ],
    "COMMODITY": [
        r"\b(oil|gold|silver|copper|commodity|metal|energy|wti|brent|natural gas|agriculture)\b"
    ],
    "CRYPTO": [
        r"\b(crypto|bitcoin|btc|eth|ethereum|solana|sol|token|blockchain|defi|stablecoin)\b"
    ],
    "COMPANY": [
        r"\b(company|corporate|ticker|quarterly|8-k|filing|expansion|merger|acquisition|ceo|cfo|management|msme|sme|small.?cap|mid.?cap|micro.?cap|earnings|guidance|outlook)\b",
        r"\b(nvidia|tesla|microsoft|apple|google|alphabet|amazon|meta|metaverse|netflix|broadcom|amd|intel|tsmc|disney|boeing|air india|indigo)\b",
        r"\b[A-Z]{3,5}\b"  # Tickers
    ],
    "EQUITY": [
        r"\b(market|s&p|nasdaq|nifty|sensex|index|indices|valuation|pe ratio|sector|rally|sell.?off)\b"
    ],
}

GEOGRAPHY_PATTERNS = {
    "US":     r"\b(us|usa|united states|america|american|fed|dollar)\b",
    "EU":     r"\b(europe|eu|eurozone|ecb|euro|germany|france|italy)\b",
    "CHINA":  r"\b(china|chinese|pboc|yuan|rmb|beijing)\b",
    "JAPAN":  r"\b(japan|japanese|boj|yen|tokyo)\b",
    "EM":     r"\b(emerging market|em|india|brazil|turkey|mexico)\b",
    "GLOBAL": r"\b(global|world|international|cross.?border)\b",
}

TIME_HORIZON_PATTERNS = {
    "SHORT_TERM":  r"\b(now|today|this week|near.?term|short.?term|1.?month|tactical)\b",
    "MEDIUM_TERM": r"\b(quarter|3.?month|6.?month|medium.?term|h1|h2|next year)\b",
    "LONG_TERM":   r"\b(long.?term|multi.?year|secular|structural|decade|5.?year|10.?year)\b",
}

DATA_INDICATORS = [
    r"\d+\.?\d*\s*%",          # any percentage
    r"\d+\.?\d*\s*bps?",       # basis points
    r"\$\d+",                  # dollar amounts
    r"\b(at|to|from)\s+\d+",  # "at X", "to X" with numbers
]


def classify_question(question: str) -> dict:
    """
    Classify a macro question and return a structured analysis profile.
    """
    q = question.lower()

    # Detect primary question types (can be multiple)
    detected_types = []
    for qtype, patterns in QUESTION_TYPE_PATTERNS.items():
        for pattern in patterns:
            # Special case for Tickers: must be uppercase in original question
            if pattern == r"\b[A-Z]{3,5}\b":
                if re.search(pattern, question): # No IGNORECASE here
                    detected_types.append(qtype)
                    break
            elif re.search(pattern, q, re.IGNORECASE):
                detected_types.append(qtype)
                break

    if not detected_types:
        detected_types = ["MULTI_FACTOR"]

    primary_type = detected_types[0]

    # Detect geographies
    geographies = []
    for geo, pattern in GEOGRAPHY_PATTERNS.items():
        if re.search(pattern, q, re.IGNORECASE):
            geographies.append(geo)
    if not geographies:
        geographies = ["US"]  # default to US

    # Detect time horizon
    time_horizon = "MEDIUM_TERM"  # default
    for horizon, pattern in TIME_HORIZON_PATTERNS.items():
        if re.search(pattern, q, re.IGNORECASE):
            time_horizon = horizon
            break

    # Detect if user pasted data
    contains_data = any(re.search(p, question) for p in DATA_INDICATORS)
    if contains_data:
        detected_types.append("DATA_PASTE")

    # Set analysis depth
    has_msme = bool(re.search(r"\b(msme|sme|small.?cap|mid.?cap|micro.?cap)\b", q))
    has_high_fidelity = any(t in detected_types for t in ["CRYPTO", "COMPANY", "CURRENCY"]) or has_msme
    is_broad = len(detected_types) >= 3 or "MULTI_FACTOR" in detected_types or has_high_fidelity
    depth = "DEEP" if is_broad else "FOCUSED"

    return {
        "primary_type": primary_type,
        "all_types": list(set(detected_types)),
        "geographies": geographies,
        "time_horizon": time_horizon,
        "contains_data": contains_data,
        "depth": depth,
        "has_msme": has_msme,
    }


def get_emphasis_instruction(classification: dict) -> str:
    """
    Returns a 1-2 line emphasis instruction to prepend to prompts
    based on question classification, sharpening the LLM's focus.
    """
    ptype = classification["primary_type"]
    geos = ", ".join(classification["geographies"])
    horizon = classification["time_horizon"].replace("_", " ").lower()
    depth = classification["depth"]

    emphasis_map = {
        "RATE_POLICY":   "Focus on monetary transmission, forward guidance, and rate-sensitive asset classes.",
        "INFLATION":     "Focus on inflation dynamics, breakevens, real rates, and pricing power across sectors.",
        "GROWTH":        "Focus on leading indicators, PMI trends, consumer/business cycle, and growth-sensitive assets.",
        "GEOPOLITICAL":  "Focus on supply chain disruption, energy risk, risk premium, and geopolitical hedges.",
        "CURRENCY":      "Focus on relative monetary policy, current account dynamics, and EM contagion risk.",
        "CREDIT":        "Focus on credit cycle, leverage, spread dynamics, and contagion to equity.",
        "COMMODITY":     "Focus on supply/demand fundamentals, dollar impact, and commodity-linked sectors.",
        "EQUITY":        "Focus on earnings trajectory, valuation vs. rates, and factor rotation.",
        "CRYPTO":        "Focus on risk-appetite correlation, dollar channel, and digital asset liquidity.",
        "COMPANY":       "Focus on idiosyncratic drivers: expansion, earnings quality, and management guidance.",
        "MULTI_FACTOR":  "This is a broad macro question. Cover all major asset classes with equal depth.",
    }

    base = emphasis_map.get(ptype, "Analyze comprehensively.")
    if classification.get("has_msme"):
        base = "Analyze impact on MSMEs and small-cap firms separately from large MNCs. Focus on margin sensitivity and lack of hedging."

    return (
        f"FOCUS AREA: {ptype} | GEOGRAPHY: {geos} | HORIZON: {horizon} | DEPTH: {depth}\n"
        f"EMPHASIS: {base}"
    )


if __name__ == "__main__":
    questions = [
        "What happens to equities if the Fed cuts rates in March?",
        "Is a US recession likely given current PMI and credit spreads at 520bps?",
        "How does the Ukraine conflict affect European energy and EUR/USD?",
        "CPI came in at 3.7%, core at 4.1%, what does this mean for the 10Y?",
    ]
    for q in questions:
        result = classify_question(q)
        print(f"Q: {q}")
        print(f"   {result}")
        print(f"   {get_emphasis_instruction(result)}\n")