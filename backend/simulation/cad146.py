"""CAD 146 two-track simulation of the canonical CSS autonomous trader on live market data.

PAPER / RESEARCH ONLY. No broker is imported or contacted; there is no order path out of this
module. Each track is an isolated TradingRouter + PaperBook in its own directory.

Designated trader: the CSS autonomous engine (AUTONOMOUS_SOURCE_ID = "CSS_AUTONOMOUS_ENGINE"),
whose signals come only from backend.signals.producer.SignalProducer. Mode "Simulated Trading"
with the code's canonical default personality for that mode (SIMULATED_DEFAULT_PERSONALITY).

Track A — strict governed CSS: the operational dual-control approvals ledger (read-only),
          CssEngineSignalBridge.publish_real_data, every router gate. With no approved
          calibration, Track A makes zero trades and records why.
Track B — research shadow: identical, except calibration approval (dual control + passed gates)
          is not required. Every Track B decision is labelled RESEARCH_COUNTERFACTUAL. R14F, R7,
          ExecutionGate/AntiBleed, personality, capital and position limits all still apply.
          Track B refuses to run against the operational paper book.

Both tracks consume the SAME observation each cycle (same bars, same digest, same quote), which
is journalled before either track acts. A bar is processed at most once per track (persisted),
so restarts and replays cannot duplicate fills. A data failure is journalled as an OUTAGE and
produces no entries; open positions are held (no mark, no exit) until data returns.

Known limitation: positions are booked in CAD notional and P&L is the instrument's price return
in its quote currency; USD/CAD moves during a holding period are not applied (no authorized
real-time USD/CAD source is connected). It is reported, not hidden.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from backend.signals.candles import CandleError, CandleSeries
from backend.signals.producer import CalibrationApprovals, ProducedSignal, SignalProducer
from backend.signals.research import CostModel
from backend.trading_profiles.copy_engine import (
    AUTONOMOUS_SOURCE_ID,
    SIMULATED_DEFAULT_PERSONALITY,
    CopyTradeEngine,
    SystemContext,
)
from backend.trading_profiles.engine_bridge import CssEngineSignalBridge
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256
from backend.trading_profiles.operating_modes import OperatingMode
from backend.trading_profiles.router import PaperBook, TradingRouter

STARTING_EQUITY_CAD = 146.00
SIM_USER = "sim-cad146"
SIM_SESSION = "sim-cad146-session"
TRACK_A, TRACK_B = "A_STRICT_GOVERNED", "B_RESEARCH_SHADOW"
LIVE_ARM_ENVS = ("REA_LIVE_ARM", "REA_CONFIRM_LIVE", "CSS_ENABLE_LIVE_TRADING", "ENABLE_LIVE_TRADING",
                 "ALLOW_LIVE_TRADING")
_REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_ENTRY_HALT_ENV = "CSS_SIM_ENTRY_HALT"
LIVE_KILL_SWITCH_ENV = "CSS_LIVE_ORDER_KILL_SWITCH"
_TRUTHY = {"1", "true", "yes", "y", "on"}


def sim_entry_halted(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(SIM_ENTRY_HALT_ENV, "")).strip().lower() in _TRUTHY


def live_kill_switch_engaged(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(LIVE_KILL_SWITCH_ENV, "")).strip().lower() in _TRUTHY


SAFE_FLAGS = {"verdict": "SAFE", "fail_closed": False, "execution_allowed": False, "live_trading_blocked": True,
              "advisory_only": True}


class SimulationError(RuntimeError):
    pass


def _utc(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def refuse_if_live_armed(env: Mapping[str, str] | None = None) -> None:
    env = os.environ if env is None else env
    for name in LIVE_ARM_ENVS:
        if str(env.get(name, "")).strip().lower() in {"1", "true", "yes", "on", "armed", "live"}:
            raise SimulationError(f"live_arming_detected:{name}")


def _is_operational(root: Path) -> bool:
    try:
        r = Path(root).resolve()
    except OSError:
        return True
    ops = {(_REPO_ROOT / "artifacts" / "trading_profiles").resolve(),
           (Path.cwd() / "artifacts" / "trading_profiles").resolve()}
    return r in ops or any(o in r.parents for o in ops)


class _ResearchApprovals:
    """Track B only: treats any unaltered artifact as routable, and says so in every reason."""

    def status(self, artifact: Mapping[str, Any]) -> tuple[bool, str]:
        from backend.signals.calibration import artifact_digest
        if artifact_digest(artifact) != artifact.get("artifact_sha256"):
            return False, "artifact_digest_mismatch"
        gates = "gates_passed" if (artifact.get("gates") or {}).get("passed") else "gates_FAILED"
        return True, f"research_counterfactual_unapproved:{gates}"


class _ObservedProvider:
    """Serves one already-journalled observation to the producer (both tracks see the same bars)."""

    def __init__(self, series: CandleSeries) -> None:
        self.series, self.source = series, series.source

    def fetch(self, instrument: str, *, granularity_s: int, end: datetime | None = None) -> CandleSeries:
        if instrument != self.series.instrument or granularity_s != self.series.granularity_s:
            raise CandleError("observation_mismatch")
        return self.series


@dataclass
class Track:
    name: str
    root: Path
    router: TradingRouter
    approvals: Any
    state_path: Path
    processed: set[str] = field(default_factory=set)

    def load(self) -> None:
        if self.state_path.exists():
            self.processed = set(json.loads(self.state_path.read_text(encoding="utf-8")).get("processed", []))

    def save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"processed": sorted(self.processed)}), encoding="utf-8")
        tmp.replace(self.state_path)


def _key(root: Path) -> bytes:
    """Per-run mandate signing key, isolated to this simulation (never a production key)."""
    path = root / "sim_signing.key"
    if not path.exists():
        root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path.read_bytes()


Presenter = Callable[[Mapping[str, Any]], bool]


def _activate(engine: CopyTradeEngine, *, operator: str, now: datetime, presenter: Presenter | None) -> None:
    """The operator activates Simulated Trading for the simulation user through the real consent
    flow: every manual page is presented in full by `presenter` and must be confirmed. Nothing is
    recorded as reviewed unless the presenter confirmed it."""
    if presenter is None:
        raise SimulationError("consent_activation_required")
    consent = engine.consent
    change = consent.propose_change(SIM_USER, operating_mode=OperatingMode.SIMULATED_TRADING.value,
                                    risk_personality=SIMULATED_DEFAULT_PERSONALITY.value, limits=None,
                                    mandate_request=None, now=now)
    review = consent.open_review(SIM_USER, auth_session_hash=SIM_SESSION, change_id=change.change_id, now=now)
    for page_id in review.pages:
        page = consent.present_page(SIM_USER, auth_session_hash=SIM_SESSION, review_id=review.review_id,
                                    page_id=page_id, now=now)
        if not presenter(page):
            raise SimulationError(f"consent_page_not_confirmed:{page_id}")
        consent.mark_reviewed(SIM_USER, auth_session_hash=SIM_SESSION, review_id=review.review_id, page_id=page_id,
                              method="non_scrollable_presented", page_sha256=page["sha256"], now=now)
    manual = consent.manual_provider()
    consent.accept(SIM_USER, auth_session_hash=SIM_SESSION, review_id=review.review_id, acknowledgement_checked=True,
                   acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256, manual_version=manual.version,
                   manual_sha256=manual.sha256, policy_hash_shown=change.policy_hash, now=now)


def build_track(name: str, root: Path, *, approvals: Any, operator: str, now: datetime,
                starting_equity: float = STARTING_EQUITY_CAD,
                session_created: Callable[[], float] | None = None, presenter: Presenter | None = None) -> Track:
    root = Path(root)
    if _is_operational(root):
        raise SimulationError("simulation_cannot_use_operational_paper_book")
    root.mkdir(parents=True, exist_ok=True)
    key = _key(root)
    engine = CopyTradeEngine(root, key_provider=lambda: key)
    created = session_created or (lambda: now.timestamp())
    router = TradingRouter(
        engine, book=PaperBook(root, starting_equity=starting_equity),
        role_resolver=lambda u: "TRADER" if u == SIM_USER else None,
        # R7 requires a sign-on within SESSION_TIMEOUT_SECONDS (1 h). The simulation honours it: the
        # session is the operator's last explicit attestation (Cad146Simulation.attest_operator).
        session_resolver=lambda u: (SIM_SESSION, created()) if u == SIM_USER else None,
        # Simulation entries are controlled by SIM_ENTRY_HALT_ENV (enforced in Cad146Simulation.cycle),
        # not by the LIVE brokerage kill switch: that switch governs real broker orders, which this
        # module cannot place, and must stay engaged during the trial (preflight requires it). The
        # env passed here is deliberately non-empty so evaluate_live_order_kill_switch does not fall
        # back to os.environ. The global emergency stop (REA_KILL_SWITCH / runtime/kill.switch) is
        # still checked by the engine via check_kill_switch and halts simulated entries too.
        system_provider=lambda: SystemContext(engine_mode="SAFE", safety_flags=dict(SAFE_FLAGS), mobile_controls={},
                                              env={"CSS_EXECUTION_CONTEXT": "SIMULATION_NO_BROKER"}),
    )
    if engine.preferences.get(SIM_USER).active is None:
        _activate(engine, operator=operator, now=now, presenter=presenter)
    track = Track(name, root, router, approvals, root / "sim_state.json")
    track.load()
    return track


class Cad146Simulation:
    """Runs one cycle at a time; the caller owns the clock (wall-clock in operation, fixed in tests)."""

    def __init__(self, root: Path | str, *, artifacts: Sequence[Mapping[str, Any]], costs: Mapping[str, CostModel],
                 operational_approvals_root: Path | str, operator: str, now: datetime | None = None,
                 starting_equity: float = STARTING_EQUITY_CAD, quote_provider: Any = None,
                 env: Mapping[str, str] | None = None, presenter: Presenter | None = None) -> None:
        refuse_if_live_armed(env)
        now = _utc(now)
        self.root = Path(root)
        if _is_operational(self.root):
            raise SimulationError("simulation_cannot_use_operational_paper_book")
        self.artifacts, self.costs, self.quote_provider = list(artifacts), dict(costs), quote_provider
        self.journal = self.root / "journal.jsonl"
        self.meta_path = self.root / "run.json"
        if not self.meta_path.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            self.meta_path.write_text(json.dumps({
                "starting_equity_cad": starting_equity, "started_utc": now.isoformat(), "operator": operator,
                "designated_trader": AUTONOMOUS_SOURCE_ID, "operating_mode": OperatingMode.SIMULATED_TRADING.value,
                "risk_personality": SIMULATED_DEFAULT_PERSONALITY.value, "engine_mode": "SAFE",
                "safety_flags": SAFE_FLAGS, "real_orders": 0}, indent=2, sort_keys=True), encoding="utf-8")
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.session_path = self.root / "operator_session.json"
        if not self.session_path.exists():
            self.attest_operator(operator, now=now)
        session_created = self._session_created
        # Track A reads the OPERATIONAL approvals ledger (read-only use: status() only).
        self.track_a = build_track(TRACK_A, self.root / "track_a",
                                   approvals=CalibrationApprovals(operational_approvals_root), operator=operator,
                                   now=now, starting_equity=meta["starting_equity_cad"], session_created=session_created,
                                   presenter=presenter)
        self.track_b = build_track(TRACK_B, self.root / "track_b", approvals=_ResearchApprovals(), operator=operator,
                                   now=now, starting_equity=meta["starting_equity_cad"], session_created=session_created,
                                   presenter=presenter)

    # ------------------------------------------------------------------ operator sign-on (R7)
    def attest_operator(self, operator: str, *, now: datetime | None = None) -> None:
        """An operator's explicit sign-on for this simulation. Never refreshed automatically."""
        if not str(operator or "").strip():
            raise SimulationError("operator_required")
        now = _utc(now)
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(json.dumps({"operator": operator, "created": now.timestamp(),
                                                 "created_utc": now.isoformat()}), encoding="utf-8")
        if self.journal.parent.exists():
            self._write({"type": "OPERATOR_SIGN_ON", "operator": operator, "at_utc": now.isoformat()})

    def _session_created(self) -> float:
        try:
            return float(json.loads(self.session_path.read_text(encoding="utf-8"))["created"])
        except (OSError, ValueError, KeyError):
            return 0.0  # unreadable -> expired -> R7 refuses

    # ------------------------------------------------------------------ journal
    def _write(self, rec: Mapping[str, Any]) -> None:
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")

    # ------------------------------------------------------------------ one cycle
    def cycle(self, fetch: Callable[[str, int], CandleSeries], instruments: Sequence[tuple[str, int]], *,
              now: datetime | None = None) -> dict[str, Any]:
        now = _utc(now)
        refuse_if_live_armed()
        summary = {"at_utc": now.isoformat(), "observations": 0, "outages": 0, "decisions": {TRACK_A: 0, TRACK_B: 0},
                   "operator_session_age_s": round(now.timestamp() - self._session_created(), 1)}
        marks: dict[str, float] = {}
        for instrument, gran in instruments:
            try:
                series = fetch(instrument, gran)
            except (CandleError, OSError, ValueError) as exc:
                summary["outages"] += 1
                self._write({"type": "OUTAGE", "instrument": instrument, "granularity_s": gran,
                             "reason": f"{type(exc).__name__}:{exc}"[:300], "at_utc": now.isoformat()})
                continue
            if not series.candles:
                summary["outages"] += 1
                self._write({"type": "OUTAGE", "instrument": instrument, "granularity_s": gran,
                             "reason": "no_candles", "at_utc": now.isoformat()})
                continue
            last = series.candles[-1]
            obs_key = f"{series.source}|{instrument}|{gran}|{last.ts}"
            self._write({"type": "OBSERVATION", "key": obs_key, "source": series.source,
                         "classification": series.classification, "instrument": instrument, "granularity_s": gran,
                         "bars": len(series.candles), "last_bar_open_utc": datetime.fromtimestamp(last.ts, tz=timezone.utc).isoformat(),
                         "last_close": last.close, "data_sha256": series.digest, "at_utc": now.isoformat()})
            summary["observations"] += 1
            marks[instrument] = last.close
            halted = sim_entry_halted()
            for track in (self.track_a, self.track_b):
                if obs_key in track.processed:
                    continue  # replay / restart: this bar was already decided for this track
                if halted:
                    # Entries halted by the simulation control: the bar is NOT marked processed, so
                    # it is decided normally if the halt is lifted while the bar is still current.
                    self._write({"type": "SIM_ENTRY_HALTED", "track": track.name, "key": obs_key,
                                 "at_utc": now.isoformat()})
                    continue
                summary["decisions"][track.name] += self._decide(track, series, now)
                track.processed.add(obs_key)
                track.save()
        for track in (self.track_a, self.track_b):
            symbols = {p.position_id: p.symbol for p in track.router.book.positions(SIM_USER)}
            for closed in track.router.run_exit_cycle(marks, now=now):
                self._write({"type": "EXIT", "track": track.name, "symbol": symbols.get(closed["position_id"]),
                             **closed, "at_utc": now.isoformat()})
            acct = track.router.book.account(SIM_USER, now)
            self._write({"type": "EQUITY", "track": track.name, "equity_cad": acct["equity"],
                         "open_positions": len(track.router.book.positions(SIM_USER)), "at_utc": now.isoformat()})
        summary["sim_entry_halted"] = sim_entry_halted()
        summary["live_kill_switch_engaged"] = live_kill_switch_engaged()
        self._write({"type": "HEARTBEAT", **summary})
        return summary

    def _decide(self, track: Track, series: CandleSeries, now: datetime) -> int:
        producer = SignalProducer(_ObservedProvider(series), track.approvals, self.artifacts, self.costs,
                                  quote_provider=self.quote_provider)
        count = 0
        for produced in producer.produce(series.instrument, granularity_s=series.granularity_s, now=now):
            rec: dict[str, Any] = {"type": "PRODUCED", "track": track.name, "instrument": series.instrument,
                                   "granularity_s": series.granularity_s, "reason": produced.reason,
                                   "artifact_sha256": produced.artifact_sha256, "data_source": produced.data_source,
                                   "data_classification": produced.data_classification,
                                   "observed_spread_bps": produced.observed_spread_bps, "at_utc": now.isoformat()}
            if track.name == TRACK_B:
                rec["label"] = "RESEARCH_COUNTERFACTUAL"
            if produced.signal is not None:
                result = self._route(track, produced, now)
                rec.update(signal_id=produced.signal.signal_id, side=produced.signal.side,
                           probability=produced.signal.probability, routed=result.accepted, route_reason=result.reason,
                           decisions=[{"outcome": d.outcome, "stage": d.stage, "reason": d.reason,
                                       "notional_cad": d.notional, "position_id": d.position_id}
                                      for d in result.decisions])
                count += len(result.decisions)
            self._write(rec)
        return count

    def _route(self, track: Track, produced: ProducedSignal, now: datetime):
        if track.name == TRACK_A:
            art = next(a for a in self.artifacts if a.get("artifact_sha256") == produced.artifact_sha256)
            return CssEngineSignalBridge(track.router).publish_real_data(produced, art, track.approvals, now=now)
        # Track B: same router gates, no calibration-approval requirement (isolated research book).
        return track.router.on_css_engine_signal(produced.signal, now=now)

    # ------------------------------------------------------------------ reporting
    def report(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = _utc(now)
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        events = [json.loads(x) for x in self.journal.read_text(encoding="utf-8").splitlines()] \
            if self.journal.exists() else []
        out = {"run": meta, "as_of_utc": now.isoformat(),
               "observations": sum(1 for e in events if e["type"] == "OBSERVATION"),
               "outages": [e for e in events if e["type"] == "OUTAGE"][-20:],
               "outage_count": sum(1 for e in events if e["type"] == "OUTAGE"),
               "cycles": sum(1 for e in events if e["type"] == "HEARTBEAT"),
               "baseline_no_trade_equity_cad": meta["starting_equity_cad"], "tracks": {},
               "operator_sign_ons": [e["at_utc"] for e in events if e["type"] == "OPERATOR_SIGN_ON"],
               # R7 refuses new entries when the operator's sign-on is older than 1 h; these cycles
               # are reported so a gap in attendance is visible rather than mistaken for "no signals".
               "cycles_with_expired_sign_on": sum(1 for e in events if e["type"] == "HEARTBEAT"
                                                  and (e.get("operator_session_age_s") or 0) > 3600),
               "sim_entry_halted_cycles": sum(1 for e in events if e["type"] == "HEARTBEAT"
                                              and e.get("sim_entry_halted")),
               "live_kill_switch_engaged_all_cycles": all(e.get("live_kill_switch_engaged", False) for e in events
                                                          if e["type"] == "HEARTBEAT")}
        last_close = {}
        for e in events:
            if e["type"] == "OBSERVATION":
                last_close[e["instrument"]] = e["last_close"]
        for track in (self.track_a, self.track_b):
            acct = track.router.book.account(SIM_USER, now)
            positions = track.router.book.positions(SIM_USER)
            produced = [e for e in events if e["type"] == "PRODUCED" and e["track"] == track.name]
            decisions = [d for e in produced for d in e.get("decisions", [])]
            exits = [e for e in events if e["type"] == "EXIT" and e["track"] == track.name]
            reasons: dict[str, int] = {}
            for e in produced:
                key = e["reason"] if not e.get("decisions") else None
                for d in e.get("decisions", []):
                    reasons[f"{d['stage']}:{d['reason']}"] = reasons.get(f"{d['stage']}:{d['reason']}", 0) + 1
                if key:
                    reasons[key] = reasons.get(key, 0) + 1
            fills = [d for d in decisions if d["outcome"] in {"SIMULATED", "COPIED"}]
            wins = [e for e in exits if (e.get("pnl") or 0) > 0]
            equity = float(acct["equity"])
            out["tracks"][track.name] = {
                "label": "RESEARCH_COUNTERFACTUAL" if track.name == TRACK_B else "GOVERNED",
                "starting_equity_cad": meta["starting_equity_cad"], "equity_cad": equity,
                "net_pnl_cad": round(equity - meta["starting_equity_cad"], 2),
                "return_pct": round((equity / meta["starting_equity_cad"] - 1) * 100, 4),
                "realized_pnl_cad": acct["realized_pnl"], "fees_cad": acct.get("fees", 0.0),
                "equity_peak_cad": acct["equity_peak"],
                "max_drawdown_cad": _max_drawdown([meta["starting_equity_cad"]] + [
                    e["equity_cad"] for e in events if e["type"] == "EQUITY" and e["track"] == track.name] + [equity]),
                "unrealized_pnl_cad": round(sum(_unrealized(p, last_close.get(p.symbol)) for p in positions), 2),
                "capital_utilization_pct": round(sum(p.notional for p in positions) / equity * 100, 4) if equity else None,
                "by_instrument": _by_instrument(exits),
                "cash_cad": round(equity - sum(p.notional for p in positions), 2),
                "open_positions": [{"symbol": p.symbol, "side": p.side, "notional_cad": p.notional,
                                    "entry_price": p.entry_price} for p in positions],
                "proposed_signals": sum(1 for e in produced if e.get("signal_id")),
                "decisions": len(decisions), "fills": len(fills),
                "rejected": sum(1 for d in decisions if d["outcome"] == "REJECTED"),
                "closed_trades": len(exits), "win_rate": (len(wins) / len(exits)) if exits else None,
                "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
            }
        return out


def _max_drawdown(path: Sequence[float]) -> float:
    peak, worst = float("-inf"), 0.0
    for x in path:
        peak = max(peak, float(x))
        worst = max(worst, peak - float(x))
    return round(worst, 2)


def _unrealized(position: Any, mark: float | None) -> float:
    if mark is None or not position.entry_price:
        return 0.0
    direction = 1 if position.side == "BUY" else -1
    return direction * (mark - position.entry_price) / position.entry_price * position.notional


def _by_instrument(exits: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in exits:
        row = out.setdefault(str(e.get("symbol")), {"closed": 0, "wins": 0, "pnl_cad": 0.0})
        row["closed"] += 1
        row["wins"] += int((e.get("pnl") or 0) > 0)
        row["pnl_cad"] = round(row["pnl_cad"] + float(e.get("pnl") or 0), 2)
    return out
