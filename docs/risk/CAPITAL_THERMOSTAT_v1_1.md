# Capital Thermostat v1.1
Capital Strata Systems (CSS)

## Purpose
The Capital Thermostat dynamically adjusts trading risk based on system health, equity performance, and drawdown conditions. It ensures rapid capital protection while allowing controlled risk expansion when conditions improve.

This version introduces **intraday mode evaluation every 4 hours** with **mode dwell requirements for escalation**.

---

# Operating Principles

1. **De-risk immediately**
2. **Increase risk gradually**
3. **Never skip intermediate risk modes**
4. **Require stability before increasing exposure**
5. **Maintain full auditability of all mode transitions**

---

# Thermostat Modes

| Mode | Risk Per Trade | Max Concurrent Positions | Purpose |
|-----|-----|-----|-----|
| HOT | Highest allowed | Full allocation | Strong performance conditions |
| WARM | Moderately elevated | Full allocation | Positive performance |
| BASE | Standard baseline | Full allocation | Normal operations |
| COOL | Reduced exposure | Limited positions | Capital protection |
| HALT | 0 | 0 | Trading stopped |

---

# Evaluation Schedule

The thermostat evaluates trading conditions at two levels:

### End-of-Day Evaluation
Performed after EOD processing to determine the **baseline mode for the next trading session**.

### Intraday Evaluation
Performed every **4 hours** during the trading day using mark-to-market equity.
