import os
import pandas as pd
import duckdb
import faiss
import numpy as np
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHUNKS_DIR = os.path.join(DATA_DIR, "chunks")
VECTOR_DB_DIR = os.path.join(DATA_DIR, "vector_db")

class StorageManager:
    """
    Advanced storage layer for Qual V3.
    Handles Parquet migration, Hive partitioning, and Analytical DuckDB queries.
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(VECTOR_DB_DIR, "metadata.db")
        os.makedirs(CHUNKS_DIR, exist_ok=True)
        os.makedirs(VECTOR_DB_DIR, exist_ok=True)
        # DuckDB can attach to the existing SQLite metadata db
        self.duck_conn = duckdb.connect()
        try:
            self.duck_conn.execute(f"INSTALL sqlite; LOAD sqlite; ATTACH '{self.db_path}' AS sqlite_db (TYPE SQLITE);")
        except Exception as e:
            logger.warning(f"Could not attach SQLite to DuckDB: {e}")

    def export_to_parquet(self, chunks: List[Dict[str, Any]], data_type: str):
        """
        Export a list of chunk dicts to Parquet with Hive-style partitioning and Zstd compression.
        Path: data/chunks/data_type/year=YYYY/month=MM/day=DD/
        """
        if not chunks:
            return
        
        # Flatten metadata if needed (already mostly flat from chunker)
        rows = []
        for c in chunks:
            row = dict(c)
            # Ensure date is present for partitioning if not in metadata
            row_date = row.get("date") or datetime.now(timezone.utc).isoformat()
            try:
                dt = datetime.fromisoformat(row_date.replace("Z", "+00:00"))
            except:
                dt = datetime.now(timezone.utc)
            
            row['year'] = dt.year
            row['month'] = dt.month
            row['day'] = dt.day
            rows.append(row)

        df = pd.DataFrame(rows)
        
        # Ensure target dir exists
        base_path = Path(CHUNKS_DIR) / data_type
        base_path.mkdir(parents=True, exist_ok=True)
        
        # Save to partitioned parquet
        df.to_parquet(
            str(base_path),
            partition_cols=['year', 'month', 'day'],
            engine='pyarrow',
            compression='zstd',
            index=False
        )
        logger.info(f"[StorageV3] Exported {len(chunks)} chunks to {base_path} (Zstd compressed)")

    def query_analytical(self, data_type: str, sql_query: str) -> pd.DataFrame:
        """
        Run a high-performance analytical query against Parquet files.
        Example sql_query: "SELECT sector, AVG(sentiment) FROM data WHERE date > '2026-01-01' GROUP BY sector"
        """
        parquet_path = Path(CHUNKS_DIR) / data_type / "**/*.parquet"
        # Register the parquet files as a view named 'data'
        rel = self.duck_conn.read_parquet(str(parquet_path))
        return self.duck_conn.execute(sql_query.replace("data", "rel")).df()

    def apply_faiss_compression(self, index: faiss.Index, vectors: np.ndarray, nlist: int = 100, m: int = 8) -> faiss.Index:
        """
        Transform a Flat index into a compressed IVFPQ index.
        nlist: number of centroids (clusters)
        m: number of sub-vectors for Product Quantization
        """
        d = vectors.shape[1]
        quantizer = faiss.IndexFlatL2(d)
        # IVFPQ: Inverted File with Product Quantization
        compressed_index = faiss.IndexIVFPQ(quantizer, d, nlist, m, 8)
        
        # Train and add
        compressed_index.train(vectors)
        compressed_index.add(vectors)
        
        return compressed_index
