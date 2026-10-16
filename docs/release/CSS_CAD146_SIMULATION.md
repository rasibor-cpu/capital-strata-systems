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
