"""CSS real-data signal producer and calibration approvals (paper routing only).

A calibration artifact is ROUTABLE only when ALL hold:
  * its recomputed digest equals artifact_sha256 (unaltered);
  * its walk-forward gates passed;
  * two DISTINCT SUPER_USERs approved exactly that digest (hash-chained approvals ledger);
  * it has not been revoked (single SUPER_USER, immediate).
The producer computes features on the latest *fresh, complete* bars, applies the approved
strategy rules, looks up the calibrated probability and net expectancy, and emits a
SourceSignal only when the expectancy net of costs is positive. It never invents values: every
field is either measured from the bars, taken from the cost model, or taken from the approved
artifact.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.signals.calibration import BinModel, artifact_digest
from backend.signals.candles import LIVE, CandleError, CandleProvider, CandleSeries, check_fresh, drop_incomplete
from backend.signals.research import CostModel, candidates_at, compute_features
from backend.trading_profiles.copy_engine import AUTONOMOUS_SOURCE_ID, SourceSignal
from backend.trading_profiles.hash_chain import HashChainLog
from backend.runtime.interprocess_lock import exclusive_file_lock

ADMIN_ROLE = "SUPER_USER"


class CalibrationApprovalError(RuntimeError):
    pass


class CalibrationApprovals:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.log = HashChainLog(self.root, "calibration_approvals", CalibrationApprovalError)
        self.lock = self.root / "calibration_approvals.lock"

    def _record(self, event: str, artifact: Mapping[str, Any], actor_ctx: Mapping[str, Any], now: datetime | None):
        actor = dict(actor_ctx or {})
        if str(actor.get("role", "")).upper() != ADMIN_ROLE or not actor.get("user_id"):
            raise CalibrationApprovalError("super_user_required")
        if artifact_digest(artifact) != artifact.get("artifact_sha256"):
            raise CalibrationApprovalError("artifact_digest_mismatch")
        if event == "APPROVED" and not (artifact.get("gates") or {}).get("passed"):
            raise CalibrationApprovalError("gates_not_passed")
        self.root.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock, timeout_seconds=10.0):
            self.log.append({"event": event, "artifact_sha256": artifact["artifact_sha256"],
                             "strategy": artifact.get("strategy"), "instrument": artifact.get("instrument"),
                             "actor": str(actor["user_id"]), "at_utc": (now or datetime.now(timezone.utc)).isoformat()})

    def approve(self, artifact: Mapping[str, Any], *, actor_ctx: Mapping[str, Any], now: datetime | None = None) -> None:
        self._record("APPROVED", artifact, actor_ctx, now)

    def revoke(self, artifact: Mapping[str, Any], *, actor_ctx: Mapping[str, Any], now: datetime | None = None) -> None:
        self._record("REVOKED", artifact, actor_ctx, now)

    def status(self, artifact: Mapping[str, Any]) -> tuple[bool, str]:
        try:
            if artifact_digest(artifact) != artifact.get("artifact_sha256"):
                return False, "artifact_digest_mismatch"
            if not (artifact.get("gates") or {}).get("passed"):
                return False, "gates_not_passed"
            events = [e for e in self.log.events() if e["artifact_sha256"] == artifact["artifact_sha256"]]
        except CalibrationApprovalError as exc:
            return False, str(exc)
        if any(e["event"] == "REVOKED" for e in events):
            return False, "revoked"
        approvers = {e["actor"] for e in events if e["event"] == "APPROVED"}
        if len(approvers) < 2:
            return False, f"approvals_insufficient:{len(approvers)}"
        return True, "approved_dual_control"


@dataclass(frozen=True)
class ProducedSignal:
    signal: SourceSignal | None
    reason: str
    artifact_sha256: str | None = None
    # Provenance of the market observation the decision was computed on (closeout).
    data_source: str | None = None
    data_classification: str | None = None
    data_digest: str | None = None
    last_bar_ts: int | None = None
    observed_spread_bps: float | None = None


# Classifications a live producer may act on. REPLAY and SYNTHETIC are never permitted here:
# replay belongs to research tools with a research router, synthetic to tests.
NEVER_LIVE = frozenset({"REPLAY", "SYNTHETIC", "UNCLASSIFIED", "BLOCKED"})


def _bins(model: Mapping[str, Any]) -> BinModel:
    return BinModel(tuple(model["edges"]), tuple(model["win_prob"]), tuple(model["avg_win_bps"]),
                    tuple(model["avg_loss_bps"]), tuple(model["expectancy_bps"]), tuple(model["counts"]))


class SignalProducer:
    def __init__(self, provider: CandleProvider, approvals: CalibrationApprovals, artifacts: list[Mapping[str, Any]],
                 costs: Mapping[str, CostModel], *, allowed_classifications: frozenset[str] = frozenset({LIVE}),
                 quote_provider: Any = None, max_spread_multiple: float = 2.0,
                 min_depth_notional: float = 0.0) -> None:
        bad = set(allowed_classifications) & NEVER_LIVE
        if bad:
            raise ValueError(f"classification_never_permitted_for_live_signals:{sorted(bad)}")
        self.provider = provider
        self.approvals = approvals
        self.artifacts = list(artifacts)
        self.costs = dict(costs)
        self.allowed_classifications = frozenset(allowed_classifications)
        self.quote_provider = quote_provider
        self.max_spread_multiple = float(max_spread_multiple)
        self.min_depth_notional = float(min_depth_notional)

    def produce(self, instrument: str, *, granularity_s: int, now: datetime) -> list[ProducedSignal]:
        relevant = [a for a in self.artifacts if a.get("instrument") == instrument
                    and a.get("granularity_s") == granularity_s]
        if not relevant:
            return [ProducedSignal(None, "no_calibration_for_instrument")]
        try:
            series = self.provider.fetch(instrument, granularity_s=granularity_s)
            series = drop_incomplete(series, now=now)  # defence in depth: never act on a forming bar
            check_fresh(series, now=now)
        except (CandleError, OSError, ValueError) as exc:
            return [ProducedSignal(None, f"market_data_unavailable:{exc}")]
        if series.classification not in self.allowed_classifications:
            return [ProducedSignal(None, f"data_classification_not_permitted:{series.classification}",
                                   data_source=series.source, data_classification=series.classification)]
        if series.candles[-1].volume <= 0:
            return [ProducedSignal(None, "market_quality:last_bar_no_volume", data_source=series.source,
                                   data_classification=series.classification)]
        spread_bps: float | None = None
        if self.quote_provider is not None:
            try:
                quote = self.quote_provider.quote(instrument)
            except (CandleError, OSError, ValueError) as exc:
                return [ProducedSignal(None, f"market_quality:quote_unavailable:{exc}", data_source=series.source,
                                       data_classification=series.classification)]
            spread_bps = quote.spread_bps
            cost = self.costs.get(series.asset_class)
            if cost is not None and spread_bps > cost.spread_bps * self.max_spread_multiple:
                return [ProducedSignal(None, f"market_quality:spread_exceeds_cost_model:{spread_bps:.1f}bps",
                                       data_source=series.source, data_classification=series.classification,
                                       observed_spread_bps=spread_bps)]
            depth = min(quote.bid_depth_notional or 0.0, quote.ask_depth_notional or 0.0)
            if self.min_depth_notional > 0 and depth < self.min_depth_notional:
                return [ProducedSignal(None, f"market_quality:depth_insufficient:{depth:.0f}",
                                       data_source=series.source, data_classification=series.classification,
                                       observed_spread_bps=spread_bps)]
        out = []
        for a in relevant:
            p = self._from_series(series, a, now)
            out.append(ProducedSignal(p.signal, p.reason, p.artifact_sha256, series.source, series.classification,
                                      series.digest, series.candles[-1].ts, spread_bps))
        return out

    def _from_series(self, series: CandleSeries, artifact: Mapping[str, Any], now: datetime) -> ProducedSignal:
        sha = artifact.get("artifact_sha256")
        ok, why = self.approvals.status(artifact)
        if not ok:
            return ProducedSignal(None, f"calibration_not_routable:{why}", sha)
        calibrated_source = artifact.get("data_source")
        if calibrated_source and calibrated_source != series.source:
            # A model fitted on one venue's bars is not applied to another venue's bars.
            return ProducedSignal(None, f"data_source_mismatch:{series.source}!={calibrated_source}", sha)
        if series.asset_class not in self.costs:
            return ProducedSignal(None, f"no_cost_model:{series.asset_class}", sha)
        feats = compute_features(series.candles)
        last = feats[-1] if feats else None
        cands = [c for c in candidates_at(last) if c.strategy == artifact["strategy"]]
        if not cands:
            return ProducedSignal(None, "no_strategy_candidate", sha)
        cand = cands[0]
        p, ev_bps = _bins(artifact["model"]).predict(cand.score)
        if ev_bps <= 0:
            return ProducedSignal(None, "calibrated_expectancy_not_positive", sha)
        cost = self.costs[series.asset_class]
        barrier = artifact["barrier"]
        stop_pct = barrier["stop_atr"] * cand.features.atr_pct * 100
        smap = artifact["score_map"]
        bar_ts = series.candles[-1].ts
        sid = hashlib.sha256(f"{sha}|{series.instrument}|{bar_ts}|{cand.side}".encode()).hexdigest()[:20]
        signal = SourceSignal(
            signal_id=f"rd-{sid}", trader_id=AUTONOMOUS_SOURCE_ID, symbol=series.instrument,
            asset_class=series.asset_class, side=cand.side, reference_price=series.candles[-1].close,
            probability=float(p), signal_score=float(smap["intercept"] + smap["per_bps"] * ev_bps),
            confidence=float(p),
            # gross expected move = calibrated net expectancy + the full round-trip cost
            expected_move_bps=float(ev_bps + cost.round_trip_bps),
            fee_bps=2 * cost.fee_bps, spread_bps=cost.spread_bps, slippage_bps=2 * cost.slippage_bps,
            stop_distance_pct=float(stop_pct), risk_reward=float(barrier["reward_risk"]),
            market_regime=cand.features.regime,
            volatility_state="HIGH" if cand.features.vol_percentile > 0.9 else (
                "LOW" if cand.features.vol_percentile < 0.3 else "MEDIUM"),
            strategy_score=float(artifact["quality_inputs"]["strategy_score"]),
            replay_confidence=float(artifact["quality_inputs"]["replay_confidence"]),
        )
        return ProducedSignal(signal, "ok", sha)
