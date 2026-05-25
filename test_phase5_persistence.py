import logging
import asyncio
logging.basicConfig(level=logging.INFO)
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator
from intelligence.context_retriever import retrieve_relevant_context

async def test_persistence_loop():
    query = "What is the latest status of the Tata-PSMC semiconductor fab in Gujarat as of April 2026?"
    orchestrator = AgenticOrchestrator(max_iterations=2)
    
    print("\n--- FIRST PASS: Researching from scratch ---")
    async for event in orchestrator.run_async(query):
        if event.stage == "learning":
            print(f"[Learner] {event.data.get('message')}")
        elif event.stage == "synthesizer" and "final_report" in event.data:
             # report found
             pass

    print("\n--- SECOND PASS: Checking if memory was established ---")
    # Directly check retrieval for the query
    context = retrieve_relevant_context(query, top_k=10)
    
    memory_found = False
    for chunk in context:
        dtype = chunk.get("data_type") or chunk.get("metadata", {}).get("data_type")
        source = chunk.get("metadata", {}).get("source")
        if dtype == "institutional_memory":
            print(f"✅ Found institutional memory! Source: {source}")
            memory_found = True
            break
            
    if memory_found:
        print("\nSUCCESS: Phase 5 Persistent Learning verified.")
    else:
        print("\nFAILURE: Institutional memory not found in second pass.")

if __name__ == "__main__":
    asyncio.run(test_persistence_loop())
