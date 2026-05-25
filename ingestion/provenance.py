import os
import json
import uuid
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")

def save_raw_payload(payload: Dict[str, Any], source: str, data_type: str) -> str:
    """
    Save a raw payload to disk and return a unique provenance_id.
    Storage format: data/raw/YYYY-MM-DD/source/data_type_uuid.json
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    
    # Create directory structure
    path = Path(RAW_DATA_DIR) / date_str / source
    path.mkdir(parents=True, exist_ok=True)
    
    provenance_id = str(uuid.uuid4())
    filename = f"{data_type}_{provenance_id}.json"
    full_path = path / filename
    
    storage_data = {
        "provenance_id": provenance_id,
        "captured_at": now.isoformat(),
        "source": source,
        "data_type": data_type,
        "payload": payload
    }
    
    def json_serial(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(storage_data, f, ensure_ascii=False, indent=2, default=json_serial)
    
    return provenance_id

def get_raw_payload(provenance_id: str) -> Dict[str, Any] | None:
    """
    Retrieve a raw payload by searching for its provenance_id in the archive.
    Note: For large archives, this should be indexed in a DB.
    """
    # This is a brute-force search for now, as we don't have a lookup table yet.
    # In V3.1 we will add a mapping in metadata.db
    for root, dirs, files in os.walk(RAW_DATA_DIR):
        for file in files:
            if provenance_id in file:
                with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                    return json.load(f)
    return None
