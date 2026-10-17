"""Print compact GitHub Actions ::notice annotations summarising an evidence directory.

Annotations are readable through the checks API (repos/{owner}/{repo}/check-runs/{id}/annotations)
by reviewers who cannot download run artifacts. GitHub shows at most 10 notices per step, so the
summary is split into sections, one workflow step each.

  python tools/css_evidence_notices.py evidence matrix|calibration|producer
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def notice(title: str, payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::notice title={title}::{text[:900]}")


def matrix(ev: Path) -> None:
    path = ev / "market_data_matrix.json"
    if not path.exists():
        notice("matrix", {"error": "market_data_matrix.json missing"})
        return
    doc = json.loads(path.read_text(encoding="utf-8"))
    for name, row in doc.get("providers", {}).items():
        keep = {k: row.get(k) for k in ("verdict", "reason", "classification", "bars", "last_bar_open_utc",
                                          "last_close", "fresh", "metrics", "quote", "quote_error", "data_sha256")
                if row.get(k) is not None}
        notice(f"provider {name}", keep)
    notice("cross-provider + clock", {"cross_provider": doc.get("cross_provider"), "clock_skew": doc.get("clock_skew"),
                                      "code_revision": doc.get("code_revision"),
                                      "operating_country": doc.get("operating_country")})


def fetch(ev: Path) -> None:
    log = ev / "fetch.log"
    for line in log.read_text(encoding="utf-8").splitlines() if log.exists() else []:
        if "sha256=" in line or line.startswith("backend.signals.candles.CandleError"):
            notice("fetch", {"line": line.strip()[:400]})


def calibration(ev: Path, granularity: int | None = None) -> None:
    for folder in ("calibration", "calibration_alpaca"):
        for p in sorted((ev / folder).glob("*.json")) if (ev / folder).exists() else []:
            a = json.loads(p.read_text(encoding="utf-8"))
            if granularity is not None and a.get("granularity_s") != granularity:
                continue
            o = a.get("oos") or {}
            notice(f"{folder} {a.get('instrument')} {a.get('granularity_s')}s {a.get('strategy')}", {
                "gates_passed": (a.get("gates") or {}).get("passed"), "failed_checks": [
                    k for k, v in ((a.get("gates") or {}).get("checks") or {}).items() if not v],
                "oos_trades": o.get("trades"), "mean_net_bps": o.get("mean_net_bps"),
                "lb95_net_bps": o.get("lower_bound_net_bps"), "brier": o.get("brier"),
                "base_rate_brier": o.get("base_rate_brier"), "pos_folds": o.get("positive_fold_fraction"),
                "max_dd_bps": o.get("max_drawdown_bps"), "folds": o.get("folds"),
                "diagnostics": a.get("diagnostics"), "data_source": a.get("data_source"),
                "artifact_sha256": (a.get("artifact_sha256") or "")[:16]})


def producer(ev: Path) -> None:
    for p in sorted(ev.glob("producer_cycle_*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        for row in doc.get("produced", []):
            notice(f"producer {doc.get('instrument')} {row.get('strategy')}", {
                k: row.get(k) for k in ("reason", "signal_emitted", "data_source", "data_classification",
                                        "last_bar_open_utc", "observed_spread_bps", "artifact_gates_passed")})


if __name__ == "__main__":
    evidence, section = Path(sys.argv[1]), sys.argv[2]
    if section.startswith("cal"):
        calibration(evidence, int(section[3:]) if section[3:] else None)
    else:
        {"matrix": matrix, "fetch": fetch, "producer": producer}[section](evidence)
