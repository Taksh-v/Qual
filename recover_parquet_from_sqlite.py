import sqlite3
import pandas as pd
import logging
from ingestion.storage_manager import StorageManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recover_from_sqlite():
    storage = StorageManager()
    db_path = "data/vector_db/metadata.db"
    
    try:
        conn = sqlite3.connect(db_path)
        # We need to get all chunks. Chunks are in 'chunks' table (or similar)
        # Let's check the table name first
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Tables in metadata.db: {tables}")
        
        # The table name is 'chunks' based on sqlite_master
        table_name = "chunks"
        if ("chunks",) not in tables:
            # Fallback searching
            for t in tables:
                if "metadata" in t[0]:
                    table_name = t[0]
                    break
        
        logger.info(f"Recovering data from table: {table_name}")
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        
        if df.empty:
            logger.warning("No data found in SQLite.")
            return
            
        # Convert df to chunks list
        chunks = df.to_dict('records')
        
        # Export to Parquet (StorageManager handles date parsing)
        storage.export_to_parquet(chunks, data_type="recovered")
        logger.info(f"Recovery complete. Migrated {len(chunks)} chunks to data/chunks/recovered")
        
    except Exception as e:
        logger.error(f"Error during recovery: {e}")

if __name__ == "__main__":
    recover_from_sqlite()
