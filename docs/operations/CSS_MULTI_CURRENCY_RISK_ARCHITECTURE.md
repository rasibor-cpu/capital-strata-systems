# CSS multi-currency trading and risk-budget design

Status: OWNER APPROVED DESIGN DIRECTION; IMPLEMENTATION IN PROGRESS; NOT A LIVE CERTIFICATE.

## Separation of concerns
- **Instrument quote/settlement currency:** independently verified ISO 4217 code from broker/instrument metadata (crypto-native tokens may require a separate asset identifier, not a fabricated fiat code).
- **Account currency:** broker account's actual funding and settlement currency.
- **Risk budget/reference currency:** configurable currency code for portfolio-wide comparisons. The current governed trial budget **remains CAD 20 per parent order and CAD 40 aggregate**, expressed in CAD-equivalent risk. CAD is a pilot configuration, not a universal trading currency.
- **Presentation currency:** operator-selectable display currency and not binding on execution authorization.
- **Broker eligibility:** distinct from ISO 4217 validity. A currency and asset must be available and lawful at the broker/account/jurisdiction; no unrestricted acceptance promise.

## Conversion controls
- Every order intent preserves ORIGINAL units, prices, contract multiplier, fees, source currency and account currency.
- Broker/exchange spot or authorized FX data supplies the rate, pair, timestamp, quote side, source ID, precision and max age. An FX conversion must be triangulated only through verified pairs with spread/fee conservatism, with explicit rounding UP for risk and safe handling of currencies with unusual decimal scales.
- Never interpret a numeric amount as CAD merely because a field says `notional`. If currency is missing, stale, unsupported, ambiguous or unconvertible, reject the *live* order.
- Quantify gross economic notional, margin, cash commitment, worst-case loss and obligations separately; don't use premium/margin alone as an exposure proxy.
- All existing R7, AntiBleed, dual control, stop trading, reservation and reconciliation checks remain mandatory; conversions may tighten but cannot override budget.
- Concurrency atomicity must operate on converted risk budget with quote freshness revalidated at submit; price/FX movements and fills must be reconciled.
- No universal hardcoded list of permitted currencies: use ISO 4217 standards + governed per-broker per-account capability/allow-lists, sanctions and legal permissions.
- For future pilot budgets, make currency and values configuration data with separately approved change-control; any increase above approved CAD 20/40 equivalent requires explicit authorization.
 
## Current branch limitations
- `backend/config/order_limit_config.py` currently uses CAD field names and ceilings.
- `backend/runtime/pilot_portfolio_limit.py` and reservation logic take caller-provided CAD amounts.
- Experimental `backend/runtime/pilot_cross_asset_exposure.py` converts quote amounts using an externally supplied quote-to-CAD numeric rate, but **cannot verify FX provenance or non-CAD risk-budget configuration**. It must not be wired into execution until these issues are resolved.
- No modification to running CSS broker/transaction state, and pilot remains **NO-GO for live orders**.

## Acceptance tests
1. USD/EUR/GBP/JPY/NGN and broker-supported fiat codes without currency-specific program branches; pair direction, stale timestamp and missing pair fail closed.
2. Cross-currency simultaneous reservations never exceed CAD-equivalent 20/40 and budget rounding never understates risk.
3. Test non-two-decimal currencies, no FX drift at authorization-to-execution, and stop if quote becomes stale.
4. Broker minimums, multiplier, fees, funding/settlement and worst-case loss checked in original and normalized currencies.
5. Permission policies and real broker routes must be certified independently before live orders.
