from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class TradeLogger:
    """
    CSS Trade Logger

    Backward-compatible logger for:
    - trade open events
    - trade close events
    - simple telemetry summaries

    Primary artifact:
    artifacts/css_trade_intelligence_log.jsonl
    """

    def __init__(self, log_path: Optional[str] = None) -> None:
        default_path = Path("artifacts") / "css_trade_intelligence_log.jsonl"
        self.log_path = Path(log_path) if log_path else default_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._events: List[Dict[str, Any]] = []
        self._open_events: List[Dict[str, Any]] = []
        self._close_events: List[Dict[str, Any]] = []

        self._load_existing_events()

    # -----------------------------------------------------
    # internal helpers
    # -----------------------------------------------------

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _safe_str(self, value: Any, default: str = "") -> str:
        try:
            if value is None:
                return default
            return str(value)
        except Exception:
            return default

    def _load_existing_events(self) -> None:
        if not self.log_path.exists():
            return

        try:
            with self.log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except Exception:
                        continue

                    self._events.append(event)

                    event_type = self._safe_str(event.get("event_type")).upper()
                    if event_type == "OPEN":
                        self._open_events.append(event)
                    elif event_type == "CLOSE":
                        self._close_events.append(event)
        except Exception:
            # fail quietly; logging must never break trading
            return

    def _append_event(self, event: Dict[str, Any]) -> None:
        self._events.append(event)

        event_type = self._safe_str(event.get("event_type")).upper()
        if event_type == "OPEN":
            self._open_events.append(event)
        elif event_type == "CLOSE":
            self._close_events.append(event)

        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # never break engine flow because of logging
            pass

    # -----------------------------------------------------
    # public API - backward compatible open log
    # -----------------------------------------------------

    def log_open(
        self,
        *,
        symbol: str,
        entry_price: float,
        quantity: float,
        score: float = 0.0,
        signal: str = "",
        regime: str = "",
        vwap: float = 0.0,
        spread_pct: float = 0.0,
        momentum: float = 0.0,
        velocity: float = 0.0,
        vwap_dev: float = 0.0,
        mean_reversion_score: float = 0.0,
        pressure_score: float = 0.0,
        acceleration_score: float = 0.0,
        **extra: Any,
    ) -> Dict[str, Any]:
        event = {
            "timestamp_utc": self._utc_now(),
            "event_type": "OPEN",
            "symbol": self._safe_str(symbol),
            "entry_price": self._safe_float(entry_price),
            "quantity": self._safe_float(quantity),
            "score": self._safe_float(score),
            "signal": self._safe_str(signal),
            "regime": self._safe_str(regime),
            "vwap": self._safe_float(vwap),
            "spread_pct": self._safe_float(spread_pct),
            "momentum": self._safe_float(momentum),
            "velocity": self._safe_float(velocity),
            "vwap_dev": self._safe_float(vwap_dev),
            "mean_reversion_score": self._safe_float(mean_reversion_score),
            "pressure_score": self._safe_float(pressure_score),
            "acceleration_score": self._safe_float(acceleration_score),
        }

        if extra:
            event["extra"] = extra

        self._append_event(event)
        return event

    # -----------------------------------------------------
    # new close log
    # -----------------------------------------------------

    def log_close(
        self,
        *,
        symbol: str,
        exit_price: float,
        pnl_pct: float = 0.0,
        exit_reason: str = "",
        score: float = 0.0,
        regime: str = "",
        pressure_score: float = 0.0,
        acceleration_score: float = 0.0,
        **extra: Any,
    ) -> Dict[str, Any]:
        event = {
            "timestamp_utc": self._utc_now(),
            "event_type": "CLOSE",
            "symbol": self._safe_str(symbol),
            "exit_price": self._safe_float(exit_price),
            "pnl_pct": self._safe_float(pnl_pct),
            "exit_reason": self._safe_str(exit_reason),
            "score": self._safe_float(score),
            "regime": self._safe_str(regime),
            "pressure_score": self._safe_float(pressure_score),
            "acceleration_score": self._safe_float(acceleration_score),
        }

        if extra:
            event["extra"] = extra

        self._append_event(event)
        return event

    # -----------------------------------------------------
    # telemetry helpers
    # -----------------------------------------------------

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        return self._events[-limit:]

    def get_recent_closes(self, limit: int = 50) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        return self._close_events[-limit:]

    def exit_reason_breakdown(self, limit: int = 100) -> Dict[str, int]:
        closes = self.get_recent_closes(limit)
        counter: Counter[str] = Counter()

        for event in closes:
            reason = self._safe_str(event.get("exit_reason"), "UNKNOWN").upper()
            counter[reason] += 1

        return dict(counter)

    def performance_summary(self, limit: int = 100) -> Dict[str, Any]:
        closes = self.get_recent_closes(limit)
        opens = self._open_events[-limit:] if limit > 0 else []

        total_closes = len(closes)
        total_opens = len(opens)

        wins = 0
        losses = 0
        flats = 0

        pnl_values: List[float] = []
        entry_scores: List[float] = []

        for event in opens:
            entry_scores.append(self._safe_float(event.get("score")))

        for event in closes:
            pnl = self._safe_float(event.get("pnl_pct"))
            pnl_values.append(pnl)

            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            else:
                flats += 1

        avg_entry_score = sum(entry_scores) / len(entry_scores) if entry_scores else 0.0
        avg_realized_pnl_pct = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0
        win_rate = (wins / total_closes) if total_closes else 0.0

        return {
            "total_open_events": total_opens,
            "total_close_events": total_closes,
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "win_rate": round(win_rate, 4),
            "avg_entry_score": round(avg_entry_score, 6),
            "avg_realized_pnl_pct": round(avg_realized_pnl_pct, 6),
            "exit_reasons": self.exit_reason_breakdown(limit),
        }

    def cycle_snapshot(
        self,
        *,
        cycle_no: int,
        open_positions_count: int,
        latest_opened: int = 0,
        latest_closed: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        perf = self.performance_summary(limit)

        snapshot = {
            "cycle_no": int(cycle_no),
            "open_positions_count": int(open_positions_count),
            "latest_opened": int(latest_opened),
            "latest_closed": int(latest_closed),
            "win_rate": perf["win_rate"],
            "avg_entry_score": perf["avg_entry_score"],
            "avg_realized_pnl_pct": perf["avg_realized_pnl_pct"],
            "exit_reasons": perf["exit_reasons"],
        }
        return snapshot