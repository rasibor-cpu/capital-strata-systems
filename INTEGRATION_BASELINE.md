\# REA Capital Trading Engine — Integration Baseline v1 (Prompt-Only, Regime-Safe)



\## Date

2026-01-28 (UTC) — first confirmed end-to-end system run



\## What this baseline proves

\- CSV replay loads and iterates bars

\- EngineLoop runs end-to-end

\- RegimeGate is active and can BLOCK

\- VWAP module is wired (deviation may be N/A when gate blocks)

\- Prompt decision layer executes (PROMPT\_ONLY outcome supported)

\- Summary counters return correctly (bars\_1m, prompts\_queued)



\## Exact run command (Windows CMD, no file edits)

python -c "from replay\_csv import replay, CSVReplayConfig; from engine\_loop import EngineLoop, EngineConfig; rcfg=CSVReplayConfig(csv\_path='sample\_spy\_1m.csv', symbol='SPY'); ecfg=EngineConfig(symbol='SPY', print\_prompts=True); engine=EngineLoop(ecfg); summary=replay(rcfg, engine); print('=== REPLAY SUMMARY ==='); print(summary)"



\## Expected/Observed outcome

\- Regime State: BLOCK

\- Decision: PROMPT\_ONLY (reason: regime gate blocked signals)

\- Summary example: {'bars\_1m': 10, 'prompts\_queued': 0}



\## Notes

\- Zero prompts is VALID at this stage.

\- This baseline is the rollback reference before any threshold tuning or dev\_force\_allow testing.

