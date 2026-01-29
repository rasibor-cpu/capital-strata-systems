\# Controlled Signal Path Test — Plan



\## Purpose

Validate VWAP → Signal → Prompt pipeline under controlled conditions.



\## Safety Constraints

\- PROMPT\_ONLY mode only

\- No live or paper execution

\- No production thresholds changed

\- RegimeGate bypass (temporary, test-only)



\## Success Criteria

\- VWAP deviation computed

\- Signal module invoked

\- prompts\_queued > 0 observed in summary



\## Rollback

\- Revert to Integration Baseline v1

\- Restore RegimeGate default behavior



