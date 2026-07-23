# CSS Enterprise Master Book — Governance

**Document ID:** EMB-GOV-001
**Master Book version:** 0.1.0-framework
**Effective date:** 2026-07-22
**Repository baseline:** `34503b155d6e1274863d0b137e23b145d2901e1e`
**Branch:** `css-unified-consolidation-2026-07-13`
**Programme:** CEP-001 — Enterprise Master Book Framework
**Approval status:** DRAFT — pending executive approval

---

## 1. Purpose

The **CSS Enterprise Master Book** is the authoritative commercial and product-description source for Capital Strata Systems (CSS).

It governs:

* product positioning,
* commercial claims,
* website content,
* sales collateral,
* investor materials,
* pilot documentation,
* customer-facing product descriptions,
* certification summaries suitable for external communication.

The Master Book does **not** replace engineering design documents, runtime configuration, or the canonical release-status authority. It translates approved evidence into consistent, evidence-linked commercial language.

---

## 2. Authority Hierarchy

Commercial and external materials must respect this order of authority:

1. **Canonical release status** — `docs/release/CSS_CANONICAL_RELEASE_STATUS.md`
2. **Approved repository evidence** — SHA-bound release, certification, operational-validation, and governance artefacts
3. **Enterprise Master Book** — this framework and its approved volumes
4. **Derived commercial materials** — website, brochures, presentations, pricing sheets, pilot packs, investor decks

### Binding rule

No commercial material may contradict the canonical release status or approved repository evidence.

Where conflict exists:

* the higher authority prevails,
* the lower material must be corrected or withdrawn,
* vague or aspirational wording does not override evidence.

---

## 3. Evidence Policy

Every product claim must be classified as exactly one of:

| Classification | Meaning |
| --- | --- |
| `DELIVERED` | Implemented and available within the documented controlled scope of the current release baseline |
| `PILOT` | Available only under an approved pilot programme with defined scope and success criteria |
| `VALIDATED_READ_ONLY` | Validated for advisory / read-only operation; not an execution or production-certification claim |
| `PLANNED` | Approved for a named future release; not currently deliverable |
| `FUTURE` | Directional roadmap item without firm release commitment |
| `NOT_CERTIFIED` | Capability exists or is discussed but lacks required certification for the claim being made |
| `OUT_OF_SCOPE` | Explicitly excluded from current commercial offering |

### Prohibited vagueness

Do **not** use unsupported phrases such as:

* “available,”
* “enterprise-ready,”
* “production-ready,”
* “fully certified,”
* “complete,”

unless the claim is bound to a classification above **and** to repository evidence.

### Evidence linkage requirement

Every claim in the Master Book or Claims Register must cite:

* classification,
* evidence source path or document ID,
* applicable restrictions,
* approved wording.

---

## 4. Versioning

Each Master Book release must record:

| Field | Requirement |
| --- | --- |
| Master Book version number | Semantic version (for example `0.1.0-framework`, later `1.0.0`) |
| Effective date | Calendar date of approval |
| Repository commit | Full SHA of the baseline used for claims |
| Approval status | `DRAFT`, `IN_REVIEW`, `APPROVED`, `SUPERSEDED`, or `WITHDRAWN` |
| Change log | Summary of material changes since prior version |
| Supersession rules | Which prior Master Book version is replaced |

### Supersession rules

1. Only one Master Book version may be `APPROVED` at a time for external use.
2. A new approved version supersedes the previous approved version on its effective date.
3. Derived materials citing a superseded Master Book version must be updated or marked obsolete.
4. Framework drafts (`0.x`) may guide internal drafting but are not authority for public claims until executive approval.

### Current framework record

| Field | Value |
| --- | --- |
| Version | `0.1.0-framework` |
| Effective date | 2026-07-22 |
| Repository commit | `34503b155d6e1274863d0b137e23b145d2901e1e` |
| Approval status | `DRAFT` |
| Change log | Initial CEP-001 governance framework, TOC, writing standard, claims register, and programme record |
| Supersedes | None (initial framework) |

---

## 5. Review and Approval

Before a Master Book version may be marked `APPROVED`, the following reviews are required:

| Review | Responsibility | Focus |
| --- | --- | --- |
| Executive approval | Executive owner | Positioning, commercial risk, go/no-go for external use |
| Engineering evidence review | Engineering lead | Claim-to-evidence accuracy; no fabricated readiness |
| Release-status review | Release authority | Consistency with `CSS_CANONICAL_RELEASE_STATUS.md` |
| Commercial consistency review | Commercial / communications owner | Terminology, collateral consistency, prohibited wording |

All four reviews must be recorded before approval.

---

## 6. Derived Document Rules

Every website page, brochure, presentation, pricing sheet, investor deck, and pilot document must:

1. Cite the relevant Master Book section ID internally (for example Volume 1 / claim IDs).
2. Use only approved wording from the Master Book or Claims Register.
3. Carry the same classification discipline as the Master Book.
4. Be withdrawn or revised if the Master Book or canonical release status changes in a conflicting way.
5. Avoid inventing capabilities, certifications, or broker readiness not present in approved evidence.

Derived documents are **downstream**. They do not create new authority.

---

## 7. Non-interference with Operational Validation

Desktop Operational Validation remains a protected environment.

Master Book and commercial-readiness documentation work:

* must not restart, access, or alter Desktop runtime services,
* must not alter OV-002 evidence,
* must not modify application code or runtime configuration as part of CEP-001.

---

## 8. Related documents

* [CSS_ENTERPRISE_MASTER_BOOK_TOC.md](CSS_ENTERPRISE_MASTER_BOOK_TOC.md)
* [CSS_MASTER_BOOK_WRITING_STANDARD.md](CSS_MASTER_BOOK_WRITING_STANDARD.md)
* [CSS_COMMERCIAL_CLAIMS_REGISTER.md](CSS_COMMERCIAL_CLAIMS_REGISTER.md)
* [README.md](README.md)
* [../commercial/CSS_COMMERCIAL_READINESS_PROGRAMME.md](../commercial/CSS_COMMERCIAL_READINESS_PROGRAMME.md)
* [../release/CSS_CANONICAL_RELEASE_STATUS.md](../release/CSS_CANONICAL_RELEASE_STATUS.md)
