from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "artifacts" / "live_micro_pilot_config.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "artifacts" / "live_micro_pilot_state.json"
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "audit_logs" / "live_micro_pilot_audit.jsonl"

CONFIRMATION_WORD = "EXECUTE"
SUPER_USER_ROLE = "SUPER_USER"
LIVE_MODES = {"LIVE", "MOBILE_LIVE_TRADING_ARMED", "BROKER_LIVE", "PRODUCTION_LIVE"}


class LiveMicroPilotConfigurationError(RuntimeError):
    """Raised when the live micro-pilot configuration is unsafe or invalid."""


class LiveMicroPilotAuthorizationError(PermissionError):
    """Raised when a user attempts an operator action without SUPER_USER authority."""


@dataclass(frozen=True)
class LiveMicroPilotConfig:
    pilot_enabled: bool = False
    currency: str = "CAD"
    max_live_test_capital: Decimal = Decimal("20.00")
    max_position_size: Decimal = Decimal("20.00")
    max_concurrent_positions: int = 1
    max_orders_per_session: int = 10
    daily_loss_limit: Decimal = Decimal("2.00")
    session_loss_limit: Decimal = Decimal("4.00")
    allow_pyramiding: bool = False
    allow_averaging_down: bool = False
    require_manual_live_arming: bool = True
    require_explicit_confirmation_word: str = CONFIRMATION_WORD
    auto_disarm_on_limit_breach: bool = True
    fail_closed_if_config_missing: bool = True

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LiveMicroPilotConfig":
        def money(key: str, default: Decimal) -> Decimal:
            try:
                value = Decimal(str(payload.get(key, default))).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError) as exc:
                raise LiveMicroPilotConfigurationError(f"{key} must be a decimal amount") from exc
            if value < Decimal("0.00"):
                raise LiveMicroPilotConfigurationError(f"{key} must be non-negative")
            return value

        def count(key: str, default: int) -> int:
            try:
                value = int(payload.get(key, default))
            except (TypeError, ValueError) as exc:
                raise LiveMicroPilotConfigurationError(f"{key} must be an integer") from exc
            if value < 0:
                raise LiveMicroPilotConfigurationError(f"{key} must be non-negative")
            return value

        config = cls(
            pilot_enabled=_bool(payload.get("pilot_enabled", False)),
            currency=str(payload.get("currency", "CAD") or "CAD").upper(),
            max_live_test_capital=money("max_live_test_capital", Decimal("20.00")),
            max_position_size=money("max_position_size", Decimal("20.00")),
            max_concurrent_positions=count("max_concurrent_positions", 1),
            max_orders_per_session=count("max_orders_per_session", 10),
            daily_loss_limit=money("daily_loss_limit", Decimal("2.00")),
            session_loss_limit=money("session_loss_limit", Decimal("4.00")),
            allow_pyramiding=_bool(payload.get("allow_pyramiding", False)),
            allow_averaging_down=_bool(payload.get("allow_averaging_down", False)),
            require_manual_live_arming=_bool(payload.get("require_manual_live_arming", True)),
            require_explicit_confirmation_word=str(
                payload.get("require_explicit_confirmation_word", CONFIRMATION_WORD) or CONFIRMATION_WORD
            ).upper(),
            auto_disarm_on_limit_breach=_bool(payload.get("auto_disarm_on_limit_breach", True)),
            fail_closed_if_config_missing=_bool(payload.get("fail_closed_if_config_missing", True)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.currency != "CAD":
            raise LiveMicroPilotConfigurationError("Phase 152A live micro-pilot currency must be CAD")
        if self.max_live_test_capital > Decimal("20.00"):
            raise LiveMicroPilotConfigurationError("max_live_test_capital cannot exceed CAD 20.00")
        if self.max_position_size > Decimal("20.00"):
            raise LiveMicroPilotConfigurationError("max_position_size cannot exceed CAD 20.00")
        if self.max_concurrent_positions > 1:
            raise LiveMicroPilotConfigurationError("max_concurrent_positions cannot exceed 1")
        if self.max_orders_per_session > 10:
            raise LiveMicroPilotConfigurationError("max_orders_per_session cannot exceed 10")
        if self.daily_loss_limit > Decimal("2.00"):
            raise LiveMicroPilotConfigurationError("daily_loss_limit cannot exceed CAD 2.00")
        if self.session_loss_limit > Decimal("4.00"):
            raise LiveMicroPilotConfigurationError("session_loss_limit cannot exceed CAD 4.00")
        if self.allow_pyramiding:
            raise LiveMicroPilotConfigurationError("allow_pyramiding cannot be true for Phase 152A")
        if self.allow_averaging_down:
            raise LiveMicroPilotConfigurationError("allow_averaging_down cannot be true for Phase 152A")
        if self.require_explicit_confirmation_word != CONFIRMATION_WORD:
            raise LiveMicroPilotConfigurationError("confirmation word must remain EXECUTE")

    def as_dict(self) -> dict[str, Any]:
        return {
            "pilot_enabled": self.pilot_enabled,
            "currency": self.currency,
            "max_live_test_capital": _money_string(self.max_live_test_capital),
            "max_position_size": _money_string(self.max_position_size),
            "max_concurrent_positions": self.max_concurrent_positions,
            "max_orders_per_session": self.max_orders_per_session,
            "daily_loss_limit": _money_string(self.daily_loss_limit),
            "session_loss_limit": _money_string(self.session_loss_limit),
            "allow_pyramiding": self.allow_pyramiding,
            "allow_averaging_down": self.allow_averaging_down,
            "require_manual_live_arming": self.require_manual_live_arming,
            "require_explicit_confirmation_word": self.require_explicit_confirmation_word,
            "auto_disarm_on_limit_breach": self.auto_disarm_on_limit_breach,
            "fail_closed_if_config_missing": self.fail_closed_if_config_missing,
        }


@dataclass(frozen=True)
class LiveMicroPilotDecision:
    approved: bool
    reason: str
    status: dict[str, Any] = field(default_factory=dict)
    audit_event_type: str = "LIVE_MICRO_PILOT_EVALUATED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "status": self.status,
            "audit_event_type": self.audit_event_type,
        }


class LiveMicroPilotGovernor:
    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        state_path: str | Path | None = None,
        audit_path: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path or os.getenv("CSS_LIVE_MICRO_PILOT_CONFIG") or DEFAULT_CONFIG_PATH)
        self.state_path = Path(state_path or os.getenv("CSS_LIVE_MICRO_PILOT_STATE") or DEFAULT_STATE_PATH)
        self.audit_path = Path(audit_path or os.getenv("CSS_LIVE_MICRO_PILOT_AUDIT") or DEFAULT_AUDIT_PATH)

    @staticmethod
    def default_config() -> LiveMicroPilotConfig:
        return LiveMicroPilotConfig()

    def load_config(self) -> tuple[LiveMicroPilotConfig, str]:
        if not self.config_path.exists():
            return self.default_config(), "DEFAULT_MISSING_FILE"
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8") or "{}")
            if not isinstance(payload, Mapping):
                raise LiveMicroPilotConfigurationError("config root must be an object")
            return LiveMicroPilotConfig.from_mapping(payload), "CONFIG_FILE"
        except (OSError, json.JSONDecodeError, LiveMicroPilotConfigurationError) as exc:
            raise LiveMicroPilotConfigurationError(str(exc)) from exc

    def write_config(
        self,
        updates: Mapping[str, Any],
        *,
        user_ctx: Mapping[str, Any],
        confirmation_word: str,
    ) -> dict[str, Any]:
        self._require_super_user(user_ctx)
        self._require_confirmation(confirmation_word)
        merged = self.default_config().as_dict()
        merged.update(dict(updates))
        config = LiveMicroPilotConfig.from_mapping(merged)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config.as_dict(), indent=2), encoding="utf-8")
        self._audit("LIVE_MICRO_PILOT_CONFIGURED", user_ctx=user_ctx, reason="operator_configured")
        return self.status(config=config, config_source="CONFIG_FILE")

    def arm(self, *, user_ctx: Mapping[str, Any], confirmation_word: str) -> dict[str, Any]:
        self._require_super_user(user_ctx)
        self._require_confirmation(confirmation_word)
        config, source = self.load_config()
        if source != "CONFIG_FILE" and config.fail_closed_if_config_missing:
            raise LiveMicroPilotConfigurationError("cannot arm without explicit live micro-pilot config file")
        if not config.pilot_enabled:
            raise LiveMicroPilotConfigurationError("cannot arm while pilot_enabled is false")
        state = self._load_state()
        state.update(
            {
                "pilot_armed": True,
                "pilot_state": "ARMED",
                "last_status_reason": "operator_armed",
                "armed_at": _utc_now(),
            }
        )
        self._save_state(state)
        self._audit("LIVE_MICRO_PILOT_ARMED", user_ctx=user_ctx, reason="operator_armed")
        return self.status(config=config, config_source=source, state=state)

    def disarm(
        self,
        *,
        user_ctx: Mapping[str, Any],
        confirmation_word: str | None = None,
        reason: str = "operator_disarmed",
        require_confirmation: bool = True,
    ) -> dict[str, Any]:
        self._require_super_user(user_ctx)
        if require_confirmation:
            self._require_confirmation(confirmation_word or "")
        state = self._load_state()
        state.update(
            {
                "pilot_armed": False,
                "pilot_state": "DISARMED",
                "last_status_reason": reason,
                "disarmed_at": _utc_now(),
            }
        )
        self._save_state(state)
        self._audit("LIVE_MICRO_PILOT_DISARMED", user_ctx=user_ctx, reason=reason)
        return self.status(state=state)

    def evaluate_order(
        self,
        order: Mapping[str, Any],
        *,
        open_positions: list[Mapping[str, Any]] | None = None,
        daily_pnl: Any = None,
        session_pnl: Any = None,
        config: LiveMicroPilotConfig | None = None,
        config_source: str | None = None,
        state: Mapping[str, Any] | None = None,
    ) -> LiveMicroPilotDecision:
        if not _is_live_order(order):
            return LiveMicroPilotDecision(True, "not_live_request", self.status(config=config, state=state))

        config_missing = False
        if config is None:
            try:
                config, config_source = self.load_config()
            except LiveMicroPilotConfigurationError as exc:
                return self._reject("live_micro_pilot_config_invalid", str(exc), config=self.default_config())
            config_missing = config_source != "CONFIG_FILE"
        if config_missing and config.fail_closed_if_config_missing:
            return self._reject("live_micro_pilot_config_missing", "explicit config file required", config=config)

        state_data = dict(state or self._load_state())
        if not config.pilot_enabled:
            return self._reject("live_micro_pilot_disabled", "pilot_enabled is false", config=config, state=state_data)
        if config.require_manual_live_arming and not bool(state_data.get("pilot_armed", False)):
            return self._reject("live_micro_pilot_not_armed", "manual live arming required", config=config, state=state_data)

        positions = [dict(item) for item in (open_positions if open_positions is not None else state_data.get("open_positions", [])) if isinstance(item, Mapping)]
        notional = _decimal(order.get("notional", order.get("amount", "0")))
        symbol = str(order.get("symbol", "")).upper()
        side = str(order.get("side", "")).upper()
        capital_deployed = sum(_position_notional(item) for item in positions)
        remaining_capacity = max(Decimal("0.00"), config.max_live_test_capital - capital_deployed)
        orders_used = int(state_data.get("orders_used_this_session", 0) or 0)
        daily_loss = _decimal(daily_pnl if daily_pnl is not None else state_data.get("daily_pnl", "0"))
        session_loss = _decimal(session_pnl if session_pnl is not None else state_data.get("session_pnl", "0"))

        if daily_loss <= -config.daily_loss_limit:
            return self._reject("daily_loss_limit_breached", "daily loss limit reached", config=config, state=state_data)
        if session_loss <= -config.session_loss_limit:
            return self._reject("session_loss_limit_breached", "session loss limit reached", config=config, state=state_data)
        if orders_used >= config.max_orders_per_session:
            return self._reject("max_orders_per_session_breached", "session order count limit reached", config=config, state=state_data)
        if notional <= Decimal("0.00"):
            return self._reject("invalid_live_notional", "live notional must be positive", config=config, state=state_data)
        if notional > config.max_position_size:
            return self._reject("max_position_size_breached", "order exceeds CAD 20 position size", config=config, state=state_data)
        if notional > remaining_capacity:
            return self._reject("max_live_test_capital_breached", "order exceeds remaining CAD 20 pilot capacity", config=config, state=state_data)
        if len(positions) >= config.max_concurrent_positions and not _same_symbol_position_exists(positions, symbol):
            return self._reject("max_concurrent_positions_breached", "open live position limit reached", config=config, state=state_data)
        if not config.allow_averaging_down and _averaging_down_position_exists(positions, symbol, side):
            return self._reject("averaging_down_blocked", "averaging down is disabled", config=config, state=state_data)
        if not config.allow_pyramiding and _same_direction_position_exists(positions, symbol, side):
            return self._reject("pyramiding_blocked", "pyramiding is disabled", config=config, state=state_data)

        status = self.status(config=config, config_source=config_source or "CONFIG_FILE", state=state_data)
        status["last_status_reason"] = "approved_for_downstream_gates"
        self._audit("LIVE_MICRO_PILOT_APPROVED", reason="approved_for_downstream_gates", order=order, status=status)
        return LiveMicroPilotDecision(True, "approved_for_downstream_gates", status, "LIVE_MICRO_PILOT_APPROVED")

    def record_order_submitted(self, order: Mapping[str, Any]) -> dict[str, Any]:
        if not _is_live_order(order):
            return self.status()
        state = self._load_state()
        state["orders_used_this_session"] = int(state.get("orders_used_this_session", 0) or 0) + 1
        positions = [item for item in state.get("open_positions", []) if isinstance(item, Mapping)]
        positions.append(
            {
                "symbol": str(order.get("symbol", "")).upper(),
                "side": str(order.get("side", "")).upper(),
                "notional": _money_string(_decimal(order.get("notional", order.get("amount", "0")))),
                "unrealized_pnl": "0.00",
                "recorded_at": _utc_now(),
            }
        )
        state["open_positions"] = positions
        state["last_status_reason"] = "order_recorded_after_downstream_approval"
        self._save_state(state)
        self._audit("LIVE_MICRO_PILOT_ORDER_RECORDED", reason="order_recorded_after_downstream_approval", order=order)
        return self.status(state=state)

    def status(
        self,
        *,
        config: LiveMicroPilotConfig | None = None,
        config_source: str | None = None,
        state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        config_valid = True
        config_error = ""
        if config is None:
            try:
                config, config_source = self.load_config()
            except LiveMicroPilotConfigurationError as exc:
                config = self.default_config()
                config_source = "INVALID_CONFIG"
                config_valid = False
                config_error = str(exc)
        state_data = dict(state or self._load_state())
        positions = [dict(item) for item in state_data.get("open_positions", []) if isinstance(item, Mapping)]
        deployed = sum(_position_notional(item) for item in positions)
        remaining = max(Decimal("0.00"), config.max_live_test_capital - deployed)
        armed = bool(state_data.get("pilot_armed", False))
        renewal_time = state_data.get("last_updated_at", "")
        return {
            "section_title": "Live Micro-Pilot Status",
            "pilot_enabled": config.pilot_enabled,
            "pilot_armed": armed,
            "pilot_state": str(state_data.get("pilot_state", "ARMED" if armed else "DISARMED")),
            "currency": config.currency,
            "max_live_test_capital": _money_string(config.max_live_test_capital),
            "max_position_size": _money_string(config.max_position_size),
            "remaining_live_test_capacity": _money_string(remaining),
            "capital_deployed": _money_string(deployed),
            "max_concurrent_positions": config.max_concurrent_positions,
            "open_live_positions": len(positions),
            "max_orders_per_session": config.max_orders_per_session,
            "orders_used_this_session": int(state_data.get("orders_used_this_session", 0) or 0),
            "daily_loss_limit": _money_string(config.daily_loss_limit),
            "session_loss_limit": _money_string(config.session_loss_limit),
            "daily_pnl": _money_string(_decimal(state_data.get("daily_pnl", "0"))),
            "session_pnl": _money_string(_decimal(state_data.get("session_pnl", "0"))),
            "allow_pyramiding": config.allow_pyramiding,
            "allow_averaging_down": config.allow_averaging_down,
            "require_manual_live_arming": config.require_manual_live_arming,
            "required_confirmation_word": config.require_explicit_confirmation_word,
            "auto_disarm_on_limit_breach": config.auto_disarm_on_limit_breach,
            "fail_closed_if_config_missing": config.fail_closed_if_config_missing,
            "config_source": config_source or "CONFIG_FILE",
            "config_valid": config_valid,
            "config_error": config_error,
            "pilot_guard_enforced": True,
            "broker_submission_guard": "REJECT_BEFORE_BROKER",
            "auto_flattening_enabled": False,
            "operator_controls": "SUPER_USER_ONLY",
            "execution_allowed": False,
            "advisory_only": True,
            "last_status_reason": str(state_data.get("last_status_reason", "status_read")),
            "last_updated_at": renewal_time,
            "reporting": {
                "cap_remaining": _money_string(remaining),
                "orders_remaining": max(0, config.max_orders_per_session - int(state_data.get("orders_used_this_session", 0) or 0)),
                "breach_action": "REJECT_AND_AUDIT_AUTO_DISARM_IF_CONFIGURED",
                "no_broker_connectivity_required": True,
            },
        }

    def _reject(
        self,
        reason: str,
        detail: str,
        *,
        config: LiveMicroPilotConfig,
        state: Mapping[str, Any] | None = None,
    ) -> LiveMicroPilotDecision:
        state_data = dict(state or self._load_state())
        if config.auto_disarm_on_limit_breach:
            state_data["pilot_armed"] = False
            state_data["pilot_state"] = "LIMIT_BREACHED"
            state_data["disarmed_at"] = _utc_now()
        state_data["last_status_reason"] = reason
        state_data["last_rejection_detail"] = detail
        self._save_state(state_data)
        status = self.status(config=config, state=state_data)
        self._audit("LIVE_MICRO_PILOT_REJECTED", reason=reason, detail=detail, status=status)
        return LiveMicroPilotDecision(False, reason, status, "LIVE_MICRO_PILOT_REJECTED")

    def _require_super_user(self, user_ctx: Mapping[str, Any]) -> None:
        if str(user_ctx.get("role", "")).strip().upper() != SUPER_USER_ROLE:
            self._audit("LIVE_MICRO_PILOT_OPERATOR_DENIED", user_ctx=user_ctx, reason="super_user_required")
            raise LiveMicroPilotAuthorizationError("Live Micro-Pilot controls require SUPER_USER")

    def _require_confirmation(self, confirmation_word: str) -> None:
        if str(confirmation_word).strip().upper() != CONFIRMATION_WORD:
            raise LiveMicroPilotAuthorizationError("Live Micro-Pilot controls require EXECUTE confirmation")

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"pilot_armed": False, "pilot_state": "DISARMED", "orders_used_this_session": 0, "open_positions": []}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
            return dict(payload) if isinstance(payload, Mapping) else {}
        except (OSError, json.JSONDecodeError):
            return {"pilot_armed": False, "pilot_state": "FAIL_CLOSED", "orders_used_this_session": 0, "open_positions": []}

    def _save_state(self, state: Mapping[str, Any]) -> None:
        payload = dict(state)
        payload["last_updated_at"] = _utc_now()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")

    def _audit(self, event_type: str, **fields: Any) -> None:
        payload = {
            "event_type": event_type,
            "timestamp": _utc_now(),
            "source": "backend.runtime.live_micro_pilot_governor",
            **fields,
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_json_safe(payload), sort_keys=True) + "\n")


def live_micro_pilot_status() -> dict[str, Any]:
    return LiveMicroPilotGovernor().status()


def _is_live_order(order: Mapping[str, Any]) -> bool:
    broker_mode = str(order.get("broker_mode", order.get("mode", ""))).strip().upper()
    mobile_mode = str(order.get("mobile_trading_mode", "")).strip().upper()
    broker = str(order.get("broker", "")).strip().upper()
    return broker_mode in {"LIVE", "REAL"} or mobile_mode in LIVE_MODES or (broker and broker != "CSS_PAPER" and broker_mode != "PAPER")


def _same_symbol_position_exists(positions: list[Mapping[str, Any]], symbol: str) -> bool:
    return any(str(item.get("symbol", "")).upper() == symbol for item in positions)


def _same_direction_position_exists(positions: list[Mapping[str, Any]], symbol: str, side: str) -> bool:
    return any(str(item.get("symbol", "")).upper() == symbol and str(item.get("side", "")).upper() == side for item in positions)


def _averaging_down_position_exists(positions: list[Mapping[str, Any]], symbol: str, side: str) -> bool:
    for item in positions:
        if str(item.get("symbol", "")).upper() != symbol:
            continue
        if str(item.get("side", "")).upper() != side:
            continue
        if _decimal(item.get("unrealized_pnl", "0")) < Decimal("0.00"):
            return True
    return False


def _position_notional(position: Mapping[str, Any]) -> Decimal:
    return _decimal(position.get("notional", position.get("amount", position.get("exposure", "0"))))


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled", ""}:
        return False
    return bool(value)


def _money_string(value: Any) -> str:
    return str(_decimal(value).quantize(Decimal("0.01")))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _money_string(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "CONFIRMATION_WORD",
    "LiveMicroPilotAuthorizationError",
    "LiveMicroPilotConfig",
    "LiveMicroPilotConfigurationError",
    "LiveMicroPilotDecision",
    "LiveMicroPilotGovernor",
    "live_micro_pilot_status",
]
