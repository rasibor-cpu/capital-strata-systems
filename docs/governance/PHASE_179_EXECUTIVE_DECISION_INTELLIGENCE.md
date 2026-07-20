# PHASE 179 — Executive Decision Intelligence Engine

**Repository:** `C:\rasib\source\capital-strata-systems`  
**Branch:** `css-unified-consolidation-2026-07-13`  
**Baseline HEAD:** `3d45e26bc1ef5df707bd181e94e156890b966d1c`  
**Phase type:** Implementation — orchestration / decision-support  
**Status:** COMPLETE (pending commit authorization)  
**Date:** 2026-07-19  

---

## Purpose

Build the canonical **Executive Decision Intelligence (EDI)** layer that consumes existing CSS intelligence and produces executive recommendations.

EDI is an **orchestration and decision-support layer only**.

---

## Explicit boundaries

| EDI does | EDI does not |
|----------|--------------|
| Consume Phase 177/178 packages via existing services | Recalculate income/balance/cash-flow statements |
| Consume Phase 176J readiness signals when present on MC state | Duplicate Phase 178 packaging math |
| Rank priorities / risks / opportunities from categorical signals | Read brokers or live execution engines |
| Produce advisory recommendations and scorecards | Allocate capital or change portfolios |
| Expose read-only APIs and an MC card | Create trading or execution authority |

- `advisory_only=true`
- `trading_impact=false`
- No mutation endpoints

---

## Architecture

```
Mission Control state
  ├─ Phase 178 ExecutiveFinancialReportingService.generate_from_state
  │    (which internally uses Phase 177 CanonicalFinancialReportingEngine)
  ├─ Phase 176J readiness blob on state (if present)
  └─ MC categorical sections (platform / risk / alerts / freshness)
        ↓
ExecutiveDecisionEngine
  ├─ decision_confidence
  ├─ executive_priorities (from Phase 178 management actions + ops flags)
  ├─ risk_priorities
  ├─ opportunity_priorities
  ├─ management_recommendations
  ├─ resource_allocator (advisory focus labels only)
  └─ executive_scorecard
        ↓
ExecutiveDecisionIntelligenceService
        ↓
API (GET-only) + Mission Control EDI card
```

### Reuse (no duplicate engines)

| Existing component | Reuse |
|--------------------|-------|
| Phase 177 engine | Via Phase 178 service only |
| Phase 178 service / management actions | Primary financial posture inputs |
| Phase 176J readiness | Optional categorical state on MC |
| Executive Intelligence (174/175) | Not replaced; EDI is a separate decision layer |
| Reports Center | Unchanged in this phase |

---

## Package layout

`backend/executive_decision_intelligence/`

| Module | Role |
|--------|------|
| `decision_engine.py` | Orchestrator |
| `decision_models.py` | Schema / constants |
| `decision_prioritizer.py` | Dedupe + ordering |
| `decision_confidence.py` | Confidence from categorical signals |
| `executive_priorities.py` | Priority list |
| `risk_priorities.py` | Risk ranking |
| `opportunity_priorities.py` | Opportunity ranking |
| `management_recommendations.py` | Advisory recommendations |
| `resource_allocator.py` | Advisory focus areas (non-allocating) |
| `executive_scorecard.py` | Scorecard rows |
| `adapters.py` | Upstream extraction |
| `service.py` | Public facade |

---

## Inputs

- Phase 178 financial summary + management actions (via service)
- Phase 177 nested readiness / statement integrity flags (as surfaced by 178)
- Phase 176J readiness on MC state when available
- Mission Control: platform, runtime, risk, alerts, data freshness, portfolio presence

Never: direct broker adapters, execution engines, schedulers, credentials, live authority.

---

## Outputs

- `executive_state` — STABLE / ATTENTION / STRESSED / NOT_READY / DEGRADED
- Priorities, immediate actions, escalations
- Risk ranking, opportunity ranking
- Recommendations + resource priorities
- Scorecard + confidence
- Recommended next action / executive focus
- Upstream provenance + limitations + disclaimer

---

## APIs

| Method | Path |
|--------|------|
| GET | `/api/executive-decision-intelligence/summary` |
| GET | `/api/executive-decision-intelligence/priorities` |
| GET | `/api/executive-decision-intelligence/risks` |
| GET | `/api/executive-decision-intelligence/opportunities` |
| GET | `/api/executive-decision-intelligence/recommendations` |
| GET | `/api/executive-decision-intelligence/scorecard` |

Mounted once on `launcher/css_mobile_launcher.py`.

---

## Mission Control

Card `#executive-decision-intelligence` (`data-phase="179"`) on Executive Overview:

- Overall executive state
- Top five priorities
- Top risks
- Top opportunities
- Recommended next action
- Confidence
- Generation timestamp

---

## Limitations

- Opportunity ranking is categorical and intentionally conservative.
- Thin live MC feeds yield NOT_READY / ATTENTION more often than STABLE.
- Does not replace Morning Brief / EI archive products.
- Does not forecast, budget, or produce board packs.
- Live launcher may need restart to load new routes if an older process holds port 8765.

---

## Future roadmap (out of scope)

- Richer multi-day opportunity models
- Optional EDI report in Reports Center
- Notification fan-out for CRITICAL escalations
- Deeper EI archive correlation

---

## Safety

Advisory decision-support only. Not audited statutory reporting. No execution authority.
