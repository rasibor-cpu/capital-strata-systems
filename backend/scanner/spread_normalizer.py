from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


MAX_SPREAD_BPS_HARD_CAP = 250.0
DEFAULT_SPREAD_BPS = 35.0
MIN_SPREAD_BPS = 0.5


@dataclass
class SpreadDiagnostics:
    product_id: str
    source: str
    bid: float
    ask: float
    mid: float
    raw_spread_bps: float
    normalized_spread_bps: float
    capped: bool
    valid_book: bool


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _first_present(snapshot: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in snapshot and snapshot[key] not in (None, "", []):
            return snapshot[key]
    return None


def _extract_bid_ask(snapshot: Dict[str, Any]) -> tuple[float | None, float | None]:
    bid = _to_float(
        _first_present(
            snapshot,
            [
                "best_bid",
                "bid",
                "bid_price",
                "best_bid_price",
            ],
        )
    )
    ask = _to_float(
        _first_present(
            snapshot,
            [
                "best_ask",
                "ask",
                "ask_price",
                "best_ask_price",
            ],
        )
    )
    return bid, ask


def _extract_last_price(snapshot: Dict[str, Any]) -> float | None:
    return _to_float(
        _first_present(
            snapshot,
            [
                "price",
                "last",
                "last_price",
                "close",
                "mark_price",
                "mid_price",
            ],
        )
    )


def _safe_mid(bid: float | None, ask: float | None, last_price: float | None) -> float | None:
    if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid:
        return (bid + ask) / 2.0
    if last_price is not None and last_price > 0:
        return last_price
    if bid is not None and bid > 0:
        return bid
    if ask is not None and ask > 0:
        return ask
    return None


def _compute_spread_bps(bid: float, ask: float, mid: float) -> float:
    if mid <= 0 or ask < bid:
        return DEFAULT_SPREAD_BPS
    return max(MIN_SPREAD_BPS, ((ask - bid) / mid) * 10000.0)


def normalize_snapshot_spread(
    snapshot: Dict[str, Any],
    *,
    fallback_spread_bps: float = DEFAULT_SPREAD_BPS,
    hard_cap_bps: float = MAX_SPREAD_BPS_HARD_CAP,
) -> Dict[str, Any]:

    product_id = str(snapshot.get("product_id") or snapshot.get("symbol") or "UNKNOWN")

    bid, ask = _extract_bid_ask(snapshot)
    last_price = _extract_last_price(snapshot)
    mid = _safe_mid(bid, ask, last_price)

    valid_book = (
        bid is not None
        and ask is not None
        and bid > 0
        and ask > 0
        and ask >= bid
    )

    capped = False
    source = "order_book"

    if valid_book and mid is not None:
        raw_spread_bps = _compute_spread_bps(bid, ask, mid)
        normalized_spread_bps = raw_spread_bps

        if normalized_spread_bps > hard_cap_bps:
            normalized_spread_bps = min(fallback_spread_bps, hard_cap_bps)
            capped = True
            source = "book_capped"
    else:
        raw_spread_bps = fallback_spread_bps
        normalized_spread_bps = min(fallback_spread_bps, hard_cap_bps)
        source = "fallback"

        if raw_spread_bps > hard_cap_bps:
            capped = True

    diagnostics = SpreadDiagnostics(
        product_id=product_id,
        source=source,
        bid=bid or 0.0,
        ask=ask or 0.0,
        mid=mid or 0.0,
        raw_spread_bps=raw_spread_bps,
        normalized_spread_bps=normalized_spread_bps,
        capped=capped,
        valid_book=valid_book,
    )

    enriched = dict(snapshot)
    enriched["bid"] = bid
    enriched["ask"] = ask
    enriched["mid_price"] = mid
    enriched["spread_bps_raw"] = round(raw_spread_bps, 4)
    enriched["spread_bps"] = round(normalized_spread_bps, 4)
    enriched["spread_source"] = source
    enriched["spread_capped"] = capped
    enriched["spread_book_valid"] = valid_book
    return enriched


def normalize_snapshot_batch(
    snapshots: List[Dict[str, Any]],
    *,
    fallback_spread_bps: float = DEFAULT_SPREAD_BPS,
    hard_cap_bps: float = MAX_SPREAD_BPS_HARD_CAP,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for snapshot in snapshots:
        normalized.append(
            normalize_snapshot_spread(
                snapshot,
                fallback_spread_bps=fallback_spread_bps,
                hard_cap_bps=hard_cap_bps,
            )
        )
    return normalized