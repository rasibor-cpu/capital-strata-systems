\# REA Capital Trading Engine — Deployment Runbook



\## 1) Purpose

This runbook defines:

\- How to start/stop the engine safely

\- What “healthy” looks like

\- How to detect silent failures

\- What to do when the engine is blocked by gates (expected) vs broken (unexpected)



This runbook is written to be valid even when the engine is in prompt-only mode.



---



\## 2) Core Operating Principles (Fail-Safe)

\- \*\*Fail-closed by default\*\*: If something is ambiguous, the engine should block rather than execute.

\- \*\*No silent success\*\*: “No output” is treated as \*\*AMBER\*\* until proven healthy.

\- \*\*Audit everything\*\*: Every privileged action (override, gate bypass, risk escalation) must be logged.

\- \*\*One run = one ENGINE\_RUN\_ID\*\*: Every engine process has a unique run ID for traceability.



---



\## 3) Expected Runtime Signals

\### 3.1 Logging

\- A startup banner should appear (if enabled):

&nbsp; - `REA CAPITAL TRADING ENGINE — STARTUP`

&nbsp; - `ENGINE\_RUN\_ID=...`

\- Logs should include:

&nbsp; - `ENGINE\_RUN\_ID=...`

&nbsp; - `TRACE\_ID=...` (per trade/action where applicable)



\### 3.2 Heartbeats

\- Engine heartbeat should emit every N seconds (default recommendation: 30s):

&nbsp; - `ENGINE\_HEARTBEAT | uptime=... | adapters=... | state=...`



Heartbeats are mandatory for declaring GREEN.



\### 3.3 Session Gating

Session checks should emit:

\- `SESSION\_ALLOW | asset\_class=... | state=... | reason=...`

or

\- `SESSION\_BLOCK | asset\_class=... | state=... | reason=...`



---



\## 4) Health States (Operational Interpretation)

\### GREEN

\- Heartbeat present and periodic

\- No unhandled exceptions

\- Adapters reporting (or explicitly allowed to be zero in dev)

\- Session gate states are explicit (ALLOW or BLOCK with reason)



\### AMBER

\- Engine alive but not “fully validated”

\- Examples:

&nbsp; - `adapters=0` when adapters are expected

&nbsp; - Stale adapter heartbeats

&nbsp; - Session blocked (expected) but persistent beyond expected timeframe

&nbsp; - No trades due to regime gate (expected) but must still show heartbeat



\### RED

\- No heartbeat

\- Repeated exceptions in logs

\- Engine process exits unexpectedly

\- Clock sanity check failing (system time mis-set)

\- Any sign of uncontrolled execution (must halt immediately)



---



\## 5) Start Procedure (Standard)

\### Preconditions

\- You are in repo root:

&nbsp; - `C:\\Users\\rasib\\source\\REA-capital-trading-engine`

\- Branch: `main` (or approved release branch)

\- Latest code:

&nbsp; - `git pull origin main`



\### Start (example)

Run the engine using your standard command (project-specific).

Immediately verify:

1\) Startup banner OR first log line appears

2\) Heartbeat begins within 60 seconds

3\) Session gate emits ALLOW/BLOCK events



---



\## 6) Stop Procedure (Standard)

Preferred:

\- Use the engine’s explicit stop command (if implemented)



Fallback:

\- `CTRL+C` to stop foreground process



After stop:

\- Confirm final logs show clean shutdown (if implemented)

\- Record ENGINE\_RUN\_ID for incident traceability



---



\## 7) Triage: “Blocked vs Broken”

\### If BLOCKED (Expected)

Common reasons:

\- `SESSION\_BLOCK` (weekend, outside hours, asset class not whitelisted)

\- Regime gate not allowing (e.g., insufficient bars)



What to check:

\- Heartbeat still running

\- No exceptions

\- Reason is explicit



\### If BROKEN (Unexpected)

Signals:

\- No heartbeat

\- Exceptions repeat

\- Adapters never beat

\- Startup banner never appears



What to do:

1\) Capture last 200 lines of logs

2\) Record `ENGINE\_RUN\_ID`

3\) Restart once

4\) If repeatable, open an incident note and do not proceed to live tests



---



\## 8) Minimal Verification Checklist (Pre-Live)

\- \[ ] On `main`, pulled latest

\- \[ ] Startup logs present

\- \[ ] Engine heartbeat visible

\- \[ ] Session gate emits explicit ALLOW/BLOCK

\- \[ ] No repeated exceptions

\- \[ ] Adapters either beating or explicitly in dev mode

\- \[ ] Any override actions are logged (who/why)



---



\## 9) Notes / Decisions Log

Record operational decisions here:

\- Date/Time:

\- Engine version / tag:

\- ENGINE\_RUN\_ID:

\- Outcome:

\- Notes:



