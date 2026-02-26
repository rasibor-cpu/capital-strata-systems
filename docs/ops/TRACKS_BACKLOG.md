# CSS Tracks Backlog (Do Not Drop)

This file ensures we do not “lose” parallel tracks while executing the current priority.

## Active Priority (A) — Financial Control Layer (Current)
1) Posting calendar governance (invalid dates, backdating, override enforcement)
2) Override logging (append-only, hash chained)
3) End-of-day snapshot + per-user print pages
4) GL printing (period-based, running balance, export-ready)
5) Month-end snapshot
6) Year-end consolidated BS/IS + auto new FY rollover

Owner intent: Complete A end-to-end before shifting focus.

---

## Parked Track (B) — Trading Engine Signal Refinement (Next)
- Threshold tuning / epsilon improvements
- Prompt generation improvements (still prompt-only unless governance enables execution)
- Performance metrics + stability validation

---

## Parked Track (C) — Futures Adapter Coding (Next)
- Futures-capable broker adapter
- Futures risk math spec (margin/drawdown stricter caps)
- Activation rule enforcement (4 profitable FX weeks, no defensive trigger)

---

## Parked Track (D) — Reporting & Audit Pack for NIW Positioning (Next)
- “Institutional Controls Pack” PDF-style exports
- Audit narrative + evidence artifacts
- Demo runbook focused on governance, controls, and traceability

---

## Previously Discussed Reporting Roadmap Options (Keep)
A) Stub registrations for legacy FinCon reports  
B) Month-end/year-end wrapper logic  
C) Report integrity hash  
D) Lock report versioning/schema freeze  
E) Wire reports into Posting Screens workflow  ✅ (selected now)