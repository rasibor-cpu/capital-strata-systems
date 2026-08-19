# CSS CONTROLLED OPERATING WINDOW — COW-001

**Document type:** Authoritative next-milestone charter
**Task ID:** `CSS-COW-001`
**Date (UTC):** 2026-08-19
**Issued from:** CSS-PKG-D-001 (governance finalization)
**Canonical development branch:** `css-v1.0.1-maintenance`
**Live trading authority:** NONE unless a later separately governed decision grants it
**Cloud-agent start:** FORBIDDEN — requires operator laptop/runtime

This is the **next real milestone** after Package D. It is **not** another smoke test, not another pre-operation certification gate, not a 72-hour prerequisite before operation, and not a feature-recovery phase.

---

## Purpose

**Start the current canonical CSS as-is in controlled mode and keep it running.**

Run the current canonical system continuously for **at least 24 hours** using **current/live market data** within the **existing controlled/paper execution boundaries**.

The operating run is simultaneously:

1. real controlled operation
2. defect discovery
3. live/current-market-data evidence collection
4. certification evidence generation

Do **not** stop at 24 hours merely because 24 hours elapsed if the system is healthy. Continue to 48/72 hours when practical. Additional hours are cumulative operational evidence. Do **not** restart merely to manufacture a “72-hour certification test.” Preserve continuity unless a SEV-1 safety-critical event requires controlled shutdown.

---

## What this is not

- Not a pre-operation smoke test
- Not a gate that must pass before the system may be started
- Not a requirement to complete another 72-hour endurance programme before operating
- Not a feature-recovery or architecture-implementation phase
- Not authorization for funded/live broker order execution
- Not MI-EXT live ingestion
- Not Phase 184A / 188+ / 196 / 197 / 198 work

Engineering after Package D is **driven by defects and evidence discovered during this window**, not by those backlog items.

---

## Operating principle

The system should **remain running** while non-safety defects are diagnosed and repaired.

A defect does **not** automatically invalidate the full operating window.

| Severity | Examples | Action |
| --- | --- | --- |
| **SEV-1 SAFETY CRITICAL** | Uncontrolled execution; risk-gate bypass; position-state corruption; inability to account for orders/positions; kill-switch failure; funded/live execution outside authorization | **Controlled shutdown immediately** |
| **SEV-2 FUNCTIONAL** | Ranking defect; intelligence defect; data-pipeline interruption; recoverable component crash; dashboard/control issue affecting operation but not safety | Repair, document, **continue** where safe |
| **SEV-3 OBSERVABILITY / UX** | Display issue; missing non-critical metric; stale dashboard label; reporting defect | Record and repair **without stopping** unless necessary |

---

## Live / current market data (careful meaning)

**Means:**

- real/current market observations where CSS already supports them safely
- not simulated historical-only inputs unless required for fallback

**Does not mean:**

- authorization for funded/live order execution
- weakening of UTG, AntiBleed, Capital Governor, Margin Gate, TTL, kill-switch, or live/paper defaults
- new live-network broker architecture (Phase 188+)

Execution remains inside the **current controlled/paper** boundaries unless a later separately governed live-authority decision is made.

Required safety posture at start (unchanged):

- `execution_allowed=false` unless already governed otherwise in the running controlled/paper profile
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true` for live-funded execution

Paper/controlled order lifecycle **inside existing fail-closed gates** is in scope for evidence. Funded live execution is **out of scope** unless separately authorized.

---

## Evidence the run itself must collect

The operating window generates certification evidence. Capture at least:

- system startup timestamp
- canonical SHA and config
- market-data source status
- opportunities detected
- TAI results
- MI-EXT results (fixture/advisory catalogue only unless later authorized)
- regime classification
- ranking outputs
- Unified Trade Gate decisions
- AntiBleed / risk decisions
- Capital Governor decisions
- accepted/rejected paper trades
- order lifecycle
- position lifecycle
- exits
- realized P&L
- unrealized P&L
- drawdown
- exposure
- heartbeats
- runtime errors
- component restarts
- process restarts
- operator interventions
- dashboard / Mission Control state
- data-quality incidents
- stale/missing-data events
- kill-switch events
- safety-gate denials
- defects discovered and repairs made during the run (with SEV class)

Do not fabricate observations. Missing evidence is recorded as missing.

---

## Window duration policy

| Rule | Policy |
| --- | --- |
| Minimum | **24 hours** continuous controlled operation |
| At 24 hours if healthy | **Do not stop** merely because 24 hours elapsed |
| Extension | Continue to **48 / 72 hours** when practical |
| Extra hours | Cumulative operational evidence |
| Restarts | No separate restart solely to create a 72-hour certification test |
| Continuity | Preserve unless SEV-1 requires shutdown |

Historical OV-002 72h (`ENDURANCE INVALIDATED`) is **not** a prerequisite and is **not** credited to this window. COW-001 evidence stands on its own SHA and observations.

---

## Backlog that must not start as the next activity

Do not begin from this charter:

- Phase 184A AntiBleed/ExecutionGate wiring
- Phase 188+ controlled broker connectivity
- Phase 196 300s live-authority lease
- Phase 197 FX-normalized live capital governor
- Phase 198 FX blocker governance
- MI-EXT **live** ingestion
- new autonomous live authority
- new FX live governor
- new broker execution architecture

Those remain backlog. They are not the next milestone.

---

## Start conditions

1. CSS-PKG-D-001 independently reviewed and landed, **or** operator explicitly starts from current landed maintenance HEAD if Package D is not yet merged (record the exact SHA either way).
2. Operator laptop/runtime with declared dependencies (including `python-dotenv==1.2.2` from `requirements.txt`).
3. Current/live market-data path that CSS already supports safely.
4. Controlled/paper execution profile; live funded orders blocked.
5. Evidence directory created and SHA-bound at start.

Cloud Agents must **not** start COW-001. Report `BLOCKED — OPERATOR_RUNTIME_REQUIRED`.
