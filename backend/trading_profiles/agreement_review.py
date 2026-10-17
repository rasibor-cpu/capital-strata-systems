"""Operating agreement review with a single final acceptance (CLI now; same model for web/mobile).

The reader moves freely through the pages with next / previous. Nothing is accepted per page:
a page counts as reviewed once it has been displayed in full and the reader moves past it.
Acceptance is ONE explicit action, offered only after every page has been reviewed, on a final
screen that shows exactly what is being accepted: agreement version and content hash, operator,
operating mode, risk personality, limits and the policy hash. Declining is recorded.

All protections stay in ConsentService (server side): the review is bound to the session and the
current manual version; pages must be presented before they can be reviewed; accept() rejects
incomplete reviews, expired (stale) proposals or reviews, an altered manual or page, tampered
pending settings and a policy hash different from the one shown. This class only removes the
per-page confirmation step.

One review may feed several consent ledgers (e.g. the two isolated simulation tracks): every page
is presented to all of them at the same moment from the same single display, and the single
acceptance is recorded in each, with the same agreement_session_id. All ledgers must be showing
the same manual content and settings, otherwise the review refuses to start.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from backend.trading_profiles.consent import ConsentError, ConsentService
from backend.trading_profiles.manual import ACKNOWLEDGEMENT_SHA256, ACKNOWLEDGEMENT_TEXT

REVIEWING, ACCEPTED, DECLINED = "REVIEWING", "ACCEPTED", "DECLINED"


class AgreementReview:
    def __init__(self, services: Sequence[ConsentService], *, user_id: str, auth_session_hash: str, operator_id: str,
                 operating_mode: str, risk_personality: str | None, limits: Mapping[str, Any] | None = None,
                 review_method: str = "non_scrollable_presented",
                 clock: Callable[[], datetime] | None = None,
                 run_bindings: Sequence[str | None] | None = None) -> None:
        if not services:
            raise ConsentError("no_consent_service")
        if not str(operator_id or "").strip():
            raise ConsentError("operator_required")
        self.services = list(services)
        # Optional per-ledger run binding (e.g. a simulation run root), recorded in each acceptance.
        self.run_bindings = list(run_bindings) if run_bindings is not None else [None] * len(self.services)
        if len(self.run_bindings) != len(self.services):
            raise ConsentError("run_bindings_mismatch")
        self.user_id, self.session, self.operator_id = user_id, auth_session_hash, str(operator_id).strip()
        self.method = review_method
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.agreement_session_id = "agr-" + secrets.token_hex(10)
        self.status, self.receipts, self.decline_reason = REVIEWING, [], None
        now = self.clock()
        self.changes = [s.propose_change(user_id, operating_mode=operating_mode, risk_personality=risk_personality,
                                         limits=dict(limits) if limits else None, mandate_request=None, now=now)
                        for s in self.services]
        if len({c.policy_hash for c in self.changes}) != 1:
            raise ConsentError("settings_differ_between_ledgers")
        manuals = [s.manual_provider() for s in self.services]
        if len({(m.version, m.sha256) for m in manuals}) != 1:
            raise ConsentError("agreement_differs_between_ledgers")
        self.manual = manuals[0]
        self.reviews = [s.open_review(user_id, auth_session_hash=auth_session_hash, change_id=c.change_id, now=now)
                        for s, c in zip(self.services, self.changes)]
        self.page_ids = list(self.manual.page_ids)
        self.position = 0  # 0..len(pages)-1 = a page; len(pages) = final acceptance screen
        self.reviewed: set[str] = set()
        self._shown: dict[str, dict] = {}

    # -- navigation ------------------------------------------------------------------
    @property
    def total(self) -> int:
        return len(self.page_ids)

    @property
    def at_final_screen(self) -> bool:
        return self.position >= self.total

    @property
    def complete(self) -> bool:
        return self.reviewed == set(self.page_ids)

    def page(self) -> dict:
        """Present the current page (recorded server-side in every ledger) and return it for display."""
        self._open()
        if self.at_final_screen:
            raise ConsentError("no_page_at_final_screen")
        pid, now = self.page_ids[self.position], self.clock()
        shown = [s.present_page(self.user_id, auth_session_hash=self.session, review_id=r.review_id, page_id=pid, now=now)
                 for s, r in zip(self.services, self.reviews)]
        if len({p["sha256"] for p in shown}) != 1:
            raise ConsentError("page_differs_between_ledgers")
        self._shown[pid] = shown[0]
        return dict(shown[0], reviewed=pid in self.reviewed)

    def next(self) -> None:
        """Move on. The page being left counts as reviewed only if it was displayed in full."""
        self._open()
        if self.at_final_screen:
            return
        pid = self.page_ids[self.position]
        shown = self._shown.get(pid)
        if shown is None:
            raise ConsentError("page_not_presented")
        if pid not in self.reviewed:
            now = self.clock()
            for s, r in zip(self.services, self.reviews):
                s.mark_reviewed(self.user_id, auth_session_hash=self.session, review_id=r.review_id, page_id=pid,
                                method=self.method, page_sha256=shown["sha256"], now=now)
            self.reviewed.add(pid)
        self.position += 1

    def previous(self) -> None:
        self._open()
        self.position = max(0, self.position - 1)

    # -- final screen --------------------------------------------------------------------
    def summary(self) -> dict:
        """Everything the single acceptance covers, shown on the final screen."""
        change = self.changes[0]
        return {
            "document_id": self.manual.document_id, "agreement_version": self.manual.version,
            "agreement_sha256": self.manual.sha256, "effective_date": self.manual.effective_date,
            "pages_total": self.total, "pages_reviewed": len(self.reviewed),
            "operator_id": self.operator_id, "operating_mode": change.operating_mode,
            "risk_personality": change.risk_personality, "limits": change.limits,
            "effective_settings": change.effective_settings, "implications": list(change.implications),
            "policy_hash": change.policy_hash, "acknowledgement_text": ACKNOWLEDGEMENT_TEXT,
            "agreement_session_id": self.agreement_session_id, "ledgers": len(self.services),
            "live_trading_authorized": False,
        }

    def accept(self, *, acknowledged: bool, policy_hash_shown: str) -> list[dict]:
        """The one explicit acceptance. Rejected unless every page was reviewed (server re-checks)."""
        self._open()
        if not self.complete:
            missing = [p for p in self.page_ids if p not in self.reviewed]
            raise ConsentError("pages_not_reviewed:" + ",".join(missing))
        now = self.clock()
        receipts = []
        for s, r, binding in zip(self.services, self.reviews, self.run_bindings):
            receipts.append(s.accept(
                self.user_id, auth_session_hash=self.session, review_id=r.review_id,
                acknowledgement_checked=acknowledged is True, acknowledgement_sha256=ACKNOWLEDGEMENT_SHA256,
                manual_version=self.manual.version, manual_sha256=self.manual.sha256,
                policy_hash_shown=policy_hash_shown, now=now, operator_id=self.operator_id,
                agreement_session_id=self.agreement_session_id, run_binding=binding))
        self.status, self.receipts = ACCEPTED, receipts
        return receipts

    def decline(self, reason: str = "declined_by_operator") -> None:
        self._open()
        now = self.clock()
        for s, r in zip(self.services, self.reviews):
            s.decline(self.user_id, auth_session_hash=self.session, review_id=r.review_id, reason=reason,
                      operator_id=self.operator_id, agreement_session_id=self.agreement_session_id, now=now)
        self.status, self.decline_reason = DECLINED, reason

    def _open(self) -> None:
        if self.status != REVIEWING:
            raise ConsentError(f"agreement_review_closed:{self.status}")
