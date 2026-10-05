"""CSS Trader Passport: service layer (Issue #102).

Coordinates engine, rules and store for one authenticated user. Every completed Passport and every later profile
update is kept as an append-only revision with the questionnaire version, rules version and full answer provenance.
"""
from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import engine
from .rules import RULES_VERSION, build_passport
from .schema import QUESTION_INDEX, QUESTIONNAIRE_VERSION, public_schema
from .store import OnboardingStore, user_key

log = logging.getLogger("css.onboarding.service")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnboardingService:
    def __init__(self, store: Optional[OnboardingStore] = None):
        self.store = store or OnboardingStore()

    # ------------------------------------------------------------ load / save
    def _doc(self, username: str) -> tuple[str, dict]:
        key = user_key(username)
        doc = self.store.load(key)
        if doc is None:
            doc = {"session": engine.new_session(key), "passport": None, "revisions": []}
            self.store.save(key, doc)
        return key, doc

    def _save(self, key: str, doc: dict) -> None:
        self.store.save(key, doc)

    # ------------------------------------------------------------ views
    def view(self, username: str) -> dict:
        _, doc = self._doc(username)
        return self._view(doc)

    @staticmethod
    def _view(doc: dict) -> dict:
        s = doc["session"]
        stage = next(st for st in public_schema()["stages"] if st["id"] == s["current_stage"])
        current_answers = {q["id"]: s["answers"][q["id"]]["value"]
                           for q in stage.get("questions", []) if q["id"] in s["answers"]}
        return {"status": s["status"], "questionnaire_version": s["questionnaire_version"],
                "rules_version": RULES_VERSION, "stage": stage, "answers": current_answers,
                "progress": engine.progress(s), "passport": doc.get("passport"),
                "revision_count": len(doc.get("revisions", [])),
                "missing_required": engine.missing_required(s) if s["current_stage"] == "passport" else []}

    # ------------------------------------------------------------ flow
    def submit(self, username: str, stage_id: str, values: Dict[str, Any]) -> dict:
        key, doc = self._doc(username)
        engine.submit_stage(doc["session"], stage_id, values)
        self._save(key, doc)
        return self._view(doc)

    def back(self, username: str) -> dict:
        key, doc = self._doc(username)
        engine.go_back(doc["session"])
        self._save(key, doc)
        return self._view(doc)

    def complete(self, username: str) -> dict:
        key, doc = self._doc(username)
        s = doc["session"]
        if s["current_stage"] != "passport":
            raise engine.OnboardingError({"stage": "Finish the remaining steps first."})
        missing = engine.missing_required(s)
        if missing:
            raise engine.OnboardingError({m: "This answer is required." for m in missing})
        passport = build_passport(s)
        self._record_revision(doc, passport, reason="onboarding_complete" if not doc["revisions"] else "profile_review")
        s["status"] = "complete"
        self._save(key, doc)
        return self._view(doc)

    def update_profile(self, username: str, values: Dict[str, Any]) -> dict:
        """Change answers after completion (e.g. new experience, new contact details). Each change keeps its
        provenance; the Passport is recomputed and stored as a new revision. If the change reveals a step that now
        needs answers (e.g. switching to Auto interest), the user is sent to that step instead."""
        key, doc = self._doc(username)
        s = doc["session"]
        if doc.get("passport") is None:
            raise engine.OnboardingError({"profile": "Complete onboarding before updating your profile."})
        errors, clean = {}, {}
        for qid, v in values.items():
            if qid not in QUESTION_INDEX:
                errors[qid] = "Unknown question."
                continue
            stage_id, q = QUESTION_INDEX[qid]
            if q["type"] == "consent" and q.get("must_be_true"):
                errors[qid] = "Acknowledgements can't be withdrawn here."
                continue
            nv, err = engine.validate_answer(q, v)
            if err:
                errors[qid] = err
            else:
                clean[qid] = (stage_id, nv)
        if errors:
            raise engine.OnboardingError(errors)
        for qid, (stage_id, nv) in clean.items():
            prev = s["answers"].get(qid)
            if nv is None:
                if prev:
                    del s["answers"][qid]
                continue
            rec = {"value": nv, "answered_at": _now(), "stage_id": stage_id,
                   "questionnaire_version": QUESTIONNAIRE_VERSION, "source": "profile_update"}
            if prev:
                rec["previous_answered_at"] = prev["answered_at"]
            s["answers"][qid] = rec
        engine._prune_hidden(s)
        missing = engine.missing_required(s)
        if missing:
            first_stage = QUESTION_INDEX[missing[0]][0]
            s["current_stage"], s["status"] = first_stage, "reviewing"
            engine._event(s, "profile_update_needs_answers", stage_id=first_stage)
        else:
            self._record_revision(doc, build_passport(s), reason="profile_update",
                                  changed=sorted(clean))
            s["status"] = "complete"
        engine._event(s, "profile_updated", questions=sorted(clean))
        self._save(key, doc)
        return self._view(doc)

    def history(self, username: str) -> list:
        _, doc = self._doc(username)
        return [{k: r[k] for k in ("revision", "created_at", "reason", "questionnaire_version", "rules_version",
                                   "changed")} for r in doc.get("revisions", [])]

    @staticmethod
    def _record_revision(doc: dict, passport: dict, reason: str, changed=None) -> None:
        rev = {"revision": len(doc["revisions"]) + 1, "created_at": _now(), "reason": reason,
               "questionnaire_version": QUESTIONNAIRE_VERSION, "rules_version": RULES_VERSION,
               "changed": changed or [], "answers": copy.deepcopy(doc["session"]["answers"]),
               "passport": passport}
        doc["revisions"].append(rev)
        doc["passport"] = passport
