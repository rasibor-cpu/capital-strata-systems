\# REA Capital Trading Engine — API Contracts

===========================================



Status: LOCKED (Wave 1)

Scope: Internal / External Interfaces (Read-first, Write-guarded)



This document defines the authoritative API contracts for interacting with the

REA Capital Trading Engine without touching core logic.



No API in this document is allowed to:

\- Mutate ledgers directly

\- Bypass governance, batch close, or validations

\- Circumvent maker–checker rules



All write APIs are subject to authorization and escalation rules.



---



\## 1. GENERAL PRINCIPLES



\- All APIs are \*\*idempotent where applicable\*\*

\- All monetary values are \*\*currency-qualified\*\*

\- All dates are \*\*ISO-8601 (YYYY-MM-DD)\*\*

\- All responses include:

&nbsp; - `status`

&nbsp; - `timestamp`

&nbsp; - `request\_id`



---



\## 2. READ-ONLY APIs (SAFE)



\### 2.1 Get Ledger Balances (As-Of)



\*\*Endpoint\*\*



