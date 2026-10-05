"""Segregated performance: CSS-attributable vs independent results (Issue #102).

The customer can answer at a glance: "How much profit/loss came from CSS recommendations?" and "How much came from
trades I chose myself?", plus the combined account result.

Segments: CSS_RECOMMENDED, CSS_RECOMMENDED_MODIFIED, USER_INDEPENDENT, ORIGIN_UNDER_REVIEW. The combined total is the
exact sum of the segments (checked) and is never shown without them. Fees are handled in commercial.py.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .lifecycle import TradeLifecycle
from .model import ORIGIN_LABELS, ORIGIN_POLICY_VERSION, TradeOrigin

SEGMENTS = [TradeOrigin.CSS_RECOMMENDED, TradeOrigin.CSS_RECOMMENDED_MODIFIED, TradeOrigin.USER_INDEPENDENT,
            TradeOrigin.ORIGIN_UNDER_REVIEW]
MEASURES = ("realized_pnl", "unrealized_pnl", "closed_trades", "wins", "losses", "flat", "open_positions")


def _empty(origin: TradeOrigin) -> dict:
    return {"origin": origin.value, "label": ORIGIN_LABELS[origin], "realized_pnl": 0.0, "unrealized_pnl": 0.0,
            "closed_trades": 0, "wins": 0, "losses": 0, "flat": 0, "open_positions": 0}


def _finish(seg: Dict[TradeOrigin, dict], extra: dict) -> dict:
    segments = [seg[o] for o in SEGMENTS]
    for s in segments:
        s["realized_pnl"] = round(s["realized_pnl"], 8)
        s["unrealized_pnl"] = round(s["unrealized_pnl"], 8)
        s["win_rate"] = round(s["wins"] / s["closed_trades"], 4) if s["closed_trades"] else None
    total = {k: (round(sum(s[k] for s in segments), 8) if k.endswith("pnl") else sum(s[k] for s in segments)) for k in MEASURES}
    css, mod = seg[TradeOrigin.CSS_RECOMMENDED], seg[TradeOrigin.CSS_RECOMMENDED_MODIFIED]
    return {
        "policy_version": ORIGIN_POLICY_VERSION, "segments": segments, "total": total,
        "views": {
            "css_attributable": {"label": "From CSS-attributable trades",
                                 "realized_pnl": round(css["realized_pnl"] + mod["realized_pnl"], 8),
                                 "unrealized_pnl": round(css["unrealized_pnl"] + mod["unrealized_pnl"], 8),
                                 "includes": [TradeOrigin.CSS_RECOMMENDED.value, TradeOrigin.CSS_RECOMMENDED_MODIFIED.value]},
            "independent": {"label": "From your independent trades",
                            "realized_pnl": seg[TradeOrigin.USER_INDEPENDENT]["realized_pnl"],
                            "unrealized_pnl": seg[TradeOrigin.USER_INDEPENDENT]["unrealized_pnl"]},
            "under_review": {"label": "Origin under review",
                             "realized_pnl": seg[TradeOrigin.ORIGIN_UNDER_REVIEW]["realized_pnl"],
                             "unrealized_pnl": seg[TradeOrigin.ORIGIN_UNDER_REVIEW]["unrealized_pnl"]},
            "combined": {"label": "Combined account result", "realized_pnl": total["realized_pnl"],
                         "unrealized_pnl": total["unrealized_pnl"]},
        },
        "headline": {
            "css_recommended_realized_pnl": css["realized_pnl"],
            "css_recommended_incl_modified_realized_pnl": round(css["realized_pnl"] + mod["realized_pnl"], 8),
            "user_independent_realized_pnl": seg[TradeOrigin.USER_INDEPENDENT]["realized_pnl"],
            "under_review_realized_pnl": seg[TradeOrigin.ORIGIN_UNDER_REVIEW]["realized_pnl"],
        },
        "commercial_note": "Segregated figures only. Fee bases are computed separately under an approved commercial policy.",
        **extra,
    }


def segregate(lifecycle: TradeLifecycle, marks: Optional[Dict[str, float]] = None) -> dict:
    marks = {k.upper(): v for k, v in (marks or {}).items()}
    seg = {o: _empty(o) for o in SEGMENTS}
    missing = set()
    for lot in lifecycle.lots.values():
        s = seg[lifecycle.origin_of(lot)]
        s["realized_pnl"] += lot.realized_pnl
        if lot.is_closed:
            s["closed_trades"] += 1
            s["wins" if lot.realized_pnl > 0 else "losses" if lot.realized_pnl < 0 else "flat"] += 1
        elif lot.quantity_open > 0:
            s["open_positions"] += 1
            if lot.symbol in marks:
                s["unrealized_pnl"] += (marks[lot.symbol] - lot.avg_entry_price) * lot.quantity_open * (1 if lot.side == "BUY" else -1)
            else:
                missing.add(lot.symbol)
    return _finish(seg, {"unrealized_incomplete_for": sorted(missing)})


def check_totals(report: dict) -> List[str]:
    """Invariant: combined total == sum of segments, for every measure."""
    errs = []
    for k in MEASURES:
        s = sum(seg[k] for seg in report["segments"])
        if abs(s - report["total"][k]) > 1e-6:
            errs.append(f"{k}: total {report['total'][k]} != segments {s}")
    v = report.get("views", {})
    if v and abs(v["combined"]["realized_pnl"] - report["total"]["realized_pnl"]) > 1e-6:
        errs.append("combined view differs from total")
    return errs


def from_legacy_closed_trades(records: Iterable[dict]) -> dict:
    """Existing closed-trade records (e.g. artifacts/css_closed_trades.json) carry no origin. They are reported as
    ORIGIN_UNDER_REVIEW, never assumed to be CSS or user trades. A valid explicit `origin` field is used as given."""
    seg = {o: _empty(o) for o in SEGMENTS}
    for r in records:
        origin = TradeOrigin.parse(r.get("origin"))
        try:
            pnl = float(r.get("realized_pnl_usd", r.get("net_realized_pnl_usd", 0.0)))
        except (TypeError, ValueError):
            pnl = 0.0
        s = seg[origin]
        s["realized_pnl"] += pnl
        s["closed_trades"] += 1
        s["wins" if pnl > 0 else "losses" if pnl < 0 else "flat"] += 1
    return _finish(seg, {"unrealized_incomplete_for": [], "source": "legacy closed-trade records (no origin recorded)"})
