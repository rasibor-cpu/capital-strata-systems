# Phase 176J — Executive Brief Readiness Orchestrator

**Status:** Advisory / read-only  
**Scope:** Canonical readiness layer for Executive Brief generation  
**Non-goals:** Trading decisions, portfolio management, execution, broker connectivity mutations, runtime scheduling

---

## Architecture

```
Mission Control state / evidence snapshot
        │
        ▼
ExecutiveBriefReadinessOrchestrator  (backend/reporting/)
        │
        ├── Component assessments (blocking / warning / advisory)
        ├── overall_readiness_score
        └── ExecutiveBriefReadinessReport
                │
                ├── GET /api/executive-brief/readiness
                └── Mission Control Executive Overview card
```

The orchestrator lives in the **reporting** package so it remains a presentation/governance concern. It evaluates evidence only. It does **not** call brokers, arm execution, mutate runtime controls, or alter report schedulers.

| Layer | Path |
|-------|------|
| Orchestrator | `backend/reporting/executive_brief_readiness_orchestrator.py` |
| API | `dashboard/runtime/api/executive_brief_readiness.py` |
| UI card | `dashboard/mission_control/pages/executive_overview.py` |
| Tests | `tests/test_phase176j_executive_brief_readiness.py` |

### Dual-layer note (not a duplicate API)

A separate generation-wait evaluator exists under `backend/executive_intelligence/` (`READY` / `WAITING` / `FAILED`) for Daily Executive Brief wait/retry UX. That path is **not** the Mission Control advisory score API.

Canonical Phase 176J advisory readiness for operators is:

- module: `backend.reporting.executive_brief_readiness_orchestrator`
- states: `GREEN` / `AMBER` / `RED` / `NOT_READY`
- endpoint: `GET /api/executive-brief/readiness` (mounted once on the launcher)

---

## Decision flow

1. Collect evidence (explicit dict, or map from Mission Control state via `evidence_from_mission_control_state`).
2. Assess each canonical component (present / ready / warning / missing / outdated / unavailable), isolating per-component exceptions.
3. Classify gaps into **blocking**, **warning**, and **advisory** lists; record **missing** and **outdated** datasets (exclusive per component).
4. Compute `overall_readiness_score` (0–100).
5. Resolve `overall_state` with explicit precedence (below).
6. Align score ceilings to the resolved state (prevent contradictory high scores).
7. Emit `recommended_actions` and `estimated_generation_time`.
8. Serialize via `to_dict()` for API / UI.

No step writes to brokers, runtime artifacts (beyond read), execution authority, or schedulers. Evidence is deep-copied before evaluation.

---

## Readiness model

### Components verified (exactly 13)

| # | Component | Severity |
|---|-----------|----------|
| 1 | Runtime | Blocking |
| 2 | Broker Connectivity | Blocking |
| 3 | Portfolio Snapshot | Blocking |
| 4 | Risk Metrics | Warning |
| 5 | PnL | Warning |
| 6 | Income Statement | Advisory |
| 7 | Balance Sheet | Advisory |
| 8 | Cash Flow | Advisory |
| 9 | Market Intelligence | Warning |
| 10 | AI Recommendation Summary | Advisory |
| 11 | Open Alerts | Warning |
| 12 | System Health | Warning |
| 13 | Reporting Data Freshness | Blocking |

Each component result includes: `key`, `label`, `severity`/`classification`, `status`, `message`, `age_seconds`, `freshness_timestamp` (only when upstream provides it), `recommended_action`, `source_available`.

Unavailable upstream data is never invented as healthy.

### Score model (effective weighting)

Per-component contribution in `[0, 1]`:

| Status | Base |
|--------|------|
| ready | 1.00 |
| warning | 0.55 × severity weight |
| outdated | 0.15 × severity weight |
| missing / unavailable | 0.00 |

Severity weights when not ready: blocking `1.00`, warning `0.85`, advisory `0.65`.

`overall_readiness_score = mean(contributions) × 100`, clamped to `[0, 100]`, then state-aligned:

| State | Max retained score |
|-------|--------------------|
| GREEN | 100 |
| AMBER | 84.9 |
| RED | 69.0 |
| NOT_READY | 49.0 |

Warnings penalize less than blockers/missing; duplicate list penalties are prevented via exclusive status + de-duplicated item strings.

### State precedence

1. **NOT_READY** — mandatory (blocking) datasets missing or unavailable  
2. **RED** — mandatory datasets outdated / materially unhealthy but evaluable, or score &lt; 60 with residual issues  
3. **AMBER** — usable but degraded (any warning items, soft blockers, or score &lt; 85)  
4. **GREEN** — score ≥ 85 **and** no blocking items **and** no warning items (advisory gaps alone may still reduce score below GREEN)

---

## State transitions (advisory)

```
evidence refresh
      │
      ▼
 assess components ──► missing/unavailable blocking ──► NOT_READY
      │
      ├── outdated blocking freshness ──► RED
      ├── warnings / soft degradation ──► AMBER
      └── all mandatory clear, high score, no warnings ──► GREEN
```

---

## API

```
GET /api/executive-brief/readiness
```

Mounted **once** on the canonical launcher. Response includes:

- `timestamp` (timezone-aware UTC, `...Z`)
- `overall_state`
- `score` / `overall_readiness_score`
- `blocking_items`, `warning_items`, `advisories`
- `missing_datasets`, `outdated_datasets`
- `recommended_actions`
- `estimated_generation_time`
- `components[]`
- `advisory_only: true`, `trading_impact: false`

Exception behavior: provider / mapping / evaluation failures return HTTP 200 with fail-closed `NOT_READY` payload (no stack traces, no secrets).

---

## Mission Control UI

Executive Overview **Executive Brief Readiness** card shows Overall State, Score, Missing Components, Warnings, Estimated Generation Time.

- Computed from the MC snapshot during page render (no extra polling loop)
- Distinct CSS classes for GREEN / AMBER / RED / NOT_READY (`NOT_READY` must not render as “good”)
- Defensive empty / evaluation-failure markup so the rest of Executive Overview remains usable

---

## Testing

```bash
.venv\Scripts\python.exe -m pytest tests/test_phase176j_executive_brief_readiness.py -q
.venv\Scripts\python.exe -m compileall backend\reporting dashboard\runtime\api
```

---

## Safety requirements (confirmed)

- Read-only evaluation  
- No broker modifications  
- No runtime modifications  
- No execution changes  
- No scheduler changes  
- No trading impact  
- No database schema changes  

---

## Phase 176J.1 certification

### Implementation review result

- Canonical advisory orchestrator: `backend/reporting/executive_brief_readiness_orchestrator.py`
- Router registered once in `launcher/css_mobile_launcher.py`
- Imports use project paths; no circular import between reporting ↔ runtime API
- UTC timestamps; deep-copied evidence; no trading/broker side effects
- Coexistence with EI wait/retry readiness documented (different module + state vocabulary)

### Exception behavior

- Per-component try/except → `unavailable` with safe message  
- API outer try/except → fail-closed JSON, HTTP 200  
- UI card try/except → local NOT_READY panel, page continues  

### UI behavior

- Snapshot-rendered card; link to API for operators  
- Long lists truncated with “+N more”  
- Missing values display as `None` / `—`, never `undefined` / `null` / `[object Object]`  

### Known limitations

- Live component freshness depends on MC state field richness; many sources lack explicit timestamps  
- Financial statement components are often advisory-missing until institutional reporting feeds them  
- EI wait-orchestrator (`READY/WAITING/FAILED`) remains a separate generation path pending Phase 177 consolidation  

### Future Phase 177 integration boundary

- Phase 177 may unify operator advisory score with generation wait UX **without** granting trading authority  
- Do not wire this layer into broker arming, execution gates, or schedulers without an explicit future phase  
- Optional: Reports Center can display the same `to_dict()` payload without mutating generate pipelines  

---

## Future integration

- Optionally surface the same report inside Reports Center without coupling to generate/wait loops.
- Consumers may gate **operator UX** (labels, confirmations) on `overall_state` while leaving DEB generation policy decisions to separate governance phases.
- Do **not** wire this layer into live trading, broker arming, or scheduler enablement without an explicit future phase.
