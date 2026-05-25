"""
intelligence/graph_rag.py
-------------------------
V7.0 Causal Knowledge Graph Foundation.

Provides a dependency-free, lightweight Knowledge Graph using NetworkX.
Allows the Macro Intelligence Engine to perform multi-hop traversals to answer 
causal inference questions (e.g., "How does Conflict X impact Asset Y?").

Features:
- Extracts (Entity) -> [Relation] -> (Entity) triples from text using LLMs.
- Stores triples in an directed multigraph.
- Performs breadth-first traversal up to N hops to construct causal pathways.
"""

import logging
import networkx as nx
from typing import Any

logger = logging.getLogger(__name__)

class CausalKnowledgeGraph:
    """Lightweight in-memory Graph for causal entity relationships."""

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        
    def save_to_disk(self, filepath: str = "data/causal_graph.gml") -> None:
        """Persist graph to GML format."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # GML requires string keys and simple types
        try:
            nx.write_gml(self.graph, filepath)
            logger.info("[GraphRAG] Saved causal graph with %d nodes to %s", len(self.graph.nodes), filepath)
        except Exception as e:
            logger.error("[GraphRAG] Failed to save graph: %s", e)

    def load_from_disk(self, filepath: str = "data/causal_graph.gml") -> None:
        """Load graph from GML format."""
        import os
        if os.path.exists(filepath):
            try:
                self.graph = nx.read_gml(filepath)
                logger.info("[GraphRAG] Loaded causal graph with %d nodes from %s", len(self.graph.nodes), filepath)
            except Exception as e:
                logger.error("[GraphRAG] Failed to load graph: %s", e)

    def add_triple(self, head: str, relation: str, tail: str, source: str = "", metadata: dict[str, Any] = None):
        """Add a causal edge between two entities."""
        head_norm = head.strip().title()
        tail_norm = tail.strip().title()
        
        if not head_norm or not tail_norm:
            return

        self.graph.add_node(head_norm)
        self.graph.add_node(tail_norm)
        
        meta = metadata or {}
        meta["source"] = source
        self.graph.add_edge(head_norm, tail_norm, relation=relation, **meta)

    def search_paths(self, start_entity: str, max_depth: int = 2) -> list[str]:
        """
        Traverse the graph from a starting entity up to max_depth hops.
        Returns a list of causal pathways as strings.
        """
        start_norm = start_entity.strip().title()
        
        if start_norm not in self.graph:
            # Fuzzy match
            matches = [n for n in self.graph.nodes if start_norm.lower() in n.lower()]
            if not matches:
                return []
            start_norm = matches[0]

        paths = []
        # We use a simple bounded DFS to gather paths
        def dfs(current: str, depth: int, current_path: list[str]):
            if depth >= max_depth:
                return
            
            for neighbor in self.graph.successors(current):
                edge_data = self.graph.get_edge_data(current, neighbor)
                # Since it's a MultiDiGraph, edge_data is a dict of dicts over multiple edges
                for edge_idx, data in edge_data.items():
                    rel = data.get("relation", "affects")
                    step = f"({current}) -[{rel}]-> ({neighbor})"
                    
                    new_path = list(current_path)
                    new_path.append(step)
                    
                    paths.append(" => ".join(new_path))
                    dfs(neighbor, depth + 1, new_path)

        dfs(start_norm, 0, [])
        return paths

    def generate_triples_for_text(self, text: str) -> list[tuple[str, str, str]]:
        """
        Calls an LLM to extract causal triples from text.
        Returns a list of (Subject, Relation, Object).
        """
        prompt = (
            "You are an expert financial analyst building a causal knowledge graph.\n"
            "Extract cause-and-effect relationships from the text below.\n"
            "Format exactly as:\n"
            "SUBJECT | RELATION | OBJECT\n"
            "Rules:\n"
            "1. Only extract strong causal or strategic relations (e.g. 'increases', 'disrupts', 'invests in').\n"
            "2. Keep entities very short (1-3 words).\n"
            "3. If no clear relations exist, return 'NONE'.\n\n"
            f"Text:\n{text[:2000]}\n\n"
            "Triples:\n"
        )
        
        from intelligence.llm_provider import generate_text
        try:
            raw, _ = generate_text(prompt, temperature=0.0, max_tokens=300)
            if "NONE" in raw.upper() and len(raw) < 10:
                return []
                
            triples = []
            for line in raw.splitlines():
                parts = line.split("|")
                if len(parts) == 3:
                    head, rel, tail = [p.strip() for p in parts]
                    if head and tail:
                        triples.append((head, rel, tail))
            return triples
        except Exception as exc:
            logger.debug("[GraphRAG] Triple extraction failed: %s", exc)
            return []

# Singleton instance across the server
_global_graph = CausalKnowledgeGraph()
_global_graph.load_from_disk()

def get_graph() -> CausalKnowledgeGraph:
    return _global_graph
