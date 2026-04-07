# CSS Options Module — Specification v1

## 1. Design Philosophy (LOCKED)

Options in CSS are controlled-risk, asymmetric payoff instruments used only when edge is high and defined.

Not for:
- speculation
- high-frequency churn
- complex spreads (yet)

---

## 2. Module Placement in CSS Architecture

Data Layer → Options Adapter  
Intelligence Layer → Options Scoring Extension  
Decision Layer → Options Selection Logic  
Execution Layer → Options Position Manager  
Governance Layer → Options Risk Controls  

---

## 3. Supported Instruments (Phase 1)

### Allowed
- Long Calls
- Long Puts

### Not allowed yet
- Short options
- Credit spreads
- Iron condors
- Multi-leg strategies

---

## 4. Options Data Schema (MANDATORY)

Each options row must contain:

```python
{
    "symbol": "AAPL_20240621_180_C",
    "underlying": "AAPL",
    "option_type": "CALL",
    "strike": 180.0,
    "expiry": "2024-06-21",
    "premium": 4.25,
    "bid": 4.20,
    "ask": 4.30,
    "spread_bps": 235.0,
    "implied_vol": 0.28,
    "delta": 0.55,
    "theta": -0.04,
    "price": 4.25,
    "asset_class": "options"
}
