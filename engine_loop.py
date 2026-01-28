"""
engine_loop.py — REA Capital Trading Engine (Prompt-Only by default)
---------------------------------------------------------
Module 1: Data readiness (min bars)
Module 2: Regime gate (conservative by default)
Module 3: VWAP mean-reversion prompt generation (prompt-only)

Hard constraints (DEFAULT MODE):
- NO trade execution (unless explicitly enabled)
- NO auto-risk escalation
- Prompt / diagnostics only

Enhancements:
- Expose prompt fields in a consistent way (prompt_payload, prompt_text, prompt)
- Attach normalized_prompt using utils.prompt_export.normalize_prompt
- Optionally write last prompt JSON to disk (OFF by default)

Module 8.4.x wiring:
- Execution Router + PaperBrokerAdapter are initialized safely
- Execution remains OFF by default (cfg.enable_paper_execution=False)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Deque
from collections import deque
import csv
import os
from datetime import datetime

# Module 8.4.x: execution routing (safe, OFF by default)
from engine.execution.order_router import OrderRouter, ExecutionRoutingConfig
from engine.domain.fees import FeeSchedule

# Optional imports (project may include these)
try:
    from regime.gate import RegimeGate  # type: ignore
except Exception:
    RegimeGate = None  # graceful fallback

try:
    from signals.vwap_mean_reversion import build_vwap_prompt_default_eps  # type: ignore
except Exception:
    build_vwap_prompt_default_eps = None  # graceful fallback

# Prompt export (added)
try:
    from utils.prompt_export import normalize_prompt, write_prompt_to_file  # type: ignore
except Exception:
    normalize_prompt = None
    write_prompt_to_file = None

# Optional OrderIntent import (only used if execution is enabled)
try:
    from engine.domain.orders import OrderIntent  # type: ignore
except Exception:
    OrderIntent = None


# =============================
# DATA MODEL
# =============================
@dataclass
class EngineConfig:
    symbol: str = "SPY"
    vwap_window_bars: int = 5
    min_bars_before_signals: int = 5
    vwap_eps_pct: float = 0.0001
    print_prompts: bool = True

    # Export control (OFF by default)
    export_last_prompt_json: bool = False
    export_last_prompt_path: str = "last_prompt.json"

    # Execution control (OFF by default: prompt-only)
    enable_paper_execution: bool = False

    # Fee schedule defaults (manager-controlled later)
    commission_rate_pct: float = 0.10  # example 0.10%
    tax_rate_pct: float = 0.00


@dataclass
class Bar:
    ts_utc: Any
    symbol: str
    close: float
    volume: float = 1.0


# =============================
# HELPERS
# =============================
def parse_ts_utc(v: Optional[str]):
    """
    Minimal timestamp parser.
    Accepts ISO strings; if parsing fails, returns raw.
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return s


def compute_vwap(window: Deque[Bar]) -> Optional[float]:
    pv = 0.0
    vol = 0.0
    for b in window:
        v = float(b.volume) if b.volume else 0.0
        pv += float(b.close) * v
        vol += v
    return pv / vol if vol > 0 else None


# =============================
# ENGINE LOOP
# =============================
class EngineLoop:
    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.window: Deque[Bar] = deque(maxlen=cfg.vwap_window_bars)
        self.prompts: List[Dict[str, Any]] = []

        # Regime gate (optional)
        self.regime = None
        if RegimeGate:
            try:
                self.regime = RegimeGate()
            except Exception:
                self.regime = None

        # Module 8.4.x: router initialized but execution OFF by default
        self.order_router: Optional[OrderRouter] = None
        self._init_execution_router()

    def _init_execution_router(self) -> None:
        """
        Initialize the router safely. This does not execute anything.
        Execution happens only if cfg.enable_paper_execution == True.
        """
        # Fee schedule: later replaced by RBAC / manager-approved config store
        fee_schedule = FeeSchedule(
            fee_schedule_id="DEFAULT",
            version="v1",
            effective_from=datetime.utcnow(),  # placeholder; can be replaced by real effective date
            effective_to=None,
            commission_rate_pct=float(self.cfg.commission_rate_pct),
            tax_rate_pct=float(self.cfg.tax_rate_pct),
            scope_company_id=None,
            scope_branch_id=None,
            scope_department_id=None,
            approved_by_user_id=None,
            approved_at=None,
            notes="Engine default fee schedule (replace with manager-approved schedule).",
        )

        routing_cfg = ExecutionRoutingConfig(
            execution_mode="PAPER",
            paper_seed=42,
            base_latency_ms=25,
            slippage_bps=1.0,
            broker_name="PAPER",
        )

        self.order_router = OrderRouter(fee_schedule=fee_schedule, cfg=routing_cfg)

    def regime_allows(self) -> bool:
        """
        Regime gating. Conservative by default.
        If RegimeGate exists and returns a boolean/allow field, use it.
        Otherwise default allow = True.
        """
        if not self.regime:
            return True

        for meth in ("allow", "allows", "evaluate", "check", "on_bar"):
            if hasattr(self.regime, meth):
                try:
                    r = getattr(self.regime, meth)()
                    if isinstance(r, bool):
                        return r
                    if isinstance(r, dict) and "allow" in r:
                        return bool(r["allow"])
                except Exception:
                    return False

        return True

    def on_bar(self, bar: Bar) -> Optional[Dict[str, Any]]:
        if bar.symbol != self.cfg.symbol:
            return None

        self.window.append(bar)

        # --- Diagnostics helper (read-only) ---
        def _diag(*, reason: str, regime_state: str = "UNKNOWN") -> None:
            print("=" * 60)
            try:
                ts_str = bar.ts_utc.isoformat()
            except Exception:
                ts_str = str(bar.ts_utc)

            print(f"Timestamp (UTC): {ts_str}")
            print("\n[DATA READINESS]")
            print(f"5m Bars: {len(self.window)} / {self.cfg.min_bars_before_signals}")
            print("Status: READY" if len(self.window) >= self.cfg.min_bars_before_signals else "Status: NOT READY")

            print("\n[SESSION]")
            print("Session Name: N/A")
            print("Session Open: True")

            print("\n[REGIME GATE]")
            print(f"Regime State: {regime_state}")

            print("\n[VWAP]")
            print("VWAP Deviation: N/A")
            print(f"VWAP Threshold: {self.cfg.vwap_eps_pct:.4f}")

            print("\n[DECISION]")
            print("Outcome: PROMPT-ONLY" if not self.cfg.enable_paper_execution else "Outcome: PAPER-EXECUTION ENABLED")
            print(f"Reason: {reason}")
            print("=" * 60)

        # Readiness
        if len(self.window) < self.cfg.min_bars_before_signals:
            _diag(reason="Insufficient bars for signals", regime_state="BLOCK")
            return None

        # Regime gate
        if not self.regime_allows():
            _diag(reason="Regime gate blocked signals", regime_state="BLOCK")
            return None

        # VWAP compute
        vwap = compute_vwap(self.window)
        if vwap is None or build_vwap_prompt_default_eps is None:
            _diag(reason="VWAP unavailable or prompt builder missing", regime_state="ALLOW")
            return None

        _diag(reason="Conditions met; prompt evaluation proceeds", regime_state="ALLOW")

        prompt = build_vwap_prompt_default_eps(
            price=bar.close,
            vwap=vwap,
            pct=self.cfg.vwap_eps_pct,
            extra={
                "symbol": bar.symbol,
                "as_of_utc": bar.ts_utc.isoformat() if hasattr(bar.ts_utc, "isoformat") else str(bar.ts_utc),
                "window": self.cfg.vwap_window_bars,
            },
        )

        if isinstance(prompt, dict):
            # Store the raw prompt
            self.prompts.append(prompt)

            # Expose prompt fields for wrappers/loggers
            payload = prompt.get("payload", {})
            prompt.setdefault("prompt_payload", payload)
            prompt.setdefault("prompt_text", f"{prompt.get('signal', 'SIGNAL')}: {payload}")
            prompt.setdefault("prompt", prompt["prompt_text"])

            # Attach normalized prompt for stable downstream use
            if callable(normalize_prompt):
                try:
                    prompt["normalized_prompt"] = normalize_prompt(prompt)
                except Exception:
                    prompt["normalized_prompt"] = {}

            # Optional: write last prompt to disk (OFF by default)
            if self.cfg.export_last_prompt_json and callable(write_prompt_to_file):
                try:
                    write_prompt_to_file(prompt, self.cfg.export_last_prompt_path)
                except Exception:
                    pass

            if self.cfg.print_prompts:
                print(prompt)

            # OPTIONAL: paper execution path (OFF by default)
            if self.cfg.enable_paper_execution:
                self._paper_execute_from_prompt(prompt, bar)

        return prompt

    def _paper_execute_from_prompt(self, prompt: Dict[str, Any], bar: Bar) -> None:
        """
        Converts a prompt into a paper-execution OrderIntent (if possible) and routes it.
        This remains OFF unless cfg.enable_paper_execution=True.

        NOTE: This function is intentionally conservative:
        - If OrderIntent is not available or prompt missing fields, it does nothing.
        - It does NOT auto-escalate risk.
        """
        if not self.order_router or OrderIntent is None:
            return

        # Very conservative mapping: only execute if prompt contains explicit direction and qty
        signal = str(prompt.get("signal", "")).upper()
        payload = prompt.get("payload", {}) or {}

        side = payload.get("side") or payload.get("action") or ""
        qty = payload.get("quantity") or payload.get("qty")

        if not side or qty is None:
            return

        side_u = str(side).upper()
        if side_u not in ("BUY", "SELL"):
            return

        try:
            qty_f = float(qty)
        except Exception:
            return

        if qty_f <= 0:
            return

        # Create an OrderIntent (LIMIT at bar.close to keep deterministic)
        order_intent = OrderIntent(
            order_id=f"paper-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            user_id=str(payload.get("user_id") or "system"),
            company_id=payload.get("company_id"),
            branch_id=payload.get("branch_id"),
            department_id=payload.get("department_id"),
            symbol=self.cfg.symbol,
            side=side_u,
            quantity=qty_f,
            order_type="LIMIT",
            limit_price=float(bar.close),
            currency=str(payload.get("currency") or "USD"),
            order_date=datetime.utcnow(),
            requested_exec_date=None,
            session_id=str(payload.get("session_id") or "N/A"),
            regime_tag=str(payload.get("regime_tag") or "ALLOW"),
            counterparty_id=payload.get("counterparty_id"),
            counterparty_name=payload.get("counterparty_name"),
            counterparty_account=payload.get("counterparty_account"),
            meta={"source_signal": signal},
        )

        reports = self.order_router.submit(order_intent)

        # Print minimal confirmation (ticket printing happens via reports module separately)
        print(f"[PAPER EXEC] Executed {len(reports)} order(s). Last execution_id={reports[-1].execution_id if reports else 'N/A'}")


# =============================
# CSV LOADER (YOUR EXISTING FORMAT)
# =============================
def load_bars_from_csv(path: str, symbol: str) -> List[Bar]:
    bars: List[Bar] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts = parse_ts_utc(row.get("ts_utc") or row.get("timestamp"))
            close = row.get("c") or row.get("close")
            volume = row.get("v") or row.get("volume")

            try:
                bars.append(
                    Bar(
                        ts_utc=ts,
                        symbol=symbol,
                        close=float(close),
                        volume=float(volume) if volume else 1.0,
                    )
                )
            except Exception:
                continue

    return bars


def main():
    cfg = EngineConfig(symbol="SPY", print_prompts=True, enable_paper_execution=False)
    engine = EngineLoop(cfg)

    csv_path = "sample_spy_1m.csv"
    if not os.path.exists(csv_path):
        print("No sample_spy_1m.csv found.")
        print("Engine ready. Use EngineLoop(cfg).on_bar(bar)")
        return

    bars = load_bars_from_csv(csv_path, cfg.symbol)

    for b in bars:
        engine.on_bar(b)

    print(f"\nDone. Prompts generated: {len(engine.prompts)}")


if __name__ == "__main__":
    main()