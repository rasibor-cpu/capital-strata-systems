# CSS Signal Quality Model

## Purpose

This document defines how Capital Strata Systems (CSS) evaluates and
classifies trading opportunities into signal quality tiers.

Signal quality is a central concept within CSS because it directly
determines which opportunities are allowed to reach the execution layer.

The objective is to prioritize **high-confidence trades** while filtering
out noise.

---

## Signal Classes

CSS currently uses four signal tiers:

ELITE  
STRONG  
WEAK  
NOISE  

Only the highest tiers should normally be allowed to reach execution.

---

## Signal Confidence

Each opportunity receives a **confidence score** produced by the
Trade Decision Orchestrator. The score is derived from multiple
intelligence engines.

Example contributing components may include:

- Market regime alignment
- Liquidity sweep detection
- Signal confluence strength
- Opportunity pressure
- VWAP elasticity
- AI opportunity scoring

---

## Example Confidence Model

confidence =
0.30 × regime alignment  
0.25 × confluence strength  
0.20 × liquidity event strength  
0.15 × pressure acceleration  
0.10 × AI opportunity score  

This weighted structure ensures that **multiple factors must align**
before a signal becomes high quality.

---

## Classification Thresholds

Typical thresholds may be:

ELITE   → confidence ≥ 0.65  
STRONG  → confidence ≥ 0.50  
WEAK    → confidence ≥ 0.40  
NOISE   → confidence < 0.40  

These thresholds may evolve as the system is tuned.

---

## Execution Policy

Recommended default behavior:

ELITE signals  
→ fully eligible for execution

STRONG signals  
→ eligible depending on risk and session conditions

WEAK signals  
→ generally filtered out

NOISE signals  
→ always rejected

---

## Strategic Philosophy

CSS favors **quality over frequency**.

The system is designed to wait for high-quality alignment rather than
generate excessive trades.

This approach supports the broader CSS philosophy:

Controlled Risk Governance  
Controlled Compounding

---

## Future Enhancements

Future improvements may include:

- adaptive thresholds based on market volatility
- regime-specific signal thresholds
- machine-learning calibration
- performance feedback loops
