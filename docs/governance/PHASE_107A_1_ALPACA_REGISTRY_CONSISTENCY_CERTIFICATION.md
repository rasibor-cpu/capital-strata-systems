# Phase 107A.1 Alpaca Registry Consistency Certification

## Root Cause
The `backend/app/brokers/broker_registry.py` defines Alpaca as a registered and approved broker (`supports_paper=True`, `supports_live=True`). However, the canonical `get_adapter()` implementation lacked a resolution path for Alpaca, allowing execution to fall through to a catch-all `KeyError`. This violated the fail-closed semantic requirement that unsupported but registered brokers must fail gracefully with explicit messaging. 

## Selected Remediation Path
**Option A** was selected based on repository evidence:
- Alpaca is actively being developed and approved for stream collection (`tests/test_alpaca_stream_collection.py` and `live_data/alpaca_adapter.py`).
- The `BROKER_REGISTRY` is documented as a metadata-only registry mapping approved capabilities, not strictly executable readiness.
- Removing Alpaca would incorrectly suggest the broker is unauthorized.
- The `KeyError` was upgraded to `NotImplementedError` for registered but unexecutable brokers. This enforces registry-resolver consistency and safely prevents Alpaca invocation while preserving its metadata status.

## Files Changed
- `backend/app/brokers/broker_registry.py`: Modified `get_adapter()` to raise `NotImplementedError` instead of `KeyError`.
- `tests/test_broker_registry.py` (New): Added tests ensuring `get_adapter("alpaca")` raises `NotImplementedError`, ensuring consistency between the registry definition and resolver boundaries.

## Tests Executed
The new `test_broker_registry.py` proves:
1. `test_registry_contains_approved_brokers`: Alpaca exists in the canonical registry.
2. `test_get_adapter_resolves_canonical_brokers`: OANDA and Coinbase resolve correctly.
3. `test_get_adapter_for_unsupported_registered_broker_raises_notimplementederror`: Alpaca safely triggers `NotImplementedError`.
4. `test_get_adapter_for_unregistered_broker_raises_keyerror`: Invalid brokers correctly trigger `KeyError`.

## Final Broker Authority Status
All supported brokers (OANDA, Coinbase) execute correctly. All unexecutable but approved brokers (Alpaca) fail closed explicitly. The broker boundary logic remains 100% stable without introducing unverified live execution logic.
