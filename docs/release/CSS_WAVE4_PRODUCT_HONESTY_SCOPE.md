# CSS Wave 4 — Product Honesty Scope (Gate 2)

**Programme:** Release Gate 2 — Wave 4  
**Date:** 2026-07-22  
**Authority:** Remediation Register AR-017 / AR-047 / AR-018  
**Safety posture:** `DISABLED / BLOCKED / FAIL_CLOSED / ADVISORY_ONLY`

This document is the Gate-2 product honesty authority for customer-visible capability declarations. It does **not** authorize new report generators, live notifications, EIS completion, or certification.

---

## 1. Institutional reporting V1 MVP (AR-017)

### MVP (generatable / customer-presentable in Gate 2)

Only reports with catalogue status `AVAILABLE` or `AVAILABLE_WITH_LIMITATIONS` and a registered producer are MVP-eligible. Live counts are exposed by `backend.product_honesty.catalogue_honesty_summary()` (do not treat the capability matrix header totals as the sole authority if the catalogue has grown).

MVP principle:

- Generatable reports may be offered with their declared limitations.
- `COMING_SOON` / `DATA_UNAVAILABLE` / `DISABLED` entries are **roadmap inventory only** — not delivered product.

### Non-claims

- Registered catalogue size is **not** reporting coverage (see live `registered_count` vs `generatable_count`).
- Phase 176 “catalogue completeness” means registry honesty, **not** institutional suite completion.

---

## 2. Board / investor / regulatory scope (AR-047)

**Gate 2 decision: OUT OF SCOPE**

| Capability | Gate 2 disposition |
| --- | --- |
| Board packs | OUT OF SCOPE — future |
| Investor client statements as commercial product | OUT OF SCOPE — future |
| Regulatory / statutory audited packs | OUT OF SCOPE — future |

Any UI, enum, or module language implying these are delivered Gate-2 products is superseded by this decision.

---

## 3. Executive Intelligence / 182A dashboard (AR-018)

**Gate 2 decision: DEFER full EIS / 182A dashboard as released capability**

| Surface | Gate 2 disposition |
| --- | --- |
| Mission Control Executive Overview | Advisory / operational visibility only |
| Phase 182A Executive Intelligence Foundation | Deferred — not a released customer dashboard |
| Board / investor EIS packs | OUT OF SCOPE (see AR-047) |

Uncommitted or foundation EIS work must not be marketed as a complete executive intelligence product.

---

## 4. Executive report classification (AR-042)

All executive financial packages remain:

- `management_report=true`
- `not_audited_statutory_statements=true`
- Missing feeds → unavailable / fail-closed — never fabricated healthy zeros for certification claims

---

## 5. Notifications (AR-022)

Default: **non-operational**. Simulated dry-run is permitted for tests. Silent success on non-dry-run channels without `CSS_NOTIFICATIONS_OPERATIONAL=1` is prohibited.

---

## 6. PWA (AR-025) / Options (AR-031)

- PWA: canonical install authority remains `docs/operations/CSS_PWA_CANONICAL_INSTALL.md` (PARTIAL until signed physical HTTPS install).
- Options advisory empty-registry honesty remains CLOSED (Wave 2).

---

*End of Wave 4 product honesty scope. Does not authorize deployment or live trading.*
