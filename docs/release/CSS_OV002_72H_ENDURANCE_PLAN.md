# CSS OV-002 — 72-Hour Endurance Plan

**Programme:** Release Gate 3 — Operational Validation OV-002  
**Authority:** Conditional approval of OV-001  
**Safety posture:** `advisory_only` / `fail_closed` / `execution_allowed=false` / live trading **BLOCKED**  
**Duration:** **72 genuine wall-clock hours** (no simulated time, no backfill)

---

## 1. Baselines

| Item | Value |
| --- | --- |
| Branch | `css-unified-consolidation-2026-07-13` |
| RC-001 (immutable) | `6513e6a1e45ffc42aff192e1c784171ad6fc182b` |
| RC-002 candidate | `fbcc31f9a877f8fbc2b67291b4b7ee8ba2fe4ff5` |
| OV-001 docs tip | `19297f9b3f3550b78a642d84f2584d3a276da9d1` |
| Endurance freeze SHA | Recorded in `CSS_OV002_PRE_RUN_READINESS.md` after harness commit |

---

## 2. Non-claims (OV-001 conditions carried forward)

- Coinbase account authentication is **not** claimed (401 residual).  
- OANDA is **practice / read-only**, not LIVE-certified.  
- Broker `FAIL_CLOSED` results are **not** broker certification.  
- Phase 181 remains **`NOT_CERTIFIED`** even if endurance passes.  
- No live trading, no broker writes, no Batch 3, no feature work during the run.

---

## 3. Evidence layout

```text
runtime_reports/operational_validation/ov002_72h_<UTC_START>/
  RUN_META.json
  SAFETY_ASSERTIONS.json
  snapshots/health_YYYYMMDDTHHMMSSZ.json          # ~every 5 minutes
  checkpoints/CHECKPOINT_TplusNNh.md + .json      # 6/12/24/36/48/60/72h
  resources/                                      # memory/CPU samples
  brokers/                                        # fail-closed posture samples
  SHUTDOWN_OBSERVATION.json                       # end-of-run
  INVALIDATION.json                               # only if invalidated
  RUN_STATUS.json                                 # RUNNING | COMPLETE | INVALIDATED
```

---

## 4. Monitoring cadence

| Cadence | Action |
| --- | --- |
| Every **5 minutes** | Automated health / safety / resource / broker-posture snapshot |
| Every **6 hours** | Executive checkpoint (CONTINUE / CONTINUE WITH OBSERVATION / INVALIDATE AND STOP) |
| T+12/24/36/48/60/72h | Full operational checkpoint (same schema; required set) |
| Continuous | Invalidation watch (live execution, commit drift, monitor gap, restart, etc.) |

Wall-clock source: OS monotonic/UTC via `time.time()` / `datetime.now(timezone.utc)` — **never** injected clocks for production eligibility.

---

## 5. Launch procedure

1. Pre-run readiness = `READY FOR ENDURANCE`.  
2. Controlled single-tree CSS start via `launch_css.bat` (eliminate duplicate process trees).  
3. Start `scripts/css_ov002_72h_endurance.py` as a detached monitor (does not enable trading).  
4. Monitor writes `RUN_STATUS.json=RUNNING` and begins snapshots.  
5. No code/config commits on the runtime machine until run ends or is invalidated.

---

## 6. Invalidation (fail-closed)

Any of: live execution enabled; broker write attempted; undocumented restart; host reboot; monitoring gap beyond tolerance; unhealthy unrecovered; false healthy supervisor; port loss; secret exposure; commit/config change mid-run; simulated/backfilled time.

On invalidation: stop safely, preserve evidence, write incident report, **do not** auto-restart a new 72h run.

Monitoring gap tolerance: **> 20 minutes** without a successful snapshot → invalidate (unless pre-documented planned pause).

---

## 7. End-of-run

At ≥ 72.0 wall-clock hours: final snapshot → controlled shutdown observation → analyze → recommendation  
`ENDURANCE PASS` | `ENDURANCE PASS WITH RESIDUALS` | `ENDURANCE FAIL` | `ENDURANCE INVALIDATED`.

---

## 8. Tools

| Tool | Role |
| --- | --- |
| `backend/certification/ov002_endurance_monitor.py` | Snapshot + invalidation + checkpoint writers |
| `scripts/css_ov002_72h_endurance.py` | CLI / long-running monitor entry |

---

*End of CSS_OV002_72H_ENDURANCE_PLAN.md*
