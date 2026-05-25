import asyncio
from rag.query import run_query

async def main():
    print("Testing rag/query.py run_query...")
    answer, chunks = await run_query("What is the current textile market in India?")
    print("----- START OUTPUT -----")
    print(answer)
    print("----- END OUTPUT -----")

asyncio.run(main())
