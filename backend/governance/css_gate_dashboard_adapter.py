from __future__ import annotations

import time
from typing import Any, Dict



class CSSGateDashboardAdapter:
    """
    Dashboard compatibility adapter for the canonical
    backend CSSUnifiedTradeGate.

    PURPOSE
    -------
    This adapter allows the legacy dashboard governance
    flow to gradually migrate toward the institutional
    backend governance gate without immediate regression.

    IMPORTANT
    ---------
    This adapter preserves dashboard-facing decision shape while routing the
    final approval decision through the canonical backend gate.
    """

    def __init__(self, backend_gate) -> None:
        self.backend_gate = backend_gate

    # ======================================================
    # DASHBOARD COMPATIBILITY ENTRYPOINT
    # ======================================================

    def approve_trade(
        self,
        *,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
        portfolio_state: Dict[str, Any] | None = None,
        engine_mode: str = "SAFE",
    ) -> Dict[str, Any]:

        # LEGACY MIGRATION: Preserve Phase 110A frozen pre-checks
        legacy_reason = self._evaluate_legacy_dashboard_rules(candidate, session, role_profile, engine_mode)
        if legacy_reason:
            return {
                "approved": False,
                "reason": legacy_reason,
                "backend_reason": legacy_reason,
                "backend_details": {"legacy_block": True},
            }

        translated_candidate = self._translate_candidate(
            candidate,
            engine_mode=engine_mode,
        )

        if "_translation_error" in translated_candidate:
            return self._normalize_decision({
                "approved": False,
                "reason": translated_candidate["_translation_error"],
                "details": {}
            })

        translated_session = self._translate_session(
            session=session,
            role_profile=role_profile,
        )

        if translated_session.get("_translation_error"):
            return {
                "approved": False,
                "reason": translated_session["_translation_error"],
                "backend_reason": translated_session["_translation_error"],
                "backend_details": {},
            }

        translated_portfolio = self._normalize_portfolio_state(
            portfolio_state
        )

        decision = self.backend_gate.approve_trade(
            candidate=translated_candidate,
            session=translated_session,
            portfolio_state=translated_portfolio,
            engine_mode=engine_mode,
        )

        return self._normalize_decision(decision)

    # ======================================================
    # INTERNAL TRANSLATORS
    # ======================================================

    def _evaluate_legacy_dashboard_rules(
        self,
        candidate: Dict[str, Any],
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
        engine_mode: str,
    ) -> str | None:
        if not isinstance(session, dict) or not session.get("session_id"):
            return "NO_VALID_SESSION"
        if not session.get("session_status", {}).get("active", True):
            return "SESSION_NOT_ACTIVE"
        if candidate.get("is_session_locked", False):
            return "SESSION_LOCKED_DEFENSIVE_MODE"
            
        asset_key = str(candidate.get("asset_class", "UNKNOWN")).upper()
        if asset_key not in {"CRYPTO", "FX", "FUTURES", "OPTIONS"}:
            return f"UNSUPPORTED_ASSET_CLASS_{asset_key}"
            
        broker_mode = str(candidate.get("broker_mode", "paper")).lower()
        if broker_mode == "live" and not role_profile.get("can_use_live_broker_mode", False):
            return "RBAC_BLOCKED_LIVE_MODE"
        if broker_mode == "live" and not role_profile.get("can_execute_live_trading", False):
            return "RBAC_BLOCKED_LIVE_EXECUTION"
        if broker_mode != "live" and not role_profile.get("can_execute_paper_trading", False):
            return "RBAC_BLOCKED_PAPER_EXECUTION"
        if engine_mode == "SAFE" and broker_mode == "live":
            return "SAFE_MODE_BLOCKS_LIVE_EXECUTION"
            
        return None

    def _translate_candidate(
        self,
        candidate: Dict[str, Any],
        *,
        engine_mode: str,
    ) -> Dict[str, Any]:
        if not isinstance(candidate, dict):
            return {"_translation_error": "INVALID_CANDIDATE_FORMAT"}

        try:
            raw_probability = float(
                candidate.get(
                    "probability",
                    candidate.get("prob_positive", 0.0),
                )
            )

            signal_score = float(
                candidate.get(
                    "signal_score",
                    0.0,
                )
            )

            expected_value = float(
                candidate.get(
                    "expected_value",
                    signal_score,
                )
            )
            if expected_value <= 0:
                expected_value = 0.000001

            cost = float(
                candidate.get(
                    "cost",
                    0.0,
                )
            )
        except (TypeError, ValueError):
            return {"_translation_error": "MALFORMED_CANDIDATE_DATA"}

        return {
            "asset_class": str(candidate.get("asset_class", "UNKNOWN")).lower(),
            "symbol": str(candidate.get("symbol", "UNKNOWN")),
            "expected_value": expected_value,
            "cost": cost,
            "probability": raw_probability,
            "dashboard_probability": raw_probability,
            "dashboard_signal_score": signal_score,
        }

    def _translate_session(
        self,
        session: Dict[str, Any],
        role_profile: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(session, dict):
            return {
                "role": "UNKNOWN",
                "created": 0,
                "_translation_error": "NO_VALID_SESSION",
            }

        if not isinstance(role_profile, dict):
            role_profile = {}

        role = str(
            role_profile.get(
                "role",
                session.get("role", "TRADER"),
            )
        ).upper()

        created = self._extract_session_created(session)

        if created is None:
            return {
                "role": role,
                "created": 0,
                "_translation_error": "NO_VALID_SESSION_TIMESTAMP",
            }

        return {
            "role": role,
            "created": created,
        }

    def _normalize_decision(self, decision) -> Dict[str, Any]:
        if isinstance(decision, dict):
            approved = bool(decision.get("approved", False))
            reason = str(decision.get("reason", "UNKNOWN"))
            details = decision.get("details", decision.get("backend_details", {}))
            if not isinstance(details, dict):
                details = {}

            return {
                "approved": approved,
                "reason": "UNIFIED_GATE_APPROVED" if approved else reason,
                "backend_reason": reason,
                "backend_details": details,
            }

        approved = bool(
            getattr(decision, "approved", False)
        )

        reason = str(
            getattr(decision, "reason", "UNKNOWN")
        )

        details = getattr(decision, "details", {})
        if not isinstance(details, dict):
            details = {}

        return {
            "approved": approved,
            "reason": "UNIFIED_GATE_APPROVED" if approved else reason,
            "backend_reason": reason,
            "backend_details": details,
        }

    def _extract_session_created(self, session: Dict[str, Any]) -> float | None:
        candidates = [
            session.get("created"),
            session.get("session_created"),
        ]

        status = session.get("session_status")
        if isinstance(status, dict):
            candidates.append(status.get("created"))

        for value in candidates:
            try:
                created = float(value)
            except (TypeError, ValueError):
                continue

            if created > 0 and created <= time.time():
                return created

        return None

    def _normalize_portfolio_state(
        self,
        portfolio_state: Dict[str, Any] | None,
    ) -> Dict[str, int]:
        normalized = {
            "crypto": 0,
            "fx": 0,
            "futures": 0,
            "options": 0,
        }

        if not isinstance(portfolio_state, dict):
            return normalized

        for key, value in (portfolio_state or {}).items():
            asset_key = str(key or "").strip().lower()
            if asset_key in normalized:
                try:
                    normalized[asset_key] = int(value)
                except (TypeError, ValueError):
                    normalized[asset_key] = 0

        return normalized
