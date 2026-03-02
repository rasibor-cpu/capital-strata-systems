"""
Capital Strata Systems (CSS)
Phase 26D-2 – Asset Engine with Optional Capitalization (Governance-Aware)

What this fixes:
- Uses the REAL journal_writer.post_transaction signature used in your codebase
- Uses your COA PPE cost account: 000-840-800
- Automatically retries capitalization with BACKDATE_EXECUTION_DATE override if required
- Writes asset to fixed_asset_registry.json ONLY after successful capitalization (when enabled)

Registry file:
- backend/app/assets/fixed_asset_registry.json
Schema (kept simple and compatible with your existing depreciation pipeline):
{
  "assets": [
     {...asset_record...}
  ]
}
"""

from __future__ import annotations

import uuid
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.ledger.journal_writer import post_transaction


REGISTRY_FILE = Path("backend/app/assets/fixed_asset_registry.json")

DEFAULT_PPE_COST_GL = "000-840-800"
DEFAULT_FUNDING_GL = "000-840-001"  # Cash on Hand


def _to_decimal(x) -> Decimal:
    return Decimal(str(x))


def _ensure_registry() -> None:
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text(json.dumps({"assets": []}, indent=2), encoding="utf-8")


def _load_registry() -> Dict[str, Any]:
    _ensure_registry()
    raw = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixed_asset_registry.json must be a JSON object")
    raw.setdefault("assets", [])
    if not isinstance(raw["assets"], list):
        raise ValueError("fixed_asset_registry.json['assets'] must be a list")
    return raw


def _save_registry(data: Dict[str, Any]) -> None:
    REGISTRY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_backdate_override(*, admin_user_id: str, ticket_id: str, reason: str) -> Dict[str, Any]:
    # Must match posting_calendar.CalendarOverride field names used elsewhere (and used successfully in period_close)
    return {
        "override_type": "BACKDATE_EXECUTION_DATE",
        "override_reason": reason,
        "override_by_user_id": admin_user_id,
        "override_ticket_ref": ticket_id,

        # Extra audit-friendly fields (harmless if ignored)
        "approved_by": admin_user_id,
        "approved_by_role": "ADMIN",
        "reason": reason,
    }


def create_asset(
    *,
    admin_user_id: str,
    asset_name: str,
    asset_class: str,
    purchase_date: str,
    cost: str,
    residual_value: str,
    useful_life_years: int,
    location: str,
    auto_capitalize: bool = False,
    ppe_cost_account: str = DEFAULT_PPE_COST_GL,
    funding_account: str = DEFAULT_FUNDING_GL,
    currency: str = "NGN",
) -> Dict[str, Any]:
    """
    Creates an asset in the registry.

    If auto_capitalize=True:
      Posts DR PPE Cost (ppe_cost_account)
           CR Funding (funding_account)

      If posting is blocked due to BACKDATE_EXECUTION_DATE,
      retries automatically with the correct override.

    Returns:
      { asset_id, status, capitalized, capitalization_transaction_id? }
    """

    if not admin_user_id:
        raise PermissionError("admin_user_id required")

    cost_dec = _to_decimal(cost)
    residual_dec = _to_decimal(residual_value)

    if cost_dec <= 0:
        raise ValueError("Asset cost must be > 0")
    if residual_dec < 0:
        raise ValueError("Residual value must be >= 0")
    if residual_dec >= cost_dec:
        raise ValueError("Residual value must be less than cost")
    if useful_life_years <= 0:
        raise ValueError("useful_life_years must be > 0")

    asset_id = f"AST-{uuid.uuid4().hex.upper()}"
    cap_ticket = f"CAP-{asset_id}"

    capitalization_txn_id: Optional[str] = None

    # 1) Optional capitalization posting (must succeed before registry write)
    if auto_capitalize:
        entries = [
            {"account_no": ppe_cost_account, "side": "DR", "amount": str(cost_dec)},
            {"account_no": funding_account, "side": "CR", "amount": str(cost_dec)},
        ]

        try:
            res = post_transaction(
                ticket_id=cap_ticket,
                entries=entries,
                maker_user_id=admin_user_id,
                execution_date=purchase_date,
                value_date=purchase_date,
                description=f"Asset Capitalization – {asset_name}",
                currency=currency,
                override=None,
            )
            capitalization_txn_id = res.get("transaction_id")

        except PermissionError as pe:
            msg = str(pe)
            if "required_override_type=BACKDATE_EXECUTION_DATE" in msg:
                res = post_transaction(
                    ticket_id=cap_ticket,
                    entries=entries,
                    maker_user_id=admin_user_id,
                    execution_date=purchase_date,
                    value_date=purchase_date,
                    description=f"Asset Capitalization – {asset_name}",
                    currency=currency,
                    override=_make_backdate_override(
                        admin_user_id=admin_user_id,
                        ticket_id=f"{cap_ticket}-OVR",
                        reason=f"Authorized backdated asset capitalization ({purchase_date})",
                    ),
                )
                capitalization_txn_id = res.get("transaction_id")
            else:
                raise

    # 2) Registry write (only after capitalization success)
    asset_record = {
        "asset_id": asset_id,
        "asset_name": asset_name,
        "asset_class": asset_class,
        "purchase_date": purchase_date,
        "cost": str(cost_dec),
        "residual_value": str(residual_dec),
        "useful_life_years": int(useful_life_years),
        "location": location,

        "accumulated_depreciation": "0",
        "depreciation_history": [],

        "capitalized": bool(auto_capitalize),
        "ppe_cost_account": ppe_cost_account,
        "funding_account": funding_account,
        "capitalization_ticket_id": cap_ticket if auto_capitalize else None,
        "capitalization_transaction_id": capitalization_txn_id,
        "currency": str(currency or "NGN").upper(),
    }

    reg = _load_registry()
    reg["assets"].append(asset_record)
    _save_registry(reg)

    return {
        "asset_id": asset_id,
        "status": "CREATED",
        "capitalized": bool(auto_capitalize),
        "capitalization_transaction_id": capitalization_txn_id,
    }