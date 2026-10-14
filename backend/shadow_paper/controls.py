"""Safety preflight and governance-control loading for the shadow paper runner.

The runner refuses to operate (fail closed) unless:
  * no live-execution flag is enabled in the environment or the repo .env files;
  * test mode is off (it disables the network feed);
  * no environment override of an engine threshold is present;
  * every required control is importable and still carries its V1 values;
  * no broker module has been imported into the process.

R14F is loaded verbatim from its single source of truth,
scripts/css_live_dashboard.py, by extracting the two R14F functions with ``ast``.
Importing that script would start the interactive dashboard, so it is never imported.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_SCRIPT = REPO_ROOT / "scripts" / "css_live_dashboard.py"
R14F_FUNCTIONS = ("_legacy_css_profitability_threshold", "_legacy_css_profitability_allows")

# V1 values that must be unchanged for the shadow run (frozen at 5d264fb).
EXPECTED_ANTI_BLEED = {
    "minimum_required_net_edge_bps": 25.0,
    "minimum_profitable_trade_size": 50.0,
    "cooldown_minutes": 10,
    "max_trades_per_symbol_per_cycle": 1,
    "dev_force_allow": False,
}
EXPECTED_ENGINE_CONSTANTS = {
    "MA_WINDOW": 20,
    "DEFAULT_STOP_DISTANCE_PCT": 0.01,
    "DEFAULT_REGIME_PERSISTENCE": 0.95,
    "BASELINE_NOTIONAL_PCT": 0.08,
    "ANTI_BLEED_FEE_BPS": 1.0,
    "ANTI_BLEED_SPREAD_BPS": 1.0,
    "ANTI_BLEED_SLIPPAGE_BPS": 1.0,
    "CORR_WINDOW": 50,
}
EXPECTED_MIN_SIGNAL_STRENGTH = 0.61
EXPECTED_R7 = {
    "MAX_POSITIONS_BY_ASSET": {"crypto": 3, "fx": 3, "futures": 2, "options": 2},
    "SAFE_PROBABILITY_THRESHOLD": 0.65,
    "SESSION_TIMEOUT_SECONDS": 3600,
}
EXPECTED_R14F_THRESHOLDS = {
    "SAFE": 17.5,
    "CONSERVATIVE": 16.5,
    "BALANCED": 15.8,
    "AGGRESSIVE": 15.0,
    "EXPANSION": 14.2,
}
EXPECTED_REGIME_MIN_BARS = 40

TRUTHY = {"1", "true", "yes", "on", "enabled", "armed", "live"}
FALSY = {"0", "false", "no", "off", "disabled"}

# Any of these set to a truthy value means live execution is (being) enabled.
LIVE_ENABLE_FLAGS = (
    "COINBASE_ENABLE_LIVE_ORDERS",
    "CSS_EXECUTION_ALLOWED",
    "CSS_LIVE_TRADING_ENABLED",
    "CSS_BROKER_EXECUTION_ARMED",
    "CSS_LIVE_ARM",
)
# These must not be explicitly turned off.
SAFETY_FLAGS_MUST_NOT_BE_FALSE = ("CSS_LIVE_TRADING_BLOCKED", "CSS_ADVISORY_ONLY")
# Environment overrides read by engine.engine_loop at import time.
THRESHOLD_OVERRIDE_VARS = (
    "CSS_MIN_SIGNAL_STRENGTH",
    "CSS_BASELINE_NOTIONAL_PCT",
    "CSS_ANTI_BLEED_FEE_BPS",
    "CSS_ANTI_BLEED_SPREAD_BPS",
    "CSS_ANTI_BLEED_SLIPPAGE_BPS",
    "CSS_STOP_DISTANCE_PCT",
    "CSS_GATE_REGIME_PERSISTENCE",
    "CSS_MAX_R_PER_BAR",
    "CSS_CORR_WINDOW",
)
# Module prefixes that can reach a broker. None may be loaded by the runner.
FORBIDDEN_MODULE_PREFIXES = (
    "engine.brokers",
    "engine.execution_router",
    "backend.brokers",
    "backend.broker",
    "backend.app.brokers",
    "backend.execution",
    "broker_oanda",
    "execution_router",
    "coinbase",
    "oandapyV20",
)


class SafetyPreflightError(RuntimeError):
    def __init__(self, failures: list[str]) -> None:
        super().__init__("; ".join(failures))
        self.failures = failures


@dataclass
class PreflightReport:
    passed: bool
    checks: dict[str, str] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": dict(self.checks), "failures": list(self.failures)}


@dataclass(frozen=True)
class R14FEvaluator:
    engine_mode: str
    source_sha256: str
    _allows: Callable[..., tuple[bool, float, float]]
    _threshold: Callable[[str], float]

    def threshold_for_mode(self, mode: str) -> float:
        return float(self._threshold(mode))

    def evaluate(self, *, symbol: str, asset_class: str, sig: float, prob: float) -> dict[str, Any]:
        ok, composite, threshold = self._allows(symbol, asset_class, sig, prob)
        return {
            "passed": bool(ok),
            "composite": round(float(composite), 6),
            "threshold": round(float(threshold), 6),
            "engine_mode": self.engine_mode,
        }


def load_r14f(engine_mode: str, script_path: Path = DASHBOARD_SCRIPT) -> R14FEvaluator:
    source = Path(script_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))
    found = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in R14F_FUNCTIONS
    }
    missing = [name for name in R14F_FUNCTIONS if name not in found]
    if missing:
        raise SafetyPreflightError([f"R14F function(s) not found in {script_path.name}: {missing}"])

    module = ast.Module(body=[found[name] for name in R14F_FUNCTIONS], type_ignores=[])
    extracted = "\n\n".join(ast.get_source_segment(source, found[name]) or "" for name in R14F_FUNCTIONS)
    namespace: dict[str, Any] = {
        "__builtins__": builtins,
        "ENGINE_MODE": str(engine_mode),
        "print": lambda *args, **kwargs: None,  # R14F prints PASS/BLOCK; the journal records it
    }
    exec(compile(module, str(script_path), "exec"), namespace)  # noqa: S102 - trusted repo source
    return R14FEvaluator(
        engine_mode=str(engine_mode),
        source_sha256=hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
        _allows=namespace["_legacy_css_profitability_allows"],
        _threshold=namespace["_legacy_css_profitability_threshold"],
    )


def _read_env_files(repo_root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    try:
        from dotenv import dotenv_values
    except Exception:  # python-dotenv is in requirements; absence is a failure upstream
        return result
    for name in (".env", ".env.practice"):
        path = repo_root / name
        if path.exists():
            values = dotenv_values(path)
            result[name] = {k: str(v) for k, v in values.items() if v is not None}
    return result


def _flag_failures(source: str, values: Mapping[str, str]) -> list[str]:
    failures: list[str] = []
    for key in LIVE_ENABLE_FLAGS:
        if str(values.get(key, "")).strip().lower() in TRUTHY:
            failures.append(f"{source}: live-execution flag {key} is enabled")
    if str(values.get("OANDA_ENV", "")).strip().lower() in {"live", "trade", "production"}:
        failures.append(f"{source}: OANDA_ENV is live")
    for key in SAFETY_FLAGS_MUST_NOT_BE_FALSE:
        if str(values.get(key, "")).strip().lower() in FALSY:
            failures.append(f"{source}: safety flag {key} is disabled")
    return failures


def forbidden_modules_loaded() -> list[str]:
    return sorted(
        name for name in list(sys.modules)
        if any(name == p or name.startswith(p + ".") for p in FORBIDDEN_MODULE_PREFIXES)
    )


def run_preflight(
    *,
    environ: Mapping[str, str] | None = None,
    repo_root: Path = REPO_ROOT,
    live_network: bool = True,
    execution_gate: Any = None,
    r14f: R14FEvaluator | None = None,
) -> PreflightReport:
    """Check every precondition. Never raises; returns a report with failures."""
    env = dict(os.environ if environ is None else environ)
    report = PreflightReport(passed=False)
    failures = report.failures

    def check(name: str, fn: Callable[[], list[str]]) -> None:
        try:
            problems = fn()
        except Exception as exc:  # an unavailable control is a failure, never a pass
            problems = [f"{name}: control unavailable ({type(exc).__name__}: {exc})"]
        report.checks[name] = "PASS" if not problems else "FAIL"
        failures.extend(problems)

    def live_flags() -> list[str]:
        problems = _flag_failures("environment", env)
        for fname, values in _read_env_files(repo_root).items():
            problems.extend(_flag_failures(fname, values))
        return problems

    def test_mode() -> list[str]:
        if live_network and env.get("CSS_TEST_MODE") == "1":
            return ["CSS_TEST_MODE=1 disables real market data; unset it for a live-data run"]
        return []

    def threshold_overrides() -> list[str]:
        return [f"threshold override {k} is set" for k in THRESHOLD_OVERRIDE_VARS if env.get(k, "") != ""]

    def engine_constants() -> list[str]:
        import engine.engine_loop as engine_loop

        problems = []
        for key, expected in EXPECTED_ENGINE_CONSTANTS.items():
            actual = getattr(engine_loop, key)
            if float(actual) != float(expected):
                problems.append(f"engine_loop.{key}={actual} (expected {expected})")
        return problems

    def anti_bleed() -> list[str]:
        if execution_gate is None:
            return ["ExecutionGate not provided"]
        guard = getattr(execution_gate, "anti_bleed_guard", None)
        if guard is None:
            return ["ExecutionGate has no AntiBleedGuard"]
        if not callable(getattr(execution_gate, "evaluate_trade", None)):
            return ["ExecutionGate.evaluate_trade unavailable"]
        problems = []
        for key, expected in EXPECTED_ANTI_BLEED.items():
            actual = getattr(guard, key)
            if actual != expected:
                problems.append(f"AntiBleedGuard.{key}={actual!r} (expected {expected!r})")
        return problems

    def r7() -> list[str]:
        from backend.governance import css_unified_trade_gate as gate

        problems = []
        if dict(gate.MAX_POSITIONS_BY_ASSET) != EXPECTED_R7["MAX_POSITIONS_BY_ASSET"]:
            problems.append(f"R7 MAX_POSITIONS_BY_ASSET={gate.MAX_POSITIONS_BY_ASSET}")
        if gate.ENGINE_MODE_PROBABILITY_THRESHOLD.get("SAFE") != EXPECTED_R7["SAFE_PROBABILITY_THRESHOLD"]:
            problems.append("R7 SAFE probability threshold changed")
        if gate.SESSION_TIMEOUT_SECONDS != EXPECTED_R7["SESSION_TIMEOUT_SECONDS"]:
            problems.append("R7 session timeout changed")
        if not callable(getattr(gate.CSSUnifiedTradeGate(), "approve_trade", None)):
            problems.append("R7 approve_trade unavailable")
        return problems

    def r14f_check() -> list[str]:
        evaluator = r14f
        if evaluator is None:
            return ["R14F evaluator not loaded"]
        problems = []
        for mode, expected in EXPECTED_R14F_THRESHOLDS.items():
            if evaluator.threshold_for_mode(mode) != expected:
                problems.append(f"R14F threshold for {mode} changed")
        return problems

    def regime_gate() -> list[str]:
        from engine.gates_registry import get_configured_gates
        from engine.regime.regime_gate import RegimeGate

        if not callable(get_configured_gates().get("regime_gate")):
            return ["regime gate unavailable"]
        if RegimeGate.MIN_BARS_5M != EXPECTED_REGIME_MIN_BARS:
            return [f"RegimeGate.MIN_BARS_5M={RegimeGate.MIN_BARS_5M}"]
        return []

    def broker_modules() -> list[str]:
        loaded = forbidden_modules_loaded()
        return [f"broker-capable module loaded: {name}" for name in loaded]

    check("live_execution_flags", live_flags)
    check("test_mode", test_mode)
    check("threshold_overrides", threshold_overrides)
    check("engine_constants", engine_constants)
    check("anti_bleed_guard", anti_bleed)
    check("r7_unified_trade_gate", r7)
    check("r14f_profitability_gate", r14f_check)
    check("regime_gate", regime_gate)
    check("no_broker_modules", broker_modules)

    report.passed = not failures
    return report
