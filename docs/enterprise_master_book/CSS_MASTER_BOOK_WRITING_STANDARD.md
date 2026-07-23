# CSS Master Book — Writing Standard

**Document ID:** EMB-WS-001
**Master Book version:** 0.1.0-framework
**Effective date:** 2026-07-22
**Repository baseline:** `34503b155d6e1274863d0b137e23b145d2901e1e`
**Status:** DRAFT — pending approval with CEP-001

---

## 1. Purpose

This standard defines how CSS commercial and Master Book content must be written so that product language remains truthful, consistent, and evidence-linked.

---

## 2. Core writing rules

1. Use **plain business language**. Prefer clarity over marketing flourish.
2. Do **not** use unsupported superlatives (“best,” “unmatched,” “industry-leading”) without evidence.
3. Do **not** claim profitability of the CSS product or of customer trading outcomes.
4. Do **not** guarantee investment outcomes, returns, or risk elimination.
5. Do **not** claim live trading capability unless formally certified and authorised by release status.
6. Keep a **clear separation** between delivered and planned functionality.
7. Keep executive summaries concise and decision-oriented.
8. Use **consistent terminology** from this standard and the Claims Register.
9. Link every material claim to repository evidence and a status classification.
10. Frame benefits around customer value without inventing readiness.
11. Do **not** disclose proprietary implementation internals beyond what is needed for honest product description.

---

## 3. Approved terminology

Use these terms when they accurately reflect evidence:

| Term | Intended use |
| --- | --- |
| advisory-only | Decisions or recommendations without execution authority |
| read-only validated | Broker or market connectivity validated without order placement |
| fail-closed | Unsafe or incomplete conditions block execution |
| execution blocked | Order placement is not permitted under current controls |
| not certified | Required certification has not been achieved |
| operationally validated | Named operational-validation evidence exists for the stated scope |
| pilot | Limited deployment under approved pilot terms |
| planned | Named future release intent |
| future release | Directional roadmap without firm commitment |

---

## 4. Prohibited or restricted terminology

Do **not** use the following unless formally evidenced and approved in the Claims Register:

| Restricted term | Restriction |
| --- | --- |
| production-ready | Prohibited unless Phase 181 / production certification is GO |
| institutionally certified | Prohibited unless a named institutional certification exists |
| fully automated | Prohibited unless automation scope is evidenced and bounded |
| live trading enabled | Prohibited while live trading is blocked / not certified |
| guaranteed | Prohibited for outcomes, profits, or risk elimination |
| risk-free | Prohibited |
| complete broker support | Prohibited; list only evidenced brokers and modes |
| all reports available | Prohibited; list only evidenced report families and limitations |

Related restricted marketing phrases without evidence:

* enterprise-ready
* commercially ready
* fully certified
* unlimited
* always available

---

## 5. Claim construction pattern

Every material claim should follow:

1. **Capability** — what is being described
2. **Classification** — `DELIVERED`, `PILOT`, `VALIDATED_READ_ONLY`, `PLANNED`, `FUTURE`, `NOT_CERTIFIED`, or `OUT_OF_SCOPE`
3. **Scope** — advisory / paper / read-only / pilot / planned
4. **Evidence** — document path or register ID
5. **Limitation** — what is not included

### Example (illustrative pattern only)

> Mission Control provides governed operational visibility for controlled paper and advisory operation (`DELIVERED` within documented scope). Live trading is not enabled (`execution blocked`).

---

## 6. Tone and audience

* Executive audiences: short, status-first, decision-relevant.
* Customer audiences: benefit-framed, limitation-honest, no jargon overload.
* Investor audiences: evidence-forward; separate delivered capability from roadmap.
* Technical audiences: may reference architecture at a high level; avoid proprietary deep internals in commercial materials.

---

## 7. Related documents

* [CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md](CSS_ENTERPRISE_MASTER_BOOK_GOVERNANCE.md)
* [CSS_COMMERCIAL_CLAIMS_REGISTER.md](CSS_COMMERCIAL_CLAIMS_REGISTER.md)
* [../release/CSS_CANONICAL_RELEASE_STATUS.md](../release/CSS_CANONICAL_RELEASE_STATUS.md)
