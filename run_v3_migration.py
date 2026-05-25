import os
import json
import logging
import faiss
import numpy as np
from pathlib import Path
from ingestion.storage_manager import StorageManager
from ingestion.metadata_store import get_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHUNKS_DIR = os.path.join(DATA_DIR, "chunks")
VECTOR_DB_DIR = os.path.join(DATA_DIR, "vector_db")

def migrate_chunks():
    storage = StorageManager()
    
    for category in ["news", "rss"]:
        cat_path = Path(CHUNKS_DIR) / category
        if not cat_path.exists():
            continue
        
        all_chunks = []
        json_files = list(cat_path.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files in {category}")
        
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_chunks.extend(data)
                    else:
                        all_chunks.append(data)
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")
        
        if all_chunks:
            logger.info(f"Migrating {len(all_chunks)} chunks for {category}...")
            storage.export_to_parquet(all_chunks, data_type=category)
            # We don't delete JSON files yet to be safe
            logger.info(f"Successfully migrated {category} to Parquet.")

def migrate_faiss():
    index_path = os.path.join(VECTOR_DB_DIR, "news.index")
    if not os.path.exists(index_path):
        logger.warning("FAISS index not found for migration.")
        return

    logger.info("Loading existing FAISS index for compression...")
    index = faiss.read_index(index_path)
    
    if isinstance(index, faiss.IndexFlatL2):
        logger.info(f"Existing index is FlatL2 with {index.ntotal} vectors. Compressing to IVFPQ...")
        
        # Get raw vectors (this only works if it's a FlatL2 index)
        # We use reconstruct_n to get the vectors
        xb = index.reconstruct_n(0, index.ntotal)
        
        storage = StorageManager()
        # nlist=100, m=8 are reasonable defaults for small-medium indices
        nlist = min(100, index.ntotal // 4) if index.ntotal > 40 else 1
        m = 8
        
        if index.ntotal > 0:
            compressed_index = storage.apply_faiss_compression(index, xb, nlist=nlist, m=m)
            out_path = os.path.join(VECTOR_DB_DIR, "news_compressed.index")
            faiss.write_index(compressed_index, out_path)
            logger.info(f"Compressed index saved to {out_path}")
            
            orig_size = os.path.getsize(index_path) / (1024 * 1024)
            new_size = os.path.getsize(out_path) / (1024 * 1024)
            logger.info(f"FAISS Compression: {orig_size:.2f} MB -> {new_size:.2f} MB")
    else:
        logger.info("Index is already compressed or not a FlatL2. Skipping.")

if __name__ == "__main__":
    logger.info("=== Starting V3 Data Migration ===")
    migrate_chunks()
    migrate_faiss()
    logger.info("=== Migration Complete ===")
