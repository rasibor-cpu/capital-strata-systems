# CSS paper decision-envelope provenance security review

Status: **SECURITY GAP CONFIRMED BY SOURCE INSPECTION — NOT CERTIFIED END-TO-END**

Reviewed branch: `governance/cad20-cross-asset-pilot-closeout`.

## Observed path
1. `backend/runtime/governed_paper_route.py` accepts a **caller-supplied** Python `decision_envelope` and tests only `decision_envelope.get("final_decision") == "ALLOW"` prior to reservations and broker simulation.
2. `engine/brokers/ibkr_paper_broker.py` and `engine/brokers/oanda_paper_broker.py` likewise reject non-ALLOW envelopes but **do not cryptographically authenticate issuer, instrument, order ID, risk context, revision, mode, expiry or replay**.
3. `engine/execution/execution_gate.py` contains AntiBleed and RiskGovernor evaluations, but reviewed paper-route code does **not call it** nor prove that it was called to produce the envelope.
4. Thus an arbitrary user of the new paper-route function can pass `{"final_decision":"ALLOW"}` with independently supplied risk amounts. The passing synthetic paper tests demonstrate precisely this usage, **not trusted end-to-end release-gate authorization**.
5. No assertion that R7, kill switch, actual broker login permissions or risk FX quote provenance is certified follows from these paper tests.

## Required remediation before any execution authority
- Bind a canonical decision to exact account/broker/instrument, side, quantity, price, settlement/quote/risk currency, parent and child ID, latest risk calculation, safety flags, expiry, one-time nonce, frozen candidate SHA and issue timestamp.
- A trusted authorization producer must independently execute R7, AntiBleed, RiskGovernor, global stop and broker readiness; consumers verify issuer authenticity and complete binding, not just an ALLOW string.
- Store and atomically consume the authorization before submission; prevent mismatched, expired, repeated, cancelled or concurrent attempts and unreviewed partial fills.
- Maintain an independent paper-only mode and disallow all real brokers in simulation. Live path requires a distinct reviewed integration, approved dual signatures, operational release gates and broker safety checks.
- Add negative tests for forged `ALLOW`, mismatched instrument/amount, missing provenance, stale safety flags, replay, kill switch on, failing AntiBleed/R7 and offline broker.
- Do not substitute caller-controlled booleans or a trusted-looking envelope field for verification.
- **Do not claim full paper integration certified** before these checks can be demonstrated end-to-end.

Current disposition: isolated module and synthetic tests pass; **decision provenance remains untrusted; live execution NO-GO**.
