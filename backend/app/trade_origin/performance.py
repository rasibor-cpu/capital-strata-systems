"""Segregated performance: CSS-recommended vs user-independent results (Issue #102).

The customer must be able to answer, at a glance:
  "How much profit/loss came from CSS recommendations?" and "How much came from trades I chose myself?"

Segments: CSS_RECOMMENDED, CSS_RECOMMENDED_MODIFIED, USER_INDEPENDENT, UNATTRIBUTED_REVIEW_REQUIRED.
The total is the exact sum of the segments (checked), and is never shown without them.

Commercial attribution: this module only supplies segregated figures. It does not compute fees and does not change
billing economics. How modified or unattributed trades are treated commercially is governed by the existing approved
CSS commercial-attribution rules and is not decided here.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .lifecycle import TradeLifecycle
from .model import ORIGIN_LABELS, ORIGIN_POLICY_VERSION, TradeOrigin

SEGMENTS = [TradeOrigin.CSS_RECOMMENDED, TradeOrigin.CSS_RECOMMENDED_MODIFIED, TradeOrigin.USER_INDEPENDENT,
            TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED]


def _empty(origin: TradeOrigin) -> dict:
    return {"origin": origin.value, "label": ORIGIN_LABELS[origin], "realized_pnl": 0.0, "unrealized_pnl": 0.0,
            "closed_trades": 0, "wins": 0, "losses": 0, "flat": 0, "open_positions": 0}


def segregate(lifecycle: TradeLifecycle, marks: Optional[Dict[str, float]] = None) -> dict:
    marks = {k.upper(): v for k, v in (marks or {}).items()}
    seg = {o: _empty(o) for o in SEGMENTS}
    missing_marks = set()
    for lot in lifecycle.lots.values():
        s = seg[lot.origin.origin]
        s["realized_pnl"] += lot.realized_pnl
        if lot.is_closed:
            s["closed_trades"] += 1
            s["wins" if lot.realized_pnl > 0 else "losses" if lot.realized_pnl < 0 else "flat"] += 1
        elif lot.quantity_open > 0:
            s["open_positions"] += 1
            if lot.symbol in marks:
                sign = 1 if lot.side == "BUY" else -1
                s["unrealized_pnl"] += (marks[lot.symbol] - lot.avg_entry_price) * lot.quantity_open * sign
            else:
                missing_marks.add(lot.symbol)
    segments = [seg[o] for o in SEGMENTS]
    for s in segments:
        s["realized_pnl"] = round(s["realized_pnl"], 8)
        s["unrealized_pnl"] = round(s["unrealized_pnl"], 8)
        s["win_rate"] = round(s["wins"] / s["closed_trades"], 4) if s["closed_trades"] else None
    total = {k: round(sum(s[k] for s in segments), 8) for k in ("realized_pnl", "unrealized_pnl")}
    total.update({k: sum(s[k] for s in segments) for k in ("closed_trades", "wins", "losses", "flat", "open_positions")})
    css_all = {k: round(seg[TradeOrigin.CSS_RECOMMENDED][k] + seg[TradeOrigin.CSS_RECOMMENDED_MODIFIED][k], 8)
               for k in ("realized_pnl", "unrealized_pnl")}
    return {
        "policy_version": ORIGIN_POLICY_VERSION,
        "segments": segments,
        "headline": {
            "css_recommended_realized_pnl": seg[TradeOrigin.CSS_RECOMMENDED]["realized_pnl"],
            "css_recommended_incl_modified_realized_pnl": css_all["realized_pnl"],
            "user_independent_realized_pnl": seg[TradeOrigin.USER_INDEPENDENT]["realized_pnl"],
            "under_review_realized_pnl": seg[TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED]["realized_pnl"],
        },
        "total": total,
        "unrealized_incomplete_for": sorted(missing_marks),
        "commercial_note": ("Segregated figures only. Fees and billing follow the existing approved CSS "
                            "commercial-attribution rules and are not calculated here."),
    }


def check_totals(report: dict) -> List[str]:
    """Invariant: total == sum of segments, for every measure."""
    errs = []
    for k in ("realized_pnl", "unrealized_pnl", "closed_trades", "wins", "losses", "open_positions"):
        s = sum(seg[k] for seg in report["segments"])
        if abs(s - report["total"][k]) > 1e-6:
            errs.append(f"{k}: total {report['total'][k]} != segments {s}")
    return errs


def from_legacy_closed_trades(records: Iterable[dict]) -> dict:
    """Existing closed-trade records (e.g. artifacts/css_closed_trades.json) carry no origin. They are reported as
    UNATTRIBUTED_REVIEW_REQUIRED, never assumed to be CSS or user trades. An explicit, valid `origin` field is used
    as given; anything else is held for review."""
    seg = {o: _empty(o) for o in SEGMENTS}
    for r in records:
        raw = str(r.get("origin", "")).upper()
        origin = TradeOrigin(raw) if raw in TradeOrigin.__members__ else TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED
        try:
            pnl = float(r.get("realized_pnl_usd", r.get("net_realized_pnl_usd", 0.0)))
        except (TypeError, ValueError):
            pnl = 0.0
        s = seg[origin]
        s["realized_pnl"] += pnl
        s["closed_trades"] += 1
        s["wins" if pnl > 0 else "losses" if pnl < 0 else "flat"] += 1
    segments = [seg[o] for o in SEGMENTS]
    for s in segments:
        s["realized_pnl"] = round(s["realized_pnl"], 8)
        s["win_rate"] = round(s["wins"] / s["closed_trades"], 4) if s["closed_trades"] else None
    total = {"realized_pnl": round(sum(s["realized_pnl"] for s in segments), 8), "unrealized_pnl": 0.0}
    total.update({k: sum(s[k] for s in segments) for k in ("closed_trades", "wins", "losses", "flat", "open_positions")})
    return {"policy_version": ORIGIN_POLICY_VERSION, "segments": segments, "total": total,
            "headline": {"css_recommended_realized_pnl": seg[TradeOrigin.CSS_RECOMMENDED]["realized_pnl"],
                         "css_recommended_incl_modified_realized_pnl": round(
                             seg[TradeOrigin.CSS_RECOMMENDED]["realized_pnl"]
                             + seg[TradeOrigin.CSS_RECOMMENDED_MODIFIED]["realized_pnl"], 8),
                         "user_independent_realized_pnl": seg[TradeOrigin.USER_INDEPENDENT]["realized_pnl"],
                         "under_review_realized_pnl": seg[TradeOrigin.UNATTRIBUTED_REVIEW_REQUIRED]["realized_pnl"]},
            "unrealized_incomplete_for": [], "source": "legacy closed-trade records (no origin recorded)",
            "commercial_note": ("Segregated figures only. Fees and billing follow the existing approved CSS "
                                "commercial-attribution rules and are not calculated here.")}
