# CSS V1 Operational Evidence Matrix

| Area | Evidence | Result |
| --- | --- | --- |
| Repository synchronization | Local HEAD and origin branch both `4f29db5484c224edfd6b3edadd52c7693bf0c418` before OP-003 docs | PASS |
| Tracked tree hygiene | No tracked changes before OP-003 documentation; untracked artifacts left unstaged | PASS |
| Desktop runtime host | `launcher.css_mobile_launcher:app` served on `127.0.0.1:8765` | PASS |
| Mission Control registration | Mission Control routes registered through `register_mission_control` with launcher runtime provider | PASS |
| Canonical runtime source | Mission Control selected `desktop_runtime_artifacts` as `RUNTIME_ARTIFACT` | PASS |
| Runtime heartbeat | Online and recovered stages reported `heartbeat_status=FRESH` | PASS |
| Runtime recovery | Runtime transitioned `RUNNING -> STOPPED -> RUNNING` without web host restart | PASS |
| Dashboard frontend contract | `/api/v1/frontend-state` returned 200 | PASS |
| Runtime API | `/api/runtime-health`, `/api/runtime-portfolio-state`, and `/api/runtime-validation-monitor` returned 200 | PASS |
| Mission Control API | State, health, runtime, source, heartbeat, brokers, certification, final certification, decision, and evidence endpoints returned 200 | PASS |
| Broker readiness display | `/api/v1/broker-readiness` and `/mission-control/api/brokers` returned 200 | PASS |
| Portfolio/capital/accounting/risk visibility | Runtime portfolio, portfolio intelligence, artifact freshness, and validation monitor endpoints returned 200 | PASS |
| Options Income visibility | Covered by OI and enterprise regressions plus frontend/runtime operational surfaces | PASS |
| Decision/audit/certification visibility | Decision validation, Mission Control decision, evidence, certification, and final certification endpoints returned 200 | PASS |
| Safety posture | Execution flags remained false/blocked/advisory-only | PASS |
| No broker mutation | No order submission, cancellation, broker order preview, or execution arming performed | PASS |
| Static OP/BR/MC/broker regressions | 181 passed | PASS |
| OI/EI/RC1/dashboard/mobile regressions | 405 passed | PASS |
| Runtime smoke | `CSS runtime smoke test PASSED` | PASS |
| Web smoke | `CSS institutional web dashboard smoke test PASSED` | PASS |
| Mobile smoke | `CSS mobile web smoke test PASSED` | PASS |
| Compile validation | Related runtime, dashboard, mobile, launcher, and script modules compiled | PASS |

## Notes

- Closed trade ledger freshness can be stale in a no-trade proof because no paper/live trades were created. This is display evidence only and does not affect execution authority.
- A heartbeat-only supervisor state is insufficient for an active Mission Control runtime source. Current canonical artifacts must be published for Mission Control to select `RUNTIME_ARTIFACT`.
