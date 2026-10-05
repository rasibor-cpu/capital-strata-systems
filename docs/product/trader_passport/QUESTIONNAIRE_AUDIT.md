# Questionnaire audit: TP-Q-1.0.0 → TP-Q-2.0.0

Phase 2 of Issue #102. Every question now carries a `purpose` (shown to the user as "Why we ask", except on the
acknowledgements, where the statement explains itself) and a `dimension` (which part of the Passport or record it
feeds). Tests enforce three things: every question has both fields, every non-record question is read by
`rules.py`, and no two prompts are identical.

Full per-question purposes are generated into `QUESTION_SCHEMA.md` ("Why each question is asked"). The
machine-readable copy is `QUESTION_SCHEMA_TP-Q-2.0.0.json`. The 1.0.0 export is kept unchanged for the record.

## Size

| | v1 | v2 |
|---|---|---|
| Questions | 67 | 68 |
| Decision screens, shortest / longest path | 18 / 20 | 17 / 19 |
| Explanatory screens | 4 | 5 (adds "Two kinds of trades, kept apart") |
| Questions on the shortest / longest path | — | 64 / 68 |

## Removed (duplicates or no use in the Passport)

| v1 question | Why removed | Where it lives now |
|---|---|---|
| `ex_holding_period` | Duplicated `holding_periods` (Markets step), asked twice with the same options | `holding_periods` |
| `ex_drawdown` | Overlapped `rc_max_loss` (capacity) and the risk-tolerance items. Its "none" option is now an explicit true/false belief check | `rc_max_loss`, `rt_temporary_loss`, `bl_drawdowns_normal` |
| `ex_automation` | Repeated `assistance_preference` with different words | `assistance_preference` |
| `ex_role` | Repeated `assistance_preference` | `assistance_preference`; what the user values goes into `ex_primary_value` |
| `ex_communication` | Overlapped `notification_preference` | `notification_preference`, `support_level` |
| `bh_time_pressure` | Self-assessed comfort that no rule used | `bh_decision_speed` (how decisions are actually made) |

## Added (coverage gaps in v1)

| v2 question | Covers |
|---|---|
| `css_familiarity` | CSS Familiarity dimension (new / similar tools / has used CSS) |
| `thinking_style` | Detail vs pattern vs big picture as one explicit choice (in v1 these were mixed into the strengths list) |
| `bh_decision_speed` | Decision speed (Decision Style dimension) |
| `support_level` | How much explanation the user wants (Support Preference) |
| `learning_style` | Learning and support preferences (format of the learning plan) |
| `ex_primary_value` | What the user most wants from CSS |
| `bl_drawdowns_normal` | Explicit drawdown-expectation check (replaces `ex_drawdown = none`) |

## Changed options

- `strengths`: detail, pattern and big picture moved out to `thinking_style`; "adaptable" added; the maximum is now 3.
- `objective_ranking`: "learning" was dropped because it duplicated the `objectives` option. "diversification" became
  "accessibility". The ranking now holds outcome priorities only.
- `feature_preferences`: "explanations" and "education" were removed. They are covered by `support_level` and
  `learning_style`.

Sessions started on v1 are migrated by `engine.migrate_session`:
- answers that still exist and still validate are kept, tagged `migrated_from`;
- everything else is dropped, and the drop is logged in the `questionnaire_migrated` event;
- the user resumes at the first step that needs an answer.

Nothing is mapped between different questions (tested).

## Coverage of the directive's list

| Topic | Questions |
|---|---|
| Experience by asset class | `experience_by_class` (6 markets) |
| Knowledge | `kq_*` (8 core questions, plus 2 leverage questions when relevant), each with "I'm not sure yet" |
| Analytical strengths | `strengths` |
| Detail / pattern / big-picture | `thinking_style` |
| Decision speed and consistency | `bh_decision_speed`, `bh_strategy_switch` |
| Risk capacity | `rc_capital_band`, `rc_living_dependence`, `rc_emergency_fund`, `rc_horizon`, `rc_max_loss` |
| Risk tolerance | `rt_*` (6) |
| Drawdown / loss tolerance | `rc_max_loss`, `rt_temporary_loss`, `rt_consecutive_losses`, `bh_drawdown_reaction`, `bl_drawdowns_normal` |
| Holding period | `holding_periods` |
| Available time | `engagement_cadence`, `monitoring_availability` |
| Preferred markets | `preferred_markets` |
| Leverage familiarity | `kq_leverage`, `kq_margin_call`, `uses_leverage`, `rt_leverage` |
| Objectives | `objectives`, `objective_ranking` |
| Expectations of CSS | `ex_primary_value`, `ex_trade_frequency`, `ex_risk`, `ex_return_range`, `ex_success`, `bl_*` |
| Desired assistance | `assistance_preference` (+ `auto_understanding` when Auto interest is chosen) |
| Learning / support | `support_level`, `learning_style`, `feature_preferences`, `notification_preference` |
| Barriers | `barriers` |
| Name, contact, consents | `display_name`, `full_name`, `email`, `phone`, `country`, `preferred_channel`, `consent_*` |

No question produces, and the Passport contains no, profitability, "potential", readiness or suitability score
(tested).

## Branching

| Step | Shown when |
|---|---|
| Leverage and margin | the user has beginner-or-better FX/crypto/options/futures experience, OR objectives include active trading or new markets, OR one of those markets is chosen |
| What Auto does and doesn't change | `assistance_preference = auto_interest` |

Answers on a step that later becomes hidden are removed, and the removal is logged
(`answer_removed_stage_hidden`).
