# REA Capital – Full System Specification (v1.0)
**Status:** LOCKED (Authoritative)  
**Date:** 2026-01-31  
**Scope:** Prompt-only trading engine + institutional-grade back-office (ledgers, governance, reporting, audit).  
**Hard Constraints:** NO trade execution; NO auto-risk escalation; prompt/diagnostics only.

---

## 0) Master Go-Live Checklist (v1.0) — LOCKED
### Phase 1 — Core Engine (LOCKED ✅)
- Data ingestion + validation (CSV replay)
- 1m → 5m aggregation
- Minimum-bar gating (Module 1)
- RegimeGate (Module 2) conservative default
- VWAP mean reversion prompt generation (Module 3) prompt-only
- Engine loop stable end-to-end
- Baseline tags/rollback discipline (v3.0-stable approved)

### Phase 2 — Ledgers & Reporting (LOCKED ✅)
- Branch/currency ledgers, DR/CR rules, running balance
- Daily EOD, Monthly, Year-End reports (formats locked)
- Nil-day handling explicit
- `GET /api/ledger/balances` endpoint
- Business calendar + holiday handling + value-date adjustments
- EOD automated generation + distribution rules
- Multi-ledger reporting: accruals, tax, amortization, fixed assets, etc.
- Reports selectable by user (scope/ledger/type/period)

### Phase 3 — Governance & Access (LOCKED ✅)
- Roles, thresholds, approvals, overrides
- Dynamic limit changes (Admin/Super) with controls; no self-change
- Password + access policy, lockouts, ON LEAVE state
- Maker–checker where required
- Role/status changes + create-user + create-branch + create-institution screens

### Phase 4 — Posting Screens (LOCKED ✅)
- Maker input → preview → approval queue → approval review
- Override flow conditional + triple confirmation
- Final immutable ticket output

### Phase 5 — Audit & Runbook (LOCKED ✅)
- Append-only immutable logs
- Full operational runbook procedures
- Consolidation audit events

### Phase 6 — Live-Readiness (LOCKED ✅ / Implementation-only)
- ENV flags (DEV/UAT/PROD), replay vs live abstraction, dry-run commands
- Explicit no-execution guarantee

---

## 1) Business Calendar & Holiday Handling (LOCKED)
### 1.1 Business Calendar
System supports configurable **Business Calendar** per market/country/branch:
- Country/Market code (US/UK/EU/NG/CA etc.)
- Holiday list (date + name + market)
- Weekend rules (default Sat/Sun; configurable)
- Admin-managed without code changes (config/admin UI)

### 1.2 Value-Date Adjustment
If value date falls on non-business day (holiday/weekend):
- Default convention: **FOLLOWING** (next business day)
- Convention set per market and logged
- Audit: original date, adjusted date, market calendar, convention, reason

### 1.3 Reporting impact
- EOD runs on business days
- Holidays either:
  - (Default) skip EOD report and log “Holiday — no business day”
  - or generate explicit Holiday Nil Report (optional future)

---

## 2) Ledgers & Reports (Formats LOCKED)

### 2.1 Daily EOD Ledger Report Format (v1.0)
**Header:**
- Title: REA Capital – Daily End-of-Day Ledger Report
- Business date (YYYY-MM-DD)
- Generation timestamp
- Environment (DEV/UAT/PROD)
- Status: FINAL

**Currency sections** (one per currency):
- Opening Balance (Start of Day)
- Transaction table (if any):
  - Seq, Time, Txn Ref, Description, DR, CR, Running Balance
  - DR or CR only; running balance after each row
- Nil-day handling:
  - “NO TRANSACTIONS FOR THIS BUSINESS DAY”
- Closing summary:
  - Total Debits, Total Credits, Closing Balance
  - Ledger Status: BALANCED or ERROR – OUT OF BALANCE

**Footer certification:**
- No trade execution performed
- All postings passed validation
- Ledger integrity preserved

**File name:**
- EOD_LEDGER_YYYYMMDD.txt (or .pdf later)

---

### 2.2 Monthly Ledger Report Format (v1.0)
**Header:**
- Title: REA Capital – Monthly Ledger Report
- Period: YYYY-MM
- Timestamp
- Environment
- Status: FINAL

**Currency sections**:
- Opening Balance (Start of Month)
- Daily summary table:
  - Date, Opening, Total DR, Total CR, Closing, Status
- Monthly totals:
  - Monthly Total DR/CR, Net Movement, Closing Balance, Status
- Nil-month handling:
  - “NO TRANSACTIONS FOR THIS MONTH”
  - Opening = Closing

**File name:**
- MONTHLY_LEDGER_YYYYMM.txt

---

### 2.3 Year-End Ledger Report Format (v1.0)
**Header:**
- Title: REA Capital – Year-End Ledger Report
- Financial year: YYYY
- Timestamp
- Environment
- Status: FINAL

**Currency sections**:
- Opening Balance (Start of Year)
- Monthly roll-up table:
  - Month, Opening, Total DR, Total CR, Closing, Status
- Year-end totals:
  - Yearly Total DR/CR, Net Movement, Closing, Status

**Year-end closing logic:**
- Default: carry forward closing as next-year opening
- No implicit resets (config must be explicit)

**File name:**
- YEAR_END_LEDGER_YYYY.txt

---

### 2.4 Consolidated (Org-level) Reporting
- Consolidation is reporting-only (read-only); never posts entries
- Currency-by-currency (no implicit FX translation)
- Admin/Super/Financial Control only
- Includes branches included/excluded, method, timestamps

---

## 3) Branch, Accounts, Access & Distribution (LOCKED)

### 3.1 Account number must encode branch domicile
Every account number begins with a **unique branch code/string**:
- Format: <BRANCH_CODE>-<ACCOUNT_TYPE>-<SEQUENCE>
- Branch domicile derived from account number prefix
- Branch code immutable

### 3.2 User access to accounts
- Users can view and transact on **any account**, regardless of domicile
- Branch domicile primarily controls:
  - ledger ownership
  - branch report routing
  - branch financial statements

### 3.3 EOD distribution rules
- On EOD processing:
  - all branch reports generated and sent to respective branch recipients
  - consolidated report sent to:
    - Admin
    - Super User
    - any user flagged as Financial Control (authorized function)
- All distributions audited

### 3.4 Financial Control function flag
- Independent flag controlling consolidated report visibility
- Does not grant posting/approval rights beyond role

---

## 4) Governance & Approvals (LOCKED)

### 4.1 Roles
- Trader (Maker)
- Approver L1
- Approver L2
- Admin
- Super User

### 4.2 Threshold bands (LOCKED)
- 0 – 2,000,000 → AUTO
- >2,000,000 – 15,000,000 → L1
- >15,000,000 – 50,000,000 → L2
- >50,000,000 – 200,000,000 → Admin
- >200,000,000 → Super

### 4.3 Dynamic approval limits (Admin/Super) — allowed with controls
- Admin/Super may change user approval limits
- **No user can change own limit**
- Maker–checker required
- No retroactive changes; default immediate
- Full audit: old/new, initiator, checker, justification, timestamp

### 4.4 Hard governance prohibitions
- No self-approval (any level)
- No splitting transactions to avoid thresholds
- Threshold bands not overrideable
- Institutional aggregate limits enforced

---

## 5) Overrides (LOCKED v1.1)

### 5.1 Non-overridable (absolute)
- Trade execution / enabling execution
- No self-approval
- Aggregate limit breach
- Currency mismatch
- Missing/invalid value date
- Ledger imbalance
- Audit logging failure
- Holiday/business-day logic bypass
- Safety flags

### 5.2 Overridable (controlled)
- Risk warnings
- Timing warnings
- Non-fatal validation warnings

### 5.3 Override auth
- Only Admin/Super within overridable scope
- Trader/L1/L2 cannot override

### 5.4 Triple confirmation
1) Explicit override select
2) Override password entry
3) Typed phrase:
   - I ACKNOWLEDGE THIS OVERRIDE AND ACCEPT FULL RESPONSIBILITY

### 5.5 Override password
- Minimum **4 characters**
- User-ID bound
- Separate from login password
- Lockout after 3 failed override attempts
- Reset requires Admin + Super
- All attempts audited

---

## 6) Password & Access Policy (LOCKED v1.1)

### 6.1 Login password
- Minimum 8 characters
- User-ID bound
- Hashed+salted
- Cannot match override password

### 6.2 Lockouts
- Max failed login attempts: **3**
- Lock duration: **5 minutes**
- Repeated lockouts escalated and audited

### 6.3 Sessions
- Idle timeout: 15 minutes
- Absolute timeout: 8 hours
- Admin/Super can terminate sessions; audited

### 6.4 Account states
- Active
- Suspended
- Disabled
- On Leave (no access)

### 6.5 On Leave policy
- On Leave user cannot log in, post, approve, override, or access APIs
- Start/end dates supported
- Early return requires Admin/Super action; audited

---

## 7) Posting Screens (LOCKED v1.0)

### Screen 1 — Maker Posting Input
Fields: DR/CR, currency, amount, value date, description, counterparty, account/ledger ref  
Validations: status active, amount>0, currency valid, value date adjusted, limit checks

### Screen 2 — Preview & Validation
Shows adjusted value date, required approval level, warnings  
Requires confirmation checkbox before submit

### Screen 3 — Approver Queue
Role-filtered pending approvals; maker cannot approve own

### Screen 4 — Approval Review
Revalidates currency/value date/limits; approve/reject with reason required

### Screen 5 — Override Confirmation (conditional)
Triple confirmation workflow + override password

### Screen 6 — Final Ticket
Immutable Txn reference; all details; printable; stored in audit trail

### Admin Console screens
- Create Institution
- Create Branch
- Create User
- Change Role/Status
- Assign Financial Control
- Manage calendars/holidays

---

## 8) Institution / Branch / User Admin (LOCKED)

### 8.1 Role change
- Admin/Super can change user roles
- No self role change
- Maker–checker enforced; full audit

### 8.2 Create Institution
Defines:
- institution code/name
- default market calendar
- default currency set
- institutional limits
- financial year-end definition

### 8.3 Create Branch
- branch code/name
- parent institution
- market calendar (can override)
- branch limits (optional)

### 8.4 Create User
- user id, name, role, status
- branch assignment
- initial login+override passwords
- Financial Control flag optional
- audited

---

## 9) Chart of Accounts & Bank-Grade GL (LOCKED v1.0)

### 9.1 GL baseline
GL must incorporate a **standard bank-grade CoA** aligned to IFRS/GAAP concepts and common FI GL layouts.

### 9.2 Mandatory account classes
Assets: Cash/Nostro, interbank, loans/advances, AR, accrued income, prepayments, fixed assets  
Liabilities: deposits, interbank borrowings, AP, accrued expenses, deferred income, taxes payable, provisions  
Equity: capital, reserves, retained earnings, current year result  
Income: interest, fees/commissions, trading/other income  
Expenses: interest expense, OPEX, staff, depreciation, amortization, tax expense

### 9.3 Dynamic account creation
Admin/Financial Control/Super can create new accounts that:
- map to correct statement side (BS or P&L)
- roll up under correct control account
- auto-appear in TB/BS/P&L and branch/consolidated reports
- fully audited; misclassification blocked

---

## 10) Full Financial Workflows (LOCKED v1.0)
System must support:
- Fixed Assets: define assets, depreciation schedules, postings, disposal/revaluation workflows
- Loans/Advances/Repayments: principal vs interest separation, accrual, repayment allocation, GL postings
- Expense processing: initiation, approvals, accrual/reversal, payment, reconciliation
- Income recognition: accrual, deferred income release, adjustments
All workflows respect:
- approvals, thresholds, period controls, audit logging

---

## 11) Accounting Period Control (LOCKED v1.0)
- Periods defined by institution
- Closed period: no postings/approvals/overrides
- Reopen only by **Admin + Super User together** (maker–checker)
- Upon reopen: **all computations reworked** based on new entries/updates
- Re-close generates new FINAL report set; old retained (not deleted)

---

## 12) Audit Logging & Runbook (LOCKED v1.0)
### 12.1 Audit logs
- Append-only, immutable, timestamped (UTC internal)
Must log:
- auth/session events
- posting lifecycle
- approvals/rejections
- overrides (success/failure)
- limit changes, role/status changes
- calendar changes, value-date adjustments
- report generation + distribution
- consolidation events

Required fields:
- audit id, event type, user id/system, role, UTC timestamp, source, object ref, outcome, message/reason

### 12.2 Runbook
Must include:
- start-up and health checks
- replay mode operation & verification of prompt-only behavior
- daily operations + EOD trigger
- exception handling + escalation
- governance ops (leave, limits, calendars)
- shutdown/recovery + rollback using tags
All steps copy/paste safe and reproducible.

---

## 13) Live-Readiness (Implementation-only)
- ENV flags (DEV/UAT/PROD)
- replay vs live abstraction (placeholders for data feeds)
- dry-run command suite
- explicit no-execution guarantee assertion

---

## End of Specification
**This document is the authoritative contract for implementation.**
