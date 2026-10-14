"""Live-data shadow paper runner (observation only, simulated fills).

Pipeline per instrument per bar, mirroring engine.engine_loop.EngineLoop.process_bar
but journaling every stage:

    real quote -> validation (stale/invalid rejected) -> SignalEngine
    -> exits (PositionBook rules, filled at the real quote side)
    -> entry gates, all must pass (gates only ever tighten):
         FLAT, min signal strength, no pyramiding, RegimeGate,
         R7 CSSUnifiedTradeGate, R14F profitability gate,
         ExecutionGate (AntiBleedGuard -> MarginTradeGate -> sizing -> RiskGovernor),
         PortfolioCapitalController
    -> paper order intent -> explicitly SIMULATED fill -> paper position

Real market prices, simulated fills and estimated costs are labelled separately in
the journal. There is no broker connection and no order-submission code path.
"""

from __future__ import annotations

import logging
import math
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from backend.shadow_paper import SCHEMA_VERSION
from backend.shadow_paper.controls import (
    EXPECTED_MIN_SIGNAL_STRENGTH,
    SafetyPreflightError,
    load_r14f,
    run_preflight,
)
from backend.shadow_paper.journal import EventJournal
from backend.shadow_paper.market_data import (
    SUPPORTED_INSTRUMENTS,
    CoinbasePublicTicker,
    MarketQuote,
)

LOGGER = logging.getLogger(__name__)

JOURNAL_FILENAME = "shadow_journal.jsonl"
ANTI_BLEED_STATE_FILENAME = "anti_bleed_state.json"
BAR_INTERVAL_SECONDS = 300  # 5-minute bars: RegimeGate counts 5m bars (MIN_BARS_5M=40)
ENGINE_BEHAVIOUR = "D"      # EngineLoop default profile
ENGINE_MODE = "SAFE"        # most restrictive R7/R14F mode
ASSET_CLASS = "CRYPTO"
# R7/R14F take dashboard-scale inputs that the price-driven SignalEngine does not
# produce. Explicit, uncalibrated proxy (reviewed item): probability := strength,
# R14F signal score := strength * 20. Both gates are ENFORCED, so the proxy can
# only block entries, never admit one that other gates rejected.
R14F_SIG_SCALE = 20.0
PRICE_BASIS = "REAL_MARKET"
FILL_BASIS = "SIMULATED"
COST_BASIS = "ESTIMATED"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def detect_commit_sha(repo_root: Path) -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root, capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:
        return "UNKNOWN"


@dataclass
class PaperPosition:
    position_id: str
    instrument: str
    side: str
    quantity: float
    entry_fill_price: float
    notional: float
    entry_fee: float
    opened_at_utc: str


class ShadowPaperRunner:
    def __init__(
        self,
        evidence_dir: Path,
        *,
        operator_id: str,
        starting_equity: float = 1000.0,
        instruments: tuple[str, ...] = SUPPORTED_INSTRUMENTS,
        ticker: Optional[CoinbasePublicTicker] = None,
        clock: Optional[Callable[[], datetime]] = None,
        commit_sha: Optional[str] = None,
        environ: Optional[Mapping[str, str]] = None,
        live_network: bool = True,
        repo_root: Optional[Path] = None,
    ) -> None:
        if not str(operator_id or "").strip():
            raise ValueError("operator_id is required")
        unsupported = [i for i in instruments if i not in SUPPORTED_INSTRUMENTS]
        if unsupported or not instruments:
            raise ValueError(f"unsupported instruments: {unsupported}")
        if not (math.isfinite(float(starting_equity)) and float(starting_equity) > 0):
            raise ValueError("starting_equity must be positive")

        from backend.shadow_paper.controls import REPO_ROOT

        self.evidence_dir = Path(evidence_dir)
        self.operator_id = str(operator_id).strip()
        self.starting_equity = float(starting_equity)
        self.instruments = tuple(instruments)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.ticker = ticker or CoinbasePublicTicker(clock=self.clock)
        self.environ = environ
        self.live_network = bool(live_network)
        self.repo_root = Path(repo_root or REPO_ROOT)
        self.commit_sha = commit_sha or detect_commit_sha(self.repo_root)
        self.run_id = f"{self.clock().strftime('%Y%m%dT%H%M%SZ')}-{id(self) & 0xFFFF:04x}"

        self.journal: Optional[EventJournal] = None
        self.engine: Any = None
        self.r7: Any = None
        self.r14f: Any = None
        self.positions: dict[str, PaperPosition] = {}
        self.realized_net = 0.0
        self.fees_total = 0.0
        self.last_trade_id: dict[str, int] = {}
        self.last_quote: dict[str, MarketQuote] = {}
        self.pending_marks: set[str] = set()
        self.reconciled = False
        self.entries_halted = False
        self.halt_reason = ""
        self.session_created_epoch: Optional[float] = None
        self.cycles = 0
        self.started = False

    # ------------------------------------------------------------------
    # startup
    # ------------------------------------------------------------------

    def _build_engine(self) -> None:
        from backend.app.risk.anti_bleed_guard import AntiBleedGuard
        from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
        from engine.engine_loop import EngineLoop
        from engine.execution.execution_gate import ExecutionGate

        engine = EngineLoop(behaviour=ENGINE_BEHAVIOUR, starting_equity=self.starting_equity)
        engine.audit_logger = None  # evidence goes to the shadow journal, not the repo tree
        engine.execution_gate = ExecutionGate(
            anti_bleed_guard=AntiBleedGuard(
                state_file=str(self.evidence_dir / ANTI_BLEED_STATE_FILENAME),
            )
        )
        for instrument in self.instruments:
            engine.asset_class_map[instrument] = ASSET_CLASS
        self.engine = engine
        self.r7 = CSSUnifiedTradeGate()
        self.r14f = load_r14f(ENGINE_MODE)

    def _preflight(self) -> dict[str, Any]:
        report = run_preflight(
            environ=self.environ,
            repo_root=self.repo_root,
            live_network=self.live_network,
            execution_gate=self.engine.execution_gate,
            r14f=self.r14f,
        )
        if float(self.engine.min_signal_strength) != EXPECTED_MIN_SIGNAL_STRENGTH:
            report.passed = False
            report.failures.append(f"min_signal_strength={self.engine.min_signal_strength}")
            report.checks["min_signal_strength"] = "FAIL"
        else:
            report.checks["min_signal_strength"] = "PASS"
        return report.to_dict()

    def start(self) -> dict[str, Any]:
        """Open the journal, run the safety preflight, then reconcile prior positions."""
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.journal = EventJournal(
            self.evidence_dir / JOURNAL_FILENAME,
            run_id=self.run_id,
            commit_sha=self.commit_sha,
            clock=self.clock,
        )  # raises JournalIntegrityError -> refuse to start

        self._build_engine()
        preflight = self._preflight()
        config = {
            "schema": SCHEMA_VERSION,
            "operator_id": self.operator_id,
            "instruments": list(self.instruments),
            "asset_class": ASSET_CLASS,
            "starting_equity": self.starting_equity,
            "bar_interval_seconds": BAR_INTERVAL_SECONDS,
            "engine_behaviour": ENGINE_BEHAVIOUR,
            "engine_mode": ENGINE_MODE,
            "r14f_source_sha256": self.r14f.source_sha256,
            "proxy_inputs": {
                "probability": "signal.strength",
                "r14f_sig": f"signal.strength * {R14F_SIG_SCALE}",
                "expected_move_bps": "signal.strength * 100 (EngineLoop convention)",
            },
            "order_route": "NONE - simulated fills only; no broker module loaded",
            "live_trading_allowed": False,
        }

        prior_starts = list(self.journal.iter_type("RUN_STARTED"))
        if prior_starts:
            prior = prior_starts[0]["payload"]["config"]
            for key in ("starting_equity", "instruments", "engine_behaviour", "engine_mode", "bar_interval_seconds"):
                if prior.get(key) != config[key]:
                    preflight["passed"] = False
                    preflight["failures"].append(f"config {key} differs from journal ({prior.get(key)!r})")

        self.journal.append("RUN_STARTED", {"config": config, "preflight": preflight})
        if not preflight["passed"]:
            self.journal.append("SAFETY_PREFLIGHT_FAILED", {"failures": preflight["failures"]})
            raise SafetyPreflightError(preflight["failures"])

        self.session_created_epoch = time.time()
        self._reconcile()
        self.started = True
        return preflight

    def _reconcile(self) -> None:
        """Rebuild paper state from the journal before any new simulated entry."""
        assert self.journal is not None
        opened: dict[str, dict[str, Any]] = {}
        closed_ids: set[str] = set()
        realized = 0.0
        fees = 0.0
        for record in self.journal.records:
            kind, payload = record["type"], record["payload"]
            if kind == "PAPER_POSITION_OPENED":
                opened[payload["position_id"]] = payload
            elif kind == "PAPER_POSITION_CLOSED":
                closed_ids.add(payload["position_id"])
                realized += float(payload["realized_pnl_net"])
                fees += float(payload["exit_fee"]) + float(payload["entry_fee"])
                self.engine.pnl_tracker.record_trade(
                    instrument=payload["instrument"],
                    realized_pnl=float(payload["realized_pnl_net"]),
                    unrealized_pnl=0.0,
                    timestamp=_parse_iso(record["ts_utc"]).replace(tzinfo=None),
                )
            elif kind == "MARKET_TICK":
                self.last_trade_id[payload["instrument"]] = int(payload["trade_id"])

        orphans = [pid for pid in closed_ids if pid not in opened]
        open_payloads = [p for pid, p in opened.items() if pid not in closed_ids]
        self.realized_net = realized
        self.fees_total = fees
        self.engine.equity_peak = max(float(self.engine.equity_peak), float(self.engine.pnl_tracker.current_equity))

        self.journal.append("RECONCILIATION_STARTED", {
            "open_positions": len(open_payloads),
            "closed_positions": len(closed_ids),
            "realized_pnl_net": round(realized, 8),
            "orphan_closes": orphans,
        })
        if orphans:
            self._halt_entries(f"orphan close events without open: {orphans}")

        now = self.clock()
        for payload in open_payloads:
            instrument = payload["instrument"]
            if instrument not in self.instruments:
                self._halt_entries(f"restored position {payload['position_id']} not in configured instruments")
                continue
            position = PaperPosition(
                position_id=payload["position_id"],
                instrument=instrument,
                side=payload["side"],
                quantity=float(payload["quantity"]),
                entry_fill_price=float(payload["entry_fill_price"]),
                notional=float(payload["notional"]),
                entry_fee=float(payload["entry_fee"]),
                opened_at_utc=payload["opened_at_utc"],
            )
            elapsed = max(0.0, (now - _parse_iso(position.opened_at_utc)).total_seconds())
            elapsed_steps = int(elapsed // BAR_INTERVAL_SECONDS) * len(self.instruments)
            self.engine.position_book.open_position(
                instrument=instrument,
                side=position.side,
                size=position.quantity,
                price=position.entry_fill_price,
                step=self.engine.current_step - elapsed_steps,
                stop_distance_pct=float(self._engine_const("DEFAULT_STOP_DISTANCE_PCT")),
            )
            self.positions[instrument] = position
            self.pending_marks.add(instrument)
            self.journal.append("POSITION_RESTORED", {
                **payload,
                "restored_hold_steps": elapsed_steps,
                "status": "OPEN_AWAITING_FRESH_MARK",
            }, dedupe_key=f"restore:{self.run_id}:{position.position_id}")

        self.reconciled = True
        self.journal.append("RECONCILIATION_COMPLETED", {
            "restored_positions": sorted(self.pending_marks),
            "entries_blocked_until_marked": sorted(self.pending_marks),
            "equity": round(float(self.engine.pnl_tracker.current_equity), 8),
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _engine_const(name: str) -> Any:
        import engine.engine_loop as engine_loop

        return getattr(engine_loop, name)

    def _halt_entries(self, reason: str) -> None:
        if not self.entries_halted:
            self.entries_halted = True
            self.halt_reason = reason
            LOGGER.error("shadow runner: new entries halted: %s", reason)
            if self.journal is not None:
                self.journal.append("ENTRIES_HALTED", {"reason": reason})

    def _costs_bps(self) -> tuple[float, float, float]:
        return (
            float(self._engine_const("ANTI_BLEED_FEE_BPS")),
            float(self._engine_const("ANTI_BLEED_SPREAD_BPS")),
            float(self._engine_const("ANTI_BLEED_SLIPPAGE_BPS")),
        )

    def _simulated_fill(self, quote: MarketQuote, side: str, notional_hint: float | None, quantity: float | None) -> dict[str, Any]:
        """Fill at the REAL quote side, plus ESTIMATED slippage; fee ESTIMATED from engine bps."""
        fee_bps, _spread_bps, slip_bps = self._costs_bps()
        if side == "BUY":
            reference = quote.ask
            fill_price = reference * (1.0 + slip_bps / 10_000.0)
            reference_side = "ask"
        else:
            reference = quote.bid
            fill_price = reference * (1.0 - slip_bps / 10_000.0)
            reference_side = "bid"
        qty = float(quantity) if quantity is not None else float(notional_hint) / fill_price
        notional = qty * fill_price
        fee = notional * fee_bps / 10_000.0
        return {
            "side": side,
            "quantity": qty,
            "fill_price": fill_price,
            "notional": notional,
            "fee": fee,
            "fill_basis": FILL_BASIS,
            "reference_price": reference,
            "reference_side": reference_side,
            "reference_basis": PRICE_BASIS,
            "reference_trade_id": quote.trade_id,
            "reference_exchange_time_utc": quote.exchange_time_utc,
            "slippage_bps": slip_bps,
            "fee_bps": fee_bps,
            "cost_basis": COST_BASIS,
        }

    def _unrealized(self, position: PaperPosition, quote: MarketQuote) -> float:
        if position.side == "BUY":
            return (quote.bid - position.entry_fill_price) * position.quantity
        return (position.entry_fill_price - quote.ask) * position.quantity

    @staticmethod
    def _exit_reason(pos: Any, price: float, step: int, incoming: str) -> Optional[str]:
        """Classify an exit using PositionBook.evaluate_exit's rule order (for the journal)."""
        if pos.side == "BUY":
            stop = pos.entry_price * (1 - pos.stop_distance_pct)
            if price <= stop:
                return "STOP_LOSS"
        else:
            stop = pos.entry_price * (1 + pos.stop_distance_pct)
            if price >= stop:
                return "STOP_LOSS"
        if pos.take_profit_pct is not None:
            if pos.side == "BUY" and price >= pos.entry_price * (1 + pos.take_profit_pct):
                return "TAKE_PROFIT"
            if pos.side == "SELL" and price <= pos.entry_price * (1 - pos.take_profit_pct):
                return "TAKE_PROFIT"
        if incoming and incoming != pos.side:
            return "OPPOSITE_SIGNAL"
        if step - pos.opened_step >= pos.max_hold_steps:
            return "MAX_HOLD"
        return None

    # ------------------------------------------------------------------
    # cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> None:
        if not self.started or self.journal is None:
            raise RuntimeError("runner not started")
        self.cycles += 1

        recheck = self._preflight()
        if not recheck["passed"]:
            self.journal.append("SAFETY_HALT", {"failures": recheck["failures"]})
            raise SafetyPreflightError(recheck["failures"])
        self.session_created_epoch = time.time()

        fresh: dict[str, MarketQuote] = {}
        for instrument in self.instruments:
            try:
                quote = self._process_instrument(instrument)
                if quote is not None:
                    fresh[instrument] = quote
            except Exception as exc:  # fail closed: record, halt entries, keep observing
                LOGGER.exception("shadow runner error on %s", instrument)
                self.journal.append("ERROR", {
                    "instrument": instrument,
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                })
                self._halt_entries(f"unhandled error while processing {instrument}")
        self._snapshot(fresh)

    def _process_instrument(self, instrument: str) -> Optional[MarketQuote]:
        assert self.journal is not None
        result = self.ticker.fetch(instrument)
        if not isinstance(result, MarketQuote):
            self.journal.append("MARKET_DATA_REJECTED", result.to_dict())
            return None

        quote = result
        if self.last_trade_id.get(instrument) == quote.trade_id or self.journal.has_key(f"tick:{instrument}:{quote.trade_id}"):
            self.journal.append("MARKET_DATA_DUPLICATE", {
                "instrument": instrument,
                "trade_id": quote.trade_id,
                "reason": "NO_NEW_TRADE_SINCE_LAST_BAR",
            })
            return None

        tick = self.journal.append(
            "MARKET_TICK",
            {**quote.to_dict(), "price_basis": PRICE_BASIS},
            dedupe_key=f"tick:{instrument}:{quote.trade_id}",
        )
        if tick is None:
            return None
        self.last_trade_id[instrument] = quote.trade_id
        self.last_quote[instrument] = quote
        tick_ref = {"tick_seq": tick["seq"], "trade_id": quote.trade_id}

        if instrument in self.pending_marks:
            position = self.positions[instrument]
            self.journal.append("POSITION_MARKED", {
                "position_id": position.position_id,
                "instrument": instrument,
                "mark_price": quote.bid if position.side == "BUY" else quote.ask,
                "unrealized_pnl": self._unrealized(position, quote),
                **tick_ref,
            })
            self.pending_marks.discard(instrument)

        engine = self.engine
        price = float(quote.price)
        engine.current_step += 1
        engine.last_price_by_instrument[instrument] = price
        engine.bars_seen_by_instrument[instrument] = int(engine.bars_seen_by_instrument.get(instrument, 0)) + 1
        if instrument not in engine.price_windows:
            from collections import deque

            engine.price_windows[instrument] = deque(maxlen=int(self._engine_const("MA_WINDOW")))
        engine.price_windows[instrument].append(price)

        if instrument not in engine.prev_price_by_instrument:
            engine.prev_price_by_instrument[instrument] = price
            if instrument not in engine.return_history:
                from collections import deque

                engine.return_history[instrument] = deque(maxlen=engine.correlation_window)
            self.journal.append("SIGNAL", {"instrument": instrument, "status": "WARMUP_SEED", **tick_ref})
            # A restored position still gets stop/take-profit/max-hold checks on the seed bar.
            self._evaluate_exit(instrument, quote, "", tick_ref)
            return quote

        engine._update_returns(instrument, price)
        prev_price = float(engine.prev_price_by_instrument[instrument])
        window = engine.price_windows[instrument]
        moving_avg = sum(window) / len(window)
        signal = engine.signal_engine.generate(
            instrument=instrument, price_now=price, price_prev=prev_price, moving_avg=moving_avg,
        )
        strength = float(getattr(signal, "strength", 0.0))
        self.journal.append("SIGNAL", {
            "instrument": instrument,
            "status": "GENERATED",
            "direction": signal.direction,
            "strength": strength,
            "style": signal.style,
            "price": price,
            "prev_price": prev_price,
            "moving_avg": moving_avg,
            "bars_seen": engine.bars_seen_by_instrument[instrument],
            **tick_ref,
        })

        self._evaluate_exit(instrument, quote, signal.direction, tick_ref)
        equity = float(engine.pnl_tracker.current_equity)
        engine.equity_peak = max(float(engine.equity_peak), equity)
        self._evaluate_entry(instrument, quote, signal, strength, equity, tick_ref)
        engine.prev_price_by_instrument[instrument] = price
        return quote

    def _evaluate_exit(self, instrument: str, quote: MarketQuote, direction: str, tick_ref: dict[str, Any]) -> None:
        assert self.journal is not None
        book = self.engine.position_book
        pos = book.positions.get(instrument)
        if pos is None:
            return
        reason = self._exit_reason(pos, float(quote.price), self.engine.current_step, direction)
        book.evaluate_exit(
            instrument=instrument,
            current_price=float(quote.price),
            current_step=self.engine.current_step,
            incoming_signal=direction,
        )
        closed = not book.has_position(instrument)
        if closed != (reason is not None):
            self._halt_entries(f"exit classification mismatch on {instrument} (reason={reason}, closed={closed})")
            if not closed:
                return
            reason = reason or "UNCLASSIFIED"
        if not closed:
            return

        position = self.positions.pop(instrument, None)
        if position is None:
            self._halt_entries(f"position book closed {instrument} with no journaled paper position")
            return
        exit_side = "SELL" if position.side == "BUY" else "BUY"
        fill = self._simulated_fill(quote, exit_side, None, position.quantity)
        if position.side == "BUY":
            gross = (fill["fill_price"] - position.entry_fill_price) * position.quantity
        else:
            gross = (position.entry_fill_price - fill["fill_price"]) * position.quantity
        net = gross - position.entry_fee - fill["fee"]

        self.journal.append("SIMULATED_FILL", {
            "position_id": position.position_id, "instrument": instrument, "purpose": "EXIT", **fill, **tick_ref,
        })
        self.engine.pnl_tracker.record_trade(instrument=instrument, realized_pnl=net, unrealized_pnl=0.0)
        self.realized_net += net
        self.fees_total += position.entry_fee + fill["fee"]
        self.journal.append("PAPER_POSITION_CLOSED", {
            "position_id": position.position_id,
            "instrument": instrument,
            "side": position.side,
            "quantity": position.quantity,
            "entry_fill_price": position.entry_fill_price,
            "exit_fill_price": fill["fill_price"],
            "exit_reason": reason,
            "realized_pnl_gross": gross,
            "entry_fee": position.entry_fee,
            "exit_fee": fill["fee"],
            "realized_pnl_net": net,
            "opened_at_utc": position.opened_at_utc,
            "fill_basis": FILL_BASIS,
            "cost_basis": COST_BASIS,
            **tick_ref,
        }, dedupe_key=f"close:{position.position_id}")

    def _evaluate_entry(
        self,
        instrument: str,
        quote: MarketQuote,
        signal: Any,
        strength: float,
        equity: float,
        tick_ref: dict[str, Any],
    ) -> None:
        assert self.journal is not None
        engine = self.engine
        fee_bps, spread_bps, slip_bps = self._costs_bps()
        expected_move_bps = strength * 100.0
        stages: list[dict[str, Any]] = []

        def stage(name: str, passed: bool, detail: Any) -> bool:
            stages.append({"stage": name, "passed": bool(passed), "detail": detail})
            return bool(passed)

        def finish(final: str, extra: Optional[dict[str, Any]] = None) -> None:
            blocked_by = next((s["stage"] for s in stages if not s["passed"]), None)
            self.journal.append("GATE_DECISION", {
                "instrument": instrument,
                "direction": signal.direction,
                "strength": strength,
                "final": final,
                "blocked_by": blocked_by,
                "stages": stages,
                **(extra or {}),
                **tick_ref,
            })

        if not stage("runner_entry_permission", self.reconciled and not self.pending_marks and not self.entries_halted, {
            "reconciled": self.reconciled,
            "awaiting_fresh_mark": sorted(self.pending_marks),
            "entries_halted": self.entries_halted,
            "halt_reason": self.halt_reason,
        }):
            return finish("ENTRY_BLOCKED")
        if not stage("signal_direction", signal.direction in {"BUY", "SELL"}, signal.direction):
            return finish("ENTRY_BLOCKED")
        if not stage("min_signal_strength", strength >= float(engine.min_signal_strength), {
            "strength": strength, "minimum": float(engine.min_signal_strength),
        }):
            return finish("ENTRY_BLOCKED")
        if not stage("no_pyramiding", not engine.position_book.has_position(instrument), {}):
            return finish("ENTRY_BLOCKED")

        regime = engine._evaluate_regime_gate(instrument=instrument, price=float(quote.price))
        engine.regime_gate_records.clear()
        if not stage("regime_gate", str(regime.get("decision", "")).upper() == "ALLOW", regime):
            return finish("ENTRY_BLOCKED")

        open_crypto = sum(1 for p in self.positions.values() if p.instrument in self.instruments)
        r7_decision = self.r7.approve_trade(
            candidate={
                "asset_class": ASSET_CLASS.lower(),
                "symbol": instrument,
                "expected_value": expected_move_bps,
                "cost": fee_bps + spread_bps + slip_bps,
                "probability": strength,
            },
            session={"created": self.session_created_epoch, "role": "TRADER", "operator_id": self.operator_id},
            portfolio_state={ASSET_CLASS.lower(): open_crypto},
            engine_mode=ENGINE_MODE,
        )
        if not stage("r7_unified_trade_gate", r7_decision.approved is True, {
            "approved": r7_decision.approved,
            "reason": r7_decision.reason,
            "engine_mode": r7_decision.engine_mode,
            "input_basis": "PROXY_UNCALIBRATED",
        }):
            return finish("ENTRY_BLOCKED")

        r14f = self.r14f.evaluate(
            symbol=instrument, asset_class=ASSET_CLASS, sig=strength * R14F_SIG_SCALE, prob=strength,
        )
        if not stage("r14f_profitability_gate", r14f["passed"] is True, {**r14f, "input_basis": "PROXY_UNCALIBRATED"}):
            return finish("ENTRY_BLOCKED")

        # Canonical paper margin snapshot (Phase 96C adapter, SIMULATED mode, no broker
        # access): spot, unlevered, derived from paper equity and open paper notional.
        # EngineLoop's legacy MarginEngine snapshot is rejected by the canonical
        # MarginTradeGate (MARGIN_SNAPSHOT_UNAVAILABLE), so it cannot be used here.
        from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter

        open_notional = sum(p.notional for p in self.positions.values())
        margin_snapshot = CoinbaseMarginAdapter(
            account_id="SHADOW-PAPER",
            available_margin=equity,
            required_margin=open_notional,
            mode="SIMULATED",
        ).get_margin_snapshot()
        requested_notional = equity * float(self._engine_const("BASELINE_NOTIONAL_PCT"))
        gate = engine.execution_gate.evaluate_trade(
            instrument=instrument,
            side=signal.direction,
            notional=requested_notional,
            stop_distance_pct=float(self._engine_const("DEFAULT_STOP_DISTANCE_PCT")),
            equity=equity,
            equity_peak=float(engine.equity_peak),
            regime_persistence=float(self._engine_const("DEFAULT_REGIME_PERSISTENCE")),
            expected_move_bps=expected_move_bps,
            fee_bps=fee_bps,
            spread_bps=spread_bps,
            slippage_bps=slip_bps,
            margin_snapshot=margin_snapshot,
            broker_mode="PAPER",
        )
        debug = gate.get("debug", {}) if isinstance(gate, dict) else {}
        anti_bleed = debug.get("anti_bleed_guard", {}) if isinstance(debug, dict) else {}
        stage("anti_bleed_guard", anti_bleed.get("approved") is True, anti_bleed)
        allowed = str(gate.get("decision", {}).get("final", "")).upper() == "ALLOW" if isinstance(gate, dict) else False
        scaled_notional = float(debug.get("scaled_notional", 0.0) or 0.0)
        if not stage("execution_gate", allowed and scaled_notional > 0.0, {
            "final": gate.get("decision", {}).get("final") if isinstance(gate, dict) else None,
            "reason": gate.get("reason") if isinstance(gate, dict) else "invalid_response",
            "requested_notional": requested_notional,
            "scaled_notional": scaled_notional,
            "margin_trade_gate": debug.get("margin_trade_gate"),
        }):
            return finish("ENTRY_BLOCKED")

        from engine.portfolio.portfolio_capital_controller import TradeProposal

        avg_corr = engine._avg_abs_corr_vs_open(instrument=instrument, asset_class=ASSET_CLASS)
        proposal = TradeProposal(
            instrument=instrument,
            asset_class=ASSET_CLASS,
            requested_notional=scaled_notional,
            equity=equity,
            current_total_exposure=engine._total_exposure_notional(),
            current_instrument_exposure=engine._instrument_exposure_notional(instrument),
            current_asset_class_exposure=engine._asset_class_exposure_notional(ASSET_CLASS),
            portfolio_dd_pct=float(engine.pnl_tracker.current_drawdown() * 100.0),
            open_positions_in_asset_class=engine._open_positions_in_asset_class(ASSET_CLASS),
            avg_correlation=float(avg_corr),
        )
        pcc = engine.pcc.evaluate(proposal)
        final_notional = scaled_notional * float(pcc.sizing_multiplier)
        if not stage("portfolio_capital_controller", pcc.final == "ALLOW" and final_notional > 0.0, {
            "final": pcc.final, "reason": pcc.reason, "sizing_multiplier": float(pcc.sizing_multiplier),
        }):
            return finish("ENTRY_BLOCKED")
        if not stage("anti_bleed_minimum_size", final_notional >= float(engine.execution_gate.anti_bleed_guard.minimum_profitable_trade_size), {
            "final_notional": final_notional,
            "minimum": float(engine.execution_gate.anti_bleed_guard.minimum_profitable_trade_size),
        }):
            return finish("ENTRY_BLOCKED")

        finish("ENTRY_ALLOWED", {"final_notional": final_notional})
        position_id = f"{instrument}:{quote.trade_id}"
        self.journal.append("PAPER_ORDER_INTENT", {
            "position_id": position_id,
            "instrument": instrument,
            "side": signal.direction,
            "notional": final_notional,
            "order_route": "NONE_SIMULATED_ONLY",
            **tick_ref,
        }, dedupe_key=f"intent:{position_id}")
        fill = self._simulated_fill(quote, signal.direction, final_notional, None)
        self.journal.append("SIMULATED_FILL", {
            "position_id": position_id, "instrument": instrument, "purpose": "ENTRY", **fill, **tick_ref,
        })
        engine.position_book.open_position(
            instrument=instrument,
            side=signal.direction,
            size=fill["quantity"],
            price=fill["fill_price"],
            step=engine.current_step,
            stop_distance_pct=float(self._engine_const("DEFAULT_STOP_DISTANCE_PCT")),
        )
        engine.trade_count += 1
        position = PaperPosition(
            position_id=position_id,
            instrument=instrument,
            side=signal.direction,
            quantity=fill["quantity"],
            entry_fill_price=fill["fill_price"],
            notional=fill["notional"],
            entry_fee=fill["fee"],
            opened_at_utc=_iso(self.clock()),
        )
        self.positions[instrument] = position
        self.journal.append("PAPER_POSITION_OPENED", {
            "position_id": position_id,
            "instrument": instrument,
            "side": position.side,
            "quantity": position.quantity,
            "entry_fill_price": position.entry_fill_price,
            "notional": position.notional,
            "entry_fee": position.entry_fee,
            "opened_at_utc": position.opened_at_utc,
            "fill_basis": FILL_BASIS,
            "cost_basis": COST_BASIS,
            **tick_ref,
        }, dedupe_key=f"open:{position_id}")

    def _snapshot(self, fresh: dict[str, MarketQuote]) -> None:
        assert self.journal is not None
        open_positions = []
        unrealized = 0.0
        for instrument, position in sorted(self.positions.items()):
            quote = fresh.get(instrument)
            if quote is not None:
                value = self._unrealized(position, quote)
                unrealized += value
                mark = {"mark_status": "FRESH", "unrealized_pnl": value, "mark_trade_id": quote.trade_id}
            else:
                mark = {"mark_status": "NO_FRESH_PRICE_THIS_CYCLE", "unrealized_pnl": None}
            open_positions.append({
                "position_id": position.position_id, "instrument": instrument, "side": position.side,
                "quantity": position.quantity, "entry_fill_price": position.entry_fill_price, **mark,
            })
        self.journal.append("PNL_SNAPSHOT", {
            "cycle": self.cycles,
            "starting_equity": self.starting_equity,
            "realized_pnl_net": self.realized_net,
            "fees_total": self.fees_total,
            "unrealized_pnl_fresh_marks": unrealized,
            "equity_realized": float(self.engine.pnl_tracker.current_equity),
            "drawdown_pct": float(self.engine.pnl_tracker.current_drawdown() * 100.0),
            "open_positions": open_positions,
            "entries_halted": self.entries_halted,
            "basis": {"prices": PRICE_BASIS, "fills": FILL_BASIS, "costs": COST_BASIS},
        })

    def probe_feed(self) -> dict[str, Any]:
        """Read-only connectivity check: fetch one quote per instrument, journal it, feed nothing."""
        if not self.started or self.journal is None:
            raise RuntimeError("runner not started")
        results: dict[str, Any] = {}
        for instrument in self.instruments:
            result = self.ticker.fetch(instrument)
            accepted = isinstance(result, MarketQuote)
            payload = {"accepted": accepted, **result.to_dict()}
            self.journal.append("FEED_PROBE", payload)
            results[instrument] = payload
        return results

    def stop(self, reason: str) -> None:
        if self.journal is None or not self.started:
            return
        self.journal.append("RUN_STOPPED", {
            "reason": str(reason)[:200],
            "cycles": self.cycles,
            "open_positions_left_open": sorted(p.position_id for p in self.positions.values()),
            "note": "open paper positions are not closed on stop; they are reconciled on the next start",
        })
        self.started = False
