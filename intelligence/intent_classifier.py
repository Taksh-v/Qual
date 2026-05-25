import logging
import json
from typing import Dict, Any
from intelligence.llm_provider import generate_text

logger = logging.getLogger(__name__)

INTENT_PROMPT = """
You are a senior macro strategist's intake assistant. 
Classify the user's query into one of four intent categories for formatting the response:

1. DYNAMIC: The user is asking for a specific format (e.g. "give me a table", "list exactly 5 reasons") or making an open-ended conversational request that requires adaptive formatting rather than a rigid institutional report.
2. ADVISORY: The user is asking for general macro advice or "what does this mean for me" (without specifying format).
3. DETAILED: The user explicitly states they want a full or deep structural analysis.
4. BRIEF: The user just wants a very short alert or single number.

Respond ONLY with a JSON object:
{{"intent": "DYNAMIC" | "ADVISORY" | "DETAILED" | "BRIEF", "reasoning": "1 sentence explanation"}}

Query: {query}
"""

class IntentClassifier:
    def classify(self, query: str) -> str:
        """
        Classifies the query intent to determine the output format.
        """
        if not query or len(query) < 10:
            return "BRIEF"

        # Heuristics for speed
        q_lower = query.lower()
        if any(w in q_lower for w in ["table", "list", "format", "compare", "summary", "bullet", "dynamic"]):
            return "DYNAMIC"
        if any(w in q_lower for w in ["tell me about", "what is happening", "should i", "opinion", "advise"]):
            return "ADVISORY"
        if any(w in q_lower for w in ["deep dive", "research", "structural", "analysis", "full report", "detailed"]):
            return "DETAILED"

        # LLM fallback for nuanced queries
        try:
            prompt = INTENT_PROMPT.format(query=query)
            response, provider = generate_text(prompt, temperature=0.0, max_tokens=100)
            
            if "{" in response:
                response = response[response.index("{"):response.rindex("}")+1]
            
            data = json.loads(response)
            intent = data.get("intent", "DYNAMIC").upper()
            logger.info(f"Intent Classifier ({provider}): {intent} | {data.get('reasoning')}")
            
            if intent in ["DYNAMIC", "ADVISORY", "DETAILED", "BRIEF"]:
                return intent.lower()
            return "dynamic"
        except Exception as e:
            logger.error(f"Failed to classify intent: {e}")
            return "dynamic" # Default to dynamic/adaptive
