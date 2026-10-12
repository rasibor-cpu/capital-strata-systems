# CSS controlled pilot activation decision — 2026-10-11

Status: **PREPARATION APPROVED; LIVE EXECUTION NO-GO**
Candidate: `7b527d24f172445908c8f9d8f0da6c2d7bef4cc8` (subject to subsequent documentation-only additions).

## Business scope
- Maximum CAD 20 per parent trial order/exposure.
- Maximum CAD 40 aggregate concurrent exposure across all asset classes, including existing and pending reservations and fees; no more than two concurrent parents.
- Intended asset-class coverage: crypto, FX, futures and options, but *instrument-specific* certification and denomination of notional, cash margin and worst-case loss are required.
- New risk limits may narrow, but not increase, these ceilings without a new approval.

## Evidence received
- Isolated targeted pilot suite: 25 passed on PR #105 revision `e373228c`.
- Extended suite initially: 103 passed, 1 skipped, 2 failed due to hardcoded original repo root in synthetic endurance-monitor process-identity fixture.
- Test-only fixture correction committed as `7b527d24`; rerun in isolated Windows checkout: **105 passed, 1 skipped, 0 failed**, 48.28 s.
- Original running checkout retained at `9bc3c52`; no live orders sent and runtime not restarted.

## Explicit limitations
- The tests prove *test behavior*, not 72 hours of real monitor observation. No complete, independently reviewed 72-hour operational manifest has been supplied. **Operational endurance is NOT CERTIFIED.**
- The owner directed that activation preparation proceed without waiting for another endurance run. This is recorded as a business schedule decision, **not** a passed endurance certificate or waiver of fail-closed live execution gates.
- `config/governance/pilot_approver_enrollment.json` still has `RELEASE_SECURITY_APPROVER: null` and no production public key enrollments. Dual control **NOT READY**.
- AntiBleed micro-size exception remains disabled. Live execution integration, cross-asset brokerage and quantitative risk normalization, kill-switch checks, complete release review, and continuous-runtime certification are outstanding.

## Activation verdict
- Controlled pilot engineering/review: GO.
- Real-money order transmission: **NO-GO**. Do not change safety flags, enable the exception, place orders, or claim endurance PASS pending independent, verifiable release clearance.
