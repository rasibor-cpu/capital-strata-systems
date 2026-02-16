"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Phase 1/2 reality:
- The surrounding codebase has evolving entrypoints (RiskGovernor / headless runner).
- This file is written to be tolerant to:
    * probe-mode calls (missing trade fields)
    * minor API drift (TradeRequest missing or allow_trade signatures changing)

Stacked gating (canonical order):
1) Volatility (fast mechanical market block)
2) RegimeGate (macro/structure block)
3) RiskGovernor (policy + capital guardrails)

Persistence:
- Uses engine.risk.risk_state_store load_state/save_state
- If RiskGovernor exposes .state dict, we hydrate it; otherwise we maintain a local state dict.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Dict, Optional

from engine.risk.risk_state_store import load_state, save_state


class ExecutionGate:
    """
    Thin orchestration layer around RiskGovernor + stacked pre-gates.
    """

    def __init__(self) -> None:
        # ---- RiskGovernor (lazy import to avoid circular imports)
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

        # ---- Load persisted state
        persisted = load_state()
        if not isinstance(persisted, dict):
            persisted = {}

        # ---- Bind / create state
        gov_state = getattr(self.risk_governor, "state", None)

        if isinstance(gov_state, dict):
            # Hydrate governor state
            if persisted:
                gov_state.update(persisted)
            self.state: Dict[str, Any] = gov_state
        else:
            # Governor doesn't expose .state; maintain our own state dict
            self.state = dict(persisted) if persisted else {}

        # Ensure common keys exist (safe defaults)
        self.state.setdefault("open_positions", 0)
        self.state.setdefault("daily_pnl", 0.0)
        self.state.setdefault("trades_today", 0)
        self.state.setdefault("consecutive_losses", 0)
        self.state.setdefault("cooldown_active", False)
        self.state.setdefault("equity", None)
        self.state.setdefault("equity_peak", None)
        self.state.setdefault("day_key", None)
        self.state.setdefault("regime", None)
        self.state.setdefault("last_extras", None)

        self._persist()

    # -------------------------
    # persistence / snapshots
    # -------------------------

    def _persist(self) -> None:
        save_state(self.state)

    def snapshot(self, instrument: str) -> Dict[str, Any]:
        return {
            "instrument": instrument,
            "day_key": self.state.get("day_key"),
            "equity": self.state.get("equity"),
            "equity_peak": self.state.get("equity_peak"),
            "trades_today": self.state.get("trades_today"),
            "daily_pnl": self.state.get("daily_pnl"),
            "consecutive_losses": self.state.get("consecutive_losses"),
            "cooldown_active": self.state.get("cooldown_active"),
            "regime": self.state.get("regime"),
            "open_positions": self.state.get("open_positions"),
            "last_extras": self.state.get("last_extras"),
        }

    def sync_context(
        self,
        *,
        day_key: Optional[str] = None,
        equity: Optional[float] = None,
        equity_peak: Optional[float] = None,
        cooldown_active: Optional[bool] = None,
        regime: Optional[str] = None,
        open_positions: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Optional helper to sync state from API/headless request context.
        Safe: only updates when a value is provided.
        """
        if day_key is not None:
            try:
                self.risk_governor.set_day(str(day_key))  # type: ignore[attr-defined]
            except Exception:
                self.state["day_key"] = str(day_key)

        if equity is not None:
            try:
                self.risk_governor.update_equity(float(equity))  # type: ignore[attr-defined]
            except Exception:
                self.state["equity"] = float(equity)

        if equity_peak is not None:
            self.state["equity_peak"] = float(equity_peak)

        if cooldown_active is not None:
            try:
                self.risk_governor.set_cooldown(bool(cooldown_active))  # type: ignore[attr-defined]
            except Exception:
                self.state["cooldown_active"] = bool(cooldown_active)

        if regime is not None:
            try:
                self.risk_governor.set_regime(str(regime))  # type: ignore[attr-defined]
            except Exception:
                self.state["regime"] = str(regime)

        if open_positions is not None:
            self.state["open_positions"] = int(open_positions)

        if extra is not None:
            self.state["last_extras"] = dict(extra)

        self._persist()

    # -------------------------
    # helpers: normalization
    # -------------------------

    def _as_dict(self, x: Any) -> Dict[str, Any]:
        if x is None:
            return {}
        if isinstance(x, dict):
            return x
        if hasattr(x, "as_dict") and callable(getattr(x, "as_dict")):
            try:
                return x.as_dict()  # type: ignore[misc]
            except Exception:
                return {}
        if hasattr(x, "__dict__"):
            try:
                return dict(x.__dict__)
            except Exception:
                return {}
        return {}

    def _decision_block(self, *, reason: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "ok": False,
            "reason": reason,
            "extra": extra or {},
        }

    def _decision_allow(self, *, reason: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "ok": True,
            "reason": reason,
            "extra": extra or {},
        }

    # -------------------------
    # stacked pre-gates
    # -------------------------

    def _build_vol_snapshot(self, *, extra: Dict[str, Any]) -> Any:
        """
        Builds a VolatilitySnapshot instance using dataclass field reflection.
        Any missing numeric fields default to 0.0; booleans to False; others to None.
        """
        from engine.volatility.volatility_gate import VolatilitySnapshot  # type: ignore

        # If it's not a dataclass for any reason, just pass through a dict (best effort)
        if not is_dataclass(VolatilitySnapshot):
            return dict(extra)

        kwargs: Dict[str, Any] = {}
        for f in fields(VolatilitySnapshot):
            name = f.name
            if name in extra:
                kwargs[name] = extra[name]
                continue

            # default heuristics
            t = str(f.type)
            if "bool" in t:
                kwargs[name] = False
            elif "int" in t:
                kwargs[name] = 0
            elif "float" in t:
                kwargs[name] = 0.0
            else:
                kwargs[name] = None

        return VolatilitySnapshot(**kwargs)  # type: ignore[arg-type]

    def _run_volatility_gate(self, *, extra: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a normalized dict:
            { ok: bool, reason: str, raw: {...} }
        """
        try:
            from engine.volatility.volatility_gate import evaluate_volatility, VolatilityPolicy  # type: ignore
        except Exception as e:
            return {
                "ok": False,
                "reason": f"volatility_import_failed: {e}",
                "raw": {},
            }

        try:
            snap = self._build_vol_snapshot(extra=extra)
            policy = VolatilityPolicy()  # uses its internal defaults
            res = evaluate_volatility(snapshot=snap, policy=policy, hard_block=True, reason_prefix="VOLATILITY_GATE")
            raw = self._as_dict(res)

            # normalize ok
            ok = bool(raw.get("ok")) if "ok" in raw else bool(raw.get("allowed", True))
            reason = raw.get("reason") or raw.get("message") or ("volatility_ok" if ok else "volatility_block")
            return {"ok": ok, "reason": str(reason), "raw": raw}
        except Exception as e:
            return {
                "ok": False,
                "reason": f"volatility_exception: {e}",
                "raw": {},
            }

    def _run_regime_gate(self, *, bars_5m: int, vol_norm_0_1: Optional[float], spread_bps: Optional[float], high_risk_news: Optional[bool], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns normalized dict:
            { ok: bool, reason: str, raw: {...} }
        """
        try:
            from engine.regime.regime_gate import RegimeGate  # type: ignore
        except Exception as e:
            return {"ok": False, "reason": f"regime_import_failed: {e}", "raw": {}}

        try:
            gate = RegimeGate()
            decision = gate.evaluate(
                bars_5m=int(bars_5m),
                vol_norm_0_1=vol_norm_0_1,
                spread_bps=spread_bps,
                high_risk_news=high_risk_news,
                extra=extra,
            )
            raw = self._as_dict(decision)

            ok = bool(raw.get("ok")) if "ok" in raw else bool(raw.get("allowed", True))
            reason = raw.get("reason") or raw.get("message") or ("regime_ok" if ok else "regime_block")
            return {"ok": ok, "reason": str(reason), "raw": raw}
        except Exception as e:
            return {"ok": False, "reason": f"regime_exception: {e}", "raw": {}}

    # -------------------------
    # public API
    # -------------------------

    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: Optional[str] = None,
        notional: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
        policy: str = "core",
        # extra “headless/runner” context (all optional)
        equity_risk: Optional[float] = None,
        bars_5m: Optional[int] = None,
        vol_norm_0_1: Optional[float] = None,
        spread_bps: Optional[float] = None,
        high_risk_news: Optional[bool] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate whether a proposed trade is allowed.
        - If trade fields are missing: return REJECTED (probe-friendly) with missing fields list.
        - If fields provided: run Volatility → Regime → RiskGovernor.
        """
        extra = dict(extra or {})
        if equity_risk is not None:
            extra["equity_risk"] = float(equity_risk)

        self.state["last_extras"] = dict(extra)
        self._persist()

        # ---- Probe/missing-field tolerance
        missing = []
        if side is None:
            missing.append("side")
        if notional is None:
            missing.append("notional")
        if stop_distance_pct is None:
            missing.append("stop_distance_pct")

        if missing:
            out = {
                "status": "REJECTED",
                "decision": {
                    "ok": False,
                    "reason": "missing_required_fields",
                    "missing": missing,
                    "note": "Caller must provide side/notional/stop_distance_pct for full evaluation.",
                },
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # ---- 1) Volatility
        vol_out = self._run_volatility_gate(extra=extra)
        if not vol_out.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": self._decision_block(reason=vol_out.get("reason", "volatility_block"), extra={"volatility": vol_out.get("raw", {})}),
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # ---- 2) RegimeGate
        b5 = int(bars_5m) if bars_5m is not None else int(extra.get("bars_5m") or 0)

        # allow vol_norm to be supplied via extra or derived from volatility raw if present
        if vol_norm_0_1 is None:
            vraw = vol_out.get("raw", {}) or {}
            vol_norm_0_1 = vraw.get("vol_norm_0_1") if isinstance(vraw, dict) else None
            if vol_norm_0_1 is None:
                vol_norm_0_1 = extra.get("vol_norm_0_1")

        rg_out = self._run_regime_gate(
            bars_5m=b5,
            vol_norm_0_1=(float(vol_norm_0_1) if vol_norm_0_1 is not None else None),
            spread_bps=(float(spread_bps) if spread_bps is not None else None),
            high_risk_news=(bool(high_risk_news) if high_risk_news is not None else None),
            extra=extra,
        )

        if not rg_out.get("ok", False):
            out = {
                "status": "REJECTED",
                "decision": self._decision_block(reason=rg_out.get("reason", "regime_block"), extra={"regime": rg_out.get("raw", {})}),
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # ---- 3) RiskGovernor (final arbiter)
        # Try TradeRequest; tolerate missing export by falling back to dict-based request.
        governor_dec: Dict[str, Any] = {}
        try:
            from engine.risk.risk_governor import TradeRequest  # type: ignore

            req = TradeRequest(
                instrument=str(instrument),
                side=str(side),
                notional=float(notional),
                stop_distance_pct=float(stop_distance_pct),
                policy=str(policy),
            )
            dec_obj = self.risk_governor.allow_trade(req)  # type: ignore[attr-defined]
            governor_dec = self._as_dict(dec_obj)
        except Exception:
            # fallback: try passing a dict, and normalize whatever comes back
            try:
                req2 = {
                    "instrument": str(instrument),
                    "side": str(side),
                    "notional": float(notional),
                    "stop_distance_pct": float(stop_distance_pct),
                    "policy": str(policy),
                }
                dec_obj2 = self.risk_governor.allow_trade(req2)  # type: ignore[attr-defined]
                governor_dec = self._as_dict(dec_obj2)
            except Exception as e:
                out = {
                    "status": "REJECTED",
                    "decision": self._decision_block(reason=f"allow_trade_exception: {e}", extra={"volatility": vol_out.get("raw", {}), "regime": rg_out.get("raw", {})}),
                    "snapshot": self.snapshot(str(instrument)),
                }
                self._persist()
                return out

        ok = bool(governor_dec.get("ok", False)) if "ok" in governor_dec else bool(governor_dec.get("allowed", False))
        if not ok:
            out = {
                "status": "REJECTED",
                "decision": governor_dec or self._decision_block(reason="allow_trade_rejected"),
                "snapshot": self.snapshot(str(instrument)),
            }
            self._persist()
            return out

        # Allowed → increment open_positions (Phase 1 simplified)
        self.state["open_positions"] = int(self.state.get("open_positions") or 0) + 1
        self._persist()

        return {
            "status": "APPROVED",
            "decision": governor_dec or self._decision_allow(reason="allow_trade_ok"),
            "open_positions": self.state["open_positions"],
            "snapshot": self.snapshot(str(instrument)),
            "pre_gates": {
                "volatility": vol_out.get("raw", {}),
                "regime": rg_out.get("raw", {}),
            },
        }

    def record_trade_result(self, *, instrument: str, pnl: float) -> Dict[str, Any]:
        """
        Record realized PnL and update loss streak logic.

        Assumption (Phase 1):
        - each recorded result closes 1 open position (if any are open)
        """
        if int(self.state.get("open_positions") or 0) > 0:
            self.state["open_positions"] = int(self.state.get("open_positions") or 0) - 1

        # Try the canonical governor method; otherwise update local state minimally.
        try:
            self.risk_governor.record_trade_outcome(float(pnl))  # type: ignore[attr-defined]
        except Exception:
            self.state["daily_pnl"] = float(self.state.get("daily_pnl") or 0.0) + float(pnl)
            if float(pnl) < 0:
                self.state["consecutive_losses"] = int(self.state.get("consecutive_losses") or 0) + 1
            else:
                self.state["consecutive_losses"] = 0

        self._persist()
        snap = self.snapshot(str(instrument))
        snap["pnl"] = float(pnl)
        return {"status": "RECORDED", "snapshot": snap}
