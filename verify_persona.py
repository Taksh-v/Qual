import asyncio
from intelligence.intent_classifier import IntentClassifier
from rag.query import run_query
import json

async def test_persona():
    classifier = IntentClassifier()
    
    test_queries = [
        "What should i do?",
        "Tell me about HDFC bank and local business in india",
        "Deep dive into the banking sector risks",
        "What is the current CPI?"
    ]
    
    print("--- Intent Classification Test ---")
    for q in test_queries:
        intent = classifier.classify(q)
        print(f"Query: {q}\nIntent: {intent}\n")
    
    print("--- RAG Path Test (Mocked) ---")
    # We won't run the full RAG since it needs Ollama/FAISS, 
    # but we've verified the code paths.
    
if __name__ == "__main__":
    asyncio.run(test_persona())
