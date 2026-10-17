# CAD 146 two-track simulation of the CSS autonomous trader

**Simulated only. LIVE_TRADING_AUTHORIZED = NO. No broker is reachable from this code.**

## Designated trader and configuration (from code, not chosen here)
- Trader: CSS autonomous engine, `AUTONOMOUS_SOURCE_ID = "CSS_AUTONOMOUS_ENGINE"`; signals only from `backend.signals.producer.SignalProducer`.
- Mode: `Simulated Trading`. Personality: `Balanced` (`SIMULATED_DEFAULT_PERSONALITY`, the code's canonical default for this mode). Engine mode `SAFE`.
- Account: isolated `PaperBook`, CAD 146.00 equity and cash, no positions, no deposits or withdrawals.
- Gates unchanged: consent, personality, user limits, R14F, R7 (incl. 1-hour sign-on), ExecutionGate/AntiBleed (CAD 50 minimum), capital governors, 10/3/3/2/2 position caps.

## Tracks
- **A — strict governed:** operational dual-control approvals ledger (read-only), `publish_real_data`.
- **B — research shadow:** same gates, calibration approval not required; every record labelled `RESEARCH_COUNTERFACTUAL`; refuses the operational paper book.
- Both consume the same journalled observation per cycle; each bar is decided once per track (persisted), so restarts and replays cannot duplicate fills. Outages are journalled and open positions are held.

## Determined before any live run
With CAD 146 equity the governed sizing yields at most **CAD 7.30** per order for Balanced (CAD 5.84 for Conservative; Safe rejects on quality and disallows crypto). That is below AntiBleed's **CAD 50** minimum, so **every entry in both tracks is rejected with `anti_bleed_guard:trade_size_too_small`, whatever the signal quality**. Separately, no calibration artifact passes the gates on real data (PR #125), so Track A cannot even produce a routable signal. The expected 48-hour outcome for both tracks is therefore CAD 146.00, identical to the no-trade baseline. The run would still record which signals CSS would have proposed and why each was refused. With the same personality, entries become size-eligible from roughly CAD 1,000 equity (Balanced) or CAD 1,250 (Conservative).

## Limitations
- USD/CAD moves are not applied to positions (no authorized real-time USD/CAD source is connected).
- Simulated fills use the governed paper fill model; R7's 1-hour sign-on means new entries require an operator attestation within the last hour.

## Runbook (FINANCE or any host with market-data access)
See `tools/css_sim_cad146.py` (run / attest / report).

## Lifecycle, recovery and supervision (added after the FINANCE 48h run of 2026-10-16)
- Cadence: `--poll-seconds 300` polls every 5 minutes (HEARTBEAT + OBSERVATION each poll); bars are
  hourly, so each bar is observed about 12 times and decided once per track. A bar is decided only
  once it has been closed for `--bar-settle-seconds` (default 600): Coinbase revised 12 of 14 FINANCE
  bars between the first poll (close + ~2.5 min) and the next one. If a decided bar still changes,
  `BAR_REVISED_AFTER_DECISION` is journalled.
- Journal records: `RUN_STARTED`, `RUN_RESUMED`, `RUN_STOPPED` (reason, exit code),
  `RUN_INTERRUPTION_DETECTED` (a resume after a stop that was never recorded: console closed,
  reboot, power loss, kill), `SUSPENSION_DETECTED` (host slept: wall-clock jump > 3x poll),
  `BARS_MISSED` (bars that closed while down; never decided late), `DECISION_INFLIGHT_RECOVERED`
  (a crash inside a decision: the bar is closed out, never re-decided), `OPERATOR_SESSION_EXPIRED` /
  `OPERATOR_SESSION_RESTORED` (also a console ALERT). The heartbeat carries `operator_session_valid` and
  `entries_blocked`; `<root>/status.json` holds the current state.
- R7 is unchanged: a sign-on older than 3600 s blocks every new entry (fail closed). A 48-hour run
  needs `attest` at least hourly while entries are wanted; `attest` is safe while `run` is active.
  `--on-session-expiry exit` stops the run with exit code 3 instead of observing with entries blocked.
- One `run` per root (`<root>/run.lock`). Exit codes: 0 completed, 1 error, 2 preflight failed,
  3 sign-on expired (exit policy), 4 root already running, 5 refused (consent/agreement),
  128+N signal (Ctrl+C 130, Ctrl+Break 149 on Windows). Re-running `run` on the same root resumes.
