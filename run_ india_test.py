import asyncio
import json
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator

async def run_india_test():
    orch = AgenticOrchestrator(max_iterations=2)
    question = "how is the housing market of India"
    
    print(f"--- QUERY: {question} ---")
    
    async for event in orch.run_async(question):
        stage = event.stage
        data = event.data
        
        if stage == "token":
            print(data.get("text", ""), end="", flush=True)
        elif stage == "correction":
            print(f"\n[CORRECTION] {data.get('message')}")
        elif stage == "audit":
            print(f"\n[AUDIT] {data.get('message')}")
        elif stage == "reflection":
            print(f"\n[REFLECTION] {data.get('message')}")
        elif stage == "search":
             print(f"\n[SEARCH] {data.get('message')}")
        elif stage == "planning":
             print(f"\n[PLANNING] {data.get('message')}")
        else:
             # Basic info events
             if "message" in data:
                 print(f"\n[{stage.upper()}] {data['message']}")

if __name__ == "__main__":
    asyncio.run(run_india_test())
