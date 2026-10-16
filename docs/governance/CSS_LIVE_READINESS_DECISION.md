# CSS live-readiness decision — RC1

**Decision: NOT LIVE-READY. PRODUCTION_GO=NO.** Live broker execution stays disabled and production is unchanged.

This report is an engineering assessment, not an owner sign-off. Live trading needs both:
- every mandatory gate below marked PASS with evidence;
- a separate, explicit owner authorization naming the exact account, capital allocation, instruments and limits.

## 1. Gate status
Status values:
- **PASS:** evidence exists in the repository or CI.
- **BUILT:** the engineering is done and tested on synthetic data, but no real-world evidence exists yet.
- **BLOCKED:** needs an external action.
- **OPEN:** needs an owner decision.

| # | Gate | Status | Evidence / what is missing |
|---|---|---|---|
| G1 | Governed router for all 4 modes, 5 personalities, user limits that can only tighten, consent | PASS | CSS-118 suites (310 tests incl. RC1 on Linux); PR #119/#122 CI |
| G2 | Manual, disclosures, versioned consent | PASS | `test_css118_consent.py`, `test_css118_onboarding_ux.py` (Playwright) |
| G3 | Bypass closure (legacy loop, mobile ticket, direct scripts, random candidates) | PASS | `test_css118_bypass_closure.py`, `test_css_rc1_retirement.py` |
| G4 | Real-data signal pipeline with calibration and dual-control approval | BUILT | `test_css_rc1_signals.py`; no real calibration run (no market-data network here) |
| G5 | Strategy evidence: out-of-sample, walk-forward, with costs, all release gates passing | **BLOCKED** | Needs `css_calibrate.py` on real data. No artifact exists. **No profitability is claimed.** |
| G6 | Shadow / governed paper record | **BLOCKED** | Needs G5, two approvals, then `css_signal_shadow.py` on FINANCE |
| G7 | 72-hour endurance (OV-002) | **BLOCKED** | Must run on FINANCE in wall-clock time (`CSS064_ENDURANCE_RUN_PACKAGE.md`) |
| G8 | OMS: idempotency, rejection, partial fills, slippage, disconnect, reconciliation, emergency halt | BUILT | `test_css_rc1_oms.py` against `SimulatedVenue` |
| G9 | Broker sandbox verification | **BLOCKED** | Needs a practice-broker `Venue` adapter and owner-held practice credentials |
| G10 | Linux + Windows regression at the exact commit | Pending CI | Workflow `css118-validation.yml` now also triggers on the RC1 branch |
| G11 | AntiBleed minimum 50 vs CAD 20 pilot (B2) | **OPEN** | Owner choice A/B/C; every CAD 20 pilot order is rejected today |
| G12 | Ledger anchor key custody (B3) | **OPEN** | Owner: key holder, storage, publication channel |
| G13 | Production key custody and broker API permissions (trade-only, no withdrawal) | **OPEN** | Owner and broker |
| G14 | Independent review of RC1 code | **OPEN** | A human reviewer |
| G15 | Regulatory / compliance review (copy trading and discretionary management of other people's money) | **OPEN** | Owner and counsel |
| G16 | Approved traders for Copy mode (B4) | **OPEN** | Registry intentionally empty; independent vetting and two SUPER_USER approvers |
| G17 | Personality caps above the capital governors (B7) | **OPEN** | Owner: keep the governors binding (current) or lower the personality values |

## 2. Approvals still required
1. **Network access for data:**
   - an allow-list for `api.exchange.coinbase.com`;
   - `api-fxpractice.oanda.com` and an `OANDA_PRACTICE_TOKEN` secret, if FX is required.

   This is needed for G5 and G6, wherever they run.
2. **FINANCE operator time:** the calibration, the two approvals, the 72-hour shadow and endurance runs (G5–G7).
3. **Two SUPER_USER approvers** for any calibration artifact that passes the gates.
4. **Practice-broker credentials,** plus authorization to build a sandbox adapter (G9).
5. **Owner decisions:**
   - B2 (G11);
   - B3 (G12);
   - key custody and API permissions (G13);
   - B4 (G16);
   - B7 (G17).
6. **Independent code review** of PRs #119–#122 and RC1 (G14).
7. **Compliance sign-off** (G15).
8. **Separate live authorization:** account, capital, instruments and limits.

## 3. Minimum-exposure supervised rollout (only after §1 is all PASS and §2.8 is given)
**Stage 0 — shadow only.** Real-data signals feed paper accounts.
- Exit criterion: at least 30 days of shadow record in which realised net expectancy is within the calibration's 95% interval, and nothing is unresolved in OMS reconciliation.

**Stage 1 — one supervised account.**
- **Scope:**
  - one owner-designated account;
  - one instrument;
  - Conservative personality;
  - the smallest size AntiBleed allows (this depends on B2);
  - at most 1 open position;
  - a daily loss stop of 1% of allocated capital.
- **Operation:**
  - CSS-Assisted mode only: every order is approved by a human;
  - an OMS reconciliation every cycle;
  - the emergency halt is tested before the first order.
- **Duration:** 2 weeks.

**Stage 2 — wider manual scope.**
- Up to 3 instruments within the same caps.
- Still CSS-Assisted.
- Weekly review of slippage against the cost model.

**Stage 3 — supervised autonomy.**
- CSS Autonomous for the single account.
- The governors are unchanged.
- **Automatic halt on any of:**
  - a reconciliation diff;
  - drawdown beyond the personality limit;
  - realised costs above 1.5 × the model;
  - a calibration revocation.

Each stage needs a written owner go/no-go. Any gate regression sends the system back to Stage 0.
