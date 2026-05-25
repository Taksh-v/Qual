"""
intelligence/agentic_rag/orchestrator_v2.py
-------------------------------------------
V7.0 Agent Orchestration Engine.

Migrated to a LangGraph-style StateMachineGraph architecture for infinite stability
and true double-streaming support.

Nodes:
  - planner
  - searcher
  - summarizer  
  - critic
  - synthesizer

The orchestrated state machine yields AgentEvents asynchronously.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .agent_state import AgentState, AgentOutput, ToolCall
from .query_planner import QueryPlanner
from .tool_registry import ToolRegistry, build_default_registry
from .reflection_engine import ReflectionEngine
from .state_machine import StateMachineGraph, END
from intelligence.admin_logger import admin_logger

logger = logging.getLogger(__name__)

# V5.0 Confidence threshold for filtering
CONFIDENCE_THRESHOLD = 0.40

@dataclass
class AgentEvent:
    stage: str
    data: dict[str, Any] = field(default_factory=dict)
    agent_name: str = ""
    iteration: int = 0
    elapsed_ms: int = 0

    def to_sse(self) -> str:
        payload = {
            "stage": self.stage,
            "agent_name": self.agent_name,
            "iteration": self.iteration,
            "elapsed_ms": self.elapsed_ms,
            **self.data,
        }
        return f"event: {self.stage}\ndata: {json.dumps(payload)}\n\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "agent_name": self.agent_name,
            "iteration": self.iteration,
            "elapsed_ms": self.elapsed_ms,
            **self.data,
        }


class AgenticOrchestrator:
    def __init__(self, max_iterations: int = 2, registry: ToolRegistry | None = None) -> None:
        self.max_iterations = max_iterations
        self.registry = registry or build_default_registry()
        self.planner = QueryPlanner()
        self.reflection = ReflectionEngine()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateMachineGraph:
        graph = StateMachineGraph()
        
        graph.add_node("planner", self._node_planner)
        graph.add_node("searcher", self._node_searcher)
        graph.add_node("summarizer", self._node_summarizer)
        graph.add_node("critic", self._node_critic)
        graph.add_node("synthesizer", self._node_synthesizer)
        graph.add_node("audit", self._node_audit)
        graph.add_node("learn", self._node_learn)

        graph.set_entry_point("planner")
        
        graph.add_edge("planner", "searcher")
        graph.add_edge("searcher", "summarizer")
        graph.add_edge("summarizer", "critic")
        
        def critic_router(state: AgentState) -> str:
            # If no context gaps or max iterations reached, move to synthesizer
            if not state.gaps or state.iteration >= state.max_iterations:
                return "synthesizer"
            return "searcher"

        graph.add_conditional_edges("critic", critic_router, {
            "searcher": "searcher",
            "synthesizer": "synthesizer"
        })
        
        graph.add_edge("synthesizer", "audit")

        def audit_router(state: AgentState) -> str:
            # If final audit fails and we have iterations left, try fixing it
            if state.gaps and state.iteration < state.max_iterations:
                return "searcher"
            # If audit passes, proceed to learning (Phase 5) before ending
            return "learn"

        graph.add_conditional_edges("audit", audit_router, {
            "searcher": "searcher",
            "learn": "learn"
        })
        
        graph.add_edge("learn", END)
        return graph

    # ── GRAPH NODES ───
    
    async def _node_planner(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        state.mark_stage("planning")
        yield AgentEvent(stage="planning", data={"message": "Decomposing query into focused sub-questions..."}, elapsed_ms=state.elapsed_ms())
        
        trace_id = admin_logger.start_trace(state.question)
        state.trace_id = trace_id # Storing temporarily in state if needed or we use a weakref 

        try:
            sub_qs = await asyncio.get_event_loop().run_in_executor(None, self.planner.decompose, state.question)
            state.sub_questions = sub_qs
        except Exception as exc:
            state.sub_questions = [state.question]
            logger.warning("[Orchestrator] Planning failed, using original query: %s", exc)

        yield AgentEvent(stage="planning", data={"sub_questions": state.sub_questions, "count": len(state.sub_questions)}, elapsed_ms=state.elapsed_ms())

    async def _node_searcher(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        state.mark_stage("search")
        
        # If it's the first iteration, we search standard sub_qs.
        # If >0 iteration, we search gap_queries.
        queries_to_search = state.sub_questions if state.iteration == 0 else state.gap_queries
        
        yield AgentEvent(stage="search", data={"message": f"Dispatching Search Agents for {len(queries_to_search)} queries (Iteration {state.iteration})..."}, elapsed_ms=state.elapsed_ms())
        
        from intelligence.analyst_agents import run_search_agent, run_web_search_agent
        
        # Determine fallback logic - use web search directly for gap queries (iter > 0)
        # because the internal index already failed to provide sufficient data.
        if state.iteration > 0:
            yield AgentEvent(stage="search", data={"message": f"Aggressive Web Search for {len(queries_to_search)} context gaps..."}, elapsed_ms=state.elapsed_ms())
            search_tasks = [run_web_search_agent(q, self.registry) for q in queries_to_search]
        else:
            search_tasks = [run_search_agent(q, self.registry) for q in queries_to_search]
        
        # Also fetch live market data concurrently on first iteration
        async def _fetch_live() -> None:
            if state.iteration > 0: return
            live_tool = self.registry.get("live_market")
            cross_tool = self.registry.get("cross_asset")
            if live_tool:
                try:
                    res = await asyncio.get_event_loop().run_in_executor(None, live_tool.run, "")
                    if res.success and res.data:
                        state.live_indicators = res.data.get("indicators", {})
                except: pass
            if cross_tool and state.live_indicators:
                try:
                    res2 = await asyncio.get_event_loop().run_in_executor(None, lambda: cross_tool.run("", indicators=state.live_indicators))
                    if res2.success:
                        state.live_meta["cross_asset"] = res2.data
                except: pass

        all_results = await asyncio.gather(*search_tasks, _fetch_live(), return_exceptions=True)
        search_outputs = []
        for r in all_results[:-1]:
            if isinstance(r, AgentOutput):
                search_outputs.append(r)
                state.add_agent_output(r)  # Cumulative accumulation
                
        # Handle CRAG fallbacks directly in Searcher node
        failed_qs = [s.sub_query for s in search_outputs if s.status != "success" or s.confidence < CONFIDENCE_THRESHOLD]
        valid_search = [s for s in search_outputs if s.status == "success" and s.confidence >= CONFIDENCE_THRESHOLD]
        
        if failed_qs:
            yield AgentEvent(stage="search", data={"message": f"Triggering Web Fallback for {len(failed_qs)} sparse queries..."}, elapsed_ms=state.elapsed_ms())
            web_results = await asyncio.gather(*[run_web_search_agent(q, self.registry) for q in failed_qs], return_exceptions=True)
            for r in web_results:
                if isinstance(r, AgentOutput) and r.status == "success":
                    valid_search.append(r)
                    state.add_agent_output(r) # Cumulative accumulation

        state.current_valid_search = valid_search
        yield AgentEvent(stage="filter", data={"message": f"Confidence filter: {len(valid_search)} passed."}, elapsed_ms=state.elapsed_ms())

    async def _node_summarizer(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        state.mark_stage("summarize")
        valid_search = getattr(state, "current_valid_search", [])
        if not valid_search:
            yield AgentEvent(stage="summarize", data={"message": "No valid search results to summarize.", "total": 0}, elapsed_ms=state.elapsed_ms())
            return
            
        yield AgentEvent(stage="summarize", data={"message": f"Dispatching {len(valid_search)} Summarizer Agents..."}, elapsed_ms=state.elapsed_ms())
        
        from intelligence.analyst_agents import run_summarizer_agent
        summarize_tasks = [
            run_summarizer_agent(raw_text=s.brief, original_query=state.question, sub_query=s.sub_query)
            for s in valid_search
        ]
        
        summary_results = await asyncio.gather(*summarize_tasks, return_exceptions=True)
        for r in summary_results:
            if isinstance(r, AgentOutput) and r.status == "success" and r.confidence >= CONFIDENCE_THRESHOLD:
                state.add_agent_output(r)
                state.valid_summaries.append(r)

        yield AgentEvent(stage="integrity", data={"message": f"Integrity check: accumulated {len(state.valid_summaries)} valid summaries.", "valid_summaries": len(state.valid_summaries)}, elapsed_ms=state.elapsed_ms())

    async def _node_critic(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        # Form context from ALL valid summaries so far
        context_text = "\\n".join([s.brief for s in state.valid_summaries])

        if state.iteration < state.max_iterations - 1:
            yield AgentEvent(stage="reflection", data={"message": f"Assessing context for missing info (iteration {state.iteration + 1}/{self.max_iterations})..."}, elapsed_ms=state.elapsed_ms())

            try:
                reflection_gaps = await asyncio.get_event_loop().run_in_executor(
                    None, self.reflection.assess_context_gaps, context_text, state.question, state.iteration
                )
            except Exception as exc:
                logger.warning("[Orchestrator] Reflection failed: %s", exc)
                reflection_gaps = []

            state.gaps = reflection_gaps
            if reflection_gaps:
                yield AgentEvent(stage="correction", data={"message": f"Context Gaps Detected: {reflection_gaps}. Routing back to Search..."}, elapsed_ms=state.elapsed_ms())
                gap_queries = await asyncio.get_event_loop().run_in_executor(
                    None, self.reflection.generate_follow_up_queries, reflection_gaps, state.question
                )
                state.gap_queries = gap_queries
                # Incrementing moved to router or loop detection logic elsewhere, 
                # but we'll increment HERE to track the 'attempt'
                state.iteration += 1
            else:
                yield AgentEvent(stage="reflection", data={"message": "Context is complete. Proceeding to synthesis."}, elapsed_ms=state.elapsed_ms())

    async def _node_synthesizer(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(stage="synthesis", data={"message": "Formulating final report (Streaming)..."}, elapsed_ms=state.elapsed_ms())

        from intelligence.analyst_agents import run_analyst_agent_stream
        final_answer_chunks = []
        
        async for token in run_analyst_agent_stream(
            summaries=state.valid_summaries,
            data_gaps=state.gaps,
            original_query=state.question,
            live_indicators=state.live_indicators,
            geography=state.geography,
            horizon=state.horizon,
            conversation_context=state.conversation_context,
        ):
            final_answer_chunks.append(token)
            yield AgentEvent(stage="token", data={"text": token}, elapsed_ms=state.elapsed_ms())

        state.final_answer = "".join(final_answer_chunks)
        state.complete = True
        state.mark_stage("synthesis")

    async def _node_audit(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        # Perform a deeper institutional audit on the final synthesized report
        if not state.final_answer or len(state.final_answer) < 100:
            return

        yield AgentEvent(stage="audit", data={"message": "Institutional Critic auditing final report for precision and logic..."}, elapsed_ms=state.elapsed_ms())
        
        try:
            audit_gaps = await asyncio.get_event_loop().run_in_executor(
                None, self.reflection.assess_gaps, state
            )
            state.gaps = audit_gaps
            if audit_gaps:
                yield AgentEvent(stage="correction", data={"message": f"Analytical Gaps Found in Draft: {audit_gaps}. Triggering corrective search..."}, elapsed_ms=state.elapsed_ms())
                gap_queries = await asyncio.get_event_loop().run_in_executor(
                    None, self.reflection.generate_follow_up_queries, audit_gaps, state.question
                )
                state.gap_queries = gap_queries
                state.iteration += 1
            else:
                yield AgentEvent(stage="audit", data={"message": "Audit PASSED. Final report verified."}, elapsed_ms=state.elapsed_ms())
        except Exception as exc:
            logger.warning("[Orchestrator] Audit failed: %s", exc)

    async def _node_learn(self, state: AgentState) -> AsyncIterator[AgentEvent]:
        # PHASE 5: Persistent Learning
        # Ingest verified web results into permanent memory
        yield AgentEvent(stage="learning", data={"message": "Active Learner committing research to Institutional Memory..."}, elapsed_ms=state.elapsed_ms())
        
        try:
            from intelligence.agentic_rag.active_learner import get_learner
            learner = get_learner()
            
            # Use results from WebSearchAgent that were successful and not already from memory
            web_results = [
                o for o in state.agent_outputs 
                if o.agent_name == "WebSearchAgent" and o.status == "success" and "Institutional Memory" not in o.brief
            ]
            
            num_learned = await learner.learn_from_outputs(web_results, state.question)
            if num_learned:
                yield AgentEvent(stage="learning", data={"message": f"Successfully learned {num_learned} new concepts. Memory updated."}, elapsed_ms=state.elapsed_ms())
            else:
                yield AgentEvent(stage="learning", data={"message": "No new significant concepts found to ingest."}, elapsed_ms=state.elapsed_ms())
        except Exception as exc:
            logger.error("[Orchestrator] Learning failed: %s", exc)

    async def run_async(self, question: str, geography: str = "US", horizon: str = "MEDIUM_TERM", response_mode: str = "detailed", session_id: str = "") -> AsyncIterator[AgentEvent]:
        # Entry point wrapper
        state = AgentState(question=question, geography=geography, horizon=horizon, response_mode=response_mode, max_iterations=self.max_iterations)
        state.mark_stage("start")

        if session_id:
            from intelligence.session_memory import get_conversation_context
            state.conversation_context = get_conversation_context(session_id)

        # Run the LangGraph-style state machine and yield any emitted events
        async for event in self.graph.run_async(state):
            yield event

        # Post-loop
        if session_id:
            from intelligence.session_memory import record_turn
            record_turn(session_id, question, state.final_answer)

        # Ensure we increment state iteration inside the loop or end of loop
        # Wait, the graph doesn't auto-increment iteration.
        # We must increment iteration before entering searcher again.
