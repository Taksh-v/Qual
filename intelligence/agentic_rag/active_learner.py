"""
intelligence/agentic_rag/active_learner.py
-------------------------------------------
Implements the "Active Learning" logic for Phase 5.
Extracts knowledge from verified agent outputs and persists them to:
1. FAISS Vector Index (Semantic Memory)
2. Metadata Store (SQLite)
3. Causal Knowledge Graph (Logical Memory)
"""

import logging
import time
import uuid
import datetime
import numpy as np
from typing import Any, List

from intelligence.agentic_rag.agent_state import AgentOutput
from ingestion.embeddings import get_embedding
from ingestion.metadata_store import get_store
from intelligence.graph_rag import get_graph

logger = logging.getLogger(__name__)

class ActiveLearner:
    """Orchestrates runtime ingestion of research findings."""

    def __init__(self):
        self.store = get_store()
        self.graph = get_graph()

    async def learn_from_outputs(self, outputs: List[AgentOutput], original_query: str) -> int:
        """
        Processes verified AgentOutputs, ingesting them into permanent memory.
        Only ingests outputs that are 'success' and have high confidence.
        """
        if not outputs:
            logger.info("[ActiveLearner] No outputs passed to learner.")
            return 0

        for o in outputs:
            logger.info("[ActiveLearner] Candidate: agent=%s, status=%s, confidence=%.2f", o.agent_name, o.status, o.confidence)

        verified = [o for o in outputs if o.status == "success" and o.confidence >= 0.7]
        if not verified:
            logger.info("[ActiveLearner] No high-confidence outputs to learn from.")
            return 0

        learned_count = 0
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 1. Prepare for Vector Ingestion
        new_chunks = []
        for out in verified:
            # We treat the entire brief as a chunk for simplicity in runtime ingestion
            chunk = {
                "chunk_id": f"web_{uuid.uuid4().hex[:8]}",
                "text": out.brief,
                "metadata": {
                    "source": "Institutional Memory (Web Fallback)",
                    "title": f"Verified Research: {original_query}",
                    "date": timestamp[:10],
                    "extracted_at": timestamp,
                    "data_type": "institutional_memory",
                    "url": "https://active-learning.internal",
                    "region": "Global",
                    "sector": "General",
                }
            }
            new_chunks.append(chunk)

        if not new_chunks:
            return 0

        # 2. Vector Ingestion (FAISS + SQLite)
        try:
            from intelligence.context_retriever import _load_index_cached
            faiss_index = _load_index_cached()
            
            # Embed all new chunks
            texts = [c["text"] for c in new_chunks]
            # FAISS add() requires float32 matrix
            embeddings = []
            for t in texts:
                emb = get_embedding(t, data_type="institutional_memory")
                embeddings.append(emb)
            
            vec_matrix = np.array(embeddings, dtype="float32")
            
            # Atomic update
            current_count = faiss_index.ntotal
            faiss_index.add(vec_matrix)
            
            # Save metadata to SQLite using the new rowids
            self.store.upsert_chunks(new_chunks, start_rowid=current_count)
            
            # Persist FAISS to disk
            from intelligence.context_retriever import INDEX_CANDIDATES
            faiss_save_path = INDEX_CANDIDATES[0] # Usually data/vector_db/news.index
            import faiss
            faiss.write_index(faiss_index, faiss_save_path)
            
            learned_count = len(new_chunks)
            logger.info("[ActiveLearner] Successfully ingested %d chunks into Semantic Memory.", learned_count)
            
        except Exception as e:
            logger.error("[ActiveLearner] Vector ingestion failed: %s", e)

        # 3. Graph Enrichment (Causal Triples)
        try:
            for chunk in new_chunks:
                triples = self.graph.generate_triples_for_text(chunk["text"])
                for head, rel, tail in triples:
                    self.graph.add_triple(head, rel, tail, source="Active Learning")
            
            # Persist Graph
            self.graph.save_to_disk()
            logger.info("[ActiveLearner] Successfully enriched Causal Graph with new triples.")
        except Exception as e:
            logger.error("[ActiveLearner] Graph enrichment failed: %s", e)

        return learned_count

# Singleton
_learner = None
def get_learner() -> ActiveLearner:
    global _learner
    if _learner is None:
        _learner = ActiveLearner()
    return _learner
