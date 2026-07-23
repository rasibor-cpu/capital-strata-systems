# CSS Commercial Readiness Programme

**Document ID:** CEP-PROG-001
**Effective date:** 2026-07-22
**Repository baseline:** `34503b155d6e1274863d0b137e23b145d2901e1e`
**Branch:** `css-unified-consolidation-2026-07-13`
**Status:** Active programme record

---

## Programme objective

Prepare Capital Strata Systems for truthful, governed commercial presentation by establishing:

* an Enterprise Master Book,
* evidence-linked commercial claims,
* website and collateral standards,
* pricing and licensing principles,
* customer and pilot documentation,
* launch-readiness controls,

without contradicting canonical release status and without interfering with Desktop Operational Validation.

---

## Workstreams

| ID | Workstream | Objective | Status |
| --- | --- | --- | --- |
| CEP-001 | Master Book Framework | Governance, TOC, writing standard, claims register, programme record | **Complete (draft awaiting approval)** |
| CEP-002 | Executive Overview | Draft Master Book Volume 1 | **Next approved phase** |
| CEP-003 | Website | Evidence-linked public site structure and copy rules | Not started |
| CEP-004 | Pricing and Licensing | Editions, licensing principles, pricing framework | Not started |
| CEP-005 | Customer Documentation | Customer-facing product and operations docs | Not started |
| CEP-006 | Sales and Investor Materials | Brochures, decks, investor summaries | Not started |
| CEP-007 | Pilot Programme | Pilot scope, selection, success and exit criteria | Not started |
| CEP-008 | Launch Readiness | Final commercial launch checklist against release status | Not started |

---

## Dependencies

1. Canonical release status remains authoritative.
2. Commercial claims require repository evidence and Claims Register classification.
3. Website, sales, and investor materials depend on approved Master Book sections.
4. Pilot and launch readiness depend on certification / operational-validation outcomes where those claims are made.
5. Desktop Operational Validation (including OV-002) must not be disturbed by commercial documentation work.

---

## Non-interference rule — Desktop Operational Validation

Commercial Readiness work on the Laptop:

* must not restart, access, or alter Desktop runtime services,
* must not modify OV-002 evidence,
* must not change application code or runtime configuration unless a later CEP explicitly authorises engineering work,
* must preserve existing untracked Laptop artefacts and stashes unless separately approved.

---

## Current status

| Item | State |
| --- | --- |
| Repository baseline | `34503b155d6e1274863d0b137e23b145d2901e1e` |
| Production certification | NOT CERTIFIED / NO-GO |
| Commercial readiness (release authority) | NO-GO |
| Live trading | Blocked |
| CEP-001 framework artefacts | Created under `docs/enterprise_master_book/` and `docs/commercial/` |
| Public commercial launch | Not authorised |

---

## Success criteria

CEP programme success requires:

1. Master Book framework approved.
2. Volume content drafted with evidence-linked claims.
3. Derived materials cite Master Book sections.
4. No contradiction with canonical release status.
5. Desktop Operational Validation remains undisturbed.
6. Launch materials remain unpublished until release status permits the claimed posture.

---

## Next approved phase

**CEP-002 — Volume 1 drafting (Executive Overview)**

Do not begin Volume 1 until CEP-001 is approved or approved with conditions.

---

## Related documents

* [../enterprise_master_book/README.md](../enterprise_master_book/README.md)
* [../enterprise_master_book/CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md](../enterprise_master_book/CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md)
* [CSS_EXECUTIVE_REPORT_CEP001.md](CSS_EXECUTIVE_REPORT_CEP001.md)
* [../release/CSS_CANONICAL_RELEASE_STATUS.md](../release/CSS_CANONICAL_RELEASE_STATUS.md)
