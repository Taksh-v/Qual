"""
intelligence/analyst_agents.py
-------------------------------
V5.0 Stateless Worker Agents for the Agent Orchestration Engine.

Each agent is a single-responsibility, stateless function that:
  - Receives a task (query, text, data)
  - Performs its job
  - Returns a standardized AgentOutput(status, payload, confidence, tokens)

Agents never call other agents. Only the Orchestrator calls agents.

Available Agents:
  - run_search_agent: Retrieves context chunks from FAISS/BM25 for a sub-query.
  - run_summarizer_agent: Condenses raw text into query-relevant facts.
  - run_analyst_agent: Synthesizes all summaries into a final institutional report.
"""

import logging
import time
from typing import Any

from intelligence.agentic_rag.agent_state import AgentOutput

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.40  # Minimum confidence to pass filtering
MAX_RETRIES = 2  # Retries for network-bound agents


# ── Helper: LLM Call with Retry ───────────────────────────────────────────────

def _llm_generate_with_retry(
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 500,
    timeout_sec: float = 45.0,
    retries: int = MAX_RETRIES,
) -> tuple[str, str]:
    """
    Call the LLM provider chain with automatic retries.
    Returns (text, provider_name).
    """
    from intelligence.llm_provider import generate_text
    last_error = None
    for attempt in range(retries + 1):
        try:
            text, provider = generate_text(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_sec=timeout_sec,
            )
            return text, provider
        except Exception as exc:
            last_error = exc
            logger.warning("[LLM Retry] Attempt %d failed: %s", attempt + 1, exc)
            if attempt < retries:
                import asyncio
                try:
                    asyncio.get_event_loop()
                except RuntimeError:
                    pass
                time.sleep(0.5 * (attempt + 1))  # Simple backoff
    raise RuntimeError(f"LLM generation failed after {retries + 1} attempts: {last_error}")


# ── Agent 1: Search Agent ─────────────────────────────────────────────────────


async def run_search_agent(
    sub_query: str,
    tool_registry: Any,
) -> AgentOutput:
    """
    Search Agent: Retrieves context chunks for a single sub-query.

    Uses the ToolRegistry's semantic_search tool (FAISS).
    Returns an AgentOutput where `brief` contains the concatenated chunk texts,
    and `confidence` reflects the quality/quantity of retrieved results.

    This agent is stateless and runs in parallel with other Search Agents.
    """
    import asyncio
    t0 = time.time()
    agent_name = "SearchAgent"

    search_tool = tool_registry.get("semantic_search")
    if not search_tool:
        return AgentOutput(
            agent_name=agent_name,
            brief="",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=0,
        )

    # Execute search tools concurrently
    async def _run_semantic():
        for attempt in range(MAX_RETRIES + 1):
            try:
                res = await asyncio.get_event_loop().run_in_executor(None, search_tool.run, sub_query)
                if res.success and res.data: return res
            except Exception:
                if attempt < MAX_RETRIES: await asyncio.sleep(0.5*(attempt+1))
        return None

    async def _run_graph():
        graph_tool = tool_registry.get("graph_search")
        if graph_tool:
            try:
                return await asyncio.get_event_loop().run_in_executor(None, graph_tool.run, sub_query)
            except Exception: pass
        return None

    semantic_res, graph_res = await asyncio.gather(_run_semantic(), _run_graph(), return_exceptions=True)

    elapsed = int((time.time() - t0) * 1000)

    if semantic_res and hasattr(semantic_res, 'success') and semantic_res.success and semantic_res.data:
        chunks = semantic_res.data if isinstance(semantic_res.data, list) else []
        payload_parts = []
        
        # Inject causal chains if found
        if graph_res and hasattr(graph_res, 'success') and graph_res.success and graph_res.data.get("causal_chains"):
            chains = graph_res.data["causal_chains"]
            chain_str = "\n".join(chains)
            payload_parts.append(f"[CAUSAL GRAPH CHAINS]\n{chain_str}\n")
            
        for i, c in enumerate(chunks[:6]):
            title = c.get("metadata", {}).get("title", "Untitled")
            source = c.get("metadata", {}).get("source", "")
            date = c.get("metadata", {}).get("date", "")
            text = c.get("text", "")[:400]
            payload_parts.append(f"[CHUNK {i+1}] {title} | {source} | {date}\n{text}")
            
        brief = "\n\n".join(payload_parts)
        confidence = min(0.95, 0.30 + 0.15 * len(chunks))
        tokens = len(brief.split())

        return AgentOutput(
            agent_name=agent_name,
            brief=brief,
            confidence=confidence,
            status="success",
            tokens=tokens,
            sub_query=sub_query,
            elapsed_ms=elapsed,
        )
    else:
        return AgentOutput(
            agent_name=agent_name,
            brief=f"Search failed: {last_error}",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=elapsed,
        )


# ── Agent 1B: Web Search Fallback Agent (V5.1 CRAG) ───────────────────────────


async def run_web_search_agent(
    sub_query: str,
    tool_registry: Any,
) -> AgentOutput:
    """
    Web Search Agent: Fallback when local FAISS data is weak or missing.
    Queries the live internet and returns an AgentOutput.
    """
    import asyncio
    t0 = time.time()
    agent_name = "WebSearchAgent"

    search_tool = tool_registry.get("web_search")
    if not search_tool:
        return AgentOutput(
            agent_name=agent_name,
            brief="",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=0,
        )

    # Execute web search with retry
    last_error = None
    result = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, search_tool.run, sub_query
            )
            if result.success and result.data:
                break
            last_error = result.error if hasattr(result, 'error') else "No data returned"
        except Exception as exc:
            last_error = str(exc)
            logger.warning("[WebSearchAgent] Attempt %d failed for '%s': %s", attempt + 1, sub_query[:50], exc)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(0.5 * (attempt + 1))

    elapsed = int((time.time() - t0) * 1000)

    if result and result.success and result.data:
        chunks = result.data if isinstance(result.data, list) else []
        payload_parts = []
        for i, c in enumerate(chunks[:3]):
            title = c.get("metadata", {}).get("title", "Untitled")
            source = c.get("metadata", {}).get("source", "")
            text = c.get("text", "")[:600]
            payload_parts.append(f"[WEB CHUNK {i+1}] {title} | {source}\n{text}")
            
        brief = "\n\n".join(payload_parts)
        # Web search results get a solid confidence score since they are direct scrapes
        confidence = 0.85
        tokens = len(brief.split())

        return AgentOutput(
            agent_name=agent_name,
            brief=brief,
            confidence=confidence,
            status="success",
            tokens=tokens,
            sub_query=sub_query,
            elapsed_ms=elapsed,
        )
    else:
        return AgentOutput(
            agent_name=agent_name,
            brief=f"Web search failed: {last_error}",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=elapsed,
        )


# ── Agent 2: Summarizer Agent ────────────────────────────────────────────────


async def run_summarizer_agent(
    raw_text: str,
    original_query: str,
    sub_query: str,
) -> AgentOutput:
    """
    Summarizer Agent: Condenses raw search text into query-relevant facts.

    Takes raw chunk text and the original query. Extracts ONLY the facts
    that are directly relevant to answering the query. Does not analyze,
    conclude, or make recommendations.

    This agent is stateless and runs in parallel with other Summarizers.
    """
    import asyncio
    t0 = time.time()
    agent_name = "SummarizerAgent"

    if not raw_text or len(raw_text.strip()) < 20:
        return AgentOutput(
            agent_name=agent_name,
            brief="No content to summarize.",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=0,
        )

    prompt = (
        "You are a precision fact-extraction engine for an institutional research desk.\n"
        "Your ONLY job is to extract facts from the provided source text that are directly relevant "
        "to the user's query. Do NOT analyze, draw conclusions, or make recommendations.\n\n"
        "RULES:\n"
        "1. Extract only verifiable facts, numbers, dates, and named entities.\n"
        "2. Preserve specific data: percentages, dollar amounts, basis points, dates.\n"
        "3. Remove all opinions, speculation, and filler language.\n"
        "4. If the source text is irrelevant to the query, return: IRRELEVANT.\n"
        "5. Output a concise bulleted list. Maximum 8 bullets.\n"
        "6. Cite the source chunk using [Sx] at the end of each fact.\n\n"
        f"USER QUERY: {original_query}\n"
        f"SUB-QUESTION: {sub_query}\n\n"
        f"SOURCE TEXT:\n{raw_text[:2000]}\n\n"
        "EXTRACTED FACTS:"
    )

    try:
        text, provider = _llm_generate_with_retry(
            prompt,
            temperature=0.0,
            max_tokens=400,
            timeout_sec=35.0,
        )

        # Check if LLM flagged content as irrelevant
        if "IRRELEVANT" in text.upper() and len(text) < 30:
            return AgentOutput(
                agent_name=agent_name,
                brief="Content irrelevant to query.",
                confidence=0.1,
                status="success",
                tokens=len(text.split()),
                sub_query=sub_query,
                elapsed_ms=int((time.time() - t0) * 1000),
            )

        # Score confidence based on density of extracted facts
        fact_count = text.count("- ") + text.count("• ") + text.count("* ")
        has_numbers = any(c.isdigit() for c in text)
        confidence = 0.50
        if fact_count >= 3:
            confidence += 0.20
        if has_numbers:
            confidence += 0.15
        confidence = min(confidence, 0.95)

        return AgentOutput(
            agent_name=agent_name,
            brief=text.strip(),
            confidence=confidence,
            status="success",
            tokens=len(text.split()),
            sub_query=sub_query,
            elapsed_ms=int((time.time() - t0) * 1000),
        )

    except Exception as exc:
        logger.error("[SummarizerAgent] Failed for sub_query '%s': %s", sub_query[:50], exc)
        return AgentOutput(
            agent_name=agent_name,
            brief=f"Summarization failed: {exc}",
            confidence=0.0,
            status="error",
            sub_query=sub_query,
            elapsed_ms=int((time.time() - t0) * 1000),
        )


# ── Agent 3: Analyst Agent (Final Synthesizer) ───────────────────────────────


async def run_analyst_agent(
    summaries: list[AgentOutput],
    data_gaps: list[str],
    original_query: str,
    live_indicators: dict[str, float] | None = None,
    geography: str = "US",
    horizon: str = "MEDIUM_TERM",
    conversation_context: str = "",
) -> AgentOutput:
    """
    Analyst Agent: The final synthesizer. Sees ALL successfully filtered summaries
    and produces the comprehensive institutional report.

    CRITICAL: The Analyst receives a `data_gaps` list. For every gap, the Analyst
    MUST explicitly acknowledge the missing data and MUST NOT fabricate an answer.

    This agent runs ONCE, at the end of the pipeline, after all parallel work is done.
    """
    t0 = time.time()
    agent_name = "AnalystAgent"

    # Build the combined evidence payload with Numerical Citation Mapping
    valid_summaries = [s for s in summaries if s.status == "success" and s.confidence >= CONFIDENCE_THRESHOLD]
    
    evidence_parts = []
    source_mapping = []
    
    for i, s in enumerate(valid_summaries):
        citation_id = i + 1
        evidence_parts.append(f"### [Source {citation_id}]: {s.sub_query} (confidence: {s.confidence:.0%})\n{s.brief}")
        source_mapping.append(f"[{citation_id}]: {s.sub_query}")
        
    evidence_block = "\n\n".join(evidence_parts) or "No usable summaries available."
    sources_str = "\n".join(source_mapping) or "No usable sources available."

    # Format live indicators as a structured Markdown table
    raw_indicators = list((live_indicators or {}).items())[:12]
    if raw_indicators:
        table_rows = ["| Indicator | Value |", "|:----------|------:|"]
        for k, v in raw_indicators:
            table_rows.append(f"| {k} | {v:.2f} |")
        indicators_str = "\n".join(table_rows)
    else:
        indicators_str = "No live market data available."

    # Build the critical data gaps warning
    gaps_block = ""
    if data_gaps:
        gap_items = "\n".join(f"  - ⚠️ {gap}" for gap in data_gaps)
        gaps_block = (
            f"\n\n🚨 CRITICAL DATA GAPS (DO NOT HALLUCINATE ANSWERS FOR THESE):\n"
            f"{gap_items}\n"
            f"You MUST explicitly acknowledge each gap in your report and state what is unknown.\n"
        )

    from intelligence.prompt_templates import MACRO_INTELLIGENCE_ENGINE_TEMPLATE
    prompt = MACRO_INTELLIGENCE_ENGINE_TEMPLATE.format(
        question=original_query,
        geography=geography,
        horizon=horizon,
        indicators_str=indicators_str,
        agent_briefs=evidence_block,
        sources_str=sources_str,
    ) + gaps_block + "\n\nBegin your response immediately with `<thinking>`."

    # Inject conversation memory if available
    if conversation_context:
        prompt = prompt + f"\n\n{conversation_context}\n"

    try:
        from intelligence.llm_provider import generate_text
        text, provider = generate_text(
            prompt,
            temperature=0.20,
            max_tokens=2000,
            timeout_sec=120.0,
        )

        return AgentOutput(
            agent_name=agent_name,
            brief=text.strip(),
            confidence=0.85,
            status="success",
            tokens=len(text.split()),
            sub_query=original_query,
            elapsed_ms=int((time.time() - t0) * 1000),
        )

    except Exception as exc:
        logger.error("[AnalystAgent] Synthesis failed: %s", exc)
        return AgentOutput(
            agent_name=agent_name,
            brief=f"Final synthesis failed: {exc}",
            confidence=0.0,
            status="error",
            sub_query=original_query,
            elapsed_ms=int((time.time() - t0) * 1000),
        )


from typing import AsyncIterator

async def run_analyst_agent_stream(
    summaries: list[AgentOutput],
    data_gaps: list[str],
    original_query: str,
    live_indicators: dict[str, float] | None = None,
    geography: str = "US",
    horizon: str = "MEDIUM_TERM",
    conversation_context: str = "",
) -> AsyncIterator[str]:
    """
    True SSE Double-Streaming generation for the Analyst Agent.
    Yields tokens as they arrive from the LLM provider.
    """
    valid_summaries = [s for s in summaries if s.status == "success" and s.confidence >= CONFIDENCE_THRESHOLD]
    
    evidence_parts = []
    source_mapping = []
    for i, s in enumerate(valid_summaries):
        citation_id = i + 1
        evidence_parts.append(f"### [Source {citation_id}]: {s.sub_query} (confidence: {s.confidence:.0%})\n{s.brief}")
        source_mapping.append(f"[{citation_id}]: {s.sub_query}")
        
    evidence_block = "\n\n".join(evidence_parts) or "No usable summaries available."
    sources_str = "\n".join(source_mapping) or "No usable sources available."

    raw_indicators = list((live_indicators or {}).items())[:12]
    if raw_indicators:
        table_rows = ["| Indicator | Value |", "|:----------|------:|"]
        for k, v in raw_indicators:
            table_rows.append(f"| {k} | {v:.2f} |")
        indicators_str = "\n".join(table_rows)
    else:
        indicators_str = "No live market data available."

    gaps_block = ""
    if data_gaps:
        gap_items = "\n".join(f"  - ⚠️ {gap}" for gap in data_gaps)
        gaps_block = (
            f"\n\n🚨 CRITICAL DATA GAPS (DO NOT HALLUCINATE ANSWERS FOR THESE):\n"
            f"{gap_items}\n"
            f"You MUST explicitly acknowledge each gap in your report and state what is unknown.\n"
        )

    from intelligence.prompt_templates import MACRO_INTELLIGENCE_ENGINE_TEMPLATE
    prompt = MACRO_INTELLIGENCE_ENGINE_TEMPLATE.format(
        question=original_query,
        geography=geography,
        horizon=horizon,
        indicators_str=indicators_str,
        agent_briefs=evidence_block,
        sources_str=sources_str,
    ) + gaps_block + "\n\nBegin your response immediately with `<thinking>`."

    if conversation_context:
        prompt = prompt + f"\n\n{conversation_context}\n"

    from intelligence.llm_provider import generate_text_stream
    import asyncio
    
    loop = asyncio.get_event_loop()
    
    # We use a standard List instead of an asyncio.Queue because generator iteration in a thread
    # doesn't easily await queue.put. Instead, we run the generator to completion in a thread 
    # while the async loop pulls from a thread-safe deque or queue.
    # The safest way is to use a thread-safe Queue and loop.call_soon_threadsafe.
    
    queue = asyncio.Queue()
    
    def _producer():
        try:
            for token in generate_text_stream(
                prompt,
                temperature=0.20,
                max_tokens=2000,
                timeout_sec=120.0,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, token)
        except Exception as e:
            logger.error("[AnalystAgentStream] Error: %s", e)
            loop.call_soon_threadsafe(queue.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    import threading
    t = threading.Thread(target=_producer, daemon=True)
    t.start()
    
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            # Only yield error if we haven't yielded anything yet, otherwise swallow or yield as string
            yield f"\n\n*(Error generating completion: {item})*"
            break
        yield item


# These stubs ensure the legacy RAG path doesn't crash. The V5.0 orchestrator
# handles all real agent work via the new stateless agents above.


def run_fundamental_analyst(context: str = "", question: str = "", **kwargs: Any) -> dict:
    """Legacy stub. Returns empty analysis dict for backward compatibility."""
    return {"analysis": "", "confidence": 0.0}


def run_sentiment_analyst(context: str = "", question: str = "", **kwargs: Any) -> dict:
    """Legacy stub. Returns empty analysis dict for backward compatibility."""
    return {"analysis": "", "confidence": 0.0}


def run_portfolio_manager(context: str = "", question: str = "", **kwargs: Any) -> dict:
    """Legacy stub. Returns empty analysis dict for backward compatibility."""
    return {"analysis": "", "confidence": 0.0}

