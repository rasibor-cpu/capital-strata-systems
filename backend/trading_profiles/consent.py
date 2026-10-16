"""Non-bypassable consent gate for trading modes and risk-policy changes (issue #118).

Flow (server-side; the client's scroll gating is UX only):
  1. propose_change(): the user's requested mode / personality / limits / mandate terms
     become a PENDING change with the exact effective settings, risk implications and an
     immutable policy hash. Nothing is active yet.
  2. open_review(): a review session bound to the user's authenticated session and to
     the current controlled manual version.
  3. present_page() / mark_reviewed(): every required manual page must be presented by
     the server and then reported reviewed (scroll bottom, keyboard or screen-reader end
     of page, or a non-scrollable page). This proves presentation, not comprehension.
  4. accept(): requires all pages reviewed in this session, an explicit acknowledgement
     (checked=True and the exact acknowledgement text hash), the current manual version
     and hash, and the policy hash the user was shown. Activation is transactional:
     the ACCEPTED record is appended to a hash-chained ledger first; then the mandate
     (copy mode) and the active settings are written, referencing that record.
  5. verify_active(): called at every trade decision. Missing, stale (material manual
     change), tampered, mismatched or revoked consent fails closed.

Risk-reducing actions (pause, kill switch, protective exits, mandate revocation) never
depend on consent. Settings changes apply to NEW trades only.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from backend.certification.ov002_persistence import (
    PersistenceError,
    atomic_append_jsonl,
    atomic_write_json,
    read_json_object,
)
from backend.runtime.interprocess_lock import exclusive_file_lock
from backend.trading_profiles.limits import LimitsError, UserRiskLimits, effective_policy
from backend.trading_profiles.mandates import CopyMandate, MandateError, MandateRegistry, ReauthorizationPolicy
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256, ControlledManual, ManualIntegrityError, current_manual
from backend.trading_profiles.operating_modes import OperatingMode, permissions_for
from backend.trading_profiles.preferences import ActiveSettings, PreferencesStore, UserTradingState
from backend.trading_profiles.risk_personalities import RiskPersonality, policy_for
from backend.trading_profiles.trader_registry import TraderRegistry, TraderRegistryError

CONSENT_STATE_SCHEMA = "css.trading_profiles.consent_state.v1"
POLICY_SCHEMA = "css.trading_profiles.policy.v1"
CHANGE_TTL = timedelta(minutes=30)
REVIEW_TTL = timedelta(hours=2)
REVIEW_METHODS = frozenset({"scroll_bottom", "keyboard_end", "screen_reader_end", "non_scrollable_presented"})
SIMULATION_DEFAULT_PERSONALITY = RiskPersonality.BALANCED
GENESIS = "GENESIS"


class ConsentError(RuntimeError):
    """Fail-closed consent error; the message is a stable reason code."""


def _canonical(body: Any) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sha(body: Any) -> str:
    return hashlib.sha256(_canonical(body)).hexdigest()


# ----------------------------------------------------------------- policy hash
def mandate_terms_from_mandate(mandate: CopyMandate) -> dict[str, Any]:
    issued = datetime.fromisoformat(mandate.issued_at_utc)
    expires = datetime.fromisoformat(mandate.expires_at_utc)
    return {
        "trader_id": mandate.trader_id,
        "asset_classes": sorted(mandate.asset_classes),
        "max_allocation": round(float(mandate.max_allocation), 2),
        "currency": mandate.currency,
        "valid_days": round((expires - issued).total_seconds() / 86400.0, 6),
        "reauthorization_policy": mandate.reauthorization_policy,
        "reauthorization_interval_hours": float(mandate.reauthorization_interval_hours),
    }


def normalize_mandate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        terms = {
            "trader_id": str(request["trader_id"]).strip(),
            "asset_classes": sorted({str(a).upper() for a in request["asset_classes"]}),
            "max_allocation": round(float(request["max_allocation"]), 2),
            "currency": str(request.get("currency") or "CAD").upper(),
            "valid_days": round(float(request["valid_days"]), 6),
            "reauthorization_policy": ReauthorizationPolicy(str(request["reauthorization_policy"])).value,
            "reauthorization_interval_hours": float(request.get("reauthorization_interval_hours") or 0),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ConsentError(f"mandate_request_invalid:{exc}") from exc
    if not terms["trader_id"] or not terms["asset_classes"] or terms["max_allocation"] <= 0 or terms["valid_days"] <= 0:
        raise ConsentError("mandate_request_invalid")
    return terms


def policy_hash(mode: OperatingMode, personality: RiskPersonality | None, limits: UserRiskLimits,
                mandate_terms: Mapping[str, Any] | None) -> str:
    return _sha({
        "schema": POLICY_SCHEMA,
        "operating_mode": mode.value,
        "risk_personality": personality.value if personality else None,
        "limits": limits.to_dict(),
        "mandate_terms": dict(mandate_terms) if mandate_terms else None,
    })


# ----------------------------------------------------------------- records
@dataclass(frozen=True)
class PendingChange:
    change_id: str
    user_id: str
    kind: str
    operating_mode: str
    risk_personality: str | None
    limits: dict
    mandate_terms: dict | None
    policy_hash: str
    effective_settings: dict
    implications: list
    created_at_utc: str
    expires_at_utc: str
    status: str = "PENDING"


@dataclass(frozen=True)
class ReviewSession:
    review_id: str
    change_id: str
    user_id: str
    auth_session_hash: str
    manual_version: str
    manual_sha256: str
    pages: dict  # page_id -> {"presented_at_utc", "page_sha256", "reviewed_at_utc", "method"}
    created_at_utc: str
    expires_at_utc: str
    status: str = "OPEN"


def _implications(mode: OperatingMode, policy, mandate_terms: Mapping[str, Any] | None) -> list[str]:
    permissions = permissions_for(mode)
    items = [
        f"Decision authority: {permissions.decision_authority}.",
        "No order is sent to any broker; this activates simulated or paper evaluation only. Live trading is not authorized.",
        "Trading involves the risk of losing some or all invested capital; profits are not guaranteed.",
        f"Up to {policy.max_position_pct_of_equity}% of equity per position and {policy.max_total_exposure_pct_of_equity}% "
        f"in total; at most {policy.max_open_copied_positions} open positions.",
        f"New trading pauses after a {policy.daily_loss_halt_pct}% daily loss or a {policy.max_drawdown_halt_pct}% drawdown; "
        "stops can be exceeded by price gaps.",
        "Every order must still pass R7, R14F, AntiBleedGuard, margin, risk governor, kill switch and position caps.",
        "Changes apply to new trades only; open positions keep their existing protective exits.",
    ]
    if permissions.requires_per_order_approval:
        items.append("You must approve or reject every proposed or manual order individually.")
    if mandate_terms:
        items.append(
            f"Copying {mandate_terms['trader_id']} within {', '.join(mandate_terms['asset_classes'])} up to "
            f"{mandate_terms['max_allocation']} {mandate_terms['currency']} for {mandate_terms['valid_days']} days; "
            "your fills and PnL will differ from the trader's; ordinary losses are not reimbursed.")
    if mode is OperatingMode.CSS_AUTONOMOUS_TRADING:
        items.append("CSS will open and close positions without asking you, within these settings.")
    return items


class ConsentLedger:
    """Append-only, SHA-256 hash-chained acceptance records."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "consent_ledger.jsonl"

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        prev, out = GENESIS, []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            claimed = record.pop("entry_hash", None)
            if record.get("prev_hash") != prev or _sha(record) != claimed:
                raise ConsentError("consent_ledger_chain_broken")
            record["entry_hash"] = claimed
            prev = claimed
            out.append(record)
        return out

    def append(self, record_type: str, body: Mapping[str, Any]) -> dict[str, Any]:
        existing = self.records()
        record = {"record_type": record_type, **dict(body), "prev_hash": existing[-1]["entry_hash"] if existing else GENESIS}
        record["entry_hash"] = _sha(record)
        atomic_append_jsonl(self.path, record, expected_root=self.root)
        return record


class ConsentService:
    def __init__(
        self,
        root: Path | str,
        *,
        preferences: PreferencesStore,
        mandates: MandateRegistry,
        manual_provider: Callable[[], ControlledManual] = current_manual,
        trader_registry: TraderRegistry | None = None,
    ) -> None:
        self.root = Path(root)
        self.preferences = preferences
        self.mandates = mandates
        # Copy mandates are only possible for traders approved (dual control) in this registry.
        self.trader_registry = trader_registry or TraderRegistry(self.root)
        self.manual_provider = manual_provider
        self.ledger = ConsentLedger(self.root)
        self.state_path = self.root / "consent_state.json"
        self.lock_path = self.root / "consent.lock"

    # -- storage -----------------------------------------------------------
    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schema": CONSENT_STATE_SCHEMA, "changes": {}, "reviews": {}}
        try:
            state = read_json_object(self.state_path)
        except PersistenceError as exc:
            raise ConsentError(f"consent_state_unreadable:{exc}") from exc
        if state.get("schema") != CONSENT_STATE_SCHEMA:
            raise ConsentError("consent_state_schema_mismatch")
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_path, state, expected_root=self.root)

    def _locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return exclusive_file_lock(self.lock_path, timeout_seconds=10.0)

    def _manual(self) -> ControlledManual:
        try:
            return self.manual_provider()
        except ManualIntegrityError as exc:
            raise ConsentError(f"manual_integrity_failed:{exc}") from exc

    # -- 1. propose ----------------------------------------------------------
    def propose_change(self, user_id: str, *, operating_mode: Any, risk_personality: Any = None,
                       limits: Mapping[str, Any] | None = None, mandate_request: Mapping[str, Any] | None = None,
                       now: datetime) -> PendingChange:
        if not user_id:
            raise ConsentError("user_required")
        try:
            mode = OperatingMode.parse(operating_mode)
            personality = RiskPersonality.parse(risk_personality) if risk_personality not in (None, "") else None
            user_limits = UserRiskLimits.from_mapping(limits)
        except (ValueError, LimitsError) as exc:
            raise ConsentError(f"proposal_invalid:{exc}") from exc
        permissions = permissions_for(mode)
        if permissions.requires_risk_personality and personality is None:
            raise ConsentError("risk_personality_required")
        applied = personality or SIMULATION_DEFAULT_PERSONALITY
        try:
            policy = effective_policy(policy_for(applied), user_limits)
        except LimitsError as exc:
            raise ConsentError(f"limit_looser_than_personality:{exc}") from exc
        terms = None
        if permissions.requires_trader_mandate:
            if not mandate_request:
                raise ConsentError("mandate_request_required")
            terms = normalize_mandate_request(mandate_request)
            outside = set(terms["asset_classes"]) - set(policy.allowed_asset_classes)
            if outside:
                raise ConsentError(f"mandate_scope_outside_policy:{sorted(outside)}")
            self._require_approved_trader(terms)
        elif mandate_request:
            raise ConsentError("mandate_request_not_allowed_for_mode")
        phash = policy_hash(mode, personality, user_limits, terms)
        manual = self._manual()
        current = self.preferences.get(user_id)
        if current.active is None:
            kind = "INITIAL_ACTIVATION"
        elif current.active.policy_hash == phash:
            kind = "RENEWAL"
        else:
            kind = "CHANGE"
        summary = policy.summary()
        summary.update({"operating_mode": mode.value, "personality_applied": applied.value,
                        "personality_selected": personality.value if personality else None,
                        "user_limits": user_limits.to_dict(), "mandate_terms": terms,
                        "manual_version": manual.version})
        change = PendingChange(
            change_id="chg-" + secrets.token_hex(12), user_id=user_id, kind=kind, operating_mode=mode.value,
            risk_personality=personality.value if personality else None, limits=user_limits.to_dict(),
            mandate_terms=terms, policy_hash=phash, effective_settings=summary,
            implications=_implications(mode, policy, terms), created_at_utc=_iso(now),
            expires_at_utc=_iso(now + CHANGE_TTL),
        )
        with self._locked():
            state = self._read_state()
            # A new proposal supersedes the user's earlier pending proposals.
            for cid, existing in state["changes"].items():
                if existing["user_id"] == user_id and existing["status"] == "PENDING":
                    existing["status"] = "SUPERSEDED"
            state["changes"][change.change_id] = asdict(change)
            self._write_state(state)
        return change

    def _require_approved_trader(self, terms: Mapping[str, Any]) -> None:
        try:
            self.trader_registry.require_active(terms["trader_id"], tuple(terms["asset_classes"]))
        except TraderRegistryError as exc:
            raise ConsentError(f"trader_not_copyable:{exc}") from exc

    # -- 2/3. review ------------------------------------------------------------
    def _get_review(self, state, review_id: str, user_id: str, auth_session_hash: str, now: datetime) -> dict:
        review = state["reviews"].get(review_id)
        # Same answer for "not yours" and "does not exist": no cross-user probing.
        if review is None or review["user_id"] != user_id or review["auth_session_hash"] != auth_session_hash:
            raise ConsentError("review_not_found")
        if review["status"] != "OPEN":
            raise ConsentError("review_closed")
        if now >= datetime.fromisoformat(review["expires_at_utc"]):
            raise ConsentError("review_expired")
        return review

    def open_review(self, user_id: str, *, auth_session_hash: str, change_id: str, now: datetime) -> ReviewSession:
        if not auth_session_hash:
            raise ConsentError("authenticated_session_required")
        manual = self._manual()
        with self._locked():
            state = self._read_state()
            change = state["changes"].get(change_id)
            if change is None or change["user_id"] != user_id:
                raise ConsentError("change_not_found")
            if change["status"] != "PENDING":
                raise ConsentError(f"change_not_pending:{change['status']}")
            if now >= datetime.fromisoformat(change["expires_at_utc"]):
                raise ConsentError("change_expired")
            review = ReviewSession(
                review_id="rev-" + secrets.token_hex(12), change_id=change_id, user_id=user_id,
                auth_session_hash=auth_session_hash, manual_version=manual.version, manual_sha256=manual.sha256,
                pages={pid: {} for pid in manual.page_ids}, created_at_utc=_iso(now),
                expires_at_utc=_iso(now + REVIEW_TTL),
            )
            state["reviews"][review.review_id] = asdict(review)
            self._write_state(state)
        return review

    def present_page(self, user_id: str, *, auth_session_hash: str, review_id: str, page_id: str, now: datetime) -> dict:
        manual = self._manual()
        with self._locked():
            state = self._read_state()
            review = self._get_review(state, review_id, user_id, auth_session_hash, now)
            if review["manual_sha256"] != manual.sha256:
                raise ConsentError("manual_changed_restart_review")
            if page_id not in review["pages"]:
                raise ConsentError("page_not_found")
            page = manual.page(page_id)
            entry = review["pages"][page_id]
            if not entry.get("presented_at_utc"):
                entry.update({"presented_at_utc": _iso(now), "page_sha256": page.sha256})
            self._write_state(state)
        index = manual.page_ids.index(page_id)
        return {"page_id": page.page_id, "title": page.title, "markdown": page.markdown, "sha256": page.sha256,
                "index": index + 1, "total": len(manual.pages), "manual_version": manual.version}

    def mark_reviewed(self, user_id: str, *, auth_session_hash: str, review_id: str, page_id: str, method: str,
                      page_sha256: str, now: datetime) -> dict:
        if method not in REVIEW_METHODS:
            raise ConsentError("review_method_invalid")
        with self._locked():
            state = self._read_state()
            review = self._get_review(state, review_id, user_id, auth_session_hash, now)
            entry = review["pages"].get(page_id)
            if entry is None:
                raise ConsentError("page_not_found")
            if not entry.get("presented_at_utc"):
                raise ConsentError("page_not_presented")
            if entry.get("page_sha256") != page_sha256:
                raise ConsentError("page_version_mismatch")
            entry.update({"reviewed_at_utc": _iso(now), "method": method})
            self._write_state(state)
            done = sum(1 for e in review["pages"].values() if e.get("reviewed_at_utc"))
        return {"page_id": page_id, "reviewed_pages": done, "total_pages": len(review["pages"])}

    # -- 4. accept ---------------------------------------------------------------
    def accept(self, user_id: str, *, auth_session_hash: str, review_id: str, acknowledgement_checked: Any,
               acknowledgement_sha256: str, manual_version: str, manual_sha256: str, policy_hash_shown: str,
               now: datetime) -> dict[str, Any]:
        if acknowledgement_checked is not True:
            raise ConsentError("acknowledgement_not_checked")
        if acknowledgement_sha256 != ACKNOWLEDGEMENT_SHA256:
            raise ConsentError("acknowledgement_text_mismatch")
        manual = self._manual()
        if manual_version != manual.version or manual_sha256 != manual.sha256:
            raise ConsentError("manual_version_mismatch")
        with self._locked():
            state = self._read_state()
            review = self._get_review(state, review_id, user_id, auth_session_hash, now)
            if review["manual_sha256"] != manual.sha256:
                raise ConsentError("manual_changed_restart_review")
            unreviewed = [pid for pid in manual.page_ids if not review["pages"].get(pid, {}).get("reviewed_at_utc")]
            if unreviewed:
                raise ConsentError("pages_not_reviewed:" + ",".join(unreviewed))
            stale = [pid for pid in manual.page_ids if review["pages"][pid].get("page_sha256") != manual.page(pid).sha256]
            if stale:
                raise ConsentError("page_version_mismatch")
            change = state["changes"].get(review["change_id"])
            if change is None or change["user_id"] != user_id:
                raise ConsentError("change_not_found")
            if change["status"] != "PENDING":
                raise ConsentError(f"change_not_pending:{change['status']}")  # replay protection
            if now >= datetime.fromisoformat(change["expires_at_utc"]):
                raise ConsentError("change_expired")
            mode = OperatingMode.parse(change["operating_mode"])
            personality = RiskPersonality.parse(change["risk_personality"]) if change["risk_personality"] else None
            limits = UserRiskLimits.from_mapping(change["limits"])
            recomputed = policy_hash(mode, personality, limits, change["mandate_terms"])
            if recomputed != change["policy_hash"]:
                raise ConsentError("pending_change_tampered")
            if policy_hash_shown != change["policy_hash"]:
                raise ConsentError("policy_hash_mismatch")
            effective_policy(policy_for(personality or SIMULATION_DEFAULT_PERSONALITY), limits)  # revalidate
            if change["mandate_terms"]:
                self._require_approved_trader(change["mandate_terms"])  # trader may have been suspended since

            receipt_id = "rcpt-" + secrets.token_hex(12)
            body = {
                "receipt_id": receipt_id, "user_id": user_id, "auth_session_hash": auth_session_hash,
                "change_id": change["change_id"], "kind": change["kind"], "policy_hash": change["policy_hash"],
                "operating_mode": change["operating_mode"], "risk_personality": change["risk_personality"],
                "limits": change["limits"], "mandate_terms": change["mandate_terms"],
                "document_id": manual.document_id, "manual_version": manual.version,
                "manual_sha256": manual.sha256, "manual_effective_date": manual.effective_date,
                "acknowledgement_sha256": ACKNOWLEDGEMENT_SHA256, "acknowledgement_checked": True,
                "pages_reviewed": [{"page_id": pid, "page_sha256": review["pages"][pid]["page_sha256"],
                                    "method": review["pages"][pid]["method"],
                                    "reviewed_at_utc": review["pages"][pid]["reviewed_at_utc"]}
                                   for pid in manual.page_ids],
                "accepted_at_utc": _iso(now), "effective_from_utc": _iso(now),
            }
            # (a) evidence first: an acceptance record without activation is harmless
            record = self.ledger.append("ACCEPTED", body)
            change["status"] = "ACCEPTED"
            review["status"] = "COMPLETED"
            self._write_state(state)
            # (b) mandate, if any
            mandate_id = None
            try:
                if change["mandate_terms"]:
                    t = change["mandate_terms"]
                    mandate = self.mandates.authorize(
                        follower_user_id=user_id, trader_id=t["trader_id"], personality=personality,
                        asset_classes=tuple(t["asset_classes"]), max_allocation=t["max_allocation"],
                        currency=t["currency"], valid_days=t["valid_days"],
                        reauthorization_policy=ReauthorizationPolicy(t["reauthorization_policy"]),
                        reauthorization_interval_hours=t["reauthorization_interval_hours"],
                        session_id=auth_session_hash, now=now)
                    if mandate_terms_from_mandate(mandate) != t:
                        raise ConsentError("mandate_terms_mismatch_after_authorization")
                    mandate_id = mandate.mandate_id
                # (c) activation references the acceptance record
                self.preferences.activate(user_id, ActiveSettings(
                    operating_mode=mode, risk_personality=personality, limits=limits, mandate_id=mandate_id,
                    policy_hash=change["policy_hash"], consent_record_hash=record["entry_hash"],
                    activated_at_utc=_iso(now)))
            except (MandateError, ConsentError) as exc:
                change["status"] = "ACTIVATION_FAILED"
                self._write_state(state)
                raise ConsentError(f"activation_failed:{exc}") from exc
            change["status"] = "ACTIVATED"
            self._write_state(state)
        return self.receipt_from_record(record, mandate_id=mandate_id)

    @staticmethod
    def receipt_from_record(record: Mapping[str, Any], *, mandate_id: str | None = None) -> dict[str, Any]:
        return {
            "receipt_id": record["receipt_id"], "record_hash": record["entry_hash"], "user_id": record["user_id"],
            "accepted_at_utc": record["accepted_at_utc"], "kind": record["kind"],
            "document": {"document_id": record["document_id"], "version": record["manual_version"],
                         "sha256": record["manual_sha256"], "effective_date": record["manual_effective_date"]},
            "acknowledgement_sha256": record["acknowledgement_sha256"], "policy_hash": record["policy_hash"],
            "operating_mode": record["operating_mode"], "risk_personality": record["risk_personality"],
            "limits": record["limits"], "mandate_terms": record["mandate_terms"], "mandate_id": mandate_id,
            "pages_reviewed": len(record["pages_reviewed"]),
            "live_trading_authorized": False,
        }

    # -- 5. verification -----------------------------------------------------------
    def verify_active(self, user_id: str, state: UserTradingState | None = None) -> tuple[bool, str]:
        try:
            state = state or self.preferences.get(user_id)
            active = state.active
            if active is None:
                return False, "consent_missing"
            records = self.ledger.records()
            record = next((r for r in records if r["entry_hash"] == active.consent_record_hash), None)
            if record is None or record.get("record_type") != "ACCEPTED":
                return False, "consent_record_missing"
            if record["user_id"] != user_id:
                return False, "consent_user_mismatch"
            if record["policy_hash"] != active.policy_hash:
                return False, "consent_policy_mismatch"
            terms = None
            if active.mandate_id:
                mandate = self.mandates.get(active.mandate_id)
                if mandate is None:
                    return False, "consent_mandate_missing"
                terms = mandate_terms_from_mandate(mandate)
            if policy_hash(active.operating_mode, active.risk_personality, active.limits, terms) != active.policy_hash:
                return False, "active_settings_tampered"
            if record["acknowledgement_sha256"] != ACKNOWLEDGEMENT_SHA256:
                return False, "consent_acknowledgement_outdated"
            if self._manual().renewal_required(record["manual_version"]):
                return False, "consent_renewal_required"
        except (ConsentError, MandateError, ValueError, KeyError) as exc:
            return False, f"consent_unverifiable:{exc}"
        return True, "consent_valid"

    def receipts(self, user_id: str) -> list[dict[str, Any]]:
        return [self.receipt_from_record(r) for r in self.ledger.records()
                if r.get("record_type") == "ACCEPTED" and r["user_id"] == user_id]

    def pending_change(self, user_id: str, change_id: str) -> dict[str, Any]:
        change = self._read_state()["changes"].get(change_id)
        if change is None or change["user_id"] != user_id:
            raise ConsentError("change_not_found")
        return change
