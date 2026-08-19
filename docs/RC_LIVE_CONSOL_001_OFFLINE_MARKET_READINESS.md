# RC-LIVE-CONSOL-001 — Offline Market Contracts, Deterministic Providers & Read-Only Broker Certification

Canonical base: `css-v1.0.1-maintenance` @ `f3c59ee4326261957e16500cf0519aad687c3865`.

Reference only (not merged, not cherry-picked wholesale):

- `15b83a32` Phase 185A
- `f0efcba3` Phase 186A
- `840c56f5` Phase 187A

Recovered as one governed package under `backend/app/market/`.

Not recovered: ExecutionGate wiring, AntiBleed/risk microstructure bridge
(`backend.app.risk.live_microstructure_provider` / `LiveMicrostructureInputs`).
The composite uses localized `OfflineCertificationQuoteFacts` only.

live authority, credentials, network OANDA, Phases 184A / 188+.
