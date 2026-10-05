# Trader Passport rules (TP-R-2.0.0)

Source: `backend/app/onboarding/rules.py`. Every output carries `because`: the question ids and the answers (as the
user saw them) it came from. In the UI, "Why?" lists the question prompts and answers. Each Passport revision stores
the questionnaire version, the rules version and full answer provenance.

## Never produced

- A suitability percentage, readiness, profitability or "potential" score.
- An **AUTO** recommendation. Auto interest is recorded and explained. Automated execution is a separate, governed
  authorisation.
- Any execution authority: `execution_authority_granted` is always `False`. Tested by inspecting the syntax tree:
  no onboarding code names runtime-mode, broker or gate state.
- Any statement that onboarding makes someone suitable for live trading. The Passport carries `suitability_note`:
  "Completing onboarding does not make anyone suitable for live trading…".
- A more permissive outcome because of an unrealistic expectation.

## The six dimensions

The states are descriptive. Foundation / Developing / Experienced describe where someone is starting from, not a
grade. Decision Style and Support Preference are descriptions, not levels.

| Dimension | State rule | Evidence |
|---|---|---|
| Market Knowledge | Share of assessed topics answered correctly: ≥80% Experienced, ≥50% Developing, otherwise Foundation. "Not sure" counts as a topic to learn | `kq_*` |
| Experience | Highest band across markets: none/beginner → Foundation, intermediate → Developing, experienced → Experienced. Per-market bands are kept | `experience_by_class` |
| Risk Discipline | Four habits: exits planned (`bh_exit_rule = always`); steady after losses (`pause_review`/`continue_plan`); no size-chasing (`bh_size_after_loss = never`); measured response to falls (`hold_plan`/`reduce`). All 4 → Experienced, 2–3 → Developing, 0–1 → Foundation | `bh_*` |
| Decision Style | Detail-led / Pattern-led / Big-picture, plus speed and consistency | `thinking_style`, `bh_decision_speed`, `bh_strategy_switch` |
| CSS Familiarity | new → Foundation, similar tools → Developing, used CSS → Experienced (self-reported) | `css_familiarity` |
| Support Preference | Walk-through / Key points / Minimal, plus learning formats | `support_level`, `learning_style` |

## Other Passport sections

| Section | Rule |
|---|---|
| Strengths | Self-described strengths (tagged "self-described") are listed separately from those indicated by answers ("from your answers"): exits planned, steady after losses, 6+ topics answered correctly |
| Areas to develop | Knowledge gaps (with explanations); habits (loss-chasing, prefers time, exits unplanned, frequent strategy changes, exits everything in falls), each paired with a CSS support action; barriers the user named |
| Risk capacity | The **most limiting** factor, not an average. LOW if: living expenses depend on the money, no emergency fund, the money is needed within a year, or a fall over 5% would change plans. MODERATE for the partial versions. Otherwise HIGHER |
| Risk tolerance | Six comfort answers, 0/1/2 points each: 0–4 LOW, 5–8 MODERATE, 9–12 HIGHER (stated as a band) |
| Loss tolerance | Capacity band (`rc_max_loss`) next to comfort with losses, and whether drawdowns are expected |
| Risk posture | The lower of capacity and tolerance; a mismatch is explained in both directions |
| Markets / holding periods / leverage | As chosen. Leverage familiarity is reported only when the leverage step was shown |
| Engagement style | Active monitor (responds within minutes) / Periodic reviewer (within hours) / End-of-day planner |
| Learning plan | Knowledge gaps, then calibration education, then the simulator when `simulation_first`. Delivered in the user's chosen learning formats |
| Starting mode | Discover or Confirm (see below) |

## Expectations calibration

| Code | Trigger | Severity | Response |
|---|---|---|---|
| ZERO_LOSS_EXPECTATION | believes every CSS trade is profitable, or defines success as every trade winning | major | education |
| LOSSES_NOT_EXPECTED | says losses aren't possible | major | education |
| AUTO_MISUNDERSTANDING | believes Auto guarantees returns, or the Auto check was answered "guaranteed"/"no risk" | major | education on Auto |
| COMPENSATION_EXPECTATION | expects CSS to repay losses | major | education |
| UNREALISTIC_RETURN | hopes to double their money or more in a year | major | education |
| ZERO_DRAWDOWN_EXPECTATION | `bl_drawdowns_normal = false` | major | education |
| RISK_EXCEEDS_CAPACITY | expects high risk with LOW capacity | major | stricter mode |
| FREQUENCY_TIME_MISMATCH | many trades a day without availability within minutes | minor | pacing advice |
| HOLDING_TIME_MISMATCH | intraday holding with end-of-day availability | minor | pacing advice |
| LEVERAGE_KNOWLEDGE_GAP | options/futures or leverage intent with a leverage or margin gap | major | simulator first |
| INCOME_DEPENDENCE | living expenses depend on the money and the top priority is "supplement" or "aggressive growth" | major | stricter mode |

## Starting mode

**CONFIRM** only if all of these hold:
- intermediate or better experience in at least one chosen market;
- at most two core knowledge gaps;
- no major calibration flag;
- risk capacity is not LOW.

Otherwise **DISCOVER**, with every reason listed.

`simulation_first` is set when experience is none or beginner, when there is any core gap, or when a simulation-first
flag fires. A user who asked for Confirm but is recommended Discover sees why. Neither mode grants execution
authority: Confirm means CSS may propose Trade Cards that the user confirms one by one, within the governed controls.
