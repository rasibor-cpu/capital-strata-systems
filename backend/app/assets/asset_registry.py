"""
Asset Registry Adapter – Phase 25C

Purpose:
- Provide a stable API for reading/writing fixed assets registry
- Backed by: backend/app/assets/fixed_asset_registry.json
- Keeps depreciation_posting and future reports decoupled from raw JSON structure

Public API:
- load_assets() -> dict[asset_id, asset_dict]
- save_assets(assets_by_id) -> None
- upsert_asset(asset_dict) -> None
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


REGISTRY_FILE = Path("backend/app/assets/fixed_asset_registry.json")


def _ensure_registry_exists() -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps({"assets": []}, indent=2), encoding="utf-8")


def load_assets() -> Dict[str, Dict[str, Any]]:
    """
    Returns dict keyed by asset_id.
    """
    _ensure_registry_exists()
    raw = json.loads(REGISTRY_FILE.read_text(encoding="utf-8") or "{}")
    assets = raw.get("assets", [])
    out: Dict[str, Dict[str, Any]] = {}
    for a in assets:
        aid = str(a.get("asset_id", "")).strip()
        if aid:
            out[aid] = a
    return out


def save_assets(assets_by_id: Dict[str, Dict[str, Any]]) -> None:
    """
    Persists to canonical registry JSON list format.
    """
    _ensure_registry_exists()
    payload = {"assets": list(assets_by_id.values())}
    REGISTRY_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def upsert_asset(asset: Dict[str, Any]) -> None:
    assets = load_assets()
    aid = str(asset.get("asset_id", "")).strip()
    if not aid:
        raise ValueError("asset must include asset_id")
    assets[aid] = asset
    save_assets(assets)