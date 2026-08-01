# ER-001 — Endurance Certification Report Template

**Instance ID:** `ER001-<YYYYMMDDTHHMMSSZ>-<supervisor_short>`
**Credit type claimed:** `OBSERVATIONAL_STABILITY` | `FORMAL_48H_STABILITY` | `OV-002_CERTIFICATION`
**Overall disposition:** `PASS` | `FAIL` | `BLOCKED` | `PASS_WITH_LIMITATIONS` | `BLOCKED_NOT_CLAIMED`
**Report generated (UTC):**
**Operator:**
**Founder authorization reference:**

Fill during/after closeout. Do not invent metrics. Use `NOT_AVAILABLE` / `NOT_APPLICABLE` when evidence is absent.

### Sealed instance record (MR-003G — reference only)

| Field | Value |
| --- | --- |
| Package path (local / gitignored) | `runtime_reports/operational_validation/er001_20260801T034921Z_closeout/` |
| Start UTC | `2026-07-30T03:17:57.105716+00:00` |
| Stop UTC | `2026-08-01T03:41:27.715688+00:00` |
| Duration seconds | `174210.609972` |
| OBSERVATIONAL_STABILITY | `PASS` |
| FORMAL_48H_STABILITY | `PASS_WITH_LIMITATIONS` |
| OV_002_CERTIFICATION | `BLOCKED_NOT_CLAIMED` |
| GRACEFUL_SHUTDOWN | `PASS` |
| PROCESS_TERMINATION | `PASS` |
| PORT_RELEASE | `PASS` |
| EXECUTION_SAFETY | `PASS` |
| Git requirement for sealed package | **Not required** — keep local/gitignored |
| Live authorization | **NONE** |
| OV-002 claimed? | **NO** |
---

## 1. Executive Summary

- Run purpose:
- Supervisor ID:
- Start (local / UTC):
- End (local / UTC):
- Elapsed wall-clock:
- Credit type claimed:
- Overall disposition:
- One-paragraph outcome:
- Live trading occurred? (`YES`/`NO`; expect `NO`):

---

## 2. Runtime Statistics

| Metric | Value |
| --- | --- |
| Branch | |
| HEAD SHA | |
| Upstream parity at closeout | |
| Supervisor status (final pre-stop) | |
| Uptime hours | |
| Cycles (if available; note provenance) | |
| Runtime mode | |
| Advisory only | |
| Execution allowed | |

---

## 3. Health Summary

| Surface | Status | Notes |
| --- | --- | --- |
| HTTP `/health` | | |
| `/api/runtime-health` | | |
| Heartbeat age (s) | | |
| Session continuity | | |
| Quiet mode | | |

---

## 4. Stability

| Item | Value | Classification |
| --- | --- | --- |
| Restart count | | PASS/FAIL/BLOCKED |
| Restart attempts | | |
| Failure count | | |
| Restart limit exhausted | | |
| Undocumented restarts | | |
| Crashes | | |

---

## 5. Memory

| Process role | PID | WS (MB) | Private (MB) | Trend note |
| --- | --- | --- | --- | --- |
| Launcher | | | | |
| Mobile | | | | |
| Dashboard | | | | |

API `memory_usage` if present:

---

## 6. CPU

| Process role | Cumulative CPU (s) | Sample Δ note |
| --- | --- | --- |
| Launcher | | |
| Mobile | | |
| Dashboard | | |

---

## 7. Restart History

| Timestamp (UTC) | Service | Reason | Documented? |
| --- | --- | --- | --- |
| | | | |

If none: `NONE` for this supervisor_id.

---

## 8. Failure History

| Timestamp (UTC) | Event type | Reason | Count |
| --- | --- | --- | --- |
| | | | |

If none: `NONE` for this supervisor_id.
Do not attribute prior supervisor_id failures to this generation without proof.

---

## 9. Portfolio

| Field | Value |
| --- | --- |
| Equity | |
| Cash | |
| Buying power | |
| Realized PnL | |
| Unrealized PnL | |
| Open positions | |
| Exposure | |
| Lifecycle / portfolio_state | |

---

## 10. Broker State

| Field | Value |
| --- | --- |
| Selected broker | |
| Broker mode | |
| Overall / readiness | |
| Authentication | |
| Live authority | |
| Execution armed | |
| Warnings / failure_reason | |

---

## 11. Mission Control

| Field | Value |
| --- | --- |
| runtime_status | |
| runtime_health | |
| heartbeat_status | |
| alert count / active alerts | |
| Schema version | |

---

## 12. Decision Intelligence Status

| Field | Value |
| --- | --- |
| DIP packages on this SHA? | YES/NO/NOT_APPLICABLE |
| Trade DNA capture active? | |
| Notes / limitations | |

---

## 13. Evidence Inventory

| Artifact ID | Path | SHA-256 | Bytes | Present |
| --- | --- | --- | --- | --- |
| | | | | |

Attach or reference `MANIFEST.json`.

---

## 14. Known Limitations

- Untimed run / missing OV-002 monitor (if applicable):
- MC RED vs process healthy divergence (if observed):
- Broker FAIL_CLOSED / contamination reporting residuals:
- AntiBleed vs CAD 20 (LDT) — not cleared by endurance:
- Other:

---

## 15. Certification Decision

| Credit type | Disposition | Rationale |
| --- | --- | --- |
| OBSERVATIONAL_STABILITY | PASS/FAIL/BLOCKED | |
| FORMAL_48H_STABILITY | PASS/FAIL/BLOCKED | |
| OV-002_CERTIFICATION | PASS/FAIL/BLOCKED | |

**Final statement:**

> This report does / does not certify OV-002. Live trading remains unauthorized unless a separate LDT execution phase explicitly authorizes it.

**Signatures**

| Role | Name | Date (UTC) |
| --- | --- | --- |
| Operator | | |
| Reviewer | | |
| Founder | | |
