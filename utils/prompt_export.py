# utils/prompt_export.py
"""
Prompt export utilities for REA Capital – Trading Engine
Canonical, stable, prompt-only (NO execution).
"""

import json
from typing import Dict, Any


def normalize_prompt(prompt: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert engine prompt into a stable, minimal schema.
    Safe for logging, file export, or downstream LLM ingestion.
    """
    if not isinstance(prompt, dict):
        return {}

    payload = prompt.get("payload", {})

    return {
        "signal": prompt.get("signal"),
        "symbol": payload.get("symbol"),
        "price": payload.get("price"),
        "vwap": payload.get("vwap"),
        "vwap_context": payload.get("vwap_context"),
        "vwap_distance_bucket": payload.get("vwap_distance_bucket"),
        "window": payload.get("window"),
        "as_of_utc": payload.get("as_of_utc"),
    }


def prompt_to_json(prompt: Dict[str, Any]) -> str:
    """
    Serialize normalized prompt to pretty JSON.
    """
    return json.dumps(normalize_prompt(prompt), indent=2)


def write_prompt_to_file(prompt: Dict[str, Any], path: str) -> None:
    """
    Write prompt JSON to a file.
    Overwrites existing content safely.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt_to_json(prompt))