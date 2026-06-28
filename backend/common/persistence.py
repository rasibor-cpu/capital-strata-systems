"""
CSS Persistent Storage Utilities

Handles standardized, thread-safe reading/writing of JSON and JSONL artifacts.
"""

import json
import os
import threading
from typing import List, Dict, Any
from backend.common.exceptions import PersistenceException

def save_json(file_path: str, data: Any, lock: threading.Lock) -> None:
    """
    Write any serializable object to a JSON file thread-safely.
    
    Responsibility: Save configurations/state details safely.
    Dependencies: PersistenceException
    Thread-safety: Fully synchronized via lock.
    """
    abs_path = os.path.abspath(file_path)
    dir_name = os.path.dirname(abs_path)
    with lock:
        try:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            raise PersistenceException(f"Failed to save JSON to {file_path}: {e}")

def load_json(file_path: str, lock: threading.Lock) -> Any:
    """
    Read a JSON file thread-safely. Returns empty list if file doesn't exist.
    
    Responsibility: Read configurations/state details safely.
    Dependencies: PersistenceException
    Thread-safety: Fully synchronized via lock.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return []
    with lock:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise PersistenceException(f"Failed to load JSON from {file_path}: {e}")

def append_jsonl(file_path: str, data: Dict[str, Any], lock: threading.Lock) -> None:
    """
    Append a dictionary as a single JSON line thread-safely.
    
    Responsibility: Write logs and events sequentially.
    Dependencies: PersistenceException
    Thread-safety: Fully synchronized via lock.
    """
    abs_path = os.path.abspath(file_path)
    dir_name = os.path.dirname(abs_path)
    line = json.dumps(data) + "\n"
    with lock:
        try:
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(abs_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            raise PersistenceException(f"Failed to append to JSONL {file_path}: {e}")

def load_jsonl(file_path: str, lock: threading.Lock) -> List[Dict[str, Any]]:
    """
    Read a JSONL file thread-safely, returning a list of dictionaries.
    
    Responsibility: Stream records from sequential logs.
    Dependencies: PersistenceException
    Thread-safety: Fully synchronized via lock.
    """
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return []
    with lock:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            raise PersistenceException(f"Failed to read JSONL file {file_path}: {e}")

    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except Exception:
            continue
    return results
