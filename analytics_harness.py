"""
Phase 12.3 CTO Analytics Harness (READ-ONLY)

Purpose:
- Consume counters from dry-run harnesses
- Compute Phase 12.1 metrics
- Emit Phase 12.2-compliant experiment log
- NO execution
- No broker access
- Deterministic and audit-safe
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any


# ------------------------
# Helpers
# ------------------------

def _safe_div(n: float, d: float) -> float:
    return 0.0 if d == 0 else n / d


def _determinism_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _governance_snapshot() -> Dict[str, Any]:
    """
    Governance snapshot for audit. Read-only import.
    If governance module ever becomes unavailable, we degrade safely to a stub
    (still read-only; still deterministic).
    """
    try:
        from governance.profit_taking_policy import (
            DEFAULT_PROFIT_TAKING_POLICY,
            policy_as_dict,
        )

        return {
            "profit_taking_policy": policy_as_dict(DEFAULT_PROFIT_TAKING_POLICY),
            "source": "governance/profit_taking_policy.py",
            "notes": (
                "Governance-locked profit-taking tiers and re-entry constraints. "
                "No martingale. No unrealized-gains re-entry."
            ),
        }
    except Exception as e:
        # Safe fallback: still deterministic, still audit-friendly.
        return {
            "profit_taking_policy": None,
            "source": "governance/profit_taking_policy.py",
            "notes": "Governance policy import failed (read-only harness fallback).",
            "error": f"{type(e).__name__}: {e}",
        }


# ------------------------
# Metrics (Phase 12.1)
# ------------------------

def compute_metrics(counters: Dict[str, int], replay_units: int) -> Dict[str, Any]:
    signals = counters.get("signals_generated_total", 0)
    regime_allow = counters.get("regime_allow", 0)
    regime_block = counters.get("regime_block", 0)

    risk_decisions = counters.get("risk_decisions_total", 0)
    risk_allowed = counters.get("risk_allowed", 0)

    exec_decisions = counters.get("execution_decisions_total", 0)
    exec_allowed = counters.get("execution_allowed", 0)
    exec_blocked = counters.get("execution_blocked", 0)

    metrics = {
        # Signal diagnostics
        "signal_frequency": _safe_div(signals, replay_units),
        "zero_signal_confirmed": signals == 0,

        # Regime diagnostics
        "regime_allow_ratio": _safe_div(regime_allow, regime_allow + regime_block),

        # Risk diagnostics
        "risk_allow_ratio": _safe_div(risk_allowed, risk_decisions),

        # Execution diagnostics
        "execution_block_ratio": _safe_div(exec_blocked, exec_decisions),
        "execution_guard_integrity": exec_allowed == 0,
    }

    return metrics


# ------------------------
# Experiment Log Builder
# ------------------------

def build_experiment_log(
    experiment_id: str,
    dataset: Dict[str, Any],
    configuration: Dict[str, Any],
    counters: Dict[str, int],
    replay_units: int,
    baseline_id: str = "BASELINE-UNSET",
    notes: str = "",
) -> Dict[str, Any]:

    metrics = compute_metrics(counters, replay_units)

    governance = _governance_snapshot()

    # Include governance in the determinism hash payload so policy changes are detectable.
    integrity_payload = {
        "counters": counters,
        "metrics": metrics,
        "configuration": configuration,
        "dataset": dataset,
        "governance": governance,
    }

    integrity = {
        "determinism_hash": _determinism_hash(integrity_payload),
        "analysis_only_confirmed": configuration.get("execution", {}).get("analysis_only", True),
        "execution_allowed_zero": counters.get("execution_allowed", 0) == 0,
    }

    overall_status = "PASS"
    if not integrity["analysis_only_confirmed"] or not integrity["execution_allowed_zero"]:
        overall_status = "FAIL"

    return {
        "experiment_id": experiment_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_version": "GIT_HEAD",
        "architecture_version": "v1.0",
        "classification": "RESEARCH_ONLY",

        "dataset": dataset,
        "configuration": configuration,

        # Governance: included for audit + operator visibility (prompt-only)
        "governance": governance,

        "counters": counters,
        "metrics": metrics,

        "baseline_comparison": {
            "baseline_id": baseline_id,
            "counter_invariance": None,
            "metric_deltas": {},
        },

        "integrity": integrity,
        "overall_status": overall_status,
        "notes": notes,
    }


# ------------------------
# Self-Test (Safe)
# ------------------------

if __name__ == "__main__":
    # Example counters from dry-run harnesses
    counters_example = {
        "signals_generated_total": 0,
        "regime_allow": 13,
        "regime_block": 39,
        "risk_decisions_total": 10,
        "risk_allowed": 10,
        "risk_blocked": 0,
        "execution_decisions_total": 10,
        "execution_allowed": 0,
        "execution_blocked": 10,
    }

    dataset_example = {
        "source": "CSV",
        "symbol": "EURUSD",
        "timeframe": "1m",
        "bars_1m": 260,
        "bars_5m": 52,
        "date_range": "SAMPLE",
        "dataset_hash": "HASH-PLACEHOLDER",
    }

    configuration_example = {
        "regime": {"min_bars_5m": 40},
        "signal": {"strategy": "VWAP_MR", "mode": "prompt_only"},
        "risk": {"risk_per_trade": 0.01},
        "execution": {"analysis_only": True},
    }

    log = build_experiment_log(
        experiment_id="SAMPLE-DRYRUN",
        dataset=dataset_example,
        configuration=configuration_example,
        counters=counters_example,
        replay_units=260,
        notes="Self-test analytics harness run",
    )

    print("=== ANALYTICS HARNESS OUTPUT (SAMPLE) ===")
    print(json.dumps(log, indent=2))
