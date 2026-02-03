\# REA Capital Trading Engine — Live Enable Runbook (Governance-Locked)



Status: \*\*LIVE EXECUTION MUST REMAIN DISABLED BY DEFAULT\*\*



This runbook defines the ONLY acceptable procedure to enable any live execution.

Any deviation is a policy breach.



---



\## 0) Non-Negotiable Safety Invariants



1\. \*\*Execution is OFF by default\*\*

&nbsp;  - No module may place orders unless explicitly enabled by operator action.



2\. \*\*Preflight must PASS\*\*

&nbsp;  - All gates must load and return deterministic outputs.



3\. \*\*3-layer instrument mapping invariant\*\*

&nbsp;  - Strategy Concept → Canonical REA Instrument → Broker Symbol

&nbsp;  - Startup must hard-fail on missing/ambiguous mapping.



4\. \*\*Human override required for high-risk trades\*\*

&nbsp;  - Override required for any trade risking > 25% equity (and must be double-confirmed).

&nbsp;  - (Note: current ExecutionGate also caps single-trade risk at 20% equity.)



5\. \*\*Drawdown cap\*\*

&nbsp;  - Max drawdown cap: \*\*25%\*\*.



6\. \*\*Cooldown rules\*\*

&nbsp;  - Global: 5 losses → 12 hour cooldown

&nbsp;  - Per-pair: 3 losses → pair block



7\. \*\*Operational limits\*\*

&nbsp;  - Max trades/day: \*\*10\*\*

&nbsp;  - Max concurrent positions: \*\*20\*\*



---



\## 1) Required Checkpoints Before Go-Live



You MUST have these tags present in repo history:



\- LIVE\_ADAPTERS\_TWELVEDATA\_OK

\- SIGNAL\_ENVELOPE\_OK

\- SIGNAL\_ARBITRATION\_OK

\- REGIME\_GATE\_OK

\- EXECUTION\_GATE\_OK

\- DRY\_RUN\_OK

\- PAPER\_SIM\_OK

\- PAPER\_SIM\_RUNNER\_OK

\- METRICS\_ROLLUP\_OK

\- REPLAY\_CSV\_OK



---



\## 2) Preflight Commands (MUST PASS)



From repo root:



1\) Confirm clean working tree:

```bash

git status



