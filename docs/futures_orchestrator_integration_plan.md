# CSS Futures Orchestrator Integration Plan
## Phase 1 Futures Live Routing Architecture Lock

### Purpose

Defines how futures trading integrates into the CSS TradeDecisionOrchestrator without disrupting existing crypto, FX, and options routing layers.

This specification governs:

- futures signal routing into orchestrator
- futures allocation path integration
- futures execution dispatch flow
- futures risk governor hook sequence
- dashboard futures lifecycle reporting
- multi-asset orchestration coexistence rules

---

## Integration Objective

Enable futures contracts to become a fully routed live asset class inside CSS.

After this integration:

TradeDecisionOrchestrator must process futures exactly like:
- crypto
- FX
- options

with futures-specific governance overlays.

---

## Orchestrator Entry Point

### New Asset Class:
```python
asset_class = "FUTURES"
