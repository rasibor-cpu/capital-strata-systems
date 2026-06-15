# Phase 1 Recovery and Resilience Validation Report

Date: 2026-06-15 12:59:58 -04:00

Branch: `css-evening-consolidation-2026-06-09`

Validation HEAD: `22ed884cfc20d1c9345f728715ca308121f3d9e4`

Scope: Item 3 Recovery Validation for CSS V1 certification evidence.

Mode restriction: PAPER / controlled local validation only. No live execution, broker order placement, trading logic modification, risk logic modification, broker logic modification, credentials change, or runtime behavior change was performed.

## Verification Before Start

`git remote -v`

```text
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (fetch)
origin  https://github.com/rasibor-cpu/capital-strata-systems.git (push)
```

`git branch --show-current`

```text
css-evening-consolidation-2026-06-09
```

`git rev-parse HEAD`

```text
22ed884cfc20d1c9345f728715ca308121f3d9e4
```

`git status`

```text
On branch css-evening-consolidation-2026-06-09
Your branch is up to date with 'origin/css-evening-consolidation-2026-06-09'.

nothing to commit, working tree clean
warning: could not open directory '.pytest_cache/': Permission denied
```

## Validation Commands

Targeted recovery and persistence tests:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_session_schema_initialization.py tests\test_pnl_snapshot_persistence_contract.py tests\test_trade_decision_orchestrator_gate.py -q
```

Result:

```text
8 passed, 9 warnings in 1.20s
```

Warnings observed:

```text
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.
Sources:
- backend/app/persistence/services/session_runtime_service.py:38
- backend/app/persistence/services/trade_runtime_service.py:45
- backend/app/persistence/services/trade_runtime_service.py:83
```

Action required: none for certification blocking. The warnings are implementation deprecation warnings, not recovery failure, broker execution, credential, or live-mode warnings.

Controlled recovery scenario probe:

```text
CSS_RECOVERY_SCENARIO_PROBE
Session Restore Validation: pass=True; active_sessions=1 restored_match=True
Fresh Startup With No Prior Session: pass=True; active_sessions=0 schema_ready=ok
Missing State File Handling: pass=True; db_created=True status=ok
Persistence Safety Validation: pass=True; snapshot_present=True broker_mode=paper open_positions=0
Broker/Account Data Unavailable Handling: pass=True; status=BROKER_UNAVAILABLE safe_degradation_required=True recommended_runtime_mode=paper
Restart / Recovery Flow: pass=True; before_close_active=1 after_close_active=0
Failed Restore Handling: pass=True; exception_type=DatabaseError fail_closed_no_execution=True
Safe-Fail Behaviour Review: pass=True; live_unavailable_recommended_mode=paper safe_degradation_required=True
overall_pass= True
```

The probe used temporary local state only. It did not use live credentials, connect to a broker, or place orders.

## A. Recovery Validation Report

The recovery validation confirms that CSS can bootstrap persistence schema on missing or fresh state, restore an active PAPER session from durable SQLite state, close and clear active sessions during restart/recovery flow, persist a PAPER PnL snapshot with zero open positions, and degrade live-unavailable broker/account conditions back to PAPER recommendation.

The failed-restore case was validated by pointing persistence at a deliberately invalid SQLite file. Current behavior raises a `DatabaseError`; this is treated as a safe-fail observation because the process does not proceed into execution and no live broker/order path is activated. It remains an operational recovery consideration for production certification because automatic corrupt-store repair was not demonstrated in this scenario.

## B. Scenario Matrix

| Scenario | Expected Behavior | Actual Behavior | Pass / Fail |
|---|---|---|---|
| 1. Session Restore Validation | Existing PAPER session remains discoverable after connection close/reopen. | Active session restored from temp SQLite state; restored session ID matched. | PASS |
| 2. Fresh Startup With No Prior Session | Fresh DB bootstraps schema and starts with zero active sessions. | Schema healthcheck returned `ok`; active session count was `0`. | PASS |
| 3. Failed Restore Handling | Invalid restore source must not enable execution or broker order placement. | Invalid DB raised `DatabaseError`; validation recorded fail-closed/no-execution behavior. | PASS WITH OBSERVATION |
| 4. Persistence Safety Validation | PAPER snapshot persists safely with no live mode and no stale open exposure. | Snapshot existed with `broker_mode=paper` and `open_positions=0`. | PASS |
| 5. Missing State File Handling | Missing runtime DB/state file is recreated through migration/bootstrap path. | Missing DB path was created and healthcheck returned `ok`. | PASS |
| 6. Broker/Account Data Unavailable Handling | Missing broker/account snapshot must degrade safely and recommend PAPER. | Status was `BROKER_UNAVAILABLE`; safe degradation required; recommended runtime mode was `paper`. | PASS |
| 7. Restart / Recovery Flow | Restart can rediscover active session, then close it cleanly. | Active before close was `1`; active after close was `0`. | PASS |
| 8. Safe-Fail Behaviour Review | Unsafe live/broker-unavailable condition must not remain live-authoritative. | Live-unavailable broker/account condition recommended `paper` and required safe degradation. | PASS |

## C. Recovery Risk Assessment

| Area | Risk Classification | Basis |
|---|---|---|
| Session restore from valid state | Low | Active PAPER session restored across connection close/reopen. |
| Fresh startup with no prior session | Low | Schema bootstrapped cleanly with no active session. |
| Missing state file | Low | Missing DB file was created and migrated successfully. |
| Persistence snapshot safety | Low | PAPER snapshot stored with zero open positions and no live mode. |
| Restart and close flow | Low | Active session was visible before close and absent after close. |
| Broker/account unavailable | Medium | Safe degradation to PAPER was proven, but live broker/account read-only evidence remains a separate certification gap. |
| Failed/corrupt restore | Medium | Behavior fails closed with `DatabaseError`, but automatic repair or operator-guided corrupt-store recovery was not demonstrated. |
| Safe-fail behavior under unavailable live authority | Medium | Recommended PAPER degradation was proven; final production certification still needs retained operator/audit evidence. |

Overall recovery risk classification: Medium.

Rationale: Core local recovery and persistence behavior passed. Residual risk remains around corrupt-store handling, operator runbook execution, retained audit evidence, and live broker/account unavailable evidence in an approved environment.

## D. Certification Recommendation

PASS WITH OBSERVATIONS

Rationale:

- All eight requested recovery scenarios passed the controlled validation probe.
- Targeted recovery, persistence, and orchestrator tests passed: `8 passed, 9 warnings`.
- No live execution was performed.
- No broker order placement was performed.
- Broker/account unavailable behavior recommended PAPER mode and safe degradation.
- Failed restore behavior failed closed and did not proceed into execution.
- Observations remain for deprecation warnings, corrupt-store operator handling, and final live broker/account recovery evidence.

## Certification Boundary

This artifact supports recovery and resilience certification evidence assembly. It does not certify production recovery readiness by itself. Final production certification still requires retained operator recovery runbook evidence, broker/account unavailable evidence from approved read-only broker contexts, recovery audit/event retention evidence, and final reviewer approval.

