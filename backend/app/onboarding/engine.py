"""CSS Trader Passport: questionnaire engine (Issue #102).

A session is plain data (a dict) so it can be persisted, resumed and audited. The engine:
- decides which stages are visible from the answers given so far (adaptive branching);
- validates answers per question type (fail closed: anything unrecognised is rejected);
- records answer provenance (value, timestamp, stage, questionnaire version, source, and the previous value on change);
- supports back navigation and resume;
- drops answers to stages that a later change made invisible, recording that it did so.

It never touches execution, runtime mode, broker or governance state.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .schema import QUESTION_INDEX, QUESTIONNAIRE_ID, QUESTIONNAIRE_VERSION, SENSITIVE_QUESTION_IDS, STAGES

log = logging.getLogger("css.onboarding.engine")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,24}$")
PHONE_RE = re.compile(r"^\+[1-9][0-9 ()\-]{6,20}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class OnboardingError(ValueError):
    """Invalid answer or navigation request. `errors` maps question id to a user-facing message."""

    def __init__(self, errors: Dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- branching
def condition_met(cond: Optional[dict], answers: Dict[str, Any]) -> bool:
    if not cond:
        return True
    if "any_of" in cond:
        return any(condition_met(c, answers) for c in cond["any_of"])
    if "all_of" in cond:
        return all(condition_met(c, answers) for c in cond["all_of"])
    if "not" in cond:
        return not condition_met(cond["not"], answers)
    value = answers.get(cond["q"], {}).get("value") if cond.get("q") in answers else None
    if value is None:
        return False
    if "in" in cond:
        return value in cond["in"]
    if "includes_any" in cond:
        return isinstance(value, list) and any(v in value for v in cond["includes_any"])
    if "row_in" in cond:
        rows, values = cond["row_in"]["rows"], cond["row_in"]["values"]
        return isinstance(value, dict) and any(value.get(r) in values for r in rows)
    raise ValueError(f"unknown condition {cond!r}")      # fail closed on schema errors


def visible_stages(answers: Dict[str, Any]) -> List[dict]:
    return [s for s in STAGES if condition_met(s.get("show_if"), answers)]


# ---------------------------------------------------------------- validation
def _option_values(q: dict) -> List[str]:
    return [o["value"] for o in q.get("options", [])]


def validate_answer(q: dict, value: Any) -> Tuple[Any, Optional[str]]:
    """Return (normalised value, error or None)."""
    t, required = q["type"], q.get("required", False)
    empty = value is None or value == "" or value == [] or value == {}
    if empty:
        if q.get("must_be_true"):
            return None, "Please confirm to continue."
        return (None, "This answer is required.") if required else (None, None)
    if t in ("text",):
        if not isinstance(value, str):
            return None, "Expected text."
        v = " ".join(value.split())
        if CONTROL_RE.search(value):
            return None, "Contains characters that aren't allowed."
        if len(v) < q.get("min_len", 0) or len(v) > q.get("max_len", 200):
            return None, f"Use {q.get('min_len', 0)}–{q.get('max_len', 200)} characters."
        return v, None
    if t == "email":
        v = str(value).strip()
        return (v.lower(), None) if EMAIL_RE.match(v) else (None, "Enter a valid email address.")
    if t == "phone":
        v = str(value).strip()
        return (v, None) if PHONE_RE.match(v) else (None, "Use international format starting with +.")
    if t == "country":
        v = str(value).strip().upper()
        return (v, None) if COUNTRY_RE.match(v) else (None, "Choose a country or region.")
    if t == "consent":
        if not isinstance(value, bool):
            return None, "Expected yes or no."
        if q.get("must_be_true") and value is not True:
            return None, "Please confirm to continue."
        return value, None
    if t == "boolean":
        return (value, None) if isinstance(value, bool) else (None, "Choose true or false.")
    if t in ("single", "quiz"):
        return (value, None) if value in _option_values(q) else (None, "Choose one of the options.")
    if t in ("multi", "rank"):
        if not isinstance(value, list) or len(set(value)) != len(value):
            return None, "Choose from the options."
        if any(v not in _option_values(q) for v in value):
            return None, "Choose from the options."
        lo, hi = q.get("min_select", 1 if required else 0), q.get("max_select", len(q.get("options", [])))
        if not lo <= len(value) <= hi:
            return None, (f"Choose exactly {lo}." if lo == hi else f"Choose between {lo} and {hi}.")
        return value, None
    if t == "matrix":
        rows = [r["value"] for r in q["rows"]]
        if not isinstance(value, dict) or set(value) != set(rows):
            return None, "Answer every row."
        if any(value[r] not in _option_values(q) for r in rows):
            return None, "Choose a band for every row."
        return {r: value[r] for r in rows}, None
    return None, f"Unsupported question type {t}."                # fail closed


# ---------------------------------------------------------------- session
def new_session(user_key: str) -> dict:
    return {"questionnaire_id": QUESTIONNAIRE_ID, "questionnaire_version": QUESTIONNAIRE_VERSION,
            "user_key": user_key, "created_at": _now(), "updated_at": _now(), "status": "in_progress",
            "current_stage": STAGES[0]["id"], "answers": {}, "events": []}


def _event(session: dict, kind: str, **data) -> None:
    # Events carry ids and timestamps only, never answer values, so they are safe to log.
    e = {"at": _now(), "kind": kind, **data}
    session["events"].append(e)
    log.info("onboarding event %s %s", kind, {k: v for k, v in data.items() if k != "value"})


def stage_by_id(stage_id: str) -> dict:
    for s in STAGES:
        if s["id"] == stage_id:
            return s
    raise OnboardingError({"stage": "Unknown stage."})


def progress(session: dict) -> dict:
    vis = [s for s in visible_stages(session["answers"]) if s["kind"] != "result"]
    ids = [s["id"] for s in vis]
    cur = session["current_stage"]
    pos = ids.index(cur) + 1 if cur in ids else len(ids)
    return {"position": pos, "total": len(ids), "stage_ids": ids}


def submit_stage(session: dict, stage_id: str, values: Dict[str, Any], source: str = "user") -> dict:
    """Validate and record every answer on one stage, then move to the next visible stage."""
    if session.get("questionnaire_version") != QUESTIONNAIRE_VERSION:
        raise OnboardingError({"questionnaire": "This onboarding was started on another questionnaire version."})
    if stage_id != session["current_stage"]:
        raise OnboardingError({"stage": "Answers must be for the current step."})
    stage = stage_by_id(stage_id)
    if stage["kind"] == "result":
        raise OnboardingError({"stage": "The result is computed, not answered."})
    unknown = set(values) - {q["id"] for q in stage.get("questions", [])}
    if unknown:
        raise OnboardingError({k: "Not a question on this step." for k in sorted(unknown)})
    errors, clean = {}, {}
    for q in stage.get("questions", []):
        v, err = validate_answer(q, values.get(q["id"]))
        if err:
            errors[q["id"]] = err
        elif v is not None:
            clean[q["id"]] = v
    if errors:
        raise OnboardingError(errors)
    for qid, v in clean.items():
        prev = session["answers"].get(qid)
        rec = {"value": v, "answered_at": _now(), "stage_id": stage_id,
               "questionnaire_version": QUESTIONNAIRE_VERSION, "source": source}
        if prev and prev["value"] != v:
            rec["previous_answered_at"] = prev["answered_at"]
            _event(session, "answer_changed", question_id=qid, sensitive=qid in SENSITIVE_QUESTION_IDS)
        session["answers"][qid] = rec
    for q in stage.get("questions", []):                       # optional answers cleared by the user
        if q["id"] not in clean and q["id"] in session["answers"]:
            del session["answers"][q["id"]]
            _event(session, "answer_cleared", question_id=q["id"])
    _prune_hidden(session)
    _event(session, "stage_submitted", stage_id=stage_id)
    session["current_stage"] = _next_stage_id(session, stage_id)
    session["updated_at"] = _now()
    return session


def _prune_hidden(session: dict) -> None:
    """Remove answers belonging to stages that are no longer visible (e.g. Auto check after switching to Discover)."""
    visible = {s["id"] for s in visible_stages(session["answers"])}
    for qid in list(session["answers"]):
        stage_id = QUESTION_INDEX.get(qid, (None,))[0]
        if stage_id not in visible:
            del session["answers"][qid]
            _event(session, "answer_removed_stage_hidden", question_id=qid, stage_id=stage_id)


def _next_stage_id(session: dict, after_id: str) -> str:
    order = [s["id"] for s in STAGES]
    visible = {s["id"] for s in visible_stages(session["answers"])}
    for sid in order[order.index(after_id) + 1:]:
        if sid in visible:
            return sid
    return "passport"


def go_back(session: dict) -> dict:
    vis = [s["id"] for s in visible_stages(session["answers"])]
    cur = session["current_stage"]
    if cur not in vis or vis.index(cur) == 0:
        return session
    session["current_stage"] = vis[vis.index(cur) - 1]
    if session["status"] == "complete":
        session["status"] = "reviewing"
    _event(session, "back", to_stage=session["current_stage"])
    session["updated_at"] = _now()
    return session


def missing_required(session: dict) -> List[str]:
    """Required questions on visible stages that still lack an answer."""
    out = []
    for s in visible_stages(session["answers"]):
        for q in s.get("questions", []):
            if q.get("required") and q["id"] not in session["answers"]:
                out.append(q["id"])
    return out


def answer_values(session: dict) -> Dict[str, Any]:
    return {k: v["value"] for k, v in session["answers"].items()}


def quiz_feedback(session: dict) -> List[dict]:
    """Per-question explanation after answering (never before)."""
    out = []
    for s in visible_stages(session["answers"]):
        for q in s.get("questions", []):
            if q["type"] == "quiz" and q["id"] in session["answers"]:
                a = session["answers"][q["id"]]["value"]
                out.append({"question_id": q["id"], "topic": q["topic"],
                            "result": "correct" if a == q["correct"] else ("not_sure" if a == "not_sure" else "review"),
                            "explain": q["explain"]})
    return out
