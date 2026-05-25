"""
intelligence/agentic_rag/query_planner.py
------------------------------------------
Decomposes complex financial queries into focused sub-questions.

The planner uses a two-stage approach:
  1. LLM-based decomposition — understands financial relationships
  2. Deterministic rule-based fallback — keyword analysis when LLM fails

A simple factual question returns itself as the sole sub-question.
A complex multi-part question is split into 2-4 targeted sub-questions,
each of which can be independently retrieved and answered.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Keywords that signal a query needs decomposition
_COMPLEX_SIGNALS = [
    r"\b(compare|versus|vs\.?|between|relative to)\b",
    r"\b(and|also|additionally|furthermore)\b.{8,}",
    r"\b(impact|effect|affect).{5,}(and|also|plus)\b",
    r"\b(sector|asset class).{3,}(sector|asset class)\b",
    r"\b(short.?term|near.?term).{3,}(long.?term|medium.?term)\b",
    r"\?.*\?",  # Multiple question marks
]

# Financial concept expansion for query splitting
_MULTI_CONCEPT_PATTERNS = [
    (r"(.*)(inflation|cpi|pce)(.*)(growth|gdp)(.*)", ["inflation {1} {3}", "economic growth {2} {4}"]),
    (r"(.*)(equity|stock|equities)(.*)(bond|treasury|yield|rate)(.*)", ["equity markets {1} {3}", "rates and bonds {2} {4}"]),
    (r"(.*)(dollar|dxy|usd)(.*)(commodity|oil|gold|copper)(.*)", ["USD strength {1} {3}", "commodity impact {2} {4}"]),
]


class QueryPlanner:
    """
    Decomposes complex financial queries into focused sub-questions
    suitable for targeted retrieval and specialist agent analysis.
    """

    def __init__(self, llm_generate_fn: Any | None = None) -> None:
        """
        Args:
            llm_generate_fn: Callable(prompt) -> str. If None, uses
                intelligence.llm_provider.generate_text() lazily.
        """
        self._llm_fn = llm_generate_fn

    def _get_llm(self):
        if self._llm_fn is not None:
            return self._llm_fn
        from intelligence.llm_provider import generate_text

        def _call(prompt: str) -> str:
            text, _ = generate_text(
                prompt,
                temperature=0.0,
                max_tokens=200,
                timeout_sec=15.0,
            )
            return text

        return _call

    def _is_complex(self, question: str) -> bool:
        """
        V5.0: Nearly all queries should be decomposed for broad coverage.
        Only very short, single-word lookups are considered 'simple'.
        """
        q_lower = question.lower()
        # Always decompose if any complex signal is present
        for pattern in _COMPLEX_SIGNALS:
            if re.search(pattern, q_lower):
                return True
        # V5.0: Lower threshold — decompose anything with 4+ words
        word_count = len(question.split())
        return word_count >= 4

    def _deterministic_decompose(self, question: str) -> list[str]:
        """
        Rule-based fallback decomposition when LLM is unavailable.
        Splits on 'and', 'vs', conjunctions where both sides are meaty.
        """
        # Try splitting on explicit conjunctions
        patterns = [
            r"\?.*?(and|also|additionally)\s+",
            r"\band\b(?=\s.{15,})",  # "and" followed by at least 15 chars
            r"\bversus\b|\bvs\.?\b",
        ]
        for pat in patterns:
            parts = re.split(pat, question, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                left = parts[0].strip().rstrip(",;")
                right = parts[1].strip()
                if len(left) >= 10 and len(right) >= 10:
                    # Re-state as independent questions
                    if not left.endswith("?"):
                        left += "?"
                    if not right.endswith("?"):
                        right += "?"
                    return [left, right]
        # No split found: return as single question
        return [question]

    def _llm_decompose(self, question: str) -> list[str]:
        """Use LLM to intelligently decompose the query into 3-5 focused sub-questions."""
        prompt = (
            "You are a research planner for a financial intelligence engine. "
            "Your job is to decompose the user's question into 3 to 5 specific, "
            "independent sub-questions that can each be searched and answered separately.\n\n"
            "Rules:\n"
            "1. You MUST produce at least 3 sub-questions. Maximum 5.\n"
            "2. Each sub-question must be self-contained (no pronouns like 'it', 'they').\n"
            "3. Preserve all time references (e.g. 'last quarter', '2024').\n"
            "4. Each sub-question must be directly answerable from financial data or news.\n"
            "5. Cover DIFFERENT ANGLES of the topic: macro, sector, geopolitical, company-level.\n"
            "6. If the original question is simple, EXPAND it into related angles.\n"
            "7. Output ONLY the sub-questions, one per line, no numbering, no explanation.\n\n"
            f"Question: {question}\n\n"
            "Sub-questions:"
        )
        try:
            llm = self._get_llm()
            raw = llm(prompt).strip()
            lines = [
                line.strip().lstrip("-•1234567890.)").strip()
                for line in raw.splitlines()
                if line.strip()
            ]
            # Filter: each sub-question must be meaningful and different from others
            valid: list[str] = []
            seen: set[str] = set()
            for line in lines:
                if len(line) >= 8 and line.lower() not in seen:
                    if not line.endswith("?"):
                        line += "?"
                    valid.append(line)
                    seen.add(line.lower()[:60])
            if 1 <= len(valid) <= 6:
                return valid
        except Exception as exc:
            logger.warning("[QueryPlanner] LLM decomposition failed: %s", exc)
        return []

    def decompose(self, question: str) -> list[str]:
        """
        Decompose a question into focused sub-questions.

        Returns a list of 1-4 sub-questions. If the question is simple,
        returns [question] unchanged.
        """
        if not question or len(question.strip()) < 5:
            return [question]

        # Simple questions don't need decomposition
        if not self._is_complex(question):
            logger.debug("[QueryPlanner] Simple question — no decomposition needed.")
            return [question]

        # Try LLM decomposition first
        sub_qs = self._llm_decompose(question)
        if sub_qs and len(sub_qs) > 1:
            logger.info(
                "[QueryPlanner] LLM decomposed into %d sub-questions.", len(sub_qs)
            )
            return sub_qs[:5]  # Cap at 5 for deep research coverage

        # Fallback: deterministic split
        sub_qs = self._deterministic_decompose(question)
        logger.info(
            "[QueryPlanner] Deterministic decomposed into %d sub-questions.", len(sub_qs)
        )
        return sub_qs
