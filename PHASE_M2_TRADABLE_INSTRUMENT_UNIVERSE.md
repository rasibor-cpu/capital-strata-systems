# PHASE M2 - Tradable Instrument Universe and Trade Tab Selector

## Scope

Phase M2 introduces a canonical instrument universe for CSS mobile trade tabs, with fail-closed behavior and paper-safe selector integration.

This phase is backend + launcher trade-tab only.

No live execution permissions were changed.
No risk gates were bypassed.
No instrument selection path auto-executes trades.

## Delivered Components

## 1. Canonical Instrument Registry

Implemented in:
- backend/trading/instrument_universe.py

Exposed types:
- InstrumentUniverse
- TradableInstrument
- InstrumentUniverseError

Each instrument includes:
- symbol
- display_name
- asset_class
- broker
- tradable
- paper_supported
- live_supported
- exchange
- currency
- min_order_size
- max_order_size
- tick_size
- last_updated
- status
- metadata

## 2. Asset Classes

Registry supports:
- CRYPTO
- FX
- OPTIONS
- FUTURES
- EQUITIES (safe placeholder path)

## 3. Discovery Sources

Primary discovery uses existing internal sources:
- backend/app/options/options_contract_registry.py
- backend/app/futures/futures_contract_registry.py
- backend/app/brokers/broker_registry.py
- known Coinbase/OANDA symbols already represented by registered broker support

## 4. Fail-Closed Behavior

If discovery fails:
- static paper-safe fallback list is returned
- fallback instruments are marked:
  - tradable=false
  - live_supported=false
  - status=DISCOVERY_FALLBACK

Live support is never set true unless existing broker support is explicitly known.

## 5. Trade Tab Integration

Integrated into launcher mobile dashboard:
- launcher/css_mobile_launcher.py
- launcher/templates/mobile_dashboard.html

Trade tickets now include:
- asset class filter
- broker filter
- searchable instrument selector
- instrument status details (tradable, paper/live support, status)

Selection behavior:
- selecting instrument populates symbol + asset class fields only
- no auto-submit
- no order execution from selection

## 6. Backend Feed Helper

Added feed wiring via launcher helper:
- get_trade_tab_instrument_feed()

Exposed route:
- GET /mobile/instruments

Feed provides:
- all instruments
- instruments by asset class
- instruments by broker
- tradable paper instruments only

## 7. Safety and Execution Controls

Submission path remains unchanged:
- POST /mobile/trade/paper

Still enforced:
- paper-only request validation
- rejection of broker_mode=live
- rejection of broker_execution_allowed=true

No RBAC/risk/execution pipeline bypass was introduced.

## 8. Tests

Added:
- tests/test_instrument_universe.py
- tests/test_trade_tab_instrument_selector.py

Updated:
- tests/test_css_mobile_launcher.py

Coverage includes:
- registry returns instruments
- filters by asset class
- filters by broker
- tradable paper instruments
- fail-closed fallback behavior
- invalid asset class fails closed
- trade tab selector renders
- selector page load does not execute trades
- paper-only execution guard remains enforced
