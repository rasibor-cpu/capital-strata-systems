"""Commercial attribution ledgers (Issue #102). Accounting machinery only; economics unchanged.

Four separate realised-P&L ledgers: CSS_RECOMMENDED, CSS_RECOMMENDED_MODIFIED, USER_INDEPENDENT, ORIGIN_UNDER_REVIEW.

Hard rules (not configurable):
- USER_INDEPENDENT results are never part of a CSS-attributable base and are never presented as CSS-generated.
- ORIGIN_UNDER_REVIEW results are excluded from any CSS-attributable base until the review is resolved (a recorded
  ledger transition); they then count in the resolved ledger from the next statement.

Owner/compliance decisions (TBD by default, so nothing is computed that hasn't been approved):
- `modified_treatment`: whether CSS_RECOMMENDED_MODIFIED results enter the base (EXCLUDE / INCLUDE / SEPARATE). Until
  decided, they are reported separately and excluded.
- `fee_rate`: the owner-stated commercial concept is 20% of profitable CSS-attributable trading. It is recorded here
  as the stated concept but is not applied until a policy is approved with an approval reference.
- `loss_recovery`: the existing profitability/loss-recovery control. No such rule exists in the repository
  (checked 2026-10-05). A generic HIGH_WATER_MARK mechanism is provided (fees only on cumulative attributable profit
  above the previous peak, so losses must be recovered first); it is applied only when an approved policy selects it.

No fee is calculated unless `approved=True`, `approval_ref` is set, and `fee_rate` and `loss_recovery` are set. The
output always says why a fee was or wasn't computed. This module moves no money and has no payment integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .lifecycle import TradeLifecycle
from .model import ORIGIN_LABELS, TradeOrigin

OWNER_STATED_FEE_CONCEPT = 0.20     # documentation of the owner's stated concept; never used unless approved
LEDGERS = [TradeOrigin.CSS_RECOMMENDED, TradeOrigin.CSS_RECOMMENDED_MODIFIED, TradeOrigin.USER_INDEPENDENT,
           TradeOrigin.ORIGIN_UNDER_REVIEW]
NEVER_IN_BASE = {TradeOrigin.USER_INDEPENDENT, TradeOrigin.ORIGIN_UNDER_REVIEW}


@dataclass(frozen=True)
class CommercialPolicy:
    version: str = "CA-1.0.0-draft"
    approved: bool = False
    approval_ref: Optional[str] = None
    fee_rate: Optional[float] = None               # TBD (owner-stated concept: OWNER_STATED_FEE_CONCEPT)
    loss_recovery: Optional[str] = None            # TBD; supported: "HIGH_WATER_MARK"
    modified_treatment: Optional[str] = None       # TBD; "EXCLUDE" | "INCLUDE" | "SEPARATE"

    def pending(self) -> List[str]:
        out = [k for k in ("fee_rate", "loss_recovery", "modified_treatment") if getattr(self, k) is None]
        if not self.approved or not self.approval_ref:
            out.append("approval")
        return out


DRAFT_POLICY = CommercialPolicy()


def ledger_entries(lifecycle: TradeLifecycle, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[dict]:
    """One entry per realised close, bucketed by the lot's current origin (resolved reviews included)."""
    out = []
    for lot in lifecycle.lots.values():
        origin = lifecycle.origin_of(lot)
        for c in lot.closes:
            at = datetime.fromisoformat(c["at"])
            if (start and at < start) or (end and at >= end):
                continue
            out.append({"ledger": origin.value, "lot_id": lot.lot_id, "symbol": lot.symbol,
                        "recommendation_id": lot.recommendation_id, "closing_order_id": c["order_id"],
                        "fill_id": c["fill_id"], "at": c["at"], "realized_pnl": round(c["realized_pnl"], 8)})
    return sorted(out, key=lambda e: (e["at"], e["lot_id"]))


def statement(lifecycle: TradeLifecycle, period_start: Optional[datetime] = None, period_end: Optional[datetime] = None,
              policy: CommercialPolicy = DRAFT_POLICY, prior_high_water_mark: float = 0.0,
              prior_cumulative_attributable: float = 0.0) -> dict:
    entries = ledger_entries(lifecycle, period_start, period_end)
    ledgers = {o.value: {"label": ORIGIN_LABELS[o], "realized_pnl": 0.0, "entries": 0} for o in LEDGERS}
    for e in entries:
        ledgers[e["ledger"]]["realized_pnl"] = round(ledgers[e["ledger"]]["realized_pnl"] + e["realized_pnl"], 8)
        ledgers[e["ledger"]]["entries"] += 1

    included = [TradeOrigin.CSS_RECOMMENDED.value]
    excluded = {TradeOrigin.USER_INDEPENDENT.value: "Independent trades are never CSS-attributable",
                TradeOrigin.ORIGIN_UNDER_REVIEW.value: "Excluded until the review is resolved"}
    if policy.modified_treatment == "INCLUDE":
        included.append(TradeOrigin.CSS_RECOMMENDED_MODIFIED.value)
    elif policy.modified_treatment == "SEPARATE":
        excluded[TradeOrigin.CSS_RECOMMENDED_MODIFIED.value] = "Reported separately under its own approved terms"
    else:
        excluded[TradeOrigin.CSS_RECOMMENDED_MODIFIED.value] = (
            "Excluded: treatment not yet decided" if policy.modified_treatment is None else "Excluded by policy")
    assert not (set(included) & {o.value for o in NEVER_IN_BASE})          # hard rule
    base = round(sum(ledgers[k]["realized_pnl"] for k in included), 8)

    out = {"period_start": period_start.isoformat() if period_start else None,
           "period_end": period_end.isoformat() if period_end else None,
           "policy_version": policy.version, "policy_pending": policy.pending(), "ledgers": ledgers,
           "attributable_base": {"included_ledgers": included, "excluded_ledgers": excluded, "realized_pnl": base},
           "entries": entries, "fee": None, "fee_status": None, "loss_recovery": None}

    if policy.loss_recovery == "HIGH_WATER_MARK":
        cumulative = round(prior_cumulative_attributable + base, 8)
        chargeable = max(0.0, cumulative - max(prior_high_water_mark, 0.0))
        out["loss_recovery"] = {"method": "HIGH_WATER_MARK", "prior_high_water_mark": prior_high_water_mark,
                                "cumulative_attributable": cumulative, "chargeable_profit": round(chargeable, 8),
                                "new_high_water_mark": max(prior_high_water_mark, cumulative)}
    elif policy.loss_recovery is not None:
        out["loss_recovery"] = {"method": policy.loss_recovery, "status": "UNSUPPORTED_METHOD"}

    if policy.pending() or policy.loss_recovery != "HIGH_WATER_MARK":
        out["fee_status"] = "NOT_COMPUTED: " + ", ".join(policy.pending() or ["unsupported loss-recovery method"])
    else:
        out["fee"] = round(policy.fee_rate * out["loss_recovery"]["chargeable_profit"], 8)
        out["fee_status"] = f"COMPUTED under approved policy {policy.version} ({policy.approval_ref})"
    return out
