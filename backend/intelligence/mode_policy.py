from __future__ import annotations

from typing import Any, Dict


MODE_POLICIES: Dict[str, Dict[str, Any]] = {
    "safe/test": {
        "optimizer": {
            "min_confluence": 0.90,
            "min_pressure": 0.30,
            "min_accel": 0.15,
            "min_abs_spread_bps": 20.0,
            "min_reversion_window": 0.72,
            "min_elasticity": 0.35,
            "min_exhaustion": 0.40,
            "min_reversal_pressure": 0.56,
            "min_elite_signal": 0.66,
            "min_entry_readiness": 0.62,
        },
        "classifier": {
            "qualified": {
                "min_trade_score": 0.45,
                "min_reversion_window": 0.40,
                "min_elasticity": 0.20,
                "min_reversal_pressure": 0.36,
            },
            "elite": {
                "min_confluence": 0.90,
                "min_pressure": 0.34,
                "min_vwap_dev_abs": 0.018,
                "min_trade_score": 0.66,
                "min_reversion_window": 0.72,
                "min_elasticity": 0.35,
                "min_exhaustion": 0.40,
                "min_reversal_pressure": 0.62,
                "min_elite_signal": 0.72,
                "min_entry_readiness": 0.70,
            },
            "elite_edge_override": {
                "min_trade_score": 0.62,
                "min_reversion_window": 0.68,
                "min_reversal_pressure": 0.60,
            },
        },
        "execution": {
            "min_trade_score": 0.66,
            "min_confluence": 0.90,
            "min_pressure": 0.30,
            "min_accel_or_pressure_boost": 0.15,
            "min_vwap_dev_abs": 0.018,
            "min_reversion_window": 0.72,
            "min_elasticity": 0.35,
            "min_exhaustion": 0.40,
            "min_reversal_pressure": 0.62,
            "min_elite_signal": 0.72,
            "min_entry_readiness": 0.70,
        },
        "expected_behavior": {
            "trade_frequency": "very_low",
            "selectivity": "extreme",
            "intent": "validation / containment / safest paper mode",
        },
    },
    "conservative": {
        "optimizer": {
            "min_confluence": 0.84,
            "min_pressure": 0.24,
            "min_accel": 0.10,
            "min_abs_spread_bps": 16.0,
            "min_reversion_window": 0.64,
            "min_elasticity": 0.30,
            "min_exhaustion": 0.36,
            "min_reversal_pressure": 0.50,
            "min_elite_signal": 0.60,
            "min_entry_readiness": 0.58,
        },
        "classifier": {
            "qualified": {
                "min_trade_score": 0.45,
                "min_reversion_window": 0.40,
                "min_elasticity": 0.20,
                "min_reversal_pressure": 0.36,
            },
            "elite": {
                "min_confluence": 0.84,
                "min_pressure": 0.26,
                "min_vwap_dev_abs": 0.015,
                "min_trade_score": 0.60,
                "min_reversion_window": 0.64,
                "min_elasticity": 0.30,
                "min_exhaustion": 0.36,
                "min_reversal_pressure": 0.56,
                "min_elite_signal": 0.66,
                "min_entry_readiness": 0.64,
            },
            "elite_edge_override": {
                "min_trade_score": 0.58,
                "min_reversion_window": 0.62,
                "min_reversal_pressure": 0.54,
            },
        },
        "execution": {
            "min_trade_score": 0.60,
            "min_confluence": 0.84,
            "min_pressure": 0.24,
            "min_accel_or_pressure_boost": 0.10,
            "min_vwap_dev_abs": 0.015,
            "min_reversion_window": 0.64,
            "min_elasticity": 0.30,
            "min_exhaustion": 0.36,
            "min_reversal_pressure": 0.56,
            "min_elite_signal": 0.66,
            "min_entry_readiness": 0.64,
        },
        "expected_behavior": {
            "trade_frequency": "low",
            "selectivity": "high",
            "intent": "strict paper-trading mode",
        },
    },
    "balanced": {
        "optimizer": {
            "min_confluence": 0.78,
            "min_pressure": 0.20,
            "min_accel": 0.08,
            "min_abs_spread_bps": 12.0,
            "min_reversion_window": 0.56,
            "min_elasticity": 0.25,
            "min_exhaustion": 0.32,
            "min_reversal_pressure": 0.42,
            "min_elite_signal": 0.54,
            "min_entry_readiness": 0.52,
        },
        "classifier": {
            "qualified": {
                "min_trade_score": 0.45,
                "min_reversion_window": 0.40,
                "min_elasticity": 0.20,
                "min_reversal_pressure": 0.36,
            },
            "elite": {
                "min_confluence": 0.80,
                "min_pressure": 0.22,
                "min_vwap_dev_abs": 0.012,
                "min_trade_score": 0.55,
                "min_reversion_window": 0.56,
                "min_elasticity": 0.25,
                "min_exhaustion": 0.32,
                "min_reversal_pressure": 0.48,
                "min_elite_signal": 0.60,
                "min_entry_readiness": 0.58,
            },
            "elite_edge_override": {
                "min_trade_score": 0.52,
                "min_reversion_window": 0.54,
                "min_reversal_pressure": 0.46,
            },
        },
        "execution": {
            "min_trade_score": 0.55,
            "min_confluence": 0.78,
            "min_pressure": 0.20,
            "min_accel_or_pressure_boost": 0.08,
            "min_vwap_dev_abs": 0.012,
            "min_reversion_window": 0.56,
            "min_elasticity": 0.25,
            "min_exhaustion": 0.32,
            "min_reversal_pressure": 0.48,
            "min_elite_signal": 0.60,
            "min_entry_readiness": 0.58,
        },
        "expected_behavior": {
            "trade_frequency": "controlled",
            "selectivity": "moderate_high",
            "intent": "default operating paper mode",
        },
    },
    "aggressive": {
        "optimizer": {
            "min_confluence": 0.70,
            "min_pressure": 0.16,
            "min_accel": 0.06,
            "min_abs_spread_bps": 10.0,
            "min_reversion_window": 0.48,
            "min_elasticity": 0.20,
            "min_exhaustion": 0.28,
            "min_reversal_pressure": 0.34,
            "min_elite_signal": 0.48,
            "min_entry_readiness": 0.46,
        },
        "classifier": {
            "qualified": {
                "min_trade_score": 0.44,
                "min_reversion_window": 0.38,
                "min_elasticity": 0.18,
                "min_reversal_pressure": 0.32,
            },
            "elite": {
                "min_confluence": 0.72,
                "min_pressure": 0.18,
                "min_vwap_dev_abs": 0.010,
                "min_trade_score": 0.50,
                "min_reversion_window": 0.48,
                "min_elasticity": 0.20,
                "min_exhaustion": 0.28,
                "min_reversal_pressure": 0.40,
                "min_elite_signal": 0.54,
                "min_entry_readiness": 0.52,
            },
            "elite_edge_override": {
                "min_trade_score": 0.48,
                "min_reversion_window": 0.46,
                "min_reversal_pressure": 0.38,
            },
        },
        "execution": {
            "min_trade_score": 0.50,
            "min_confluence": 0.70,
            "min_pressure": 0.16,
            "min_accel_or_pressure_boost": 0.06,
            "min_vwap_dev_abs": 0.010,
            "min_reversion_window": 0.48,
            "min_elasticity": 0.20,
            "min_exhaustion": 0.28,
            "min_reversal_pressure": 0.40,
            "min_elite_signal": 0.54,
            "min_entry_readiness": 0.52,
        },
        "expected_behavior": {
            "trade_frequency": "medium",
            "selectivity": "moderate",
            "intent": "broader participation mode",
        },
    },
    "opportunistic/expansion": {
        "optimizer": {
            "min_confluence": 0.62,
            "min_pressure": 0.12,
            "min_accel": 0.04,
            "min_abs_spread_bps": 8.0,
            "min_reversion_window": 0.42,
            "min_elasticity": 0.16,
            "min_exhaustion": 0.24,
            "min_reversal_pressure": 0.28,
            "min_elite_signal": 0.44,
            "min_entry_readiness": 0.40,
        },
        "classifier": {
            "qualified": {
                "min_trade_score": 0.42,
                "min_reversion_window": 0.36,
                "min_elasticity": 0.16,
                "min_reversal_pressure": 0.28,
            },
            "elite": {
                "min_confluence": 0.64,
                "min_pressure": 0.14,
                "min_vwap_dev_abs": 0.008,
                "min_trade_score": 0.44,
                "min_reversion_window": 0.42,
                "min_elasticity": 0.16,
                "min_exhaustion": 0.24,
                "min_reversal_pressure": 0.34,
                "min_elite_signal": 0.48,
                "min_entry_readiness": 0.46,
            },
            "elite_edge_override": {
                "min_trade_score": 0.44,
                "min_reversion_window": 0.40,
                "min_reversal_pressure": 0.32,
            },
        },
        "execution": {
            "min_trade_score": 0.44,
            "min_confluence": 0.62,
            "min_pressure": 0.12,
            "min_accel_or_pressure_boost": 0.04,
            "min_vwap_dev_abs": 0.008,
            "min_reversion_window": 0.42,
            "min_elasticity": 0.16,
            "min_exhaustion": 0.24,
            "min_reversal_pressure": 0.34,
            "min_elite_signal": 0.48,
            "min_entry_readiness": 0.46,
        },
        "expected_behavior": {
            "trade_frequency": "higher",
            "selectivity": "broadest",
            "intent": "expansionary opportunity capture mode",
        },
    },
}


def get_mode_policy(engine_mode: str) -> Dict[str, Any]:
    mode = str(engine_mode or "").strip().lower()
    return MODE_POLICIES.get(mode, MODE_POLICIES["balanced"])


def get_optimizer_policy(engine_mode: str) -> Dict[str, float]:
    return dict(get_mode_policy(engine_mode)["optimizer"])


def get_classifier_policy(engine_mode: str) -> Dict[str, Dict[str, float]]:
    return dict(get_mode_policy(engine_mode)["classifier"])


def get_execution_policy(engine_mode: str) -> Dict[str, float]:
    return dict(get_mode_policy(engine_mode)["execution"])


def get_expected_behavior(engine_mode: str) -> Dict[str, str]:
    return dict(get_mode_policy(engine_mode)["expected_behavior"])