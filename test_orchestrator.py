import asyncio
import json
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator

async def main():
    print("Testing AgenticOrchestrator...")
    orchestrator = AgenticOrchestrator(max_iterations=2)
    response_buffer = ""
    async for event in orchestrator.run_async("What is the current state of interest rates? Provide a detailed analysis."):
        if event.stage == "clear_stream":
            print("\n>>> RECEIVED CLEAR STREAM EVENT - FLUSHING BUFFER <<<\n")
            response_buffer = ""
        elif event.stage == "token":
            response_buffer += event.data.get("text", "")
            print(event.data.get("text", ""), end="", flush=True)

    print("\n\n----- FINAL BUFFER CONTENT -----")
    print(response_buffer[:200] + "\n...\n(truncated for test script)")

asyncio.run(main())
