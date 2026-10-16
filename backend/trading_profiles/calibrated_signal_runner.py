"""Paper-only runner: authorized bars -> EngineLoop -> CssEngineSignalBridge -> TradingRouter.

Does not arm live trading. Requires an approved calibration artifact and enabled strategy.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from backend.trading_profiles.engine_bridge import CssEngineSignalBridge
from backend.trading_profiles.engine_loop_calibration import (
    CalibrationArtifact,
    build_calibration_callable,
    load_calibration,
)
from backend.trading_profiles.market_bar_source import BarRecord
from backend.trading_profiles.router import TradingRouter
from backend.trading_profiles.strategy_enablement import StrategyEnablement
from engine.engine_loop import EngineLoop

LIVE_ARM_ENVS = ("CSS_LIVE_ORDER_KILL_SWITCH", "REA_KILL_SWITCH")


class RunnerError(RuntimeError):
    pass


@dataclass
class RunnerSummary:
    bars_processed: int = 0
    signals_emitted: int = 0
    signals_refused: int = 0
    positions_opened: int = 0
    refusals: list[dict[str, Any]] = field(default_factory=list)
    paper_only: bool = True
    strategy_id: str = ""
    approved_for_routing: bool = False


def _live_armed() -> bool:
    for name in LIVE_ARM_ENVS:
        value = str(os.environ.get(name) or "").strip().upper()
        if value in {"ARMED", "1", "TRUE", "YES", "ON", "LIVE"}:
            return True
    return False


class CalibratedSignalRunner:
    """Replay bars through EngineLoop with a provenance-checked CSS signal sink (paper only)."""

    def __init__(
        self,
        *,
        router: TradingRouter,
        calibration: CalibrationArtifact,
        enablement: StrategyEnablement,
        asset_class: str = "FX",
        paper_only: bool = True,
    ) -> None:
        if not paper_only:
            raise RunnerError("live_runner_not_authorized")
        self.paper_only = True
        self.router = router
        self.calibration = calibration
        self.enablement = enablement
        self.asset_class = str(asset_class).upper()
        self.bridge = CssEngineSignalBridge(router)

    @classmethod
    def from_paths(
        cls,
        *,
        router: TradingRouter,
        calibration_path: Path | str,
        enablement_root: Path | str,
        asset_class: str = "FX",
    ) -> "CalibratedSignalRunner":
        artifact = load_calibration(calibration_path)
        return cls(
            router=router,
            calibration=artifact,
            enablement=StrategyEnablement(enablement_root),
            asset_class=asset_class,
            paper_only=True,
        )

    def run(self, bars: Sequence[BarRecord], *, starting_equity: float = 10_000.0) -> RunnerSummary:
        if _live_armed():
            raise RunnerError("live_arming_env_detected_runner_refuses")
        if not self.calibration.approved_for_routing:
            raise RunnerError("calibration_not_approved_for_routing")
        if not self.enablement.is_enabled(self.calibration.strategy_id):
            raise RunnerError("strategy_disabled")

        calibrate = build_calibration_callable(self.calibration, enablement=self.enablement)
        loop = EngineLoop(starting_equity=float(starting_equity))
        loop.asset_class_map = {b.instrument: self.asset_class for b in bars}  # type: ignore[attr-defined]
        loop.css_signal_sink = self.bridge.engine_loop_sink(calibrate, asset_class=self.asset_class)

        before_positions = len(self.router.book.positions())
        before_refusals = len(self.bridge.refusals)
        for bar in bars:
            loop.process_bar(bar.instrument, float(bar.close))
        after_refusals = len(self.bridge.refusals)
        after_positions = len(self.router.book.positions())
        # Emitted ≈ events that reached publish with approved provenance; approximate via ledger
        ledger = self.router.engine.ledger.records() if hasattr(self.router.engine, "ledger") else []
        return RunnerSummary(
            bars_processed=len(bars),
            signals_emitted=max(0, len(ledger) - 0),  # ledger grows on decisions
            signals_refused=after_refusals - before_refusals,
            positions_opened=max(0, after_positions - before_positions),
            refusals=list(self.bridge.refusals[before_refusals:]),
            paper_only=True,
            strategy_id=self.calibration.strategy_id,
            approved_for_routing=True,
        )


def refuse_if_live(fn: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if _live_armed():
            raise RunnerError("live_arming_env_detected_runner_refuses")
        return fn(*args, **kwargs)

    return wrapped
