#!/usr/bin/env python3
"""
scripts/bootstrap_graph.py
Bootstraps the Causal Knowledge Graph from existing metadata chunks.
"""

import sys
import os
import json
import logging
import asyncio

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.graph_rag import CausalKnowledgeGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap_graph")

def main():
    graph = CausalKnowledgeGraph()
    # Try to load existing
    graph.load_from_disk()

    # Hardcode causal chains for testing the Multi-Hop routing
    triples = [
        ("Middle East", "decreases supply of", "Crude Oil", "TestSource"),
        ("Crude Oil", "increases costs for", "Transport Sector", "TestSource"),
        ("Transport Sector", "reduces margins of", "Tech Components", "TestSource"),
        ("Tech Components", "hurts production of", "Nvidia", "TestSource"),
        ("Generative AI", "increases demand for", "Nvidia", "TestSource"),
        ("Federal Reserve Rate Cuts", "boosts valuation of", "Growth Stocks", "TestSource"),
        ("Growth Stocks", "includes", "Nvidia", "TestSource")
    ]
    
    count = 0
    for head, rel, tail, src in triples:
        logger.info("  => %s -[%s]-> %s", head, rel, tail)
        graph.add_triple(head, rel, tail, source=src)
        count += 1

    logger.info("Added %d new triples.", count)
    graph.save_to_disk()
    logger.info("Bootstrap complete.")

if __name__ == "__main__":
    main()
