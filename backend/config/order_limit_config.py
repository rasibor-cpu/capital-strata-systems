from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


SAFE_FLAGS = {
    "paper_only": True,
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}


class OrderLimitConfigurationError(ValueError):
    """Raised when order/exposure limit configuration fails closed."""


@dataclass(frozen=True)
class CanonicalOrderLimitConfig:
    """Typed advisory limit configuration.

    Live limits are ceilings only and never grant execution authority. Paper and
    preview values can model larger hypothetical amounts independently.
    """

    live_order_default_notional_usd: Decimal = Decimal("1.00")
    live_pilot_max_total_cad: Decimal = Decimal("20.00")
    live_pilot_max_position_cad: Decimal = Decimal("20.00")
    live_pilot_daily_loss_cad: Decimal = Decimal("2.00")
    live_pilot_session_loss_cad: Decimal = Decimal("4.00")
    live_pilot_max_concurrent_positions: int = 1
    live_pilot_max_orders_per_session: int = 10
    paper_order_default_notional_usd: Decimal = Decimal("1000.00")
    paper_order_max_notional_usd: Decimal = Decimal("1000000.00")
    preview_max_hypothetical_notional_usd: Decimal = Decimal("10000000.00")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None = None) -> "CanonicalOrderLimitConfig":
        values = dict(payload or {})
        config = cls(
            live_order_default_notional_usd=_money(
                values,
                "live_order_default_notional_usd",
                cls.live_order_default_notional_usd,
            ),
            live_pilot_max_total_cad=_money(
                values,
                "live_pilot_max_total_cad",
                cls.live_pilot_max_total_cad,
            ),
            live_pilot_max_position_cad=_money(
                values,
                "live_pilot_max_position_cad",
                cls.live_pilot_max_position_cad,
            ),
            live_pilot_daily_loss_cad=_money(
                values,
                "live_pilot_daily_loss_cad",
                cls.live_pilot_daily_loss_cad,
            ),
            live_pilot_session_loss_cad=_money(
                values,
                "live_pilot_session_loss_cad",
                cls.live_pilot_session_loss_cad,
            ),
            live_pilot_max_concurrent_positions=_count(
                values,
                "live_pilot_max_concurrent_positions",
                cls.live_pilot_max_concurrent_positions,
            ),
            live_pilot_max_orders_per_session=_count(
                values,
                "live_pilot_max_orders_per_session",
                cls.live_pilot_max_orders_per_session,
            ),
            paper_order_default_notional_usd=_money(
                values,
                "paper_order_default_notional_usd",
                cls.paper_order_default_notional_usd,
            ),
            paper_order_max_notional_usd=_money(
                values,
                "paper_order_max_notional_usd",
                cls.paper_order_max_notional_usd,
            ),
            preview_max_hypothetical_notional_usd=_money(
                values,
                "preview_max_hypothetical_notional_usd",
                cls.preview_max_hypothetical_notional_usd,
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        _at_most(self.live_order_default_notional_usd, Decimal("1.00"), "live_order_default_notional_usd")
        _at_most(self.live_pilot_max_total_cad, Decimal("20.00"), "live_pilot_max_total_cad")
        _at_most(self.live_pilot_max_position_cad, Decimal("20.00"), "live_pilot_max_position_cad")
        _at_most(self.live_pilot_daily_loss_cad, Decimal("2.00"), "live_pilot_daily_loss_cad")
        _at_most(self.live_pilot_session_loss_cad, Decimal("4.00"), "live_pilot_session_loss_cad")
        _count_at_most(
            self.live_pilot_max_concurrent_positions,
            1,
            "live_pilot_max_concurrent_positions",
        )
        _count_at_most(
            self.live_pilot_max_orders_per_session,
            10,
            "live_pilot_max_orders_per_session",
        )
        _at_most(self.paper_order_default_notional_usd, self.paper_order_max_notional_usd, "paper_order_default_notional_usd")
        _at_most(self.paper_order_max_notional_usd, Decimal("1000000.00"), "paper_order_max_notional_usd")
        _at_most(
            self.preview_max_hypothetical_notional_usd,
            Decimal("10000000.00"),
            "preview_max_hypothetical_notional_usd",
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = _money_string(value)
        return {**payload, **SAFE_FLAGS}


DEFAULT_ORDER_LIMIT_CONFIG = CanonicalOrderLimitConfig()


def load_order_limit_config(payload: Mapping[str, Any] | None = None) -> CanonicalOrderLimitConfig:
    return CanonicalOrderLimitConfig.from_mapping(payload)


def _money(values: Mapping[str, Any], key: str, default: Decimal) -> Decimal:
    raw = values.get(key, default)
    try:
        value = Decimal(str(raw)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise OrderLimitConfigurationError(f"{key} must be a finite decimal amount") from exc
    if not value.is_finite():
        raise OrderLimitConfigurationError(f"{key} must be finite")
    if value < Decimal("0.00"):
        raise OrderLimitConfigurationError(f"{key} must be non-negative")
    return value


def _count(values: Mapping[str, Any], key: str, default: int) -> int:
    try:
        value = int(values.get(key, default))
    except (TypeError, ValueError) as exc:
        raise OrderLimitConfigurationError(f"{key} must be an integer") from exc
    if value < 0:
        raise OrderLimitConfigurationError(f"{key} must be non-negative")
    return value


def _at_most(value: Decimal, ceiling: Decimal, key: str) -> None:
    if value > ceiling:
        raise OrderLimitConfigurationError(f"{key} exceeds canonical ceiling {ceiling}")


def _count_at_most(value: int, ceiling: int, key: str) -> None:
    if value > ceiling:
        raise OrderLimitConfigurationError(f"{key} exceeds canonical ceiling {ceiling}")


def _money_string(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


__all__ = [
    "CanonicalOrderLimitConfig",
    "DEFAULT_ORDER_LIMIT_CONFIG",
    "OrderLimitConfigurationError",
    "SAFE_FLAGS",
    "load_order_limit_config",
]
