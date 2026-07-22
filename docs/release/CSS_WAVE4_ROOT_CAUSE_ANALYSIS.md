# Wave 4 — Consolidated Root Cause Analysis

**Programme:** Release Gate 2  
**Batch:** Wave 4 — Product Honesty & Customer Trust  
**Scope:** AR-017, AR-047, AR-018, AR-042, AR-022, AR-025 (residual), AR-031 (already CLOSED — confirm only)  
**Date:** 2026-07-22  
**Prior approval:** Wave 3 executively approved

## Guiding principle

> CSS must never overstate capability, readiness, certification, reporting coverage, notification behaviour, or operational status.

## Shared theme

Customer-visible surfaces (catalogue, dashboards, notifications, EIS/182A language, board/investor/regulatory enums) present **roadmap completeness or simulated delivery** as if they were production-delivered capabilities. Shared corrective principle: **fail-closed honesty labels** — publish MVP/out-of-scope decisions, demote simulated delivery, and refuse fabricated completeness claims without adding new product features.

## Shared architectural causes

| Cluster | ARs | Cause |
| --- | --- | --- |
| Catalogue integrity | 017, 047 | 191 registered rows treated as delivered suite; board/investor/regulatory implied |
| Dashboard / EIS presentation | 018, 042 | Uncommitted 182A / executive surfaces without universal management-vs-audited honesty |
| Simulated customer behaviour | 022 | Notification providers return success without real transport |
| Install / advisory residuals | 025, 031 | Docs/partial (025); empty-registry honesty already CLOSED (031) |

## Duplicated presentation logic

1. Catalogue totals appear in matrix docs, registry payloads, MC institutional pages, and reports hub — without a single Gate-2 honesty banner.
2. Notification providers each independently “simulate success” when `dry_run=False`.
3. Executive overview / EIS / financial reporting each have partial provenance; not one customer-facing honesty contract.

## Smallest coherent remediation set

1. **AR-017:** Publish V1 MVP list; catalogue API honesty banner (registered ≠ generatable).
2. **AR-047:** Formal OUT OF SCOPE for board/investor/regulatory packs in Gate 2.
3. **AR-018:** Formal DEFER of full EIS/182A dashboard as released capability.
4. **AR-042:** Universal management/not-audited provenance on executive package + MC overview honesty banner; missing feeds → unavailable (no fabricated healthy zeros where service already supports it).
5. **AR-022:** Production profile cannot silently simulate SMTP/SMS/push success; expose `notifications_operational=False`.
6. **AR-025:** Keep PARTIAL; add launcher manifest non-canonical marker.
7. **AR-031:** Confirm CLOSED; no Wave 4 rework.

## Expected closure posture

| AR | Expected recommendation |
| --- | --- |
| 047, 018 | CLOSE (defer / out-of-scope decisions) |
| 017, 042, 022 | PARTIALLY CLOSE (honesty landed; full product delivery residual) |
| 025 | Remain PARTIALLY CLOSED |
| 031 | Already CLOSED |

## Safety constraints

- No live trading enablement.
- No fabricated reports, notifications, or certification.
- No new product features / platform expansion.
- No Wave 5 work.
