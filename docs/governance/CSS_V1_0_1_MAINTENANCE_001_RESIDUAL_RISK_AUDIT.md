# CSS v1.0.1 — Maintenance Workstream 001  
## Residual-Risk Audit and Prioritization

**Programme:** CSS v1.0.1 Maintenance  
**Workstream:** MW-001 / RR-001  
**Status:** **IMPLEMENTED — VALIDATION COMPLETE (uncommitted)**  
**Workspace:** Laptop development (`C:\rasib\source\capital-strata-systems`)  
**Branch:** `css-v1.0.1-maintenance`  
**Baseline HEAD:** `b0703f36096bf183514293ef9b83b6e7849bd087`  
**Date:** 2026-07-29  
**Scope:** Residual-risk audit + RR-001 equity_peak persistence/read-path repair  
**Does not authorize:** live trading, OV-002, production deployment, desktop runtime interference

---

## 1. Executive summary

RC-004 approved `b0703f3` as the certified **controlled paper-trading** baseline with live trading **not authorized**. RR-001 (**PnL `equity_peak` schema / mobile resolution**) has been implemented on the maintenance branch and independently reviewed.

Implementation adds migration `005_pnl_snapshots_equity_peak.sql`, persists peak through repository/service (default peak=`equity` when omitted), and hardens mobile `_resolve_equity_peak_for_gate` so missing/zero/invalid peaks do not feed `0.0` into ExecutionGate while equity is positive. Historical peaks greater than equity are preserved. No gate thresholds, orchestrator, firewall, broker, or live-authority modules were changed.

**Recommendation:** `READY_TO_COMMIT` (await explicit commit approval).

---

## 2. Verified repository state

| Check | Result |
| --- | --- |
| Path | `C:\rasib\source\capital-strata-systems` |
| Branch | `css-v1.0.1-maintenance` |
| HEAD | `b0703f36096bf183514293ef9b83b6e7849bd087` |
| Worktree | clean (pre-document) |
| `HEAD...origin/css-unified-consolidation-2026-07-13` | `0 0` |
| Upstream for maintenance branch | may be absent (acceptable) |
| Desktop runtime | **not** accessed / started / stopped |

---

## 3. Evidence sources reviewed

### Certification / governance (repository)

| Source | Role |
| --- | --- |
| `docs/governance/PHASE_183J_PAPER_ACCEPTANCE_ROUTE_CERTIFICATION.md` | Paper acceptance route defect + remediation |
| `docs/release/RC002B_PAPER_ENVIRONMENT_CERTIFICATION.md` | Paper environment profile certification |
| `docs/release/CSS_CANONICAL_RELEASE_STATUS.md` | Canonical release posture (paper GO; live/prod NO-GO) |
| `docs/release/RC001_EXECUTIVE_SUMMARY.md` / `RC001_OPERATIONAL_BASELINE.md` | Engineering stabilization / ops baseline lineage |
| `docs/certification/RC1_FULL_REGRESSION_CERTIFICATION.md` | Regression certification record |
| `docs/architecture/CSS_TECHNICAL_DEBT_REGISTER.md` | Broader post-remediation debt (context; not all RC-004 residuals) |
| `docs/governance/PHASE_103A_CONTROLLED_PAPER_TRADING_REPORT.md` | Historical VolatilityPositionSizer harness warning |
| Git log at HEAD | `b0703f3` Phase 183J; `500e8b5` RC-002B |

### Operational evidence (external, not regenerated)

| Source | Role |
| --- | --- |
| `%TEMP%\css_rc003r_final_evidence_e99e6619\` | RC-003R FINAL package (`acceptance_run.json`, MC health, authority, manifest) |
| `%TEMP%\css_rc003r_evidence_0ce702fe\` | Pre-183J RC-003R package (orchestrator reject baseline) |
| RC-004 executive sign-off (session record) | Residual classifications; `EXECUTIVE_RELEASE_APPROVED`; `LIVE_TRADING_NOT_AUTHORIZED` |

### Code anchors inspected (read-only)

| Path | Relevance |
| --- | --- |
| `dashboard/mobile/mobile_app.py` | `equity_peak` consumption for ExecutionGate |
| `backend/app/persistence/migrations/sql/003_pnl_snapshots.sql` | No `equity_peak` column |
| `backend/app/persistence/repositories/pnl_snapshot_repository.py` | Insert/select contract omits `equity_peak` |
| `backend/app/persistence/services/pnl_runtime_service.py` | `create_snapshot` API omits `equity_peak` |
| `dashboard/mission_control/health.py` | `broker_state_not_green` → AMBER |
| `engine/execution/execution_gate.py` | Vol-sizer call / fallback |
| `engine/risk/volatility_position_sizer.py` | `size(notional, price, ...)` requires `price` |
| `backend/app/persistence/migrations/sql/002_trades.sql` | Partial unique open-trade index |

**Note:** No committed `docs/**` file named `RC-004` was found via `git grep`; RC-004 exists as the executive sign-off record plus the RC-003R FINAL evidence package tied to HEAD `b0703f3`.

---

## 4. Complete residual-risk register

Priority classes: **P0** safety/authority · **P1** material runtime/data/execution/accounting · **P2** reliability/observability · **P3** usability/docs/debt.

### RR-001 — PnL `equity_peak` schema / read-path gap

| Field | Value |
| --- | --- |
| 1. Finding | Mobile paper path requires `equity_peak` for ExecutionGate/RiskGovernor, but durable PnL snapshots do not persist `equity_peak`. Missing/null peak causes incorrect risk adjustment / rejection unless operators wrap reads. |
| 2. Source file | Schema: `backend/app/persistence/migrations/sql/003_pnl_snapshots.sql`; Service: `backend/app/persistence/services/pnl_runtime_service.py`; Repo: `backend/app/persistence/repositories/pnl_snapshot_repository.py`; Consumer: `dashboard/mobile/mobile_app.py` |
| 3. Line / section | Schema L1–23 (no column); consumer ~L3641–3642 (`equity = …`, `equity_peak = float(pnl_snapshot.get("equity_peak", 0.0))`); RC-003R `acceptance_run.json` risk step `equity_peak_precondition: set_to_equity_when_missing` |
| 4. Original classification | RC-004: **POST-RELEASE ENGINEERING** |
| 5. Affected subsystem | PnL persistence; mobile paper execution; RiskGovernor / ExecutionGate inputs |
| 6. Current behavior | Snapshots store equity without peak; mobile defaults missing peak to `0.0`; paper tickets may fail risk sizing |
| 7. Safety impact | Does **not** unlock live trading; may **over-block** paper (fail closed in a broken way) |
| 8. Paper-trading impact | **High** — blocks deterministic paper acceptance without operational wrap |
| 9. Live-trading relevance | Indirect (same gate inputs if live path used peak); live remains blocked by authority |
| 10. Likelihood of recurrence | **High** on any real PnL-backed mobile paper session |
| 11. Operational consequence | False risk rejects; acceptance requires non-durable workarounds |
| 12. Reproducible | **Yes** — observed in RC-003R FINAL before wrap; code/schema confirm absence |
| 13. Existing tests | Mobile tests **mock** `equity_peak=10000`; `tests/test_pnl_snapshot_persistence_contract.py` does not assert peak |
| 14. Recommended disposition | Persist and round-trip `equity_peak` (default peak=`equity` on create when omitted); harden mobile null/missing coercion |
| 15. Proposed v1.0.1 priority | **P1** |

### RR-002 — Mission Control AMBER `broker_state_not_green`

| Field | Value |
| --- | --- |
| 1. Finding | Mission Control health returned AMBER with reason `broker_state_not_green` during RC-003R FINAL while paper mode and live authority remained blocked. |
| 2. Source file | `dashboard/mission_control/health.py`; evidence `mission_control_api_health.json` |
| 3. Line / section | `health.py` L42–46 (reason append), L57–58 (AMBER if reasons); evidence health=`AMBER` |
| 4. Original classification | RC-004: **POST-RELEASE ENGINEERING** |
| 5. Affected subsystem | Mission Control health projection / broker display state |
| 6. Current behavior | When active broker `connection_status`/`readiness` ∈ FAIL/RED/UNAVAILABLE set → AMBER; safety flags still force `execution_allowed=false` |
| 7. Safety impact | **Low** — advisory surface; does not grant execution |
| 8. Paper-trading impact | **Low** — paper orders still accepted |
| 9. Live-trading relevance | Observability only; not an arming path |
| 10. Likelihood of recurrence | **Medium–High** under paper/practice broker projection gaps |
| 11. Operational consequence | Operator ambiguity (AMBER vs healthy paper session) |
| 12. Reproducible | **Yes** from RC-003R FINAL evidence |
| 13. Existing tests | Mission Control health unit coverage exists elsewhere; paper+practice green projection not certified in RC-003R |
| 14. Recommended disposition | Align paper/practice broker projection so MC does not imply failure when practice MD is healthy; keep fail-closed safety flags |
| 15. Proposed v1.0.1 priority | **P2** |

### RR-003 — VolatilityPositionSizer missing `price` (ExecutionGate fallback)

| Field | Value |
| --- | --- |
| 1. Finding | ExecutionGate volatility sizing falls back because `VolatilityPositionSizer.size()` requires `price`, but gate `_vol_size` preferred kwargs omit `price`. Warning logged; base notional used. |
| 2. Source file | `engine/execution/execution_gate.py`; `engine/risk/volatility_position_sizer.py`; RC-003R `acceptance_run.json` `vol_size_error`; also `docs/governance/PHASE_103A_CONTROLLED_PAPER_TRADING_REPORT.md` |
| 3. Line / section | Sizer API L101+; gate `_vol_size` preferred dict ~L79–91 (no `price`); evidence `vol_size_error` string |
| 4. Original classification | RC-004: **POST-RELEASE ENGINEERING** |
| 5. Affected subsystem | ExecutionGate volatility sizing |
| 6. Current behavior | Fallback to unchanged base notional after warning |
| 7. Safety impact | **Low–Medium** — sizing may be less vol-aware; still gated by RiskGovernor/AntiBleed |
| 8. Paper-trading impact | **Medium** — noise + less accurate sizing; did not block RC-003R after peak fix |
| 9. Live-trading relevance | Would affect live if armed; live not authorized |
| 10. Likelihood of recurrence | **High** on every mobile paper gate evaluation without price |
| 11. Operational consequence | Log noise; degraded vol scaling |
| 12. Reproducible | **Yes** |
| 13. Existing tests | Gate integration tests often supply richer context; mobile path does not pass price |
| 14. Recommended disposition | Supply last price (or explicit safe default policy) into `_vol_size` **without** bypassing other gates |
| 15. Proposed v1.0.1 priority | **P2** |

### RR-004 — Open-trade uniqueness / session reuse `LEDGER_PERSISTENCE_FAILED`

| Field | Value |
| --- | --- |
| 1. Finding | Second paper BUY on same session/symbol/direction failed ledger persist with UNIQUE constraint when an open/pending row already existed; fresh session succeeded. |
| 2. Source file | `backend/app/persistence/migrations/sql/002_trades.sql`; RC-003R operational notes / acceptance retries |
| 3. Line / section | `uq_open_trade_session_symbol_direction` L27–29 (`WHERE status IN ('pending','open','partially_filled')`) |
| 4. Original classification | RC-004: **POST-RELEASE ENGINEERING** |
| 5. Affected subsystem | Trade ledger / mobile paper persistence |
| 6. Current behavior | Intentional unique open position per session/symbol/direction; reopen requires close or new session |
| 7. Safety impact | **None** (prevents duplicate opens) |
| 8. Paper-trading impact | **Low–Medium** — operator must close or rotate session |
| 9. Live-trading relevance | Same ledger rule if used |
| 10. Likelihood of recurrence | **High** if operators reuse sessions without close |
| 11. Operational consequence | Confusing `LEDGER_PERSISTENCE_FAILED` vs clearer “open position exists” |
| 12. Reproducible | **Yes** |
| 13. Existing tests | Trade persistence uniqueness covered in lifecycle tests (partial) |
| 14. Recommended disposition | Improve error mapping/UX; do **not** drop unique index |
| 15. Proposed v1.0.1 priority | **P3** (messaging) / leave constraint |

### Contextual debt (not RC-004 residuals; not selected)

Items in `docs/architecture/CSS_TECHNICAL_DEBT_REGISTER.md` (PCA2-TD-001…020) describe broader consolidation debt (runtime snapshot divergence, broker readiness multiplicity, etc.). They remain valid backlog but were **not** the RC-004 residual set and are out of scope for MW-001 candidate selection unless re-evidenced against `b0703f3` paper certification.

---

## 5. Priority rationale

1. **No P0** — live authority BLOCKED; firewall/quarantine/kill switch held in RC-003R FINAL.  
2. **RR-001 is P1** — breaks deterministic paper risk evaluation using the canonical PnL store the mobile path already depends on.  
3. **RR-002/RR-003 are P2** — observability / sizing fidelity with gates still functional.  
4. **RR-004 is P3** for messaging; uniqueness itself is protective.  
5. Selection order per workstream principles: safety → live block preserved → **deterministic paper** → reliability → broker truthfulness → observability → minimal surface → automated tests.

---

## 6. Selected Maintenance-001 candidate

**RR-001 — Persist and round-trip `equity_peak` on PnL snapshots; harden mobile consumption.**

---

## 7. Confirmed root symptom

**Symptom:** Mobile `execute_mobile_trade_ticket` loads `equity`/`equity_peak` from `PnlRuntimeService.get_latest_snapshot`. Durable snapshots never write `equity_peak`. With peak missing or effectively `0`, ExecutionGate/RiskGovernor risk adjustment can reject paper notionals that should clear under normal equity==peak paper capital.

**Evidence chain:** RC-003R FINAL failures → operational wrap `equity_peak=equity` → approvals; schema `003_pnl_snapshots.sql` + repository INSERT omit column; tests mock peak rather than persisting it.

---

## 8. Investigation boundaries

**In scope for implementation (future approval only):**

- PnL snapshot schema migration adding `equity_peak`
- Repository + `PnlRuntimeService.create_snapshot` / read mapping
- Safe defaults: if peak omitted on create, set `equity_peak = equity`
- Mobile null/missing peak coercion (prefer peak=equity, never silent `0` when equity>0)
- Automated tests for persist/round-trip and regression of paper risk path

**Out of scope:**

- Desktop continuous paper runtime
- Live authority, firewall, quarantine, kill switch semantics
- Threshold reductions / orchestrator or gate bypasses
- Mission Control broker projection (RR-002) except as follow-on
- VolatilityPositionSizer wiring (RR-003) except as follow-on
- Dropping trade uniqueness (RR-004)

---

## 9. Files likely involved

| File | Change type (planned) |
| --- | --- |
| `backend/app/persistence/migrations/sql/00x_pnl_snapshots_equity_peak.sql` (new) | Add column |
| `backend/app/persistence/repositories/pnl_snapshot_repository.py` | Persist/read |
| `backend/app/persistence/services/pnl_runtime_service.py` | API + defaulting |
| `dashboard/mobile/mobile_app.py` | Defensive peak resolution |
| `tests/test_pnl_snapshot_persistence_contract.py` | Round-trip assertions |
| `tests/mobile/test_mobile_paper_*.py` and/or new focused test | Unmocked/missing-peak behavior |

---

## 10. Tests likely involved

- Extend `tests/test_pnl_snapshot_persistence_contract.py` for `equity_peak` write/read and default-to-equity
- Mobile paper expected-value / margin tests (ensure mocks remain valid)
- Optional: targeted ExecutionGate paper risk test with snapshot lacking peak **before** fix (expect fail) and **after** (expect allow) — without lowering thresholds
- Regression subset: orchestrator gate, execution gate, paper authority, live-execution-authority (confirm unchanged)

---

## 11. Explicit non-goals

- Authorize live trading or OV-002  
- Weaken live-execution firewall / quarantine / kill switch  
- Lower probability/confidence thresholds to force acceptance  
- Bypass orchestrator, ExecutionGate, RiskGovernor, or AntiBleedGuard  
- Change broker credentials or convert OANDA Practice → live  
- Enable IBKR live execution  
- Change capital-exposure limits  
- Modify or stop the desktop continuous paper runtime  
- Delete runtime evidence or rewrite certification history  
- Implement RR-002/RR-003/RR-004 in the same change set  

---

## 12. Safety invariants

The proposed repair **must**:

- Keep `execution_allowed=false` defaults and live authority fail-closed  
- Leave live AntiBleed missing-input fail-closed behavior unchanged  
- Preserve all ENGINE_MODE probability thresholds  
- Preserve RiskGovernor / ExecutionGate decision semantics aside from supplying correct peak inputs  
- Remain paper-safe and reversible via migration rollback notes  

---

## 13. Proposed implementation plan (for later approval)

1. Add migration: `equity_peak TEXT NOT NULL DEFAULT '0'` (or equivalent) on `pnl_snapshots`.  
2. Update repository INSERT/SELECT contract; backfill semantics: new writes set peak=`equity` when omitted.  
3. Update `PnlRuntimeService.create_snapshot` signature to accept optional `equity_peak` with default=`equity`.  
4. In mobile ticket path, resolve peak as: explicit peak if finite and >0, else equity (never coerce missing→0 while equity>0).  
5. Add/adjust unit tests; run targeted + safety regression suites.  
6. Do **not** commit/push until separately authorized; never touch desktop host.

---

## 14. Proposed validation plan

1. `pytest` PnL persistence contract (peak round-trip + default).  
2. Mobile paper tests including peak-missing defensive behavior.  
3. Regression: `test_trade_decision_orchestrator_gate`, execution/anti-bleed/margin, `test_paper_trading_authority`, `test_phase153i_live_execution_authority`.  
4. Confirm no live-enable flag or authority module changes in diff.  
5. **Do not** start CSS continuous mode on laptop as part of MW-001 unless a later ops task authorizes an isolated paper probe.

---

## 15. Rollback strategy

- Revert the maintenance commit(s) on `css-v1.0.1-maintenance`.  
- If migration applied locally: document down-migration or restore DB from pre-change backup; column addition is non-destructive to existing rows if defaulted.  
- Desktop continuous paper runtime remains untouched throughout.

---

## 16. Recommendation (planning-era)

~~READY_FOR_IMPLEMENTATION~~ — superseded by §17 after implementation validation.

---

## 17. Implementation validation record (MW-001 / RR-001)

### 17.1 Files implemented

| File | Role |
| --- | --- |
| `backend/app/persistence/migrations/sql/005_pnl_snapshots_equity_peak.sql` | Add `equity_peak`; backfill from `equity` |
| `backend/app/persistence/repositories/pnl_snapshot_repository.py` | Persist optional peak (default=`equity`) |
| `backend/app/persistence/services/pnl_runtime_service.py` | Service API + defaulting |
| `dashboard/mobile/mobile_app.py` | `_resolve_equity_peak_for_gate` + ticket path |
| `tests/test_pnl_snapshot_persistence_contract.py` | Round-trip / default / explicit peak |
| `tests/mobile/test_mobile_equity_peak_resolution.py` | Resolver + missing-peak gate kwargs |
| `tests/dashboard/test_mobile_live_order_kill_switch.py` | Assert kill-switch isolation without requiring incidental paper failure |

### 17.2 Independent review findings

- Migration is non-destructive and tracked once via `schema_migrations`.
- Backfill `UPDATE … WHERE equity_peak = '0'` after `DEFAULT '0'` correctly sets peak=`equity` for pre-existing rows (peak was never stored).
- Explicit historical peak > equity is preserved on write and in mobile resolver.
- Missing / `None` / `0` / malformed / NaN / ±Inf peaks resolve to equity when equity > 0; both-zero remains 0.
- Negative peaks are not treated as valid peaks (fall back to equity) — consistent with peak semantics.
- No changes to orchestrator thresholds, ExecutionGate policy, AntiBleed, RiskGovernor formulas, live firewall, broker adapters, or live-authority evaluators.
- Incidental test dependency: paper kill-switch test previously expected `ok is False` due to peak=0 risk rejects; updated to assert non-engagement of kill switch only.

### 17.3 Validation commands and results

| Suite | Command | Result |
| --- | --- | --- |
| Targeted RR-001 | `pytest tests/test_pnl_snapshot_persistence_contract.py tests/mobile/test_mobile_equity_peak_resolution.py` | **12 passed** |
| Live authority | `pytest tests/test_phase153i_live_execution_authority.py` | **6 passed** (`reportlab` present in venv 5.0.0) |
| Safety regression | orchestrator / anti-bleed / margin / canonical execution / paper authority / live-authority / mobile paper + RR-001 | **50 passed** |
| Broader deterministic | mobile/ + persistence + risk governor + safety group + dashboard mobile | Initial env/brittle failures; after kill-switch env clear + test intent fix, dashboard mobile tests pass |

### 17.4 Post-implementation recommendation

**READY_TO_COMMIT**

Do not push or tag until separately authorized. Do not start CSS or touch the desktop continuous paper runtime.

---

*End of CSS_V1_0_1_MAINTENANCE_001_RESIDUAL_RISK_AUDIT.md*
