"""
Capital Strata Systems (CSS)
Phase 25C – Fixed Asset Engine (Foundation Layer)

Capabilities:
- Create new fixed asset (Admin-controlled)
- Store asset metadata
- Compute straight-line depreciation
- Track accumulated depreciation
- Prevent double-posting per period
- Prepare depreciation posting payload for GL engine

Does NOT yet auto-post.
Posting integration will be Phase 25C-2.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, List, Optional


REGISTRY_FILE = Path("backend/app/assets/fixed_asset_registry.json")


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _to_decimal(v) -> Decimal:
    return Decimal(str(v))


def _ensure_registry_exists() -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps({"assets": []}, indent=2), encoding="utf-8")


def _load_registry() -> Dict[str, Any]:
    _ensure_registry_exists()
    with REGISTRY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(data: Dict[str, Any]) -> None:
    REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------
# Asset Creation
# ---------------------------------------------------

def create_asset(
    *,
    admin_user_id: str,
    asset_name: str,
    asset_class: str,
    purchase_date: str,
    cost: str,
    residual_value: str,
    useful_life_years: int,
    location: str = "",
    insurance_policy_ref: Optional[str] = None,
    vehicle_registration: Optional[str] = None,
    engine_number: Optional[str] = None,
) -> Dict[str, Any]:

    if not admin_user_id:
        raise PermissionError("Admin user ID required.")

    if useful_life_years <= 0:
        raise ValueError("Useful life must be positive.")

    cost_dec = _to_decimal(cost)
    residual_dec = _to_decimal(residual_value)

    if residual_dec > cost_dec:
        raise ValueError("Residual value cannot exceed cost.")

    registry = _load_registry()

    asset_id = f"AST-{uuid.uuid4().hex.upper()}"

    asset_record = {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "purchase_date": purchase_date,
        "cost": str(cost_dec),
        "residual_value": str(residual_dec),
        "useful_life_years": useful_life_years,
        "depreciation_method": "STRAIGHT_LINE",
        "accumulated_depreciation": "0",
        "status": "ACTIVE",
        "location": location,
        "admin_owner_id": admin_user_id,
        "insurance_policy_ref": insurance_policy_ref,
        "vehicle_registration": vehicle_registration,
        "engine_number": engine_number,
        "depreciation_history": []  # tracks posted periods
    }

    registry["assets"].append(asset_record)
    _save_registry(registry)

    return {
        "asset_id": asset_id,
        "status": "CREATED"
    }


# ---------------------------------------------------
# Depreciation Computation
# ---------------------------------------------------

def _annual_depreciation(asset: Dict[str, Any]) -> Decimal:
    cost = _to_decimal(asset["cost"])
    residual = _to_decimal(asset["residual_value"])
    life = Decimal(str(asset["useful_life_years"]))
    return (cost - residual) / life


def _monthly_depreciation(asset: Dict[str, Any]) -> Decimal:
    return _annual_depreciation(asset) / Decimal("12")


def compute_depreciation_for_period(period: str) -> List[Dict[str, Any]]:
    """
    period format: YYYY-MM
    Returns depreciation payloads for posting.
    Does NOT update registry yet.
    """

    registry = _load_registry()
    results = []

    for asset in registry.get("assets", []):

        if asset.get("status") != "ACTIVE":
            continue

        if period in asset.get("depreciation_history", []):
            continue  # already depreciated this period

        monthly_dep = _monthly_depreciation(asset)

        results.append({
            "asset_id": asset["asset_id"],
            "asset_name": asset["asset_name"],
            "period": period,
            "depreciation_amount": str(monthly_dep),
        })

    return results


# ---------------------------------------------------
# Apply Depreciation (Update Registry Only)
# ---------------------------------------------------

def apply_depreciation_to_registry(
    *,
    asset_id: str,
    period: str,
    amount: str
) -> None:

    registry = _load_registry()

    for asset in registry.get("assets", []):
        if asset["asset_id"] == asset_id:

            acc_dep = _to_decimal(asset["accumulated_depreciation"])
            new_acc = acc_dep + _to_decimal(amount)

            asset["accumulated_depreciation"] = str(new_acc)
            asset["depreciation_history"].append(period)

            break

    _save_registry(registry)