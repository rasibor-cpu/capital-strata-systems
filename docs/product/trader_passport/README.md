# CSS Trader Passport (Issue #102)

Progressive, mobile-first onboarding that builds an explainable **Trader Passport**, plus a trade-origin model that keeps
**CSS-recommended** and **user-independent** trades separate from recommendation to performance.

Status: **software built and tested on an isolated branch; not merged, not deployed, not connected to the governed
execution path.** Owner, compliance and release gates remain (see the end of this file).

## What is where

| Path | Purpose |
|---|---|
| `backend/app/onboarding/schema.py` | Versioned questionnaire `TP-Q-2.0.0`: 25 stages, 68 questions, each with `purpose` and `dimension`; adaptive `show_if` branching. Single source of truth for server, UI and tests |
| `backend/app/onboarding/engine.py` | Visibility, validation (fail closed), navigation, resume, answer provenance, pruning of answers on newly hidden stages, migration of older-version sessions |
| `backend/app/onboarding/rules.py` | Passport rules `TP-R-2.0.0`: six dimensions with descriptive states and `because` evidence for every output. No suitability score, no Auto recommendation, `execution_authority_granted` always `False` |
| `backend/app/onboarding/service.py` | Start/resume, submit, back, complete, profile updates; append-only revisions |
| `backend/app/onboarding/store.py` | JSON store per user, salted-hash file names, atomic writes, mode 0600, no answer values in logs |
| `backend/app/onboarding/router.py` | FastAPI router under `/passport`, existing CSS bearer sessions (`backend.app.auth.token_store`), serves the UI |
| `backend/app/onboarding/standalone.py` | Development app (auth + Passport only). Run on any port **except 8765** |
| `backend/app/trade_origin/model.py` | Four origin states, envelope-based `MaterialityPolicy`, immutable `AttributionRecord`, `reproduce()`, append-only `OriginLedger` with an explicit state machine, policy `TO-2.0.0` |
| `backend/app/trade_origin/lifecycle.py` | Origin through fills, lots, partial/final closes and journal entries |
| `backend/app/trade_origin/performance.py` | Segregated performance, CSS-attributable / independent / combined views, total = sum of segments (checked), legacy records held for review |
| `backend/app/trade_origin/commercial.py` | Four separate commercial ledgers; attributable base; fee computed only under an approved policy (none by default) |
| `backend/app/trade_origin/demo.py` | Synthetic sample for the results view, shown only with `CSS_PASSPORT_DEMO=1` and labelled as sample |
| `frontend/trader_passport/` | Vanilla HTML/CSS/JS client (no build step, no external fonts or CDNs) and 9 original SVG assets |
| `tests/onboarding/`, `tests/trade_origin/` | Unit/integration tests + browser tests (Playwright + axe-core); counts in `evidence/` |
| `docs/product/trader_passport/` | This documentation: `QUESTIONNAIRE_AUDIT.md`, `RECOMMENDATION_RULES.md`, `ATTRIBUTION_SPEC.md`, `COMMERCIAL_ATTRIBUTION.md`, `POST_OV002_INTEGRATION.md`, `UX_SPEC.md`, schema exports, evidence (phase1_before / phase2_after), artifact register |

## Screen flow (adaptive, TP-Q-2.0.0)

Phones see one principal decision per screen: 17 decision screens on the shortest path and 19 on the longest, plus
five short explanatory screens. The progress indicator counts only the steps visible to that user. Every question has
a "Why we ask" note. The v1 → v2 changes are in `QUESTIONNAIRE_AUDIT.md`.

1. **Welcome** (explanation): what CSS is; Discover, Confirm and Auto (separate approval); risk callout; required acknowledgement.
2. **About you**: name, contact, country, channel, separate opt-in consents.
3. **Goals and priorities**: up to three objectives; top three outcome priorities in order.
4. **Your experience**: band per market (six markets); familiarity with CSS or similar tools.
5. **Knowledge check** (explanation), then 6. **Orders and sizing** and 7. **Volatility, drawdown and diversification** (four questions each, each with "I'm not sure yet").
8. **How you think about markets**: detail / pattern / big picture; up to three strengths.
9. **How you make decisions**: speed, after losses, in sharp falls, size after a loss, exit planning, strategy switching.
10. **Two different questions about risk** (explanation), then 11. **Risk capacity** and 12. **Comfort with risk**.
13. **What holds you back**.
14. **Markets and holding periods**.
15. **Leverage and margin** *(only when the answers involve leveraged markets)*.
16. **How much help from CSS**: Discover, Confirm or *interest in* Auto.
17. **What Auto does and doesn't change** *(only with Auto interest)*.
18. **How CSS can support you**: tools, explanation depth, learning formats.
19. **Your time**: cadence, availability, notifications.
20. **Expectations** (explanation), then 21. **What you expect from CSS** and 22. **Reality check** (five true/false questions and what success means).
23. **Two kinds of trades, kept apart** (explanation): CSS idea → you choose → CSS-attributable record; your idea → your independent results. The dashboard shows CSS P&L, independent P&L and the combined result. A recommendation is not a guaranteed profit.
24. **Before your Passport**: four acknowledgements.
25. **Trader Passport** (result): six dimensions (Market Knowledge, Experience, Risk Discipline, Decision Style, CSS Familiarity, Support Preference) with Foundation / Developing / Experienced states; strengths; areas to develop; starting mode; risk; markets and engagement; learning plan. Every item has a "Why?". Then the separated-results view.

Full question list: `QUESTION_SCHEMA.md`, machine-readable `QUESTION_SCHEMA_TP-Q-2.0.0.json`. The 1.0.0 export is kept.

## Running it locally

```
pip install fastapi uvicorn pydantic httpx pytest            # repo requirements already list fastapi/uvicorn/pydantic
CSS_ONBOARDING_DIR=/tmp/passport CSS_PASSPORT_DEMO=1 \
  uvicorn backend.app.onboarding.standalone:app --port 8790   # never 8765
# open http://127.0.0.1:8790/  (sign in through the existing /auth flow)
python -m pytest tests/onboarding tests/trade_origin -q
# browser tests: pip install playwright; npm install axe-core; set CSS_AXE_PATH=.../axe-core/axe.min.js
```

## Integration (deferred until OV-002 completes)

Design only, in `POST_OV002_INTEGRATION.md`. It covers the recommendation → order → R7 → R14F → AntiBleedGuard →
broker → fills → lots → closes → P&L → ledgers → dashboard path, the journals, persistence tables and the release
sequence. Nothing in that path was modified. The Passport is not mounted in the production runtime.

## Gates remaining

| Gate | Owner |
|---|---|
| Wording review: risk statements, Auto description, expectations messages, "not investment advice" positioning, country-specific suitability rules | Compliance / legal |
| Whether a questionnaire like this triggers regulatory suitability or appropriateness obligations in each target country | Compliance / legal |
| Privacy: lawful basis, retention period, consent wording, data-subject rights for contact and financial-profile data | Privacy / legal |
| Materiality policy TBDs: `entry_fallback_tolerance_bps`, `fill_slippage_fallback_bps`, `target_change_material`, `thesis_break_disposition`; confirm or raise the zero size/leverage allowances (`ATTRIBUTION_SPEC.md`) | Owner / compliance |
| Commercial policy: modified-trade treatment, fee rate (owner-stated 20% concept), loss-recovery method, approval reference; authoritative source of the existing hurdles (`COMMERCIAL_ATTRIBUTION.md`) | Owner / compliance |
| Classification of today's system-generated positions (no user Trade Card step exists yet) | Owner |
| Integration per `POST_OV002_INTEGRATION.md`, after OV-002 completes | Owner / release |
| Physical S24 device validation (only emulated here) and human UX review | Owner / QA |
| Merge, deploy, release | Owner |
