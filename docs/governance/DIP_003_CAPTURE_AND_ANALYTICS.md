# DIP-003 — Trade DNA Capture & Analytics Foundation

**Programme:** CSS Decision Intelligence Platform (DIP)
**Workstream:** DIP-003
**Title:** Trade DNA Capture & Analytics Foundation (Hardened)
**Status:** HARDENING COMPLETE — AWAITING REVIEW (do not commit in this phase unless authorized)
**Repository:** `C:\rasib\source\capital-strata-systems`
**Branch:** `css-v1.0.1-maintenance`
**Base HEAD:** `99498bbcc248ab2491a1b909c86c27b0b2f244b6`
**Date:** 2026-07-30

**Does not authorize:** ExecutionGate/RiskGovernor/AntiBleed/sizing/broker/authority changes, Mission Control UI, capital allocation, desktop interference.

Supersedes the earlier capture audit note and the first capture implementation write-up.

---

## 1. Objectives

1. Emit one canonical close event per completed trade (authoritative facts only).
2. Capture immutable Trade DNA with durable, restart-safe reconciliation.
3. Provide read-only Decision Analytics over stored DNA + derived metrics.
4. Keep **operational close** independent of **intelligence capture** success.

---

## 2. Close-path ordering

```text
TradeRuntimeService.close_trade
  1) Load trade_record
  2) Canonical warehouse persist  (fail-closed for operational uniqueness)
  3) Intelligence capture (advisory):
       a) Build CanonicalCloseEvent (authoritative facts only)
       b) Durable OUTBOX PENDING_DNA   ← discoverable after restart without logs
       c) Commit close event + Trade DNA + derived metrics
       d) Outbox COMPLETE (or CONFLICT with governed evidence)
  4) Legacy outcome ledger
  5) DB trades.close_trade
```

Capture exceptions in step 3 are logged and **must not** abort steps 4–5.

### Operational-close vs intelligence-capture boundary

| Concern | Owner | Failure effect |
| --- | --- | --- |
| Warehouse uniqueness / DB closed status | Operational close | Blocks or completes trade lifecycle |
| Outbox / DNA / derived / analytics | Intelligence capture | May be PENDING; recovered later |
| Gates / sizing / brokers | Frozen | Untouched by DIP-003 |

---

## 3. Durable reconciliation mechanism

**Artifact:** `artifacts/trade_dna_capture/capture_outbox.json` (atomic write)

| Status | Meaning |
| --- | --- |
| `PENDING_DNA` | Warehouse close intent sealed in outbox; DNA missing or incomplete |
| `DNA_COMMITTED` | DNA persisted; completion (derived/COMPLETE) interrupted |
| `COMPLETE` | Close event + DNA + derived reconciled |
| `CONFLICT` | Conflicting close/DNA evidence; fail-closed; no duplicate mint |

Recovery: `TradeDNACaptureService.recover_pending_captures()` — idempotent, log-independent.

Conflict evidence also lands in `capture_conflicts.json` (governed, non-executing).

---

## 4. Crash windows

| Window | Durable state | Recovery |
| --- | --- | --- |
| After warehouse, before outbox | Warehouse only | Future warehouse↔DNA compare (limitation if outbox write itself fails) |
| After outbox, before DNA | `PENDING_DNA` | `recover_pending_captures` |
| After DNA, before COMPLETE | `DNA_COMMITTED` | Finish derived + mark COMPLETE |
| After COMPLETE | Done | Idempotent no-op |

---

## 5. Idempotency & conflict handling

- Same sealed close event → one DNA (`idempotent_hit`).
- Conflicting close facts / DNA hash mismatch → `CONFLICT` + evidence; **never** overwrite or mint a second closed DNA for the conflict path.
- Repeated recovery never duplicates DNA ids (`dna_id` deterministic from `schema|closed|trade_id`).

---

## 6. Determinism proof

Canonical event id/hash and DNA hash are functions of:

- contract/schema versions
- authoritative close facts (`trade_id`, prices, qty, timestamps from close contract, broker, sealed open economics)

Excluded from seals:

- wall-clock generation time at capture
- filesystem paths
- random UUIDs / PIDs
- live market data
- unordered dict iteration (canonical JSON `sort_keys=True`)

Analytics `generated_at` is supplied by the caller (tests pass fixed timestamps) and is **not** an execution fact.

---

## 7. Evidence separation & availability semantics

| Layer | Storage | Contents |
| --- | --- | --- |
| Facts | Trade DNA | Immutable execution/context seals |
| Derived | `derived_metrics.json` | PnL, holding, return % |
| Analytics | Ephemeral report objects | Cohorts with Evidence Graph |

Semantics:

- `UNAVAILABLE` / omitted / null → field not present as observed truth (placeholders like bare `UNKNOWN` are stripped).
- `OBSERVED_UNKNOWN` → explicitly observed unknown state (allowed enum).
- Confidence / sample size live only on Evidence Graph / analytics — never as execution evidence.

---

## 8. Validation evidence

Focused suite: `tests/test_dip003_capture_and_analytics.py` (+ DIP-002 schema tests).

Hardening cases covered:

1. Warehouse success + DNA write failure → durable outbox
2. Restart discovery without logs
3. Recovery of missing DNA
4. Repeated recovery idempotent
5. Duplicate identical close → one DNA
6. Conflicting duplicate → fail-closed CONFLICT evidence
7. Crash after outbox before DNA
8. Crash after DNA before COMPLETE
9–11. Stable event id / event hash / DNA hash
12. Unavailable context not fabricated; OBSERVED_UNKNOWN preserved
13. Close completes when capture raises
14. MW-004 / warehouse / amount_traded paths remain covered by existing suites

---

## 9. Remaining limitations

1. If outbox persistence itself fails after warehouse success, discovery requires a future warehouse↔DNA scanner (not fully automated here).
2. DNA still requires a caller of `close_trade` with authoritative exit/PnL.
3. Capture failures do not block operational close (by design).
4. Default store is local artifact JSON, not multi-node consensus.

---

## 10. Recommendation

**READY_TO_COMMIT** after operators confirm focused + broad regression green in the review report.

---

*End of DIP_003_CAPTURE_AND_ANALYTICS.md*
