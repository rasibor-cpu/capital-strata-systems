# CSS Runtime Consistency Matrix

Phase: OP-001

Baseline: `1a4d817f906eb65161081a461d3137f6d297b8ed`

This matrix records what OP-001 could observe from focused validation. No active Desktop runtime listener was available, so live host consistency is classified as blocked where applicable.

| Subsystem | Primary source | Observed value | Hash | Freshness | Status | Warnings | Consistency result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Runtime Supervisor | Launcher/runtime modules | No active listener/process observed | Not observed | Not observed | BLOCKED | Desktop host was not running or not observable from validation shell. | `UNVERIFIED_ACTIVE_HOST` |
| Runtime Snapshot | Runtime smoke payload and dashboard runtime tests | In-process smoke session `SMOKE-SESSION`, cycle `1`, broker `DEMO` | Not captured from active host | In-process fixture current for test | PASS_IN_PROCESS | Fixture evidence only. | `CONSISTENT_IN_PROCESS` |
| Mission Control | MC route/state tests | MC-001 through MC-007C passed | Tested in MC slices | In-process test freshness | PASS | Active HTTP endpoints not queried because no listener. | `CONSISTENT_IN_PROCESS` |
| Dashboard | Frontend payload and dashboard route tests | Dashboard payloads, broker reconciliation, mode, and PnL tests passed | Evidence hash tests not part of OP focused slice | In-process test freshness | PASS | Active dashboard host not observed. | `CONSISTENT_IN_PROCESS` |
| Mobile Dashboard | Mobile focused tests and mobile smoke | Focused mobile tests passed; standalone smoke failed login text contract | Not applicable | In-process test freshness | DEGRADED | Login page missing expected `Engine SAFE` / `System READ ONLY` strings. | `PARTIAL` |
| Canonical Broker State | Broker readiness/canonical tests | 146 broker tests passed | Not captured from active host | In-process test freshness | PASS | Mocked/no live broker traffic. | `CONSISTENT_IN_PROCESS` |
| Portfolio | Runtime smoke and dashboard PnL tests | Cash `10000.00`, equity `10250.00`, buying power `5000.00`, available margin `4000.00` | Not captured from active host | Fixture evidence | PASS_IN_PROCESS | Values are smoke fixtures, not live account values. | `CONSISTENT_IN_PROCESS` |
| Risk | Runtime smoke and safety tests | Risk state `NORMAL`, risk gate `OPEN` in smoke fixture | Not captured from active host | Fixture evidence | PASS_IN_PROCESS | One startup-summary display test failed outside core risk gate behavior. | `CONSISTENT_WITH_WARNING` |
| Decision Intelligence | Mission Control MC-006 tests | Decision intelligence slice passed | Not captured from active host | In-process test freshness | PASS | Active runtime decision payload not queried. | `CONSISTENT_IN_PROCESS` |
| Options Income | OI-008/OI-009/OI-010/RC1-OI tests | 76 passed | OI replay/certification hashes tested by OI suite | In-process test freshness | PASS | Paper/advisory only. | `CONSISTENT_IN_PROCESS` |
| Certification | Runtime smoke, MC, broker, OI, RC1 slices | Runtime/MC/broker/OI certification slices passed; safety slice had one display failure | Not captured from active host | In-process test freshness | DEGRADED | Active platform certificate endpoint not observed. | `CONSISTENT_WITH_WARNING` |
| Audit | Dashboard audit/mobile tests and OI/RC1 evidence | Covered by focused mobile and OI slices | Not captured from active host | In-process test freshness | PASS_IN_PROCESS | Active audit endpoint not queried. | `CONSISTENT_IN_PROCESS` |
| Alerts | Mission Control and runtime/dashboard test evidence | MC operations/secure ops slices passed | Not captured from active host | In-process test freshness | PASS_IN_PROCESS | Delivery channel not operationally tested. | `CONSISTENT_IN_PROCESS` |
| Runtime Heartbeat | Mission Control heartbeat tests and launcher routes | Route definitions and MC tests passed | Not captured from active host | Not observed live | BLOCKED | No active listener for live heartbeat query. | `UNVERIFIED_ACTIVE_HOST` |

## Proof Field Consistency

| Field | Active Desktop observation | In-process observation | Result |
| --- | --- | --- | --- |
| Runtime ID | Not observed | `SMOKE-SESSION` | `UNVERIFIED_ACTIVE_HOST` |
| Runtime Status | Not observed | Runtime smoke passed | `CONSISTENT_IN_PROCESS` |
| Heartbeat | Not observed | MC heartbeat tests passed | `UNVERIFIED_ACTIVE_HOST` |
| Cycle | Not observed | `1` | `CONSISTENT_IN_PROCESS` |
| Broker | Not observed | `DEMO` smoke fixture; broker slices mocked | `CONSISTENT_IN_PROCESS` |
| Execution Flags | Not observed live | Tests assert blocked/advisory posture | `CONSISTENT_WITH_WARNING` |
| Portfolio | Not observed live | Smoke fixture and dashboard PnL tests passed | `CONSISTENT_IN_PROCESS` |
| Cash | Not observed live | `10000.00` smoke fixture | `CONSISTENT_IN_PROCESS` |
| Buying Power | Not observed live | `5000.00` smoke fixture | `CONSISTENT_IN_PROCESS` |
| Risk Status | Not observed live | `NORMAL` smoke fixture | `CONSISTENT_IN_PROCESS` |
| Readiness | Not observed live | Broker/OI/MC slices passed | `CONSISTENT_IN_PROCESS` |
| Certification | Not observed live | Broker/OI/MC/runtime slices passed; safety display warning | `CONSISTENT_WITH_WARNING` |
| State Hash | Not observed live | MC/hash behavior covered by tests outside live host | `UNVERIFIED_ACTIVE_HOST` |
| Freshness | Not observed live | In-process route tests covered freshness behavior | `UNVERIFIED_ACTIVE_HOST` |
| Generated Timestamp | Not observed live | In-process generated payloads | `CONSISTENT_IN_PROCESS` |
| Source Provenance | Not observed live | Mission Control source registry tests passed | `CONSISTENT_IN_PROCESS` |

## Matrix Conclusion

The repository and in-process runtime contracts are broadly consistent. The complete OP-001 Desktop operational proof is not complete because no active Desktop host was available to observe over local HTTP.
