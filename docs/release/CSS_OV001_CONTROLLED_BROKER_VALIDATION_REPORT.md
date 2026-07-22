# OV-001 Controlled Broker Validation Report

**Programme:** Release Gate 3 — Operational Validation OV-001  
**Date:** 2026-07-22  
**Evidence package:** `runtime_reports/operational_validation/ov001_20260722T041013Z/brokers/`  
**Mode:** Read-only operational validation only  
**Credentials printed:** **No** (redacted artifacts)  
**Live trading:** **BLOCKED** throughout  
**Orders placed/modified/cancelled:** **None**

---

## Safety controls confirmed

| Control | Result |
| --- | --- |
| No order placement | Confirmed (read-only validators only) |
| No order modification / cancel | Confirmed |
| No funding actions | Confirmed |
| Live execution authority | `execution_allowed=false`, `can_live_execute=false` |
| Credential values in reports | Redacted (`[REDACTED]`) |
| Environment load | `load_css_runtime_environment` / dotenv; dangerous CSS live flags forced off if present |

---

## Coinbase (truthful result)

| Dimension | Result |
| --- | --- |
| Configured (credentials resolved after env load) | **Yes** (adapter ready prior to validate) |
| Authenticated (account path) | **No** — `AUTH_FAILED` (HTTP 401) |
| API reachable | **Yes** |
| Market data available | **Yes** — `server_time` / `products_list` / `market_ticker` **PASS** |
| Account / portfolio / balances | **FAIL** |
| Data freshness | Captured via validation timestamp; market path succeeded |
| Timeout / fail-closed | Fail-closed overall status **`FAIL_CLOSED`** |
| Invalid/unavailable auth → READY? | **No** — not READY |
| Execution blocked | **Yes** |
| Security gate | `SECURITY_ERROR`: LIVE mode contaminated by `COINBASE_TEST_ORDER_USD` |

**Final distinction:** configured · **not** fully authenticated for account · market data available · **execution blocked**.

Artifact: `brokers/coinbase_read_only_validation.json`

---

## OANDA (truthful result)

| Dimension | Result |
| --- | --- |
| Practice/read-only identified | **Yes** — `OANDA_ENV=practice` while validator mode labeled LIVE_READ_ONLY |
| Authenticated | **Yes** (`authenticated=true`) |
| Account query | **PASS** |
| Pricing / market data | **PASS** (ticker + candles) |
| All read_checks | **PASS** (8/8) |
| Freshness / latency | Recorded in operational status fields (redacted pack) |
| Fail-closed on profile mismatch | **Yes** — `SECURITY_ERROR`: live mode requires `OANDA_ENV=live`, got `practice` |
| Legacy writes | Remain blocked (Wave 2 quarantine; regression `test_oanda_live_firewall.py` green) |
| Execution blocked | **Yes** |

**Final distinction:** configured · authenticated · **read-only operational (practice)** · **execution blocked** · overall `FAIL_CLOSED` due to env/profile security gate (honest, not fabricated PASS).

Artifact: `brokers/oanda_read_only_validation.json`

---

## Interpretation for endurance approval

Broker validation produced **truthful** outcomes. Neither broker is claimed as production LIVE-ready:

- Coinbase: market read path works; account auth failed; security contamination present.  
- OANDA: full read suite passed on practice; security gate correctly refuses LIVE label mismatch.

These residuals do **not** reopen OAT (already 100%). They condition the endurance recommendation.

---

*End of CSS_OV001_CONTROLLED_BROKER_VALIDATION_REPORT.md*
