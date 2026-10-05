# CSS Trader Passport (Issue #102)

Progressive, mobile-first onboarding that builds an explainable **Trader Passport**, plus a trade-origin model that keeps
**CSS-recommended** and **user-independent** trades separate from recommendation to performance.

Status: **software built and tested on an isolated branch; not merged, not deployed, not connected to the governed
execution path.** Owner, compliance and release gates remain (see the end of this file).

## What is where

| Path | Purpose |
|---|---|
| `backend/app/onboarding/schema.py` | Versioned questionnaire `TP-Q-1.0.0`: 25 stages, adaptive `show_if` branching. Single source of truth for server, UI and tests |
| `backend/app/onboarding/engine.py` | Visibility, validation (fail closed), navigation, resume, answer provenance, pruning of answers on newly hidden stages |
| `backend/app/onboarding/rules.py` | Recommendation rules `TP-R-1.0.0`: Passport with `because` evidence for every output. No suitability score, no Auto recommendation, `execution_authority_granted` always `False` |
| `backend/app/onboarding/service.py` | Start/resume, submit, back, complete, profile updates; append-only revisions |
| `backend/app/onboarding/store.py` | JSON store per user, salted-hash file names, atomic writes, mode 0600, no answer values in logs |
| `backend/app/onboarding/router.py` | FastAPI router under `/passport`, existing CSS bearer sessions (`backend.app.auth.token_store`), serves the UI |
| `backend/app/onboarding/standalone.py` | Development app (auth + Passport only). Run on any port **except 8765** |
| `backend/app/trade_origin/model.py` | `TradeOrigin`, immutable `OriginEvidence`, `classify_order`, append-only `OriginLedger`, policy `TO-1.0.0` |
| `backend/app/trade_origin/lifecycle.py` | Origin through fills, lots, partial/final closes and journal entries |
| `backend/app/trade_origin/performance.py` | Segregated performance, total = sum of segments (checked), legacy records held for review |
| `backend/app/trade_origin/demo.py` | Synthetic sample for the results view, shown only with `CSS_PASSPORT_DEMO=1` and labelled as sample |
| `frontend/trader_passport/` | Vanilla HTML/CSS/JS client (no build step, no external fonts or CDNs) and 8 original SVG assets |
| `tests/onboarding/`, `tests/trade_origin/` | 71 unit/integration tests + 8 browser tests (Playwright + axe-core) |
| `docs/product/trader_passport/` | This documentation, schema export, rules, attribution and UX specs, evidence, artifact register |

## Screen flow (adaptive)

Phones see one principal decision per screen: 18 decision screens on the shortest path, 20 on the longest, plus four
short explanatory interstitials. The progress indicator counts the steps that are visible for that user.

1. **Welcome** (interstitial): what CSS is; Discover, Confirm and Auto explained; risk statement; required acknowledgement.
2. **About you**: preferred name, optional full name, email, optional phone, country, preferred channel, separate opt-in consents.
3. **Goals and priorities**: up to three objectives, then the top three priorities in order.
4. **Experience by market**: one band (none to experienced) for each of six asset classes.
5. **Knowledge check intro** (interstitial).
6. **Orders and sizing**: four diagnostic questions, always with an "I'm not sure yet" option.
7. **Volatility, drawdown, diversification, exposure**: four questions.
8. **Strengths**: up to four.
9. **Decision behaviour**: six questions.
10. **Risk intro** (interstitial): capacity vs tolerance.
11. **Risk capacity**: capital band, dependence, emergency fund, horizon, maximum tolerable fall.
12. **Risk tolerance**: six comfort questions.
13. **Barriers**.
14. **Markets and holding periods**.
15. **Leverage and margin** *(only if the user has leveraged-market experience, active or new-market objectives, or chose FX, crypto, options or futures)*: two quiz questions and leverage intent.
16. **CSS assistance**: Discover, Confirm or *interested in* Auto.
17. **What Auto does and doesn't change** *(only if Auto interest was chosen)*.
18. **Features**.
19. **Time and engagement**.
20. **Expectations intro** (interstitial).
21. **Expectations: CSS's role**: role, frequency, holding period, automation, communication.
22. **Expectations: risk and results**: risk, acceptable fall, hoped-for yearly result (aspiration, with a no-guarantee note), what success means.
23. **True or false**: profitable every trade, losses possible, Auto guarantees returns, CSS compensates losses.
24. **Before your Passport**: how CSS separates its trades from yours, plus four acknowledgements (attribution, no guarantee, recommendation is not authority, own responsibility).
25. **Trader Passport** (result): built on request, then the separated-results view.

Full question list: `QUESTION_SCHEMA.md`, machine-readable `QUESTION_SCHEMA_TP-Q-1.0.0.json`.

## Running it locally

```
pip install fastapi uvicorn pydantic httpx pytest            # repo requirements already list fastapi/uvicorn/pydantic
CSS_ONBOARDING_DIR=/tmp/passport CSS_PASSPORT_DEMO=1 \
  uvicorn backend.app.onboarding.standalone:app --port 8790   # never 8765
# open http://127.0.0.1:8790/  (sign in through the existing /auth flow)
python -m pytest tests/onboarding tests/trade_origin -q
# browser tests: pip install playwright; npm install axe-core; set CSS_AXE_PATH=.../axe-core/axe.min.js
```

## Integration points (not done in this tranche, by design)

These change governed or running surfaces. They need owner approval and a window that doesn't touch OV-002.

1. **Mount the router** in the production web app (`dashboard/web/web_app.py` `create_app`: `app.include_router(create_onboarding_router())`) or in the API app, behind the existing auth. Not done here because the file may be part of the frozen OV-002 runtime.
2. **Record origins in the order path**: wherever a Trade Card or manual order becomes an order, call `classify_order` and `OriginLedger.record` before submission. The Trade Card UI must pass `recommendation_id` and `card_fingerprint`; manual orders pass neither. This touches the governed execution path (R7/R14F/AntiBleedGuard sit nearby) and was deliberately left out.
3. **Lifecycle hooks**: feed broker fills and closes into `TradeLifecycle` (lot id = opening order id), and persist `OriginLedger` and the journal (currently in-memory) in the CSS persistence layer.
4. **Trade warehouse**: add `origin` and `recommendation_id` to `dashboard/trade_warehouse/trade_record_contract.TradeRecord` (additive, defaulted). Until then, existing records are reported as **Origin under review** by `from_legacy_closed_trades`, never guessed.
5. **Persistence**: move `OnboardingStore` from JSON files to `backend/app/persistence` with the same encryption and retention rules as other personal data.
6. **Legal acceptance**: the Passport's acknowledgements are not legal acceptance. The production flow should send users to `backend.app.compliance.legal_acceptance*` for the CSS Terms and the Trading Risk Disclosure.

## Gates remaining

| Gate | Owner |
|---|---|
| Wording review: risk statements, Auto description, expectations messages, "not investment advice" positioning, country-specific suitability rules | Compliance / legal |
| Whether a questionnaire like this triggers regulatory suitability or appropriateness obligations in each target country | Compliance / legal |
| Privacy: lawful basis, retention period, consent wording, data-subject rights for contact and financial-profile data | Privacy / legal |
| Material-change tolerances for CSS_RECOMMENDED_MODIFIED (`MATERIAL_TOLERANCES`, policy `TO-1.0.0`) | Owner |
| How modified and under-review trades are treated by the existing approved commercial-attribution rules (not changed here) | Owner |
| Integration steps 1–6 above, scheduled away from OV-002 | Owner / release |
| Physical S24 device validation (only emulated here) and human UX review | Owner / QA |
| Merge, deploy, release | Owner |
