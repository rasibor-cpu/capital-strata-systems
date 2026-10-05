"""CSS Trader Passport (Issue #102): engine, rules, service and API tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.app.onboarding import engine
from backend.app.onboarding.engine import OnboardingError, condition_met, visible_stages
from backend.app.onboarding.rules import RULES_VERSION, build_passport
from backend.app.onboarding.schema import QUESTIONNAIRE_VERSION, STAGES, public_schema
from backend.app.onboarding.service import OnboardingService
from backend.app.onboarding.store import OnboardingStore, user_key

ALL_CLASSES = ["equities", "etfs", "fx", "crypto", "options", "futures"]

# A realistic, experienced user. Tests override single answers to probe each rule.
BASE = {
    "ack_risk_intro": True, "display_name": "Ada", "full_name": None, "email": "ada@example.com", "phone": None,
    "country": "CA", "preferred_channel": "in_app", "consent_service_notifications": True, "consent_marketing": False,
    "objectives": ["improve_process", "discipline"],
    "experience_by_class": {"equities": "experienced", "etfs": "intermediate", "fx": "none", "crypto": "none",
                            "options": "none", "futures": "none"},
    "kq_market_vs_limit": "b", "kq_stop": "b", "kq_position_size": "b", "kq_risk_reward": "b",
    "kq_volatility": "a", "kq_drawdown": "b", "kq_diversification": "b", "kq_exposure": "b",
    "kq_leverage": "b", "kq_margin_call": "b",
    "css_familiarity": "other_tools", "thinking_style": "pattern",
    "strengths": ["disciplined", "risk_aware"],
    "bh_decision_speed": "considered", "bh_after_losses": "pause_review", "bh_drawdown_reaction": "hold_plan",
    "bh_size_after_loss": "never", "bh_exit_rule": "always", "bh_strategy_switch": "rarely",
    "rc_capital_band": "10k_50k", "rc_living_dependence": "no", "rc_emergency_fund": "yes_6m", "rc_horizon": "gt_3y",
    "rc_max_loss": "15_30",
    "rt_volatility": "acceptable", "rt_temporary_loss": "acceptable", "rt_consecutive_losses": "acceptable",
    "rt_uncertainty": "acceptable", "rt_concentration": "acceptable", "rt_leverage": "uncomfortable",
    "barriers": ["time"], "preferred_markets": ["equities", "etfs"], "holding_periods": ["days", "weeks"],
    "uses_leverage": "no", "assistance_preference": "confirm", "auto_understanding": "mechanics_only",
    "feature_preferences": ["trade_cards", "analytics", "journal"], "support_level": "key_points",
    "learning_style": ["worked_examples", "practice"],
    "engagement_cadence": "daily", "monitoring_availability": "within_hours", "notification_preference": "important_only",
    "ex_primary_value": "understand", "ex_trade_frequency": "weekly", "ex_risk": "moderate", "ex_return_range": "modest",
    "ex_success": ["better_decisions", "discipline"],
    "bl_every_trade_profitable": False, "bl_losses_possible": True, "bl_drawdowns_normal": True, "bl_auto_guarantees": False,
    "bl_css_compensates": False,
    "objective_ranking": ["steady_growth", "long_term_wealth", "preservation"],
    "ack_attribution": True, "ack_no_guarantee": True, "ack_recommendation_not_authority": True,
    "ack_responsibility": True,
}


@pytest.fixture
def svc(tmp_path):
    return OnboardingService(OnboardingStore(tmp_path))


def walk(svc, user, persona, stop_before=None):
    """Answer every visible stage with the persona's answers. Returns the stage ids visited."""
    visited = []
    for _ in range(60):
        v = svc.view(user)
        stage = v["stage"]
        if stage["kind"] == "result" or stage["id"] == stop_before:
            return visited
        vals = {q["id"]: persona.get(q["id"]) for q in stage.get("questions", [])}
        svc.submit(user, stage["id"], vals)
        visited.append(stage["id"])
    raise AssertionError("flow did not terminate")


def complete(svc, user, **overrides):
    p = dict(BASE, **overrides)
    walk(svc, user, p)
    return svc.complete(user)["passport"]


# ---------------------------------------------------------------- schema
def test_schema_versions_and_unique_ids():
    ids = [s["id"] for s in STAGES]
    qids = [q["id"] for s in STAGES for q in s.get("questions", [])]
    assert len(ids) == len(set(ids)) and len(qids) == len(set(qids))
    assert QUESTIONNAIRE_VERSION and RULES_VERSION
    assert STAGES[-1]["kind"] == "result"


def test_public_schema_hides_answer_keys():
    blob = json.dumps(public_schema())
    assert '"correct"' not in blob and '"explain"' not in blob and '"realistic"' not in blob


def test_stage_count_is_adaptive_and_within_target():
    minimal = {"experience_by_class": {"value": {c: "none" for c in ALL_CLASSES}}, "objectives": {"value": ["learn"]},
               "preferred_markets": {"value": ["equities"]}, "assistance_preference": {"value": "discover"}}
    maximal = {"experience_by_class": {"value": {c: "beginner" for c in ALL_CLASSES}},
               "objectives": {"value": ["active_trading"]}, "preferred_markets": {"value": ["options"]},
               "assistance_preference": {"value": "auto_interest"}}
    n = lambda a: len([s for s in visible_stages(a) if s["kind"] != "result"])
    assert n(minimal) < n(maximal)
    decision = lambda a: len([s for s in visible_stages(a) if s["kind"] == "question"])
    assert 15 <= decision(minimal) < decision(maximal) <= 20     # directive: ~15-20 adaptive decision stages
    assert n(maximal) - decision(maximal) <= 5                    # plus a few short explanatory interstitials


def test_forbidden_language_absent():
    blob = json.dumps(public_schema()).lower()
    for phrase in ("guaranteed return", "replace your income", "quit your job", "passive income", "risk-free",
                   "limited time", "only today", "spots left", "testimonial"):
        assert phrase not in blob


# ---------------------------------------------------------------- progression / validation / navigation
def test_full_progression_and_passport(svc):
    p = complete(svc, "ada")
    assert p["questionnaire_version"] == QUESTIONNAIRE_VERSION and p["rules_version"] == RULES_VERSION
    assert p["preferred_name"] == "Ada"
    assert p["execution_authority_granted"] is False


def test_required_and_optional_answers(svc):
    with pytest.raises(OnboardingError) as e:
        svc.submit("u", "welcome", {"ack_risk_intro": False})
    assert "ack_risk_intro" in e.value.errors
    svc.submit("u", "welcome", {"ack_risk_intro": True})
    with pytest.raises(OnboardingError) as e:
        svc.submit("u", "identity", {"display_name": ""})
    assert "display_name" in e.value.errors
    v = svc.submit("u", "identity", {"display_name": "Sam", "full_name": None, "email": "sam@example.com",
                                     "phone": None, "country": "GB", "preferred_channel": "email"})  # optionals blank
    assert v["stage"]["id"] == "objective"


@pytest.mark.parametrize("qid,value", [("email", "not-an-email"), ("phone", "0416 555"), ("country", "Canada"),
                                       ("preferred_channel", "carrier_pigeon")])
def test_field_validation(svc, qid, value):
    walk(svc, "v", BASE, stop_before="identity")
    vals = {q["id"]: BASE.get(q["id"]) for q in engine.stage_by_id("identity")["questions"]}
    vals[qid] = value
    with pytest.raises(OnboardingError) as e:
        svc.submit("v", "identity", vals)
    assert qid in e.value.errors


def test_multi_limits_and_unknown_fields(svc):
    walk(svc, "m", BASE, stop_before="objective")
    with pytest.raises(OnboardingError):
        svc.submit("m", "objective", {"objectives": ["learn", "diversify", "discipline", "new_markets"]})  # max 3
    with pytest.raises(OnboardingError) as e:
        svc.submit("m", "objective", {"objectives": ["learn"], "runtime_mode": "LIVE"})
    assert "runtime_mode" in e.value.errors


def test_answers_must_target_current_step(svc):
    with pytest.raises(OnboardingError):
        svc.submit("x", "objective", {"objectives": ["learn"]})   # not the current step


def test_back_navigation_keeps_answers(svc):
    walk(svc, "b", BASE, stop_before="objective")
    v = svc.back("b")
    assert v["stage"]["id"] == "identity" and v["answers"]["email"] == "ada@example.com"


def test_answer_persistence_and_resume(tmp_path):
    s1 = OnboardingService(OnboardingStore(tmp_path))
    walk(s1, "r", BASE, stop_before="experience")
    s2 = OnboardingService(OnboardingStore(tmp_path))         # new process, same store
    v = s2.view("r")
    assert v["stage"]["id"] == "experience"
    walk(s2, "r", BASE)
    assert s2.complete("r")["passport"]["preferred_name"] == "Ada"


def test_provenance_recorded(svc):
    walk(svc, "p", BASE, stop_before="identity")
    ident = {q["id"]: BASE.get(q["id"]) for q in engine.stage_by_id("identity")["questions"]}
    svc.submit("p", "identity", dict(ident, display_name="First"))
    svc.back("p")
    svc.submit("p", "identity", dict(ident, display_name="Second"))
    doc = svc.store.load(user_key("p"))
    rec = doc["session"]["answers"]["display_name"]
    assert rec["value"] == "Second" and rec["questionnaire_version"] == QUESTIONNAIRE_VERSION
    assert rec["source"] == "user" and "previous_answered_at" in rec and rec["answered_at"]
    kinds = [e["kind"] for e in doc["session"]["events"]]
    assert "answer_changed" in kinds and "back" in kinds


def test_sensitive_values_not_in_events_or_logs(svc, caplog):
    caplog.set_level("INFO")
    walk(svc, "s", BASE)
    doc = svc.store.load(user_key("s"))
    events = json.dumps(doc["session"]["events"])
    assert "ada@example.com" not in events and "ada@example.com" not in caplog.text


def test_store_file_is_private_and_not_named_by_user(tmp_path):
    svc = OnboardingService(OnboardingStore(tmp_path))
    walk(svc, "Private.Person", BASE, stop_before="objective")
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1 and "private" not in files[0].name.lower()
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"


def test_every_question_has_purpose_and_dimension():
    for s in STAGES:
        for q in s.get("questions", []):
            assert len(q.get("purpose", "")) >= 20, q["id"]
            assert q.get("dimension"), q["id"]


def test_every_question_is_used_by_rules_or_record():
    """No orphan questions: each answer feeds the Passport (rules), contact/consent records, or an acknowledgement."""
    import inspect
    from backend.app.onboarding import rules
    src = inspect.getsource(rules)
    record_only = {"full_name", "email", "phone", "country", "consent_service_notifications", "consent_marketing",
                   "ack_risk_intro", "ack_attribution", "ack_no_guarantee", "ack_recommendation_not_authority",
                   "ack_responsibility"}
    quiz = {q["id"] for s in STAGES for q in s.get("questions", []) if q["type"] == "quiz"}   # via quiz_feedback
    for s in STAGES:
        for q in s.get("questions", []):
            if q["id"] in record_only or q["id"] in quiz:
                continue
            assert f'"{q["id"]}"' in src, f"{q['id']} is asked but never used"


def test_no_duplicate_prompts():
    prompts = [q["prompt"].strip().lower() for s in STAGES for q in s.get("questions", [])]
    assert len(prompts) == len(set(prompts))


def test_store_rejects_path_tricks(tmp_path):
    with pytest.raises(ValueError):
        OnboardingStore(tmp_path).load("../etc/passwd")


# ---------------------------------------------------------------- adaptive branching
def test_leverage_knowledge_only_when_relevant(svc):
    visited = walk(svc, "nolev", BASE)
    assert "knowledge_leverage" not in visited
    visited = walk(svc, "lev", dict(BASE, experience_by_class=dict(BASE["experience_by_class"], fx="beginner")))
    assert "knowledge_leverage" in visited
    visited = walk(svc, "lev2", dict(BASE, preferred_markets=["equities", "futures"]))   # chosen market alone
    assert "knowledge_leverage" in visited


def test_auto_check_appears_only_for_auto_interest(svc):
    assert "auto_check" not in walk(svc, "c1", BASE)
    assert "auto_check" in walk(svc, "c2", dict(BASE, assistance_preference="auto_interest"))


def test_hidden_stage_answers_are_pruned(svc):
    walk(svc, "pr", dict(BASE, assistance_preference="auto_interest"), stop_before="support")
    svc.back("pr"); svc.back("pr")                            # back to the assistance step
    svc.submit("pr", "assistance", {"assistance_preference": "discover"})
    doc = svc.store.load(user_key("pr"))
    assert "auto_understanding" not in doc["session"]["answers"]
    assert any(e["kind"] == "answer_removed_stage_hidden" for e in doc["session"]["events"])


def test_condition_fails_closed_on_unknown_operator():
    with pytest.raises(ValueError):
        condition_met({"q": "objectives", "between": [1, 2]}, {"objectives": {"value": ["learn"]}})


# ---------------------------------------------------------------- recommendations
def test_confirm_recommendation_for_ready_user(svc):
    p = complete(svc, "ready")
    assert p["mode"]["recommended"] == "CONFIRM"
    assert p["expectations_calibration"] == []
    assert p["mode"]["because"]


def test_discover_for_beginner_with_simulation_first(svc):
    p = complete(svc, "new", experience_by_class={c: "none" for c in ALL_CLASSES}, assistance_preference="discover",
                 kq_drawdown="not_sure", kq_exposure="a", kq_leverage="not_sure")
    assert p["mode"]["recommended"] == "DISCOVER" and p["mode"]["simulation_first"]
    assert "Drawdown" in p["knowledge"]["gaps"] and "Portfolio exposure" in p["knowledge"]["gaps"]
    assert any("Drawdown" in e["item"] for e in p["education_plan"])
    assert any("simulator" in e["item"] for e in p["education_plan"])


def test_auto_interest_never_grants_authority_or_auto_mode(svc):
    p = complete(svc, "auto", assistance_preference="auto_interest")
    assert p["mode"]["recommended"] in ("DISCOVER", "CONFIRM")
    assert p["mode"]["auto_interest_recorded"] is True
    assert p["execution_authority_granted"] is False
    assert "not granted by this questionnaire" in p["mode"]["note"]


def test_no_code_path_grants_authority():
    """No onboarding code names, sets or imports execution/runtime/governance state. Checked on the syntax tree
    (identifiers, attributes, keyword args, string keys, imports), so docstrings explaining the boundary are fine."""
    import ast
    forbidden = ("runtime_mode", "execution_allowed", "advisory_only", "live_authority", "set_live", "enable_live",
                 "antibleed", "r14f", "broker", "execution_router", "risk_router", "orchestrat")
    for f in Path("backend/app/onboarding").glob("*.py"):
        tree = ast.parse(f.read_text())
        doc_nodes = {id(n.body[0].value) for n in ast.walk(tree)
                     if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                     and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        tokens = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Name): tokens.append(n.id)
            elif isinstance(n, ast.Attribute): tokens.append(n.attr)
            elif isinstance(n, ast.keyword) and n.arg: tokens.append(n.arg)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                tokens += [a.name for a in n.names] + ([n.module] if getattr(n, "module", None) else [])
            elif isinstance(n, ast.Dict):
                tokens += [k.value for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        for t in tokens:
            assert not any(x in t.lower() for x in forbidden), (f.name, t)


@pytest.mark.parametrize("overrides,code", [
    ({"bl_every_trade_profitable": True}, "ZERO_LOSS_EXPECTATION"),
    ({"bl_losses_possible": False}, "LOSSES_NOT_EXPECTED"),
    ({"bl_auto_guarantees": True}, "AUTO_MISUNDERSTANDING"),
    ({"assistance_preference": "auto_interest", "auto_understanding": "guaranteed"}, "AUTO_MISUNDERSTANDING"),
    ({"bl_css_compensates": True}, "COMPENSATION_EXPECTATION"),
    ({"ex_return_range": "double_plus"}, "UNREALISTIC_RETURN"),
    ({"bl_drawdowns_normal": False}, "ZERO_DRAWDOWN_EXPECTATION"),
    ({"holding_periods": ["intraday"], "monitoring_availability": "end_of_day"}, "HOLDING_TIME_MISMATCH"),
    ({"rc_living_dependence": "yes", "objective_ranking": ["supplement", "steady_growth", "preservation"]}, "INCOME_DEPENDENCE"),
    ({"ex_trade_frequency": "many_daily"}, "FREQUENCY_TIME_MISMATCH"),
])
def test_expectation_mismatches_are_calibrated_not_rewarded(svc, overrides, code):
    p = complete(svc, "e-" + code.lower(), **overrides)
    codes = [f["code"] for f in p["expectations_calibration"]]
    assert code in codes
    flag = next(f for f in p["expectations_calibration"] if f["code"] == code)
    assert flag["message"] and flag["because"]
    if flag["severity"] == "major":
        assert p["mode"]["recommended"] == "DISCOVER"          # stricter, never more permissive
    assert "score" not in json.dumps(p).lower().replace("scoring", "")


def test_leverage_knowledge_gap_flag(svc):
    p = complete(svc, "lg", experience_by_class=dict(BASE["experience_by_class"], options="beginner"),
                 preferred_markets=["options"], uses_leverage="yes", kq_leverage="a", kq_margin_call="not_sure")
    flag = next(f for f in p["expectations_calibration"] if f["code"] == "LEVERAGE_KNOWLEDGE_GAP")
    assert flag["action"] == "simulation:first" and p["mode"]["simulation_first"]


def test_risk_capacity_and_tolerance_are_distinct(svc):
    # Comfortable with risk, but cannot afford losses.
    p = complete(svc, "rc", rc_living_dependence="yes", rc_emergency_fund="no",
                 **{k: "comfortable" for k in ("rt_volatility", "rt_temporary_loss", "rt_consecutive_losses",
                                               "rt_uncertainty", "rt_concentration", "rt_leverage")})
    assert p["risk_capacity"]["level"] == "LOW" and p["risk_tolerance"]["level"] == "HIGHER"
    assert p["risk_posture"]["level"] == "LOW" and p["risk_posture"]["mismatch"]
    assert p["mode"]["recommended"] == "DISCOVER"
    # The reverse: strong finances, low comfort.
    p2 = complete(svc, "rt", **{k: "uncomfortable" for k in ("rt_volatility", "rt_temporary_loss",
                                                              "rt_consecutive_losses", "rt_uncertainty",
                                                              "rt_concentration", "rt_leverage")})
    assert p2["risk_capacity"]["level"] == "HIGHER" and p2["risk_tolerance"]["level"] == "LOW"
    assert p2["risk_posture"]["level"] == "LOW"


def test_development_areas_from_habits_gaps_and_barriers(svc):
    p = complete(svc, "bh", bh_size_after_loss="often", bh_exit_rule="rarely", kq_drawdown="not_sure",
                 barriers=["emotions"])
    areas = {d["area"]: d["source"] for d in p["development_areas"]}
    assert areas["Chasing losses"] == "decision habits" and areas["Planning exits"] == "decision habits"
    assert areas["Drawdown"] == "knowledge check"
    assert any(src == "your barriers" for src in areas.values())
    assert "Plans exits in advance" not in [s["strength"] for s in p["strengths"]]


def test_every_recommendation_is_explainable(svc):
    p = complete(svc, "why", bl_every_trade_profitable=True, bh_size_after_loss="often")
    for section in (p["risk_capacity"], p["risk_tolerance"], p["mode"], p["experience"]):
        assert section["because"], section
    for item in p["expectations_calibration"] + p["development_areas"] + p["strengths"] + p["dimensions"]:
        assert item["because"]
        for b in item["because"]:
            assert b["question_id"] and "answer" in b


def test_passport_dimensions_states_and_traceability(svc):
    p = complete(svc, "dims")
    names = [d["dimension"] for d in p["dimensions"]]
    assert names == ["Market Knowledge", "Experience", "Risk Discipline", "Decision Style", "CSS Familiarity",
                     "Support Preference"]
    levelled = {d["dimension"]: d["state"] for d in p["dimensions"]}
    for n in ("Market Knowledge", "Experience", "Risk Discipline", "CSS Familiarity"):
        assert levelled[n] in ("Foundation", "Developing", "Experienced")
    assert levelled["Experience"] == "Experienced" and levelled["CSS Familiarity"] == "Developing"
    assert levelled["Decision Style"] == "Pattern-led" and levelled["Support Preference"] == "Key points"
    for d in p["dimensions"]:
        assert d["because"] and d["basis"] and d["summary"]
    beginner = complete(svc, "dims2", experience_by_class={c: "none" for c in ALL_CLASSES}, css_familiarity="new",
                        kq_stop="a", kq_drawdown="not_sure", kq_exposure="a", kq_volatility="b", kq_risk_reward="a",
                        bh_exit_rule="rarely", bh_size_after_loss="often", bh_after_losses="trade_more")
    st = {d["dimension"]: d["state"] for d in beginner["dimensions"]}
    assert st["Experience"] == "Foundation" and st["Market Knowledge"] == "Foundation"
    assert st["Risk Discipline"] == "Foundation" and st["CSS Familiarity"] == "Foundation"


def test_passport_never_implies_suitability_or_auto(svc):
    p = complete(svc, "suit", assistance_preference="auto_interest")
    blob = json.dumps(p).lower()
    assert "does not make anyone suitable for live trading" in p["suitability_note"].lower()
    assert p["mode"]["recommended"] != "AUTO" and p["execution_authority_granted"] is False
    for bad in ("you are suitable", "approved for live", "ready for live", "profitability score", "potential score",
                "suitability score", "readiness score"):
        assert bad not in blob


def test_passport_reports_markets_engagement_and_loss_tolerance(svc):
    p = complete(svc, "mk", monitoring_availability="within_minutes")
    assert p["preferred_markets"] == ["Stocks (equities)", "ETFs"]
    assert p["engagement"]["style"] == "Active monitor" and p["engagement"]["because"]
    assert p["loss_tolerance"]["capacity_band"] == "15–30%" and p["loss_tolerance"]["realistic_about_drawdowns"]
    assert p["objectives"]["priorities"][0] == "Steady growth"


# ---------------------------------------------------------------- version migration
def test_v1_session_migrates_keeping_valid_answers(svc):
    walk(svc, "mig", BASE)
    svc.complete("mig")
    doc = svc.store.load(user_key("mig"))
    s = doc["session"]
    s["questionnaire_version"] = "TP-Q-1.0.0"
    s["answers"]["ex_role"] = {"value": "propose", "answered_at": "2026-01-01T00:00:00+00:00", "stage_id": "expectations",
                               "questionnaire_version": "TP-Q-1.0.0", "source": "user"}       # removed in v2
    s["answers"]["objective_ranking"]["value"] = ["steady_growth", "learning", "preservation"]  # option removed in v2
    del s["answers"]["css_familiarity"]                                                          # new in v2
    svc.store.save(user_key("mig"), doc)
    v = svc.view("mig")
    assert v["questionnaire_version"] == QUESTIONNAIRE_VERSION and v["status"] == "reviewing"
    assert v["stage"]["id"] == "objective"                     # first step that now needs an answer
    doc = svc.store.load(user_key("mig"))
    a = doc["session"]["answers"]
    assert "ex_role" not in a and "objective_ranking" not in a
    assert a["email"]["migrated_from"] == "TP-Q-1.0.0"
    ev = next(e for e in doc["session"]["events"] if e["kind"] == "questionnaire_migrated")
    assert "ex_role" in ev["dropped"] and "email" in ev["kept"]
    walk(svc, "mig", BASE)
    assert svc.complete("mig")["passport"]["questionnaire_version"] == QUESTIONNAIRE_VERSION


# ---------------------------------------------------------------- profile updates
def test_profile_update_creates_revision(svc):
    complete(svc, "up")
    v = svc.update_profile("up", {"experience_by_class": {c: "none" for c in ALL_CLASSES}})
    assert v["passport"]["mode"]["recommended"] == "DISCOVER"
    h = svc.history("up")
    assert [r["reason"] for r in h] == ["onboarding_complete", "profile_update"]
    assert h[1]["changed"] == ["experience_by_class"] and h[1]["rules_version"] == RULES_VERSION
    doc = svc.store.load(user_key("up"))
    assert doc["session"]["answers"]["experience_by_class"]["source"] == "profile_update"


def test_profile_update_that_needs_new_answers(svc):
    complete(svc, "up2")
    v = svc.update_profile("up2", {"assistance_preference": "auto_interest"})
    assert v["status"] == "reviewing" and v["stage"]["id"] == "auto_check"
    assert len(svc.history("up2")) == 1                       # no revision until the gap is filled


def test_profile_update_validates_and_protects_acknowledgements(svc):
    complete(svc, "up3")
    with pytest.raises(OnboardingError):
        svc.update_profile("up3", {"email": "nope"})
    with pytest.raises(OnboardingError):
        svc.update_profile("up3", {"ack_no_guarantee": False})


def test_complete_requires_all_steps(svc):
    walk(svc, "inc", BASE, stop_before="markets")
    with pytest.raises(OnboardingError):
        svc.complete("inc")


# ---------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("httpx", reason="FastAPI TestClient needs httpx (not in requirements.txt); API tests skipped")
    from fastapi.testclient import TestClient
    from backend.app.auth.token_store import token_store
    from backend.app.onboarding.standalone import create_app
    app = create_app(OnboardingService(OnboardingStore(tmp_path)))
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + token_store.create_session("api-user", ["user"], minutes=5)
    return c


def test_api_requires_session(client):
    from fastapi.testclient import TestClient
    anon = TestClient(client.app)
    assert anon.get("/passport/session").status_code == 401
    assert anon.get("/passport/session", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert anon.get("/passport/schema").status_code == 200        # public: questions only, no answer keys


def test_api_flow_and_errors(client):
    r = client.post("/passport/answer", json={"stage_id": "welcome", "answers": {"ack_risk_intro": False}})
    assert r.status_code == 422 and "ack_risk_intro" in r.json()["detail"]["errors"]
    for _ in range(60):
        v = client.get("/passport/session").json()
        if v["stage"]["kind"] == "result":
            break
        vals = {q["id"]: BASE.get(q["id"]) for q in v["stage"].get("questions", [])}
        assert client.post("/passport/answer", json={"stage_id": v["stage"]["id"], "answers": vals}).status_code == 200
    r = client.post("/passport/complete")
    assert r.status_code == 200 and r.json()["passport"]["execution_authority_granted"] is False


def test_api_performance_fails_closed_without_data(client, monkeypatch):
    monkeypatch.delenv("CSS_PASSPORT_DEMO", raising=False)
    r = client.get("/passport/performance")
    assert r.status_code == 503 and r.json()["detail"]["status"] == "not_connected"
    monkeypatch.setenv("CSS_PASSPORT_DEMO", "1")
    d = client.get("/passport/performance").json()
    assert d["data_source"] == "SAMPLE" and "not real" in d["sample_notice"]


def test_api_static_ui_and_path_traversal(client):
    assert client.get("/passport/app/index.html").status_code == 200
    assert client.get("/passport/app/../../router.py").status_code == 404
    assert client.get("/passport/app/%2e%2e/%2e%2e/router.py").status_code == 404
