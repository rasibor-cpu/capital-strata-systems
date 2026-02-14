\# Capital Strata Systems

\## Phase 1 – Institutional Baseline Lock



Status: LOCKED  

Date: 2026-02-14  



---



\## 1. Governance Invariants



The following rules are permanent architectural invariants:



\- RiskGovernor policy is loaded at session initialization only.

\- No runtime capital policy mutation is allowed.

\- Any policy change requires a fresh login/session restart.

\- All policy loads are session-logged and auditable.



---



\## 2. Deterministic Risk Sizing



\- Position sizing must be deterministic.

\- Caps must be computed from declared policy only.

\- Micro-mode is triggered automatically under capital stress.

\- No discretionary overrides outside approved Super User scope.



---



\## 3. Execution Gate Rules



Execution requires ALL:



\- RiskGovernor approval

\- RegimeGate approval

\- Liquidity gate approval

\- Correlation/concentration approval

\- Duplicate trade guard approval



If any gate fails → execution is denied.



---



\## 4. Kill Switch



\- Global execution kill switch exists.

\- Must override all gates.

\- Must be enforceable in LIVE mode.

\- State must be visible in logs.



---



\## 5. Capital Allocation Policy



Baseline allocation:



\- 75% FX

\- 25% Futures



Separate capital buckets.

Shared Governance Core.



---



\## 6. Futures Activation Rule



Futures module remains dormant until:



\- 4 consecutive profitable FX weeks

\- No global defensive trigger active



Activation must be logged.



---



\## 7. Headless Mode



\- HEADLESS\_DEV\_MODE allowed for structured paper testing.

\- dev\_force\_allow MUST be False before any production environment.

\- RegimeGate must remain active at all times.



---



\## Phase 1 Definition of Done



\- Deterministic risk caps

\- Stable execution firewall

\- Adaptive portfolio scaling

\- Session-locked governance

\- Separate TEST/LIVE ledger handling

\- Audit logging active



Phase 1 is considered institutionally stable.



