from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping


ASSET_BUCKETS = ("CRYPTO", "FX", "OPTIONS", "FUTURES")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_asset_pnl_maps(
    symbols: list[str] | tuple[str, ...],
    fx_symbols: list[str] | tuple[str, ...],
    option_symbols: list[str] | tuple[str, ...],
    futures_symbols: list[str] | tuple[str, ...],
) -> dict[str, dict[str, float]]:
    return {
        "CRYPTO": {symbol: 0.0 for symbol in symbols},
        "FX": {symbol: 0.0 for symbol in fx_symbols},
        "OPTIONS": {symbol: 0.0 for symbol in option_symbols},
        "FUTURES": {symbol: 0.0 for symbol in futures_symbols},
    }


def realized_by_asset(asset_pnls: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    return {
        asset: sum(_safe_float(value) for value in asset_pnls.get(asset, {}).values())
        for asset in ASSET_BUCKETS
    }


def total_realized_pnl(asset_pnls: Mapping[str, Mapping[str, Any]]) -> float:
    return round(sum(realized_by_asset(asset_pnls).values()), 4)


def pnl_dict_for_asset(asset_pnls: dict[str, dict[str, float]], asset_class: str) -> dict[str, float]:
    if asset_class not in asset_pnls:
        raise ValueError(f"Unsupported asset class: {asset_class}")
    return asset_pnls[asset_class]


def build_cycle_runtime_summary(
    asset_pnls: Mapping[str, Mapping[str, Any]],
    mtm_engine: "MarkToMarketEngine",
    *,
    funded_only: bool = False,
) -> dict[str, Any]:
    display_by_asset = mtm_engine.floating_by_asset(funded_only=funded_only)
    realized = realized_by_asset(asset_pnls)

    return {
        "display_by_asset": display_by_asset,
        "broker_test_positions": mtm_engine.count_open_broker_test_positions(),
        "mtm_unrealized": round(sum(display_by_asset.values()), 4),
        "open_positions": mtm_engine.count_open_positions(),
        "mtm_realized": round(sum(realized.values()), 4),
        "realized_by_asset": realized,
        "open_counts_by_asset": mtm_engine.count_open_positions_by_asset(),
    }


class SessionRecoveryEngine:
    def __init__(
        self,
        state_file: str | Path,
        *,
        reset_on_boot: bool = False,
        context_provider: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self.state_file = Path(state_file)
        self.reset_on_boot = reset_on_boot
        self.context_provider = context_provider

    def save_state(
        self,
        *,
        cycle: int,
        crypto_pnl: dict,
        fx_pnl: dict,
        options_pnl: dict,
        futures_pnl: dict,
        last_trade: str,
        position_counter: int,
    ) -> None:
        context = dict(self.context_provider() or {}) if self.context_provider else {}
        payload = {
            "cycle": cycle,
            "crypto_pnl": crypto_pnl,
            "fx_pnl": fx_pnl,
            "options_pnl": options_pnl,
            "futures_pnl": futures_pnl,
            "last_trade": last_trade,
            "position_counter": position_counter,
            "session_user_ctx": context.get("session_user_ctx", {}),
            "selected_broker": context.get("selected_broker"),
            "selected_broker_mode": context.get("selected_broker_mode"),
            "engine_mode": context.get("engine_mode"),
            "session_lock_state": context.get("session_lock_state", {}),
        }

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def load_state(self) -> dict[str, Any] | None:
        if self.reset_on_boot:
            return None

        if not self.state_file.exists():
            return None

        try:
            with self.state_file.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return None


class LockedProfitLedger:
    def __init__(self) -> None:
        self.forced_exit_profit_banked = 0.0
        self.priority_exits = 0
        self.recycled_slots = 0
        self.trail_stops_hit = 0
        self.defensive_reduction_exits = 0
        self._booked: set[str] = set()

    def record_forced_exit(self, pid: str, amount: float) -> None:
        if pid in self._booked:
            return

        self._booked.add(pid)
        self.forced_exit_profit_banked += round(amount, 4)
        self.trail_stops_hit += 1

    def record_priority_exit(self) -> None:
        self.priority_exits += 1

    def record_recycled_slot(self) -> None:
        self.recycled_slots += 1

    def record_defensive_reduction_exit(self) -> None:
        self.defensive_reduction_exits += 1


class MomentumClusterAmplifier:
    def __init__(self) -> None:
        self.cluster_map = {
            "CRYPTO_CORE": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "CRYPTO_ALT": ["XRP-USD", "ADA-USD", "DOGE-USD"],
            "FX_MAJOR": ["EUR_USD", "GBP_USD", "EUR_GBP"],
            "FX_YEN": ["USD_JPY", "EUR_JPY", "GBP_JPY"],
            "OPTIONS_INDEX": ["SPY-C", "QQQ-C", "AAPL-C"],
            "FUTURES_INDEX": ["ES", "NQ", "CL"],
        }

        self.cluster_strength: dict[str, float] = defaultdict(float)

    def record_cluster_win(self, symbol: str, pnl: float) -> None:
        if pnl <= 0:
            return

        for cname, members in self.cluster_map.items():
            if symbol in members:
                self.cluster_strength[cname] += pnl

    def top_cluster(self) -> str | None:
        if not self.cluster_strength:
            return None

        ranked = sorted(
            self.cluster_strength.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[0][0]


class ClusterSaturationRiskGovernor:
    def __init__(self) -> None:
        self.cluster_slot_counts: dict[str, int] = defaultdict(int)
        self.total_slots_seen = 0

    def record_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name:
            self.cluster_slot_counts[cluster_name] += 1
            self.total_slots_seen += 1

    def release_cluster_slot(self, cluster_name: str | None) -> None:
        if cluster_name and self.cluster_slot_counts[cluster_name] > 0:
            self.cluster_slot_counts[cluster_name] -= 1
            self.total_slots_seen = max(0, self.total_slots_seen - 1)

    def cluster_share(self, cluster_name: str | None) -> float:
        if not cluster_name or self.total_slots_seen == 0:
            return 0.0

        return self.cluster_slot_counts[cluster_name] / self.total_slots_seen


class SmartDriftEngine:
    def __init__(
        self,
        drift_profile: Mapping[str, tuple[float, float]],
        *,
        rng: Any | None = None,
    ) -> None:
        self.drift_profile = drift_profile
        self.rng = rng or random

    def generate_drift(self, pos: dict) -> float:
        lo, hi = self.drift_profile.get(pos["asset_class"], (-0.05, 0.10))
        base = self.rng.uniform(lo, hi)

        signal_bias = ((_safe_float(pos.get("signal_score")) - 10.0) / 10.0) * 0.04
        prob_bias = (_safe_float(pos.get("prob_positive")) - 0.5) * 0.08

        return round(base + signal_bias + prob_bias, 4)


class MarkToMarketEngine:
    def __init__(
        self,
        *,
        cluster_amplifier: MomentumClusterAmplifier,
        cluster_risk_governor: ClusterSaturationRiskGovernor,
        capital_governor: Any | None = None,
        price_provider: Callable[..., float] | None = None,
        session_context_provider: Callable[[], Mapping[str, Any]] | None = None,
        asset_classes: tuple[str, ...] = ASSET_BUCKETS,
    ) -> None:
        self.positions: list[dict] = []
        self.position_counter = 0
        self.cluster_amplifier = cluster_amplifier
        self.cluster_risk_governor = cluster_risk_governor
        self.capital_governor = capital_governor
        self.price_provider = price_provider or (lambda _symbol, fallback=100.0: fallback)
        self.session_context_provider = session_context_provider or (lambda: {})
        self.asset_classes = asset_classes

    def register_position(
        self,
        asset_class: str,
        symbol: str,
        signal_score: float,
        prob_positive: float,
        allow_live_funding: bool = False,
    ) -> dict:
        self.position_counter += 1
        pid = f"POS-{self.position_counter}"

        cluster_name = self._cluster_for_symbol(symbol)
        self.cluster_risk_governor.record_cluster_slot(cluster_name)

        broker_tested = False
        if allow_live_funding and self.capital_governor is not None:
            broker_tested = bool(self.capital_governor.allocate_trade(pid))

        entry_price = self._reference_price(symbol)
        session_context = dict(self.session_context_provider() or {})

        position = {
            "position_id": pid,
            "asset_class": asset_class,
            "symbol": symbol,
            "cluster_name": cluster_name,
            "entry_price": float(entry_price),
            "current_price": float(entry_price),
            "floating": 0.0,
            "forced_exit": False,
            "exit_reason": None,
            "age_cycles": 0,
            "signal_score": signal_score,
            "prob_positive": prob_positive,
            "broker_tested": broker_tested,
            "live_funded": broker_tested,
            "broker_order_ok": False,
            "broker_note": "NO_BROKER_ORDER",
            "session_user_id": session_context.get("user_id"),
            "session_role": session_context.get("role"),
            "session_id": session_context.get("session_id"),
        }

        self.positions.append(position)
        return position

    def count_open_positions(self) -> int:
        return sum(1 for position in self.positions if not position["forced_exit"])

    def count_open_positions_by_asset(self) -> dict[str, int]:
        counts = {asset: 0 for asset in self.asset_classes}

        for pos in self.positions:
            if pos["forced_exit"]:
                continue
            counts.setdefault(pos["asset_class"], 0)
            counts[pos["asset_class"]] += 1

        return counts

    def count_open_broker_test_positions(self) -> int:
        return sum(
            1
            for position in self.positions
            if not position["forced_exit"] and position.get("broker_tested", False)
        )

    def count_open_funded_positions(self) -> int:
        return self.count_open_broker_test_positions()

    def floating_by_asset(self, funded_only: bool = False) -> dict[str, float]:
        by_asset = {asset: 0.0 for asset in self.asset_classes}

        for pos in self.positions:
            if pos["forced_exit"]:
                continue

            if funded_only and not pos.get("broker_tested", False):
                continue

            by_asset.setdefault(pos["asset_class"], 0.0)
            by_asset[pos["asset_class"]] += _safe_float(pos.get("floating"))

        return by_asset

    def _cluster_for_symbol(self, symbol: str) -> str | None:
        for cname, members in self.cluster_amplifier.cluster_map.items():
            if symbol in members:
                return cname
        return None

    def _reference_price(self, symbol: str) -> float:
        try:
            return float(self.price_provider(symbol, fallback=100.0))
        except TypeError:
            return float(self.price_provider(symbol))
