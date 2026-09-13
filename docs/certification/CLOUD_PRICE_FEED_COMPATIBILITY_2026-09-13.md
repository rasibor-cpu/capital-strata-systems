# Cloud Price-Feed Compatibility Repair — 2026-09-13

Status: compatibility repair only; no live market-data activation.

The GitHub tree referenced backend.data.price_feed from the legacy live dashboard, but the backend/data package was absent. That prevented two existing test modules from being collected in cloud CI.

The repair adds a minimal fail-closed compatibility boundary:

- no network client;
- no broker credentials;
- no live market-data activation;
- no order/execution methods;
- no money-movement methods;
- deterministic price injection only in simulated/test context;
- unavailable prices return None.

This repair exists to restore repository integrity and test collection. It must not be treated as the final production market-data provider. The canonical local/QRO tree should be reconciled before final merge in case it contains a newer authoritative implementation.
