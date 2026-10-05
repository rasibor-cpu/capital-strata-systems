# Trader Passport recommendation rules (TP-R-1.0.0)

Source: `backend/app/onboarding/rules.py`. Every output carries `because`: the question ids and answers it came from.
Persisted with each Passport revision: questionnaire version, rules version, full answer provenance.

## Never produced

- A suitability percentage, readiness score or "potential" score.
- An **AUTO** recommendation. Auto interest is recorded, acknowledged and explained; automated execution is a separate
  governed authorisation.
- Any execution authority: `execution_authority_granted` is always `False` (tested by syntax-tree inspection).
- A more permissive outcome because of an unrealistic expectation.

## Components

| Output | Rule |
|---|---|
| Experience | Highest band across asset classes; per-class bands kept |
| Knowledge | Each quiz topic is *demonstrated* (correct) or a *gap* (wrong or "not sure"). Gaps drive the learning plan |
| Strengths | Self-reported (as chosen) kept apart from strengths indicated by answers: exits planned (`bh_exit_rule = always`), steady after losses (`pause_review`/`continue_plan`), 6+ topics demonstrated |
| Risk capacity | The **most limiting** factor, not an average. LOW if: living expenses depend on the money, no emergency fund, needed within a year, or a fall over 5% would change plans. MODERATE for the partial versions. Otherwise HIGHER |
| Risk tolerance | Six comfort answers, 0/1/2 points each: 0–4 LOW, 5–8 MODERATE, 9–12 HIGHER (a band, stated as such) |
| Risk posture | Lower of capacity and tolerance; mismatch explained in both directions |
| Behaviour | Loss-chasing, prefers time, exits unplanned, quick strategy switching, exits everything in falls: each maps to a CSS support action, not a diagnosis |

## Expectations calibration

| Code | Trigger | Severity | Response |
|---|---|---|---|
| ZERO_LOSS_EXPECTATION | believes every CSS trade will be profitable, or success = every trade wins | major | education |
| LOSSES_NOT_EXPECTED | says losses aren't possible | major | education |
| AUTO_MISUNDERSTANDING | believes Auto guarantees returns, or Auto check answered "guaranteed"/"no risk" | major | education on Auto |
| COMPENSATION_EXPECTATION | expects CSS to repay losses | major | education |
| UNREALISTIC_RETURN | hopes to double money or more in a year | major | education; CSS won't tune to it |
| ZERO_DRAWDOWN_EXPECTATION | accepts no temporary fall at all | major | education |
| RISK_EXCEEDS_CAPACITY | expects high risk with LOW capacity | major | stricter mode |
| FREQUENCY_TIME_MISMATCH | many trades a day without minute-level availability | minor | pacing advice |
| LEVERAGE_KNOWLEDGE_GAP | options/futures or leverage intent with a leverage/margin gap | major | simulation first |
| INCOME_DEPENDENCE | needs the money for living and ranks "supplement" first | major | stricter mode |

## Mode recommendation

**CONFIRM** only if all hold:
- intermediate or better experience in at least one chosen market;
- at most two core knowledge gaps;
- no major calibration flag;
- risk capacity is not LOW.

Otherwise **DISCOVER**, with every reason listed. `simulation_first` is set for none/beginner experience, any core gap
or a simulation-first flag. A user who asked for Confirm but is recommended Discover sees why, and can revisit later.
