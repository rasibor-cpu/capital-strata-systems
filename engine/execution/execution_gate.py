"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA

Fail-closed by design.

This gate is governor-API adaptive:
- Tries common RiskGovernor decision method names across builds
- Tolerates diagnostic kwargs (equity_risk, spread_bps, etc.)
- Probe-safe (missing trade fields => clean rejection)

New in this version:
- Regime-Weighted Controlled Compounding (CompoundingEngine)
  Only applies when regime_persistence is available AND >= threshold.
  Otherwise, uses base_risk_pct * drawdown_factor (still governed).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable
import inspect

from engine.capital.compounding_engine import CompoundingEngine


class ExecutionGate:
    def __init__(self) -> None:
        # Lazy import to avoid circular imports
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()
        self.compounding = CompoundingEngine()

    # -----------------------------
    # helpers (normalization)
    # -----------------------------
    def _rej(self, reason: str, **extras: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ok": False, "reason": reason}
        if extras:
            out.update(extras)
        return out

    def _call_if_exists(self, name: str) -> Optional[Callable[..., Any]]:
        fn = getattr(self.risk_governor, name, None)
        return fn if callable(fn) else None

    def _normalize_governor_result(self, res: Any) -> Dict[str, Any]:
        """
        Normalizes a governor response into:
          {"ok": bool, "reason": str, ...optional fields...}
        """
        if isinstance(res, dict):
            if "ok" in res:
                return dict(res)
            if "allowed" in res:
                return {"ok": bool(res.get("allowed")), "reason": str(res.get("reason") or "")}
            if "decision" in res and isinstance(res["decision"], str):
                ok = res["decision"].upper() in ("ALLOW", "ALLOWED", "APPROVE", "APPROVED", "OK", "PASS")
                return {"ok": ok, "reason": str(res.get("reason") or res.get("message") or ""), "raw": res}
            return {"ok": False, "reason": "unrecognized_governor_dict", "raw": res}

        if hasattr(res, "as_dict") and callable(getattr(res, "as_dict")):
            try:
                d = res.as_dict()
                if isinstance(d, dict):
                    return self._normalize_governor_result(d)
            except Exception:
                return self._rej("governor_as_dict_failed")

        if hasattr(res, "ok"):
            try:
                return {"ok": bool(getattr(res, "ok")), "reason": str(getattr(res, "reason", "") or "")}
            except Exception:
                return self._rej("governor_result_ok_unreadable")

        if hasattr(res, "allowed"):
            try:
                return {"ok": bool(getattr(res, "allowed")), "reason": str(getattr(res, "reason", "") or "")}
            except Exception:
                return self._rej("governor_result_allowed_unreadable")

        if isinstance(res, bool):
            return {"ok": bool(res), "reason": ""}

        if isinstance(res, str):
            ok = res.upper() in ("ALLOW", "ALLOWED", "APPROVE", "APPROVED", "OK", "PASS")
            return {"ok": ok, "reason": "" if ok else res}

        return self._rej("unrecognized_governor_result_type", raw=str(type(res)))

    def _governor_decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Try multiple known RiskGovernor APIs across versions.
        """
        candidates = ["allow_trade", "evaluate_trade", "allow", "evaluate", "decide", "check"]
        last_err: Optional[str] = None

        for name in candidates:
            fn = self._call_if_exists(name)
            if not fn:
                continue

            try:
                # Prefer single payload dict for older builds that expect it
                try:
                    res = fn(payload)
                    return self._normalize_governor_result(res)
                except TypeError:
                    # Try kwargs call if supported
                    sig = None
                    try:
                        sig = inspect.signature(fn)
                    except Exception:
                        sig = None

                    if sig is not None:
                        accepts_varkw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
                        if accepts_varkw:
                            res = fn(**payload)  # type: ignore[arg-type]
                            return self._normalize_governor_result(res)

                        allowed_keys = {k for k in payload.keys() if k in sig.parameters}
                        trimmed = {k: payload[k] for k in allowed_keys}
                        res = fn(**trimmed)  # type: ignore[arg-type]
                        return self._normalize_governor_result(res)

                    last_err = f"{name}: TypeError"
                    continue

            except Exception as e:
                last_err = f"{name}: {type(e).__name__}: {e}"
                continue

        return self._rej("no_supported_risk_governor_api", detail=last_err or "")

    # -----------------------------
    # Controlled Compounding (CCE)
    # -----------------------------
    def _compute_equity_risk_if_possible(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        If we have enough info, compute equity_risk using CompoundingEngine and attach it.

        Inputs expected in payload (optional):
          - equity
          - equity_peak
          - regime_persistence   (0..1)
        If regime_persistence is missing, we do NOT force compounding.
        """
        try:
            equity = payload.get("equity", None)
            equity_peak = payload.get("equity_peak", None)
            regime_persistence = payload.get("regime_persistence", None)

            # Only apply compounding if we have a real persistence score
            if equity is None or equity_peak is None or regime_persistence is None:
                return {
                    "applied": False,
                    "reason": "missing_compounding_inputs",
                }

            equity = float(equity)
            equity_peak = float(equity_peak)
            regime_persistence = float(regime_persistence)

            risk_pct = self.compounding.compute_dynamic_risk(
                equity=equity,
                equity_peak=equity_peak,
                regime_persistence=regime_persistence,
            )

            payload["equity_risk"] = float(equity) * float(risk_pct)

            return {
                "applied": True,
                "risk_pct": float(risk_pct),
                "equity_risk": float(payload["equity_risk"]),
            }
        except Exception as e:
            return {
                "applied": False,
                "reason": "compounding_exception",
                "error": str(e),
            }

    # -----------------------------
    # public API
    # -----------------------------
    def evaluate_trade(
        self,
        *,
        instrument: str,
        side: Optional[str] = None,
        notional: Optional[float] = None,
        stop_distance_pct: Optional[float] = None,
        policy: str = "core",
        extras: Any = None,
        **diagnostic_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Evaluate whether a proposed trade is allowed.

        Supports:
        - probe/diagnostic calls where side/notional/stop_distance_pct are missing
        - extra diagnostic kwargs like equity_risk, spread_bps, vol_norm_0_1, high_risk_news, equity/equity_peak, etc.
        """
        snapshot: Dict[str, Any] = {
            "instrument": str(instrument),
            "last_extras": diagnostic_kwargs or None,
        }

        missing = []
        if not side:
            missing.append("side")
        if notional is None:
            missing.append("notional")
        if stop_distance_pct is None:
            missing.append("stop_distance_pct")

        if missing:
            decision = self._rej(
                "missing_required_fields",
                missing=missing,
                note="Caller must provide side/notional/stop_distance_pct for full evaluation.",
            )
            return {"status": "REJECTED", "decision": decision, "snapshot": snapshot}

        payload: Dict[str, Any] = {
            "instrument": str(instrument),
            "side": str(side),
            "notional": float(notional),
            "stop_distance_pct": float(stop_distance_pct),
            "policy": str(policy),
        }

        # Add diagnostics/extras without breaking older governors
        if isinstance(diagnostic_kwargs, dict) and diagnostic_kwargs:
            payload.update(diagnostic_kwargs)
        if extras is not None:
            payload["extras"] = extras

        # Apply controlled compounding ONLY when regime_persistence is present
        comp = self._compute_equity_risk_if_possible(payload)

        # -------------------------------------------------------
        # HYDRATE GOVERNOR STATE (critical for RiskGovernor v2)
        # -------------------------------------------------------
        equity = payload.get("equity", None)
        if equity is not None:
            try:
                # RiskGovernor v2 uses set_equity(), and requires equity before allow_trade()
                self.risk_governor.set_equity(float(equity))  # type: ignore[attr-defined]
            except Exception:
                # Fail-closed philosophy: we do NOT crash the engine for hydration failure.
                # Governor will reject if it truly needs equity.
                pass

        # Governor decision (API adaptive)
        dec = self._governor_decide(payload)

        # Attach compounding metadata (for audit/debug)
        dec["compounding"] = comp

        if not dec.get("ok", False):
            return {"status": "REJECTED", "decision": dec, "snapshot": snapshot}

        return {"status": "APPROVED", "decision": dec, "snapshot": snapshot}
