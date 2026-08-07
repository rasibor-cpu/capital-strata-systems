# LDT-002 R2A Live Pilot Currency Authority

Status: APPROVED OWNER POLICY FOR CURRENT BASELINE

Scope: Controlled live micro-pilot capital and risk gating only.

## Authority

The current live micro-pilot capital authority is denominated exclusively in CAD.

No FX conversion is authorized for live micro-pilot risk or capital gating in this phase.

An order may be evaluated against Phase 152A live-pilot ceilings only when its authoritative exposure amount is explicitly denominated in CAD.

## Explicit CAD Identity Contract

Allowed comparison path:

1. source exposure amount is explicit;
2. source exposure currency is explicit `CAD`;
3. target limit currency is explicit `CAD`;
4. authoritative monetary amount is valid under Decimal semantics;
5. no FX rate is applied;
6. evidence records the operation as an explicit CAD identity comparison.

This is an identity comparison, not an FX conversion.

## Fail-Closed Rejections

The following must fail closed before downstream approval:

- non-CAD exposure;
- missing exposure currency;
- blank or ambiguous exposure currency;
- invalid or unsupported exposure currency;
- missing authoritative exposure amount;
- invalid authoritative exposure amount;
- unit-only orders without authoritative CAD exposure;
- any order that would require an FX rate;
- broker or account currency substitution for order-exposure currency;
- inferred currency from instrument naming;
- inferred CAD equivalence;
- accounting FX-cache fallback;
- broker-rate fallback;
- inverse-rate fallback;
- cross-rate or triangulation fallback.

## Prohibitions

- No use of `backend/app/fx_daily_rates.py` for live-pilot authorization.
- No network access inside risk gates.
- No broker-supplied FX rate trust path.
- No inverse-rate or cross-rate authority.
- No paper-mode or reporting-mode behavior may confer live authority.

## Decimal and Comparison Rules

- Authoritative monetary evaluation must use Decimal semantics.
- Exposure amounts must not be rounded upward to grant authority.
- No float coercion is permitted for authoritative live-pilot currency gating.
- Because no FX conversion is authorized, no rate freshness window applies in this phase.

## Consequences

- OANDA unit-based live orders are not authorized by this phase.
- Coinbase USD live exposure is not authorized by this phase.
- Non-CAD live exposure remains blocked.

## Future Work

A future separately approved phase may introduce a typed FX authority contract.

That future work must not be inferred from this decision and requires separate owner approval.

## Trading Authority

This policy does not increase trading authority.