"""
OANDA Adapter — REA Capital Trading Engine

Goals:
- Small, reliable surface area used by smoke tests and guarded runners.
- Fail-closed: missing creds => is_configured() == False, request methods raise.
- Provide stable methods:
    - get_account_summary()
    - get_open_positions()
    - get_open_trades()
    - place_order(...)
    - close_trade(...)
    - close_position(...)

Live Firewall (hardened):
    place_order() calls _evaluate_live_firewall() which requires ALL of:
      1. OANDA_ENABLE_LIVE_TRADING == "1"
      2. broker_mode == "live"
      3. broker_execution_armed == True
      4. governance_approved == True
      5. kill switch NOT active (CSS_LIVE_ORDER_KILL_SWITCH + controls)
      6. runtime NOT paused (trading_paused in controls)
      7. user authorized for live execution (live_toggle)
      8. no fail-closed condition (margin_rejection_lock, health RED)

    Any missing condition blocks execution, logs the denial reason, and
    returns an explicit firewall-denied result. Never silently continues.

    close_trade() and close_position() are quarantined with place_order under
    AR-026 unless CSS_OANDA_LEGACY_WRITES_ENABLED=1 (default off / fail-closed).
"""

from __future__ import annotations

import os
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, List

import requests

from backend.app.brokers.operational_state import BrokerOperationalState, operation_result
from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch
from backend.app.security.live_toggle import is_live_execution_authorized
from backend.app.observability.audit_context import get_audit_user


def _legacy_writes_enabled() -> bool:
    return os.getenv("CSS_OANDA_LEGACY_WRITES_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _legacy_write_quarantine_result(
    method: str,
    *,
    firewall: Optional["OandaLiveFirewallDecision"] = None,
) -> Dict[str, Any]:
    logging.warning(
        "[OANDA QUARANTINE] Legacy write method blocked method=%s",
        method,
    )
    secondary = []
    if firewall is not None and not firewall.allowed and firewall.denied_reason:
        secondary.append(f"live_firewall_denied:{firewall.denied_reason}")
    return {
        "ok": False,
        "status": None,
        "data": None,
        "error": "oanda_legacy_writes_quarantined",
        "method": method,
        "execution_allowed": False,
        "implementation_status": "WRITES_QUARANTINED",
        "allowed": False,
        "primary_denial_code": "oanda_legacy_writes_quarantined",
        "secondary_denial_codes": secondary,
        "quarantine_active": True,
        "firewall_active": True,
        "execution_authorized": False,
        "network_attempted": False,
        "firewall_audit": dict(firewall.audit_log) if firewall is not None else {},
    }


@dataclass(frozen=True)
class OrderRequest:
    """
    Canonical order request object for guarded execution.

    symbol: OANDA instrument e.g. "EUR_USD"
    side: "BUY" or "SELL"
    units: absolute units (int). Adapter converts SELL to negative units.
    order_type: "MARKET" for now
    """
    symbol: str
    side: str = "BUY"
    units: int = 1
    order_type: str = "MARKET"


@dataclass(frozen=True)
class OandaLiveFirewallDecision:
    """
    Result of the OANDA live execution firewall evaluation.

    allowed=True only when every condition passed.
    denied_reason is set whenever allowed=False.
    audit_log contains per-condition pass/fail detail for logging.
    """
    allowed: bool
    denied_reason: str = ""
    audit_log: Dict[str, Any] = field(default_factory=dict)


class OandaAdapter:
    def __init__(self, credentials: Dict[str, Any] = None) -> None:
        if credentials is None:
            from backend.app.brokers.credential_loader import load_credentials
            mode = "live" if str(os.getenv("OANDA_ENABLE_LIVE_TRADING") or "").strip() in ("1", "true", "yes", "on") else "paper"
            credentials = load_credentials("oanda", mode=mode) or {}
            
        self.api_key = str(credentials.get("OANDA_API_KEY") or credentials.get("OANDA_ACCESS_TOKEN") or credentials.get("OANDA_TOKEN") or "").strip()
        self.account_id = str(credentials.get("OANDA_ACCOUNT_ID") or credentials.get("OANDA_PRACTICE_ACCOUNT_ID") or "").strip()
        self.base_url = str(credentials.get("OANDA_BASE_URL") or "").strip().rstrip("/")
        self.env = str(credentials.get("OANDA_ENV") or "practice").strip().lower()
        # Condition 1 source of truth is the process env; credentials may also carry the flag.
        self.allow_live_trades = str(
            credentials.get("OANDA_ENABLE_LIVE_TRADING")
            or os.getenv("OANDA_ENABLE_LIVE_TRADING")
            or "false"
        ).strip().lower() in ("1", "true", "yes", "on")
        
        self.health_state = "GREEN"
        self.consecutive_failures = 0
        self.margin_rejection_lock = False

    # -------------------------
    # configuration
    # -------------------------
    def is_configured(self) -> bool:
        return bool(self.api_key and self.account_id and self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            result = operation_result(
                broker="OANDA",
                operation=f"http_{method.lower()}",
                state=BrokerOperationalState.CONFIGURATION_REQUIRED,
                failure_code="CONFIGURATION_REQUIRED",
                operator_message="OANDA read-only configuration is required",
                technical_message="No network request was attempted",
                recommended_action="Configure OANDA endpoint, credentials, and account selection",
                data={"path": path},
            ).as_dict()
            return {
                "ok": False,
                "status": None,
                "data": None,
                "error": "CONFIGURATION_REQUIRED",
                "operation_result": result,
            }

        if self.margin_rejection_lock and method.upper() in ("POST", "PUT"):
            # Block new orders if margin rejected
            return {"ok": False, "status": None, "data": None, "error": "margin_rejection_lock_active"}

        url = f"{self.base_url}/{path.lstrip('/')}"
        
        max_retries = 3
        backoff_factor = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                resp = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=self._headers(),
                    json=payload,
                    timeout=20,
                )
                
                # Check for 429 Rate Limit
                if resp.status_code == 429:
                    if attempt < max_retries:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    else:
                        self._record_failure()
                        return {"ok": False, "status": 429, "data": None, "error": "rate_limit_exhausted"}
                
                # Check for other errors
                ok = 200 <= (resp.status_code or 0) < 300
                data: Any = None
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

                # Check for margin rejection (usually 400 with specific message in OANDA)
                if resp.status_code == 400 and data and isinstance(data, dict):
                    err_msg = str(data.get("errorMessage", "")).upper()
                    if "INSUFFICIENT" in err_msg or "MARGIN" in err_msg:
                        self.margin_rejection_lock = True
                        self._record_failure()
                        logging.warning("[OANDA ADAPTER] Margin rejection detected. Order submissions locked.")
                        return {"ok": False, "status": 400, "data": data, "error": "insufficient_margin"}

                if not ok:
                    if attempt < max_retries and resp.status_code >= 500:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    
                    self._record_failure()
                    return {"ok": False, "status": resp.status_code, "data": data, "error": f"http_{resp.status_code}"}

                self._record_success()
                return {"ok": True, "status": resp.status_code, "data": data, "error": None}

            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    time.sleep(backoff_factor * (2 ** attempt))
                    continue
                self._record_failure()
                return {"ok": False, "status": None, "data": None, "error": f"request_error: {e}"}

        self._record_failure()
        return {"ok": False, "status": None, "data": None, "error": "max_retries_exhausted"}

    def operational_readiness(self) -> Dict[str, Any]:
        """Structured compatibility boundary; performs no authentication."""
        from backend.app.brokers.operational_adapter import OandaOperationalAdapter

        configuration = {
            "OANDA_BASE_URL": self.base_url,
            "OANDA_API_TOKEN": "configured" if self.api_key else "",
            "OANDA_ACCOUNT_ID": "configured" if self.account_id else "",
            "OANDA_ENVIRONMENT": self.env,
        }
        return OandaOperationalAdapter(configuration=configuration).readiness()

    def _record_success(self):
        self.consecutive_failures = 0
        self.health_state = "GREEN"

    def _record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= 5:
            self.health_state = "RED"
        elif self.consecutive_failures >= 2:
            self.health_state = "DEGRADED"

    # -------------------------
    # read endpoints
    # -------------------------
    def get_server_status(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/summary")

    def get_account_details(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}")

    def get_instruments(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/instruments")

    def get_pricing(self, instruments: str = "EUR_USD") -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/pricing?instruments={instruments}")

    def get_account_summary(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/summary")

    def get_open_positions(self) -> Dict[str, Any]:
        # returns list of positions (may be empty)
        return self._request_json("GET", f"v3/accounts/{self.account_id}/openPositions")

    def get_open_trades(self) -> Dict[str, Any]:
        return self._request_json("GET", f"v3/accounts/{self.account_id}/openTrades")

    # -------------------------
    # trade/order endpoints
    # -------------------------

    def _evaluate_live_firewall(
        self,
        *,
        broker_mode: str = "",
        broker_execution_armed: bool = False,
        governance_approved: bool = False,
        controls: Optional[Mapping[str, Any]] = None,
        user_context: Optional[Mapping[str, Any]] = None,
    ) -> OandaLiveFirewallDecision:
        """
        Evaluate all 8 required conditions for live order execution.

        Conditions checked in order (first failure blocks immediately):
          1. OANDA_ENABLE_LIVE_TRADING env var == "1"
          2. broker_mode == "live"
          3. broker_execution_armed == True
          4. governance_approved == True
          5. kill switch NOT active
          6. runtime NOT paused
          7. user authorized for live execution
          8. no fail-closed condition (margin lock / health RED)

        Returns OandaLiveFirewallDecision(allowed=False, denied_reason=...) on
        any failure. Never raises — always returns a decision.
        """
        audit: Dict[str, Any] = {}

        # ── Condition 1: env-var firewall ────────────────────────────────────
        env_enabled = bool(getattr(self, "allow_live_trades", False))
        audit["oanda_enable_live_trading"] = env_enabled
        if not env_enabled:
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_1_failed:OANDA_ENABLE_LIVE_TRADING_not_set",
                audit_log=audit,
            )

        # ── Condition 2: live broker mode selected ────────────────────────────
        mode_normalised = str(broker_mode or "").strip().lower()
        audit["broker_mode"] = mode_normalised
        if mode_normalised != "live":
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason=f"firewall_condition_2_failed:broker_mode_not_live:{mode_normalised}",
                audit_log=audit,
            )

        # ── Condition 3: broker execution armed ──────────────────────────────
        audit["broker_execution_armed"] = broker_execution_armed
        if not broker_execution_armed:
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_3_failed:broker_execution_not_armed",
                audit_log=audit,
            )

        # ── Condition 4: governance approved ─────────────────────────────────
        audit["governance_approved"] = governance_approved
        if not governance_approved:
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_4_failed:governance_not_approved",
                audit_log=audit,
            )

        # ── Condition 5: kill switch not active ──────────────────────────────
        try:
            ks_decision = evaluate_live_order_kill_switch(controls=controls or {})
            audit["kill_switch_blocked"] = ks_decision.blocked
            audit["kill_switch_reason"] = ks_decision.reason
            if ks_decision.blocked:
                return OandaLiveFirewallDecision(
                    allowed=False,
                    denied_reason=f"firewall_condition_5_failed:kill_switch_active:{ks_decision.reason}",
                    audit_log=audit,
                )
        except Exception as exc:
            audit["kill_switch_error"] = str(exc)
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason=f"firewall_condition_5_failed:kill_switch_evaluation_error:{exc}",
                audit_log=audit,
            )

        # ── Condition 6: runtime not paused ──────────────────────────────────
        active_controls = controls or {}
        trading_paused = str(active_controls.get("trading_paused", "false")).strip().lower()
        runtime_paused = str(active_controls.get("runtime_paused", "false")).strip().lower()
        paused = trading_paused in ("true", "1", "yes", "on") or runtime_paused in ("true", "1", "yes", "on")
        audit["trading_paused"] = trading_paused
        audit["runtime_paused"] = runtime_paused
        if paused:
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_6_failed:runtime_paused",
                audit_log=audit,
            )

        # ── Condition 7: user authorized for live execution ───────────────────
        try:
            # Build user context from audit thread-local if not explicitly supplied
            resolved_user_ctx: Optional[Mapping[str, Any]] = user_context
            if resolved_user_ctx is None:
                audit_user = get_audit_user()
                if audit_user is not None:
                    resolved_user_ctx = {
                        "user_id": str(audit_user.user_id),
                        "role": audit_user.role,
                        "role_profile": {"can_execute_live_trading": True}
                        if str(audit_user.role).upper() == "SUPER_USER"
                        else {},
                    }

            authorized, auth_reason, _ = is_live_execution_authorized(resolved_user_ctx)
            audit["user_authorized"] = authorized
            audit["auth_reason"] = auth_reason
            if not authorized:
                return OandaLiveFirewallDecision(
                    allowed=False,
                    denied_reason=f"firewall_condition_7_failed:user_not_authorized:{auth_reason}",
                    audit_log=audit,
                )
        except Exception as exc:
            audit["auth_error"] = str(exc)
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason=f"firewall_condition_7_failed:auth_evaluation_error:{exc}",
                audit_log=audit,
            )

        # ── Condition 8: no fail-closed conditions ────────────────────────────
        margin_rejection_lock = bool(getattr(self, "margin_rejection_lock", False))
        health_state = str(getattr(self, "health_state", "GREEN"))
        audit["margin_rejection_lock"] = margin_rejection_lock
        audit["health_state"] = health_state
        if margin_rejection_lock:
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_8_failed:margin_rejection_lock_active",
                audit_log=audit,
            )
        if health_state == "RED":
            return OandaLiveFirewallDecision(
                allowed=False,
                denied_reason="firewall_condition_8_failed:adapter_health_RED",
                audit_log=audit,
            )

        # ── All conditions passed ─────────────────────────────────────────────
        audit["firewall_result"] = "ALLOWED"
        return OandaLiveFirewallDecision(allowed=True, denied_reason="", audit_log=audit)

    def place_order(
        self,
        order: Optional[OrderRequest] = None,
        symbol: Optional[str] = None,
        side: str = "BUY",
        units: int = 1,
        order_type: str = "MARKET",
        price_bound: Optional[str] = None,
        # ── Firewall parameters ───────────────────────────────────────────────
        broker_mode: str = "",
        broker_execution_armed: bool = False,
        governance_approved: bool = False,
        controls: Optional[Mapping[str, Any]] = None,
        user_context: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Accept either:
          - place_order(OrderRequest(...))
          - place_order(symbol="EUR_USD", units=1, side="BUY")

        Live execution requires ALL firewall conditions to pass.
        Denial is always logged with the specific reason.
        Practice/paper paths are unaffected — they are not routed here.
        """
        if order is not None:
            symbol = order.symbol
            side = order.side
            units = order.units
            order_type = order.order_type

        symbol_final = (symbol or "").strip()
        if not symbol_final:
            return {"ok": False, "status": None, "data": None, "error": "missing_symbol"}

        firewall = self._evaluate_live_firewall(
            broker_mode=broker_mode,
            broker_execution_armed=broker_execution_armed,
            governance_approved=governance_approved,
            controls=controls,
            user_context=user_context,
        )
        if not _legacy_writes_enabled():
            return _legacy_write_quarantine_result("place_order", firewall=firewall)

        # ── Live firewall: all 8 conditions evaluated atomically ──────────────
        if not firewall.allowed:
            logging.warning(
                "[OANDA FIREWALL] Live order DENIED. reason=%s symbol=%s audit=%s",
                firewall.denied_reason,
                symbol_final,
                firewall.audit_log,
            )
            return {
                "ok": False,
                "status": None,
                "data": None,
                "error": f"live_firewall_denied:{firewall.denied_reason}",
                "allowed": False,
                "primary_denial_code": f"live_firewall_denied:{firewall.denied_reason}",
                "secondary_denial_codes": [],
                "quarantine_active": False,
                "firewall_active": True,
                "execution_authorized": False,
                "network_attempted": False,
                "firewall_audit": dict(firewall.audit_log),
            }

        side_u = (side or "BUY").upper().strip()
        if side_u not in ("BUY", "SELL"):
            return {"ok": False, "status": None, "data": None, "error": "invalid_side"}

        units_i = int(units)
        if units_i <= 0:
            return {"ok": False, "status": None, "data": None, "error": "invalid_units"}

        signed_units = units_i if side_u == "BUY" else -units_i

        otype = (order_type or "MARKET").upper().strip()
        if otype != "MARKET":
            return {"ok": False, "status": None, "data": None, "error": "unsupported_order_type"}

        payload = {
            "order": {
                "type": "MARKET",
                "instrument": symbol_final,
                "units": str(signed_units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }

        if price_bound is not None:
            payload["order"]["priceBound"] = str(price_bound)

        logging.info(
            "[OANDA FIREWALL] Live order ALLOWED. symbol=%s side=%s units=%s",
            symbol_final, side_u, signed_units,
        )
        return self._request_json("POST", f"v3/accounts/{self.account_id}/orders", payload)

    def close_trade(self, trade_id: str) -> Dict[str, Any]:
        if not _legacy_writes_enabled():
            return _legacy_write_quarantine_result("close_trade")
        tid = (trade_id or "").strip()
        if not tid:
            return {"ok": False, "status": None, "data": None, "error": "missing_trade_id"}
        return self._request_json("PUT", f"v3/accounts/{self.account_id}/trades/{tid}/close")

    def close_position(self, instrument: str, long_units: str = "ALL", short_units: str = "ALL") -> Dict[str, Any]:
        if not _legacy_writes_enabled():
            return _legacy_write_quarantine_result("close_position")
        instr = (instrument or "").strip()
        if not instr:
            return {"ok": False, "status": None, "data": None, "error": "missing_instrument"}
        payload = {"longUnits": long_units, "shortUnits": short_units}
        return self._request_json("PUT", f"v3/accounts/{self.account_id}/positions/{instr}/close", payload)

    # -------------------------
    # small helpers for guarded runner
    # -------------------------
    @staticmethod
    def extract_balance_nav(summary_resp: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Works on:
          GET /summary response => {"account": {"balance": "...", "NAV": "..."}}
        """
        try:
            acc = (summary_resp.get("data") or {}).get("account") or {}
            bal = float(acc.get("balance")) if acc.get("balance") is not None else None
            nav = float(acc.get("NAV")) if acc.get("NAV") is not None else None
            return {"balance": bal, "nav": nav}
        except Exception:
            return {"balance": None, "nav": None}
