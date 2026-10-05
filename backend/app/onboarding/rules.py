"""CSS Trader Passport: recommendation rules (Issue #102).

Turns recorded answers into a Trader Passport. Every output item carries `because`: the question ids and answers it
was derived from, so the Passport is fully explainable and auditable.

Deliberately absent:
- No suitability percentage or composite "potential" score.
- No AUTO recommendation. AUTO interest is recorded and acknowledged, never recommended; automated execution is a
  separate governed authorisation outside this module.
- No execution authority. `execution_authority_granted` is always False and there is no code path that changes it.
- No validation of unrealistic expectations: mismatches produce calibration messages, never a higher score.

Risk capacity (what finances can absorb) and risk tolerance (comfort with swings) are computed separately and never
averaged. The effective planning posture is the lower of the two.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .engine import answer_values, quiz_feedback, visible_stages
from .schema import QUESTION_INDEX, QUESTIONNAIRE_VERSION

RULES_VERSION = "TP-R-1.0.0"
LEVELS = ["LOW", "MODERATE", "HIGHER"]
BAND_ORDER = ["none", "beginner", "intermediate", "experienced"]
COMPLEX_TOPICS = {"leverage", "margin"}
CORE_TOPICS = {"order_types", "stop_orders", "position_sizing", "risk_reward", "volatility", "drawdown",
               "diversification", "portfolio_exposure"}
TOPIC_LABELS = {
    "order_types": "Market vs limit orders", "stop_orders": "Stop orders", "position_sizing": "Position sizing",
    "risk_reward": "Risk and reward", "volatility": "Volatility", "drawdown": "Drawdown",
    "diversification": "Diversification", "portfolio_exposure": "Portfolio exposure", "leverage": "Leverage",
    "margin": "Margin",
}
EDUCATION_MODULES = {t: f"CSS Learn: {l}" for t, l in TOPIC_LABELS.items()}


def _label(qid: str, value: Any) -> Any:
    q = QUESTION_INDEX[qid][1]
    labels = {o["value"]: o["label"] for o in q.get("options", [])}
    if isinstance(value, list):
        return [labels.get(v, v) for v in value]
    if isinstance(value, dict):
        rows = {r["value"]: r["label"] for r in q.get("rows", [])}
        return {rows.get(k, k): labels.get(v, v) for k, v in value.items()}
    return labels.get(value, value)


def _because(a: Dict[str, Any], *qids: str) -> List[dict]:
    return [{"question_id": q, "answer": _label(q, a[q])} for q in qids if q in a]


def _min_level(*levels: str) -> str:
    return min(levels, key=LEVELS.index)


# ------------------------------------------------------------------ components
def experience(a: Dict[str, Any]) -> dict:
    by = a.get("experience_by_class", {})
    top = max(by.values(), key=BAND_ORDER.index) if by else "none"
    return {"overall": top, "by_class": by, "because": _because(a, "experience_by_class")}


def knowledge(session: dict) -> dict:
    fb = quiz_feedback(session)
    demonstrated = sorted({f["topic"] for f in fb if f["result"] == "correct"})
    gaps = sorted({f["topic"] for f in fb if f["result"] != "correct"})
    return {"demonstrated": [TOPIC_LABELS[t] for t in demonstrated], "gaps": [TOPIC_LABELS[t] for t in gaps],
            "gap_topics": gaps, "assessed_topics": sorted({f["topic"] for f in fb}),
            "because": [{"question_id": f["question_id"], "answer": f["result"]} for f in fb]}


def strengths(a: Dict[str, Any], know: dict) -> dict:
    self_reported = _label("strengths", a.get("strengths", []))
    demonstrated = []
    if a.get("bh_exit_rule") == "always":
        demonstrated.append({"attribute": "Plans exits in advance", "because": _because(a, "bh_exit_rule")})
    if a.get("bh_after_losses") in ("pause_review", "continue_plan"):
        demonstrated.append({"attribute": "Steady after losing streaks", "because": _because(a, "bh_after_losses")})
    if len(know["demonstrated"]) >= 6:
        demonstrated.append({"attribute": "Solid grasp of trading basics",
                             "because": [{"question_id": "knowledge_check",
                                          "answer": f"{len(know['demonstrated'])} topics answered correctly"}]})
    return {"self_reported": self_reported, "indicated_by_answers": demonstrated,
            "because": _because(a, "strengths"),
            "note": "Self-reported strengths are your own description; the others follow from your answers."}


def risk_capacity(a: Dict[str, Any]) -> dict:
    limits = []
    dep = a.get("rc_living_dependence")
    if dep == "yes":
        limits.append(("LOW", "rc_living_dependence", "Losing this money would affect living expenses."))
    elif dep == "somewhat":
        limits.append(("MODERATE", "rc_living_dependence", "Losing this money would partly affect living expenses."))
    ef = a.get("rc_emergency_fund")
    if ef == "no":
        limits.append(("LOW", "rc_emergency_fund", "No separate emergency savings."))
    elif ef == "yes_lt6m":
        limits.append(("MODERATE", "rc_emergency_fund", "Emergency savings cover less than six months."))
    hz = a.get("rc_horizon")
    if hz == "lt_1y":
        limits.append(("LOW", "rc_horizon", "The money may be needed within a year."))
    elif hz == "1_3y":
        limits.append(("MODERATE", "rc_horizon", "The money may be needed within three years."))
    ml = a.get("rc_max_loss")
    if ml == "lt_5":
        limits.append(("LOW", "rc_max_loss", "A fall of more than 5% would change life plans."))
    elif ml == "5_15":
        limits.append(("MODERATE", "rc_max_loss", "A fall of more than 15% would change life plans."))
    level = _min_level("HIGHER", *[l for l, _, _ in limits])
    return {"level": level, "limiting_factors": [msg for _lvl, _qid, msg in limits],
            "because": _because(a, "rc_capital_band", "rc_living_dependence", "rc_emergency_fund", "rc_horizon",
                                "rc_max_loss"),
            "note": "Capacity is set by the most limiting factor, not an average."}


TOLERANCE_ITEMS = ["rt_volatility", "rt_temporary_loss", "rt_consecutive_losses", "rt_uncertainty",
                   "rt_concentration", "rt_leverage"]


def risk_tolerance(a: Dict[str, Any]) -> dict:
    points = {"uncomfortable": 0, "acceptable": 1, "comfortable": 2}
    vals = [points[a[q]] for q in TOLERANCE_ITEMS if q in a]
    total = sum(vals)
    level = "LOW" if total <= 4 else ("MODERATE" if total <= 8 else "HIGHER")
    return {"level": level, "because": _because(a, *TOLERANCE_ITEMS),
            "note": "Tolerance reflects comfort with swings and losses, in six answers (0–12 points banded "
                    "0–4 low, 5–8 moderate, 9–12 higher). It is a band, not a precise measure."}


def behaviour(a: Dict[str, Any]) -> List[dict]:
    out = []
    if a.get("bh_size_after_loss") in ("sometimes", "often") or a.get("bh_after_losses") == "trade_more" \
            or a.get("bh_drawdown_reaction") == "add_more":
        out.append({"consideration": "Risk of chasing losses",
                    "support": "CSS will show position-size reminders after losing trades and flag size increases.",
                    "because": _because(a, "bh_size_after_loss", "bh_after_losses", "bh_drawdown_reaction")})
    if a.get("bh_time_pressure") == "stressful":
        out.append({"consideration": "Prefers time to decide",
                    "support": "Favour longer holding periods and alerts with wider decision windows.",
                    "because": _because(a, "bh_time_pressure")})
    if a.get("bh_exit_rule") == "rarely":
        out.append({"consideration": "Exits not usually planned in advance",
                    "support": "Trade Cards show a stop and target up front; the journal prompts for an exit plan.",
                    "because": _because(a, "bh_exit_rule")})
    if a.get("bh_strategy_switch") == "often":
        out.append({"consideration": "Changes strategy quickly",
                    "support": "Analytics show results over a meaningful sample before suggesting changes.",
                    "because": _because(a, "bh_strategy_switch")})
    if a.get("bh_drawdown_reaction") == "exit_all":
        out.append({"consideration": "May exit everything in a sharp fall",
                    "support": "Start smaller so normal swings stay within your comfort.",
                    "because": _because(a, "bh_drawdown_reaction")})
    return out


# ------------------------------------------------------------------ expectations calibration
def expectations_calibration(a: Dict[str, Any], know: dict, cap: dict) -> List[dict]:
    flags = []

    def add(code, severity, message, action, *qids):
        flags.append({"code": code, "severity": severity, "message": message, "action": action,
                      "because": _because(a, *qids)})

    if a.get("bl_every_trade_profitable") is True or "every_trade_wins" in a.get("ex_success", []):
        add("ZERO_LOSS_EXPECTATION", "major",
            "No approach makes every trade profitable. Losing trades are a normal part of trading, including on "
            "CSS recommendations.", "education:expectations", "bl_every_trade_profitable", "ex_success")
    if a.get("bl_losses_possible") is False:
        add("LOSSES_NOT_EXPECTED", "major",
            "You can lose money, including on trades CSS recommends. CSS does not guarantee profit.",
            "education:expectations", "bl_losses_possible")
    if a.get("bl_auto_guarantees") is True or a.get("auto_understanding") in ("guaranteed", "no_risk"):
        add("AUTO_MISUNDERSTANDING", "major",
            "Automation changes how trades are placed, not market risk. Automated trades can lose money.",
            "education:auto_mode", "bl_auto_guarantees", "auto_understanding")
    if a.get("bl_css_compensates") is True:
        add("COMPENSATION_EXPECTATION", "major",
            "CSS does not pay back trading losses. Gains and losses in your account are yours.",
            "education:expectations", "bl_css_compensates")
    if a.get("ex_return_range") == "double_plus":
        add("UNREALISTIC_RETURN", "major",
            "Aiming to double your money in a year usually needs very high risk, which also makes large losses "
            "likely. CSS will not tune itself to that target.", "education:returns_and_risk", "ex_return_range")
    if a.get("ex_drawdown") == "none":
        add("ZERO_DRAWDOWN_EXPECTATION", "major",
            "Every trading approach has periods where the account falls. Expecting none at all isn't realistic.",
            "education:drawdown", "ex_drawdown")
    if a.get("ex_risk") == "high" and cap["level"] == "LOW":
        add("RISK_EXCEEDS_CAPACITY", "major",
            "You expect to take high risk, but your answers show this money can't absorb large losses. CSS will "
            "plan around your capacity.", "mode:stricter", "ex_risk", "rc_living_dependence", "rc_emergency_fund")
    if a.get("ex_trade_frequency") == "many_daily" and a.get("monitoring_availability") != "within_minutes":
        add("FREQUENCY_TIME_MISMATCH", "minor",
            "Many trades a day needs quick responses. With your availability, fewer, longer trades fit better.",
            "education:pacing", "ex_trade_frequency", "monitoring_availability")
    wants_complex = any(m in a.get("preferred_markets", []) for m in ("options", "futures")) \
        or a.get("uses_leverage") in ("small", "yes")
    if wants_complex and COMPLEX_TOPICS & set(know["gap_topics"]):
        add("LEVERAGE_KNOWLEDGE_GAP", "major",
            "Leveraged or complex products can lose more than expected quickly. Learn leverage and margin and "
            "practise in the simulator first.", "simulation:first", "preferred_markets", "uses_leverage",
            "kq_leverage", "kq_margin_call")
    if a.get("rc_living_dependence") == "yes" and "supplement" in a.get("objective_ranking", [])[:1]:
        add("INCOME_DEPENDENCE", "major",
            "Money needed for living expenses shouldn't depend on trading results.", "mode:stricter",
            "rc_living_dependence", "objective_ranking")
    return flags


# ------------------------------------------------------------------ mode
def recommend_mode(a: Dict[str, Any], exp: dict, know: dict, cap: dict, tol: dict, flags: List[dict]) -> dict:
    reasons, because = [], []
    major = [f for f in flags if f["severity"] == "major"]
    core_gaps = set(know["gap_topics"]) & CORE_TOPICS
    markets = a.get("preferred_markets", [])
    exp_in_markets = [exp["by_class"].get(m, "none") for m in markets]
    experienced_somewhere = any(BAND_ORDER.index(b) >= 2 for b in exp_in_markets)

    blocked = []
    if not experienced_somewhere:
        blocked.append("Intermediate or better experience in a market you chose is needed for Confirm.")
    if len(core_gaps) > 2:
        blocked.append("Several core topics to learn first.")
    if major:
        blocked.append("Some expectations need calibrating first: " + ", ".join(f["code"] for f in major) + ".")
    if cap["level"] == "LOW":
        blocked.append("Your risk capacity is low, so CSS keeps you in control of every decision.")
    mode = "DISCOVER" if blocked else "CONFIRM"
    reasons = blocked or ["Experience in your chosen markets, solid core knowledge and realistic expectations."]
    because = _because(a, "experience_by_class", "preferred_markets", "assistance_preference")
    simulation_first = (exp["overall"] in ("none", "beginner")) or bool(core_gaps) or \
        any(f["action"] == "simulation:first" for f in flags)
    pref = a.get("assistance_preference")
    note = None
    if pref == "auto_interest":
        note = ("Your interest in Auto is recorded. Automated execution is a separate, governed authorisation; it is "
                "not granted by this questionnaire and is available only where legally, operationally and "
                "technically permitted.")
    elif pref == "confirm" and mode == "DISCOVER":
        note = "You asked for Confirm. CSS suggests starting in Discover for the reasons shown; you can revisit later."
    return {"recommended": mode, "user_preference": pref, "reasons": reasons, "simulation_first": simulation_first,
            "auto_interest_recorded": pref == "auto_interest", "note": note, "because": because}


def education_plan(know: dict, flags: List[dict], mode: dict) -> List[dict]:
    plan = [{"item": EDUCATION_MODULES[t], "why": f"Knowledge check: {TOPIC_LABELS[t]}"} for t in know["gap_topics"]]
    for f in flags:
        if f["action"].startswith("education:"):
            plan.append({"item": "CSS Learn: " + f["action"].split(":", 1)[1].replace("_", " ").title(),
                         "why": f["code"]})
    if mode["simulation_first"]:
        plan.append({"item": "Paper trading in the CSS simulator", "why": "Practise before using real money"})
    seen, out = set(), []
    for p in plan:
        if p["item"] not in seen:
            seen.add(p["item"]); out.append(p)
    return out


# ------------------------------------------------------------------ passport
def build_passport(session: dict) -> dict:
    a = answer_values(session)
    exp = experience(a)
    know = knowledge(session)
    cap = risk_capacity(a)
    tol = risk_tolerance(a)
    flags = expectations_calibration(a, know, cap)
    mode = recommend_mode(a, exp, know, cap, tol, flags)
    posture = _min_level(cap["level"], tol["level"])
    return {
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "rules_version": RULES_VERSION,
        "preferred_name": a.get("display_name"),
        "experience": exp,
        "strengths": strengths(a, know),
        "knowledge": know,
        "risk_capacity": cap,
        "risk_tolerance": tol,
        "risk_posture": {"level": posture,
                         "mismatch": cap["level"] != tol["level"],
                         "note": ("Your comfort with risk is higher than your finances can absorb; CSS plans around "
                                  "capacity." if LEVELS.index(tol["level"]) > LEVELS.index(cap["level"]) else
                                  "Your finances could absorb more risk than you're comfortable with; CSS plans around "
                                  "your comfort." if LEVELS.index(tol["level"]) < LEVELS.index(cap["level"]) else
                                  "Capacity and tolerance agree.")},
        "behavioural_considerations": behaviour(a),
        "preferred_markets": _label("preferred_markets", a.get("preferred_markets", [])),
        "holding_periods": _label("holding_periods", a.get("holding_periods", [])),
        "engagement": {k: _label(k, a[k]) for k in ("engagement_cadence", "monitoring_availability",
                                                     "notification_preference") if k in a},
        "barriers": _label("barriers", a.get("barriers", [])),
        "priorities": _label("objective_ranking", a.get("objective_ranking", [])),
        "expectations_calibration": flags,
        "education_plan": education_plan(know, flags, mode),
        "mode": mode,
        "feature_preferences": _label("feature_preferences", a.get("feature_preferences", [])),
        "stages_answered": [s["id"] for s in visible_stages(session["answers"]) if s["kind"] != "result"],
        "execution_authority_granted": False,
        "authority_note": ("This Passport is guidance. It grants no execution authority and does not change any CSS "
                           "trading mode, broker setting or governance gate."),
        "legal_acceptance_note": ("Onboarding acknowledgements are not acceptance of the CSS Terms or the Trading Risk "
                                  "Disclosure; those are recorded separately by CSS compliance."),
    }
