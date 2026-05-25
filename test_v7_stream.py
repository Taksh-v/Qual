import asyncio
from intelligence.agentic_rag.orchestrator import AgenticOrchestrator

async def test_stream():
    orch = AgenticOrchestrator(max_iterations=1)
    # We do a simple question that won't require many fallback loops to test streaming
    events = orch.run_async('What is the current state of Nvidia stock?')
    
    first_token_ms = -1
    token_count = 0
    thinking_started = False
    
    async for event in events:
        if event.stage == 'token':
            if token_count == 0:
                first_token_ms = event.elapsed_ms
            token_count += 1
            if '<thinking>' in event.data.get('text', ''):
                thinking_started = True
            print(event.data.get('text', ''), end='', flush=True)
            
    print(f'\\n\\n[TEST] TTFT = {first_token_ms}ms')
    print(f'[TEST] Streamed Tokens = {token_count}')
    if thinking_started:
        print('[TEST] `<thinking>` tag successfully triggered!')
    else:
        print('[TEST] Warning: No `<thinking>` tag seen.')

asyncio.run(test_stream())
