import logging
from typing import Dict, Any
from intelligence.llm_provider import generate_text
import json # needed for the class

logger = logging.getLogger(__name__)

SCORER_PROMPT = """
You are an institutional-grade Strategy Triage Agent. 
Assess the following content and provide a score from 0 to 10 based on Phase 1: SIGNAL TRIAGE.

SCORING CRITERIA:
- SOURCE CREDIBILITY (0-3 pts): Primary/Regulatory = 3, Tier-1 (Bloomberg/Reuters) = 2, Unverified/Rumor = 0.
- EVENT SCALE (0-4 pts): Systemic/SIFI (Macro, Major Bank) = 4, Sectoral = 2, Single Entity/Minor = 1.
- PROPAGATION SPEED (0-3 pts): Contagion risk is high/immediate = 3, Slow/Localized = 1.

0-2: Noise. Routine fluff or unverified rumors.
3-5: Relevant Context. Useful but not a major market mover today.
6-8: High Signal. Confirmed sectoral or systemic event with clear transmission channels.
9-10: Critical. Immediate systemic risk, policy pivot, or major bank failure.

CRITICAL INSTRUCTION: If the content describes FINANCIAL STRESS, LIQUIDITY CRISES, or MARGIN SQUEEZES (especially for HDFC or MSMEs), give it a HIGH score (minimum 7).

CONTENT:
{content}

Respond ONLY with a JSON object:
{{"score": float, "reasoning": "1 sentence explanation"}}
"""

class ImportanceScorer:
    def score_content(self, text: str, title: str = "") -> float:
        """
        Scores the importance of a piece of news or filing.
        """
        # Truncate content to avoid token overflow
        sample = (title + "\n" + text)[:2000]
        prompt = SCORER_PROMPT.format(content=sample)
        
        try:
            response, provider = generate_text(prompt, temperature=0.0, max_tokens=150)
            
            # Extract JSON
            if "{" in response:
                response = response[response.index("{"):response.rindex("}")+1]
            
            data = json.loads(response)
            score = float(data.get("score", 5.0))
            logger.info(f"Importance Scorer ({provider}): Score {score} | {data.get('reasoning')}")
            return score
        except Exception as e:
            logger.error(f"Failed to score content: {e}")
            return 5.0 # Default to neutral
