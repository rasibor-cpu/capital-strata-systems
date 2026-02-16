"""
Execution Gate – Central Trade Approval Layer
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.

Goal:
- Provide a stable, governor-API-adaptive execution gate.
- Tolerate diagnostic/probe calls (missing trade fields) without crashing.
- Normalize outputs into a consistent decision dict.

Key behaviors:
- If side/notional/stop_distance_pct are missing -> REJECTED with missing_required_fields
- If RiskGovernor API differs across versions, we auto-detect callable methods:
    allow_trade, allow, evaluate_trade, evaluate, decide, check
  and normalize their return.
- Any exception -> REJECTED (fail-closed).

Note:
- We do NOT assume RiskGovernor exposes .state or specific attributes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable
import inspect


class ExecutionGate:
    def __init__(self) -> None:
        # Lazy import to avoid circular imports
        from engine.risk.risk_governor import RiskGovernor  # type: ignore

        self.risk_governor = RiskGovernor()

    # -----------------------------
    # helpers (normalization)
    # -----------------------------
    def _rej(self, reason: str, **extras: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": False,
            "reason": reason,
        }
        if extras:
            out.update(extras)
        return out

    def _ok(self, **extras: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ok": True}
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
        # dict-like
        if isinstance(res, dict):
            if "ok" in res:
                return dict(res)
            if "allowed" in res:
                return {"ok": bool(res.get("allowed")), "reason": str(res.get("reason") or "")}
            if "decision" in res and isinstance(res["decision"], str):
                ok = res["decision"].upper() in ("ALLOW", "ALLOWED", "APPROVE", "APPROVED", "OK", "PASS")
                return {"ok": ok, "reason": str(res.get("reason") or res.get("message") or "") , "raw": res}
            return {"ok": False, "reason": "unrecognized_governor_dict", "raw": res}

        # object with as_dict()
        if hasattr(res, "as_dict") and callable(getattr(res, "as_dict")):
            try:
                d = res.as_dict()
                if isinstance(d, dict):
                    return self._normalize_governor_result(d)
            except Exception:
                return self._rej("governor_as_dict_failed")

        # object with .ok / .allowed
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

        # bool
        if isinstance(res, bool):
            return {"ok": bool(res), "reason": ""}

        # string
        if isinstance(res, str):
            ok = res.upper() in ("ALLOW", "ALLOWED", "APPROVE", "APPROVED", "OK", "PASS")
            return {"ok": ok, "reason": "" if ok else res}

        return self._rej("unrecognized_governor_result_type", raw=str(type(res)))

    def _governor_decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Try multiple known RiskGovernor APIs across versions.
        """
        # Common method candidates (most specific first)
        candidates = [
            "allow_trade",
            "evaluate_trade",
            "allow",
            "evaluate",
            "decide",
            "check",
        ]

        last_err: Optional[str] = None

        for name in candidates:
            fn = self._call_if_exists(name)
            if not fn:
                continue

            try:
                # Try calling with a single payload dict
                try:
                    res = fn(payload)
                    return self._normalize_governor_result(res)
                except TypeError:
                    # Try calling with kwargs if it supports it
                    sig = None
                    try:
                        sig = inspect.signature(fn)
                    except Exception:
                        sig = None

                    if sig is not None:
                        # Only pass kwargs the function can accept (unless **kwargs present)
                        accepts_varkw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
                        if accepts_varkw:
                            res = fn(**payload)  # type: ignore[arg-type]
                            return self._normalize_governor_result(res)

                        allowed_keys = {k for k in payload.keys() if k in sig.parameters}
                        trimmed = {k: payload[k] for k in allowed_keys}
                        res = fn(**trimmed)  # type: ignore[arg-type]
                        return self._normalize_governor_result(res)

                    # If we can't inspect signature, fail this candidate
                    last_err = f"{name}: TypeError"
                    continue

            except Exception as e:
                last_err = f"{name}: {type(e).__name__}: {e}"
                continue

        return self._rej("no_supported_risk_governor_api", detail=last_err or "")

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
        - extra diagnostic kwargs like equity_risk, spread_bps, vol_norm_0_1, high_risk_news, etc.

        Returns:
          {
            "status": "APPROVED"|"REJECTED",
            "decision": {...},
            "snapshot": {...},
            "note": "...",
          }
        """
        # Snapshot is intentionally minimal and governor-agnostic
        snapshot: Dict[str, Any] = {
            "instrument": str(instrument),
            "open_positions": 0,
            "last_extras": diagnostic_kwargs or None,
        }

        # Missing required trade fields -> fail-closed but non-crashing
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
            return {
                "status": "REJECTED",
                "decision": decision,
                "snapshot": snapshot,
            }

        # Build payload for governor (dict is safest cross-version)
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

        # Governor decision (API adaptive)
        dec = self._governor_decide(payload)

        if not dec.get("ok", False):
            return {
                "status": "REJECTED",
                "decision": dec,
                "snapshot": snapshot,
            }

        return {
            "status": "APPROVED",
            "decision": dec,
            "snapshot": snapshot,
        }
