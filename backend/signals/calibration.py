"""Walk-forward calibration and release gates for CSS strategies.

Method (per instrument series, per approved strategy):
  * Anchored walk-forward: train on bars [0, t), test on [t, t + step), roll t forward. The
    model is never evaluated on data it was fitted on.
  * Model: score quantile bins (from TRAIN scores only); per bin, win probability with a
    Beta(1, 1) prior and mean net win / loss in bps -> expected net bps.
  * Selection: in TEST, a trade is taken only if its bin's TRAIN expectancy (net of costs) > 0.
  * OOS metrics on selected trades: count, mean / std / t-stat of net bps, one-sided p-value,
    95% lower bound of the mean, Brier score vs the base-rate Brier, fraction of folds with a
    positive mean, max drawdown of cumulative net bps.
Gates (all must pass; thresholds are explicit and conservative):
  min_oos_trades, lower_bound_net_bps > 0, brier < base_rate_brier, positive_fold_fraction,
  max_drawdown_bps.
The final artifact refits the bins on ALL data, pins the data digests and the code revision,
and is only routable after two distinct approvers sign off (see producer.py).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.signals.research import Event

SCHEMA = "css.signals.calibration.v1"


@dataclass(frozen=True)
class GateThresholds:
    min_oos_trades: int = 100
    min_positive_fold_fraction: float = 0.6
    max_drawdown_bps: float = 2_000.0


@dataclass(frozen=True)
class BinModel:
    edges: tuple[float, ...]  # upper edges of all bins but the last
    win_prob: tuple[float, ...]
    avg_win_bps: tuple[float, ...]
    avg_loss_bps: tuple[float, ...]
    expectancy_bps: tuple[float, ...]
    counts: tuple[int, ...]

    def bin_of(self, score: float) -> int:
        for k, edge in enumerate(self.edges):
            if score <= edge:
                return k
        return len(self.edges)

    def predict(self, score: float) -> tuple[float, float]:
        k = self.bin_of(score)
        return self.win_prob[k], self.expectancy_bps[k]


def fit_bins(events: Sequence[Event], n_bins: int = 3) -> BinModel | None:
    if len(events) < n_bins * 10:
        return None
    scores = sorted(e.score for e in events)
    edges = tuple(scores[int(len(scores) * q / n_bins)] for q in range(1, n_bins))
    groups: list[list[Event]] = [[] for _ in range(n_bins)]
    proto = BinModel(edges, (), (), (), (), ())
    for e in events:
        groups[proto.bin_of(e.score)].append(e)
    wp, aw, al, ex, ct = [], [], [], [], []
    for g in groups:
        wins = [e.net_bps for e in g if e.win]
        losses = [e.net_bps for e in g if not e.win]
        p = (len(wins) + 1) / (len(g) + 2)  # Beta(1,1)
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        wp.append(p)
        aw.append(avg_w)
        al.append(avg_l)
        ex.append(p * avg_w + (1 - p) * avg_l if g else -1.0)
        ct.append(len(g))
    return BinModel(edges, tuple(wp), tuple(aw), tuple(al), tuple(ex), tuple(ct))


@dataclass
class OOSResult:
    trades: int
    mean_net_bps: float
    std_net_bps: float
    t_stat: float
    p_value_one_sided: float
    lower_bound_net_bps: float
    brier: float
    base_rate_brier: float
    positive_fold_fraction: float
    max_drawdown_bps: float
    folds: int
    per_fold_mean_bps: list[float] = field(default_factory=list)


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def walk_forward(events: Sequence[Event], *, n_bars: int, train_bars: int, step_bars: int,
                 n_bins: int = 3) -> OOSResult:
    events = sorted(events, key=lambda e: e.entry_index)
    selected: list[tuple[Event, float]] = []
    fold_means: list[float] = []
    evaluated = 0  # folds with a trained model and test events; a fold that selects nothing is NOT positive
    t = train_bars
    while t < n_bars:
        # train only on trades fully closed before t: no outcome leaks from the test window
        train = [e for e in events if e.exit_index < t]
        test = [e for e in events if t <= e.entry_index < t + step_bars]
        model = fit_bins(train, n_bins)
        if model is not None and test:
            evaluated += 1
            fold = []
            for e in test:
                p, ev = model.predict(e.score)
                if ev > 0:
                    selected.append((e, p))
                    fold.append(e.net_bps)
            if fold:
                fold_means.append(sum(fold) / len(fold))
        t += step_bars
    n = len(selected)
    if n == 0:
        return OOSResult(0, 0.0, 0.0, 0.0, 1.0, float("-inf"), 1.0, 0.0, 0.0, 0.0, evaluated)
    nets = [e.net_bps for e, _ in selected]
    mean = sum(nets) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in nets) / (n - 1)) if n > 1 else 0.0
    se = std / math.sqrt(n) if n > 1 else float("inf")
    t_stat = mean / se if se and math.isfinite(se) else 0.0
    wins = [1.0 if e.win else 0.0 for e, _ in selected]
    base = sum(wins) / n
    brier = sum((p - w) ** 2 for (_, p), w in zip(selected, wins)) / n
    base_brier = sum((base - w) ** 2 for w in wins) / n
    equity, peak, dd = 0.0, 0.0, 0.0
    for x in nets:
        equity += x
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return OOSResult(n, mean, std, t_stat, _norm_sf(t_stat), mean - 1.645 * se, brier, base_brier,
                     sum(1 for m in fold_means if m > 0) / evaluated, dd, evaluated, fold_means)


def evaluate_gates(r: OOSResult, g: GateThresholds) -> dict[str, Any]:
    checks = {
        "min_oos_trades": r.trades >= g.min_oos_trades,
        "lower_bound_net_bps_positive": r.lower_bound_net_bps > 0,
        "brier_beats_base_rate": r.brier < r.base_rate_brier,
        "positive_fold_fraction": r.positive_fold_fraction >= g.min_positive_fold_fraction,
        "max_drawdown_bps": r.max_drawdown_bps <= g.max_drawdown_bps,
    }
    return {"passed": all(checks.values()), "checks": checks}


def build_artifact(*, strategy: str, instrument: str, asset_class: str, granularity_s: int,
                   events: Sequence[Event], oos: OOSResult, gates: GateThresholds, data_digests: Sequence[str],
                   barrier: Mapping[str, Any], costs: Mapping[str, Any], code_revision: str,
                   score_map: Mapping[str, float] | None = None, n_bins: int = 3) -> dict[str, Any]:
    final = fit_bins(events, n_bins)
    body = {
        "schema": SCHEMA, "strategy": strategy, "instrument": instrument, "asset_class": asset_class,
        "granularity_s": granularity_s, "data_digests": sorted(data_digests), "code_revision": code_revision,
        "barrier": dict(barrier), "costs": dict(costs), "gate_thresholds": asdict(gates),
        "oos": asdict(oos), "gates": evaluate_gates(oos, gates), "events_total": len(events),
        "model": asdict(final) if final else None,
        # Explicit, owner-approved mapping from net expectancy to the R14F signal-score scale.
        "score_map": dict(score_map or {"intercept": 10.0, "per_bps": 0.1}),
        "quality_inputs": {"strategy_score": round(oos.positive_fold_fraction, 4),
                           "replay_confidence": round(1 - oos.p_value_one_sided, 4)},
    }
    body["artifact_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return body


def artifact_digest(artifact: Mapping[str, Any]) -> str:
    body = {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
