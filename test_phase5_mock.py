import asyncio
from intelligence.agentic_rag.active_learner import get_learner
from intelligence.agentic_rag.agent_state import AgentOutput
from intelligence.context_retriever import retrieve_relevant_context

async def test_mock_persistence():
    learner = get_learner()
    
    # Mock some web search results
    mock_outputs = [
        AgentOutput(
            agent_name="WebSearchAgent",
            brief="Mock fact about the quantum housing market in 2026. Prices have stabilized due to antigravity tech.",
            confidence=0.9,
            status="success",
            sub_query="quantum housing market trends 2026"
        )
    ]
    
    print("--- STEP 1: Ingesting mock research ---")
    num_learned = await learner.learn_from_outputs(mock_outputs, "testing persistence")
    print(f"Learned {num_learned} chunks.")
    
    print("\n--- STEP 2: Verifying retrieval with 'institutional_memory' label ---")
    # Search for something related to the mock fact
    context = retrieve_relevant_context("antigravity housing 2026", top_k=5)
    
    found = False
    for chunk in context:
        dtype = chunk.get("data_type") or chunk.get("metadata", {}).get("data_type")
        source = chunk.get("metadata", {}).get("source")
        text = chunk.get("text")
        if dtype == "institutional_memory":
            print(f"✅ Success: Found institutional memory.")
            print(f"   Source: {source}")
            print(f"   Text: {text[:100]}...")
            found = True
            break
            
    if not found:
        print("❌ Failure: Could not find ingested chunk as institutional memory.")

if __name__ == "__main__":
    asyncio.run(test_mock_persistence())
