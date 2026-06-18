"""Advisory-only stock alert evaluation for runtime diagnostics.

This module is intentionally informational. It does not create signals, place
orders, call brokers, mutate risk state, or influence execution gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence


STOCK_ALERT_TYPES = {
    "PRICE_CROSSES_ABOVE",
    "PRICE_CROSSES_BELOW",
    "INTRADAY_PERCENT_MOVE",
    "VOLUME_SPIKE",
    "GAP_UP",
    "GAP_DOWN",
    "NEW_HIGH",
    "NEW_LOW",
    "WATCHLIST_SIGNAL",
    "RISK_WARNING",
    "MARKET_HALT_ABNORMAL_DATA",
}

STOCK_ALERT_SEVERITIES = {
    "INFO",
    "WATCH",
    "WARNING",
    "CRITICAL",
}


@dataclass(frozen=True)
class StockAlertRule:
    alert_type: str
    symbol: str
    threshold: float | None = None
    severity: str = "INFO"
    data_source: str = "RUNTIME"
    enabled: bool = True
    message: str | None = None


def generate_stock_alerts(
    snapshot: Mapping[str, Any],
    rules: Sequence[StockAlertRule | Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate configured advisory alert rules against one market snapshot."""

    alerts: list[dict[str, Any]] = []

    for raw_rule in rules:
        rule = _coerce_rule(raw_rule)
        if rule is None or not rule.enabled:
            continue

        symbol = str(snapshot.get("symbol", snapshot.get("instrument", ""))).upper()
        if rule.symbol and rule.symbol.upper() not in {symbol, "*"}:
            continue

        triggered, observed_value, threshold_value, reason = _evaluate_rule(
            snapshot=snapshot,
            rule=rule,
        )
        if not triggered:
            continue

        alerts.append(
            {
                "event_type": "STOCK_ALERT",
                "symbol": symbol,
                "alert_type": rule.alert_type.upper(),
                "severity": _normalize_severity(rule.severity),
                "observed_value": observed_value,
                "threshold_value": threshold_value,
                "data_source": str(rule.data_source or "RUNTIME"),
                "source_timestamp": snapshot.get("source_timestamp"),
                "detection_timestamp": _utc_timestamp(),
                "reason": reason,
                "message": rule.message or reason,
                "advisory_only": True,
                "execution_authority": "NONE",
            }
        )

    return alerts


def _coerce_rule(raw_rule: StockAlertRule | Mapping[str, Any]) -> StockAlertRule | None:
    if isinstance(raw_rule, StockAlertRule):
        return raw_rule

    if not isinstance(raw_rule, Mapping):
        return None

    try:
        return StockAlertRule(
            alert_type=str(raw_rule.get("alert_type", "")),
            symbol=str(raw_rule.get("symbol", "*")),
            threshold=_optional_float(raw_rule.get("threshold")),
            severity=str(raw_rule.get("severity", "INFO")),
            data_source=str(raw_rule.get("data_source", "RUNTIME")),
            enabled=bool(raw_rule.get("enabled", True)),
            message=(
                None
                if raw_rule.get("message") is None
                else str(raw_rule.get("message"))
            ),
        )
    except Exception:
        return None


def _evaluate_rule(
    *,
    snapshot: Mapping[str, Any],
    rule: StockAlertRule,
) -> tuple[bool, float | None, float | None, str]:
    alert_type = rule.alert_type.upper()

    if alert_type not in STOCK_ALERT_TYPES:
        return False, None, rule.threshold, "unsupported_alert_type"

    price = _optional_float(snapshot.get("price"))
    previous_price = _optional_float(snapshot.get("previous_price"))
    threshold = rule.threshold

    if alert_type == "PRICE_CROSSES_ABOVE":
        return _crosses_above(price, previous_price, threshold)

    if alert_type == "PRICE_CROSSES_BELOW":
        return _crosses_below(price, previous_price, threshold)

    if alert_type == "INTRADAY_PERCENT_MOVE":
        pct_move = _optional_float(snapshot.get("intraday_pct_move"))
        if pct_move is None and price is not None and previous_price:
            pct_move = ((price - previous_price) / previous_price) * 100.0
        if pct_move is not None and threshold is not None and abs(pct_move) >= threshold:
            return True, pct_move, threshold, "intraday_percent_move_threshold"
        return False, pct_move, threshold, "intraday_percent_move_not_triggered"

    if alert_type == "VOLUME_SPIKE":
        volume_ratio = _optional_float(snapshot.get("volume_ratio"))
        if volume_ratio is not None and threshold is not None and volume_ratio >= threshold:
            return True, volume_ratio, threshold, "volume_spike_threshold"
        return False, volume_ratio, threshold, "volume_spike_not_triggered"

    if alert_type == "GAP_UP":
        gap_pct = _optional_float(snapshot.get("gap_pct"))
        if gap_pct is not None and threshold is not None and gap_pct >= threshold:
            return True, gap_pct, threshold, "gap_up_threshold"
        return False, gap_pct, threshold, "gap_up_not_triggered"

    if alert_type == "GAP_DOWN":
        gap_pct = _optional_float(snapshot.get("gap_pct"))
        if gap_pct is not None and threshold is not None and gap_pct <= -abs(threshold):
            return True, gap_pct, threshold, "gap_down_threshold"
        return False, gap_pct, threshold, "gap_down_not_triggered"

    if alert_type == "NEW_HIGH":
        high = _optional_float(snapshot.get("lookback_high"))
        if price is not None and high is not None and price >= high:
            return True, price, high, "new_high_observed"
        return False, price, high, "new_high_not_triggered"

    if alert_type == "NEW_LOW":
        low = _optional_float(snapshot.get("lookback_low"))
        if price is not None and low is not None and price <= low:
            return True, price, low, "new_low_observed"
        return False, price, low, "new_low_not_triggered"

    if alert_type == "WATCHLIST_SIGNAL":
        if bool(snapshot.get("watchlist_match", True)):
            return True, price, threshold, "watchlist_signal"
        return False, price, threshold, "watchlist_not_triggered"

    if alert_type == "RISK_WARNING":
        warning = snapshot.get("risk_warning")
        if bool(warning):
            return True, price, threshold, str(warning)
        return False, price, threshold, "risk_warning_not_triggered"

    abnormal = snapshot.get("abnormal_data") or snapshot.get("market_halt")
    if bool(abnormal):
        return True, price, threshold, "market_halt_or_abnormal_data"

    return False, price, threshold, "market_halt_not_triggered"


def _crosses_above(
    price: float | None,
    previous_price: float | None,
    threshold: float | None,
) -> tuple[bool, float | None, float | None, str]:
    if price is None or threshold is None:
        return False, price, threshold, "price_cross_above_missing_input"
    if previous_price is None:
        triggered = price > threshold
    else:
        triggered = previous_price <= threshold < price
    return triggered, price, threshold, (
        "price_crossed_above_threshold" if triggered else "price_cross_above_not_triggered"
    )


def _crosses_below(
    price: float | None,
    previous_price: float | None,
    threshold: float | None,
) -> tuple[bool, float | None, float | None, str]:
    if price is None or threshold is None:
        return False, price, threshold, "price_cross_below_missing_input"
    if previous_price is None:
        triggered = price < threshold
    else:
        triggered = previous_price >= threshold > price
    return triggered, price, threshold, (
        "price_crossed_below_threshold" if triggered else "price_cross_below_not_triggered"
    )


def _normalize_severity(severity: str) -> str:
    normalized = str(severity or "INFO").upper()
    return normalized if normalized in STOCK_ALERT_SEVERITIES else "INFO"


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()
