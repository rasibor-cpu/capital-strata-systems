# CSS pilot: independent reviewer handoff

**Frozen code-review baseline:** `6107cb7cb40e7292884df414150ad4f6266c1cab` (not the later documentation-commit SHA). Compare and review this exact commit. PR #106 remains **DRAFT** and targets PR #105's feature branch; neither is deployed.

**Reviewer assignment:** sponsor Robert Asibor; independent reviewer **either** Diana Whyte **or** Ehis, once verified as the selected release/security approver and independently enrolled under the accepted authorization policy. Diana accepted the reviewer *role*, not the release itself. Current enrollment implementation may require a separately reviewed policy/registry change for Ehis as an alternative. No second independent person is required by the owner's desired governance model, but the distinct sponsor and independent approver roles remain mandatory.

## Owner-approved limits
- CAD 20 equivalent maximum trial parent order/exposure, CAD 40 equivalent aggregate; two concurrent parents.
- Crypto, FX, futures and options in intended scope, limited to individually eligible and certified instruments.
- CAD is the **current pilot reference denomination**, not a universal CSS trading currency; quote/settlement and account currencies must be separate and actual risk normalized to the configured budget.
- Tighter per-instrument and per-asset restrictions are allowed, never higher limits without a separate owner decision.

## Independent test evidence (from FINANCE Windows, user-supplied logs)
| Candidate revision | Focused test selection | Outcome |
|---|---|---|
| `7b527d24` | Extended CSS pilot and monitor unit tests | 105 passed, 1 skipped |
| `09134322` | Cross-currency risk/reservation | 50 passed |
| `910d49cc` | Broker evidence and conversion | 55 passed |
| `c9628e15` | Synthetic IBKR/OANDA paper routes | 34 passed |
| `6107cb7c` | Signed intent, dual-control and isolated paper authorization | 44 passed, 1 skipped |

Counts are overlapping selections, **not additive**. These are not proof of real broker submission or operational certification. Original running checkout remained `9bc3c52`.

## Findings that prohibit live release
- Latest `governed_paper_route.py` deliberately fails closed on caller-provided `ALLOW`; signed-intent verifier is **not wired to a trusted risk decision producer**, verified issuer key registry, atomic replay ledger and complete R7/AntiBleed/RiskGovernor/kill-switch execution chain.
- Broker evidence module consumes broker-like records and allowlisted source identifiers; **cryptographic broker identity, market-rate provenance and actual brokerage connectivity are not certified**.
- FX conversion and preflight reservation code are stand-alone and must be proven on *all* live submit routes; current reservation ledger remains CAD-denominated.
- Independent reviewer keys are not enrolled, and separate release signatures bound to the exact candidate are not in hand.
- Genuine continuous 72-hour wall-clock operational endurance and independently reviewed final manifest are not established. Unit tests passing do **not** establish operational endurance PASS.
- Full candidate CI/regression, live broker connectivity, emergency stop, permissions, asset-specific contract risk, restart, fill and reconciliation evidence remain open.

## Reviewer decision
Reviewers should independently select one of: **REJECT / DEFER (OPEN GATES) / APPROVE ENGINEERING REVIEW ONLY**. **Do not sign a live-execution release authorization** while the above mandatory gates are open. Record reviewer identity, timestamp, exact reviewed commit, exceptions, evidence reviewed and any action items. A review document or WhatsApp acceptance does not substitute for the required cryptographic signature and gate evidence.

**Current release verdict:** candidate ready for independent *code/security review*; **live trading NO-GO**. No deployment, kill-switch change, bypass flag activation or real-money order submission authorized by this handoff.
