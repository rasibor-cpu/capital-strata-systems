# CSS Branch Consolidation Audit

Audit generated: 2026-07-14

Authoritative branch audited against: `css-evening-consolidation-2026-06-09`

Scope: branch reconciliation only. No merge, rebase, reset, branch deletion, force-push, commit, or push was performed.

## Stage 1 Inventory Snapshot

Commands run:

```powershell
git fetch --all --prune
git status --short --branch
git branch -vv
git branch -a
git remote -v
git tag --list
git log --graph --decorate --oneline --all -100
```

Repository state after fetch:

- Current branch: `css-evening-consolidation-2026-06-09`
- Current branch head: `33f814d82882c91a09694c4fd8644e21b0786d35`
- Upstream: `origin/css-evening-consolidation-2026-06-09`
- Upstream delta: ahead 0, behind 0
- Remote: `origin https://github.com/rasibor-cpu/capital-strata-systems.git`
- Untracked files were present before this audit and were not modified: `automated_run_log.txt`, `broker_bootstrap_coinbase.txt`, `broker_bootstrap_oanda.txt`, `broker_diag_runner.py`, `broker_diagnostics.txt`, `broker_search_results.txt`, `coinbase_rc1b_expected_report.json`, `manual_run_log.txt`, `oanda_rc1b_expected_report.json`, `run_output.txt`, `runtime_reports/`
- `git status --short --branch` reported `warning: could not open directory '.pytest_cache/': Permission denied`

## Classification Rules Used

- `ALREADY_INTEGRATED`: branch tip is an ancestor of `css-evening-consolidation-2026-06-09`.
- `DUPLICATE`: branch tip SHA is shared by another branch, or the branch is a local/remote duplicate of the same work.
- `GENERATED_ONLY`: unique diff is only generated reports/logs/artifacts.
- `EXPERIMENTAL`: spec, WIP, documentation-only, or planning branch with no unique runtime implementation evidence.
- `SUPERSEDED`: no unique commits versus the authoritative branch but not otherwise classified. No active branch in this audit required this label after ancestor checks.
- `SALVAGE_REQUIRED`: unique work exists but is destructive, obsolete, ambiguous, or risky to merge directly.
- `CANDIDATE_FOR_MERGE`: unique implementation work exists and should be reviewed in isolation before consolidation.

## Branch Inventory

`Unique` means commits reachable from the branch and not reachable from `css-evening-consolidation-2026-06-09`. File counts use `git diff --name-only css-evening-consolidation-2026-06-09...BRANCH`.

| Kind | Branch | HEAD SHA | Date | Upstream | A/B upstream | Merged to auth | Merged to main | Unique | Files | Areas touched | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| local | `CSS_PRE_PROFIT_PER_WINNER_BASELINE_2026_04_14` | `f22f91657ba7cee25795bbd5512b9addc8cf550e` | 2026-04-14 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `CSS_SLOT_ENGINE_LOCK_2026_04_22` | `8c18f3f779d712c802692cd6b72c41e682617fd3` | 2026-04-22 |  |  | no | no | 63 | 64 | options, futures, dashboard, broker, execution, risk, PnL, governance | CANDIDATE_FOR_MERGE |
| local | `PRE_MERGE_SAFETY_2026_05_20` | `e6ab6cdd2de091fbe5a54a47bbacac0a11f82d99` | 2026-05-20 |  |  | no | no | 73 | 139 | options, dashboard, broker, execution, risk, PnL, governance, tests | CANDIDATE_FOR_MERGE |
| local | `audit-governance` | `e61060d13994e66f520c175b5590f8d8687a2e04` | 2026-02-14 | origin/governance_phase_lock | ahead 0, behind 0 | no | no | 27 | 20 | options, futures, broker, execution, risk | DUPLICATE |
| local | `audit-options` | `f374539b7cd20172fe9865e1ce0f30f7755c4caf` | 2026-04-12 | origin/feature/options-sandbox-phase1 | ahead 0, behind 0 | no | no | 3 | 3 | options, futures | DUPLICATE |
| local | `audit-post-claude` | `8f0f33fca0116267cd48438c890b4a1a96b0dd68` | 2026-05-27 | origin/post-claude-audit-remediation-phase-a-clean | ahead 0, behind 0 | no | no | 1 | 1 | governance | DUPLICATE |
| local | `audit-world-event` | `f5c8ecf14859569239f17c817c8c9ca2aeb546f4` | 2026-05-18 | origin/feature/css-world-event-intelligence | ahead 0, behind 0 | no | no | 1 | 1 | intelligence docs | DUPLICATE |
| local | `codex/build-css-profitability-analytics-foundation` | `ea229cd05dfa1117cb249f080cda237e4dee28fc` | 2026-05-25 | origin/codex/build-css-profitability-analytics-foundation | ahead 0, behind 0 | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `codex/fix-remaining-test-failures-for-phase-54` | `d4eee30ce07ba6e19a441ee52f7124695ba0d44f` | 2026-05-22 | origin/codex/fix-remaining-test-failures-for-phase-54 | ahead 0, behind 0 | no | no | 1 | 6 | dashboard, broker, execution, governance | DUPLICATE |
| local | `codex/implement-opportunity-normalization-foundation` | `51dc02eab5a81ebe4090833fb7039272c321fabd` | 2026-05-25 | origin/codex/implement-opportunity-normalization-foundation | ahead 0, behind 0 | no | no | 1 | 6 | dashboard, tests | DUPLICATE |
| local | `consolidation/pcnrass-mainline` | `3fd6f4d4cabd8508ad2036eb699300f97c4648f4` | 2026-05-31 |  |  | no | no | 12 | 25 | dashboard, broker, execution, risk, PnL, governance | CANDIDATE_FOR_MERGE |
| local | `css-audit-fix-phaseA` | `6a707e93993a5a78f4ae1db19915037e1d104555` | 2026-05-02 |  |  | no | no | 38 | 43 | dashboard, broker, execution, risk, PnL, governance | CANDIDATE_FOR_MERGE |
| local | `css-claude-engine` | `26b53cf3589d39d60504b5d6c6b92de9dca27be7` | 2026-05-02 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `css-dashboard-recovery-merge` | `e4df7042b8c4cb5f2e614992811ba26250446a2e` | 2026-04-21 |  |  | no | no | 64 | 35 | options, futures, dashboard, broker, execution, risk, governance | CANDIDATE_FOR_MERGE |
| local | `css-dashboard-separation-phase2` | `2221a6a59196a770190d1cdd2efd86dfede5ef39` | 2026-05-16 |  |  | no | no | 53 | 118 | dashboard, broker, execution, risk, PnL, governance, tests | CANDIDATE_FOR_MERGE |
| local | `css-evening-consolidation-2026-06-09` | `33f814d82882c91a09694c4fd8644e21b0786d35` | 2026-07-13 | origin/css-evening-consolidation-2026-06-09 | ahead 0, behind 0 | yes | no | 0 | 0 | authoritative branch | ALREADY_INTEGRATED |
| local | `css-must-haves-phase1-2026-05-12` | `03b242f5511f4be895338e076e3ecb6e20b3136e` | 2026-05-12 |  |  | no | no | 1 | 12 | dashboard, broker, execution, tests | CANDIDATE_FOR_MERGE |
| local | `css-phase2-coinbase-init-fix` | `ee5f0606c1c994683c3e0df9148eace6bbdd2205` | 2026-05-02 | origin/css-phase2-coinbase-init-fix | ahead 0, behind 0 | no | no | 36 | 42 | dashboard, broker, execution, risk, PnL, governance | DUPLICATE |
| local | `css-phone-review-2026-06-17` | `467ecf22095d36d00b788adc2e07bdab1632a619` | 2026-06-17 | origin/css-phone-ops-2026-06-17 | ahead 0, behind 0 | no | no | 18 | 18 | broker, risk, governance | DUPLICATE |
| local | `css-pnl-optimization-v2` | `16efbb778d960ca0e1182d4788cb063ed0ef9cf5` | 2026-04-23 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `css-pnl-optimization-v2-local-backup` | `16efbb778d960ca0e1182d4788cb063ed0ef9cf5` | 2026-04-23 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `css-pnl-recovery-clean-2026-04-25` | `16efbb778d960ca0e1182d4788cb063ed0ef9cf5` | 2026-04-23 | origin/css-pnl-recovery-clean-2026-04-25 | ahead 0, behind 0 | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `css-profit-baseline-reference` | `8af7e1a01843a817dcc5a3092a2ea56775346db0` | 2026-04-22 | origin/css-profit-baseline-reference | ahead 2, behind 0 | no | no | 58 | 31 | options, futures, dashboard, broker, execution, risk, governance | CANDIDATE_FOR_MERGE |
| local | `desktop-broker-readiness` | `d749e743d34d3852a9e0321411a659865b59e83b` | 2026-07-11 |  |  | yes | no | 0 | 0 | broker readiness | ALREADY_INTEGRATED |
| local | `feature/css-world-event-intelligence` | `f5c8ecf14859569239f17c817c8c9ca2aeb546f4` | 2026-05-18 | origin/feature/css-world-event-intelligence | ahead 0, behind 0 | no | no | 1 | 1 | intelligence docs | DUPLICATE |
| local | `j7-canonical-intelligence-wiring` | `c79ecd40d7853d79b87404b5fa9d8dfae00f7940` | 2026-06-01 |  |  | no | no | 1 | 1 | PnL, governance | EXPERIMENTAL |
| local | `main` | `171a15d9ecae4733f7d03c13abe4b0a3a561ce5d` | 2026-06-17 | origin/main | ahead 0, behind 1 | no | yes | 4 | 1 | deployment docs | EXPERIMENTAL |
| local | `phase1-lock-candidate-manual` | `31634eaf9776fec942a664c1984457c30d2b0a84` | 2026-06-08 | origin/phase1-lock-candidate-manual | ahead 0, behind 0 | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `phase1-persistence-foundation` | `0fae9decac055e5ccfb4e6ca596b086a587bdf47` | 2026-05-23 | origin/main | ahead 97, behind 249 | no | no | 97 | 157 | options, futures, dashboard, broker, execution, risk, PnL, governance, tests | CANDIDATE_FOR_MERGE |
| local | `phase1c-date-override-audit` | `4235953df498a35586a087d37cbf159c1e62e1fe` | 2026-02-26 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `phase1c-ledger-printing` | `dfc657c5c0b379e1ac7f0c93c51a888db39abce3` | 2026-03-07 | origin/phase1c-ledger-printing | ahead 0, behind 0 | no | no | 115 | 212 | dashboard, broker, execution, risk, PnL, governance, tests | DUPLICATE |
| local | `phase52_visual_validation` | `c1d9781b79c9e33936486b1e8d6f6816f6caeb48` | 2026-05-16 |  |  | no | no | 55 | 119 | dashboard, broker, execution, risk, PnL, governance, tests | CANDIDATE_FOR_MERGE |
| local | `phase57-regime-governance-foundation` | `ee5043d5557688af8a51d15a20145072868110dd` | 2026-05-25 | origin/phase57-regime-governance-foundation | ahead 0, behind 0 | no | no | 1 | 1 | governance, tests | DUPLICATE |
| local | `phase65b-pnl-governance-integration` | `4fa1bf7dee78553c3c9369305fd4b24352d7a82e` | 2026-05-26 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `phase70b-legal-acceptance` | `d7991c94ef83cd84fef45071fab4bb43991648b2` | 2026-06-02 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `phase71-phone-recovery` | `a59a0dc7ab189156979a8159aef662f24414a2de` | 2026-06-07 | origin/phase71-phone-recovery | ahead 0, behind 0 | no | no | 1 | 8 | dashboard, execution, PnL | DUPLICATE |
| local | `phone-offline-audit` | `77b8c5aa417eccecf3bfef9c1b1673f859b66399` | 2026-05-31 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `phone-offline-merge` | `b7b01a0a37032ed9ccaebe253180b0c7fee1cd69` | 2026-01-28 | origin/phone-offline-merge | ahead 0, behind 0 | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| local | `pnl-engine-safe-integration` | `53753f42afe7271c2b21e99accfb05ef25ef4c03` | 2026-04-21 |  |  | no | no | 63 | 35 | options, futures, dashboard, broker, execution, risk, governance | DUPLICATE |
| local | `recover-full-dashboard-2056` | `175b7f884c05595c80f6fb238fab420465497d12` | 2026-04-27 | origin/recover-full-dashboard-2056 | ahead 4, behind 0 | no | no | 14 | 37 | dashboard, broker, execution, risk, PnL, governance | CANDIDATE_FOR_MERGE |
| remote | `origin/codex/build-css-profitability-analytics-foundation` | `ea229cd05dfa1117cb249f080cda237e4dee28fc` | 2026-05-25 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/codex/fix-phase-54-pilot-safety-controls-test-failures` | `45fbdac0d07344392744bd76b200fbc19c1548c5` | 2026-05-22 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/codex/fix-remaining-test-failures-for-phase-54` | `d4eee30ce07ba6e19a441ee52f7124695ba0d44f` | 2026-05-22 |  |  | no | no | 1 | 6 | dashboard, broker, execution, governance | DUPLICATE |
| remote | `origin/codex/implement-opportunity-normalization-foundation` | `51dc02eab5a81ebe4090833fb7039272c321fabd` | 2026-05-25 |  |  | no | no | 1 | 6 | dashboard, tests | DUPLICATE |
| remote | `origin/consolidation/pcnrass-mainline` | `540a21e0e44d2c6162c9cff63a5de0a08e5fd413` | 2026-05-28 |  |  | no | no | 1 | 8 | broker, execution, risk, PnL, governance | EXPERIMENTAL |
| remote | `origin/css-evening-consolidation-2026-06-09` | `33f814d82882c91a09694c4fd8644e21b0786d35` | 2026-07-13 |  |  | yes | no | 0 | 0 | authoritative remote | ALREADY_INTEGRATED |
| remote | `origin/css-phase2-coinbase-init-fix` | `ee5f0606c1c994683c3e0df9148eace6bbdd2205` | 2026-05-02 |  |  | no | no | 36 | 42 | dashboard, broker, execution, risk, PnL, governance | DUPLICATE |
| remote | `origin/css-phone-ops-2026-06-17` | `467ecf22095d36d00b788adc2e07bdab1632a619` | 2026-06-17 |  |  | no | no | 18 | 18 | broker, risk, governance | DUPLICATE |
| remote | `origin/css-pnl-recovery-clean-2026-04-25` | `16efbb778d960ca0e1182d4788cb063ed0ef9cf5` | 2026-04-23 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/css-profit-baseline-reference` | `d2f0129faabcc79f8b1bf8d0d09c1d908ebc7e6e` | 2026-04-20 |  |  | no | no | 56 | 31 | options, futures, dashboard, broker, execution, risk, governance | CANDIDATE_FOR_MERGE |
| remote | `origin/feature/backend-core-wiring` | `c5f62333c48f1650ce534a2fc7800fb827cec0ac` | 2026-01-30 |  |  | no | no | 7 | 6 | backend deletion risk | SALVAGE_REQUIRED |
| remote | `origin/feature/broker-bootstrap` | `407d8bc86a45ab87bea6a68c823c487449609203` | 2026-03-06 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/feature/css-world-event-intelligence` | `f5c8ecf14859569239f17c817c8c9ca2aeb546f4` | 2026-05-18 |  |  | no | no | 1 | 1 | intelligence docs | DUPLICATE |
| remote | `origin/feature/futures-orchestrator-integration-spec` | `0f0283083608700c15b60faa92363337d5462943` | 2026-04-12 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/feature/options-dashboard-pnl-spec` | `d6410e1d9fb4336403fc8b5f8ec38d65fedf023b` | 2026-04-12 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/feature/options-expiry-lifecycle-spec` | `980630ccd6695022722667cbdcf23413942f5d4b` | 2026-04-12 |  |  | no | no | 2 | 2 | options docs | EXPERIMENTAL |
| remote | `origin/feature/options-orchestrator-integration-spec` | `192aacb5a7c0624ff3244d7653825c4c0912e5b1` | 2026-04-12 |  |  | no | no | 1 | 1 | options execution docs | EXPERIMENTAL |
| remote | `origin/feature/options-position-manager-spec` | `c41c5f90d4c2ef653a567b74d64a8085b1d3fe71` | 2026-04-12 |  |  | no | no | 1 | 1 | options docs | EXPERIMENTAL |
| remote | `origin/feature/options-risk-governor-spec` | `15b00a0aae7b0a26ceeafb8b81d02a6d241aba0f` | 2026-04-12 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/feature/options-sandbox-phase1` | `f374539b7cd20172fe9865e1ce0f30f7755c4caf` | 2026-04-12 |  |  | no | no | 3 | 3 | options, futures | DUPLICATE |
| remote | `origin/feature/options-sandbox-test-harness-spec` | `a91fe7cc9d316c083117f6ef19ca8f4fcf050653` | 2026-04-12 |  |  | no | no | 1 | 1 | options tests docs | EXPERIMENTAL |
| remote | `origin/feature/posting-screens` | `f76a63378915a0f5074a085a00737a3a228def54` | 2026-01-31 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/governance_phase_lock` | `e61060d13994e66f520c175b5590f8d8687a2e04` | 2026-02-14 |  |  | no | no | 27 | 20 | options, futures, broker, execution, risk | DUPLICATE |
| remote | `origin/live-adapters` | `cb97af4409b83bf92961210f1e01d67015348104` | 2026-02-03 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/main` | `faf1485dd88d7056bbd8f7f891cb47caf7685603` | 2026-06-18 |  |  | no | no | 5 | 2 | deployment and operations docs | EXPERIMENTAL |
| remote | `origin/master` | `eaa8d538a74d5ace04766bfb21762fb221af0023` | 2026-01-26 |  |  | no | no | 3 | 0 | unrelated historical root | SALVAGE_REQUIRED |
| remote | `origin/phase-10-posting-screens` | `50c23337eb4155a67667507d54e0d7975a7c11c8` | 2026-01-31 |  |  | no | no | 7 | 7 | posting, risk, PnL, tests | CANDIDATE_FOR_MERGE |
| remote | `origin/phase-155-caie-capital-allocation-intelligence` | `a81ce8a18f957d48fab448f019a4e72dee1934dd` | 2026-07-04 |  |  | yes | no | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/phase1-lock-candidate-manual` | `31634eaf9776fec942a664c1984457c30d2b0a84` | 2026-06-08 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/phase1c-ledger-printing` | `dfc657c5c0b379e1ac7f0c93c51a888db39abce3` | 2026-03-07 |  |  | no | no | 115 | 212 | dashboard, broker, execution, risk, PnL, governance, tests | DUPLICATE |
| remote | `origin/phase57-regime-governance-foundation` | `ee5043d5557688af8a51d15a20145072868110dd` | 2026-05-25 |  |  | no | no | 1 | 1 | governance, tests | DUPLICATE |
| remote | `origin/phase71-church-governance-pack` | `a758643204ad632d68ce5907b7dfccf29e614865` | 2026-06-08 |  |  | no | no | 8 | 8 | dashboard, broker, risk, governance | EXPERIMENTAL |
| remote | `origin/phase71-phone-recovery` | `a59a0dc7ab189156979a8159aef662f24414a2de` | 2026-06-07 |  |  | no | no | 1 | 8 | dashboard, execution, PnL | DUPLICATE |
| remote | `origin/phase90a-institutional-instrument-framework` | `2f66bd66ca28942ffdf02a6d78004552864711b7` | 2026-06-12 |  |  | no | no | 3 | 2 | governance docs | EXPERIMENTAL |
| remote | `origin/phase90b-institutional-registry-engine` | `7136df7ab971b7a0a33fad2e124c5f04dba29739` | 2026-06-12 |  |  | no | no | 4 | 3 | governance docs | EXPERIMENTAL |
| remote | `origin/phone-offline-merge` | `b7b01a0a37032ed9ccaebe253180b0c7fee1cd69` | 2026-01-28 |  |  | yes | yes | 0 | 0 | none | ALREADY_INTEGRATED |
| remote | `origin/pnl-engine-safe-integration` | `53753f42afe7271c2b21e99accfb05ef25ef4c03` | 2026-04-21 |  |  | no | no | 63 | 35 | options, futures, dashboard, broker, execution, risk, governance | DUPLICATE |
| remote | `origin/post-claude-audit-remediation-phase-a-clean` | `8f0f33fca0116267cd48438c890b4a1a96b0dd68` | 2026-05-27 |  |  | no | no | 1 | 1 | governance | DUPLICATE |
| remote | `origin/recover-full-dashboard-2056` | `2bdbfd3bc2f66ba4247244c6990975a26865239c` | 2026-04-27 |  |  | no | no | 10 | 25 | dashboard, broker, execution, risk, governance | CANDIDATE_FOR_MERGE |
| remote | `origin/wip/intel-adapter-edits` | `778bc2fadfc3813ce1989032628bd5b25363a15b` | 2026-02-02 |  |  | no | no | 1 | 4 | broker/intelligence adapters | EXPERIMENTAL |

## Duplicate Work

Duplicate branch tips discovered:

| HEAD | Branches |
| --- | --- |
| `d4eee30` | `codex/fix-remaining-test-failures-for-phase-54`, `origin/codex/fix-remaining-test-failures-for-phase-54` |
| `31634ea` | `phase1-lock-candidate-manual`, `origin/phase1-lock-candidate-manual` |
| `ea229cd` | `codex/build-css-profitability-analytics-foundation`, `origin/codex/build-css-profitability-analytics-foundation` |
| `33f814d` | `css-evening-consolidation-2026-06-09`, `origin/css-evening-consolidation-2026-06-09` |
| `ee5043d` | `phase57-regime-governance-foundation`, `origin/phase57-regime-governance-foundation` |
| `f374539` | `audit-options`, `origin/feature/options-sandbox-phase1` |
| `b7b01a0` | `phone-offline-merge`, `origin/phone-offline-merge` |
| `467ecf2` | `css-phone-review-2026-06-17`, `origin/css-phone-ops-2026-06-17` |
| `8f0f33f` | `audit-post-claude`, `origin/post-claude-audit-remediation-phase-a-clean` |
| `e61060d` | `audit-governance`, `origin/governance_phase_lock` |
| `ee5f060` | `css-phase2-coinbase-init-fix`, `origin/css-phase2-coinbase-init-fix` |
| `dfc657c` | `phase1c-ledger-printing`, `origin/phase1c-ledger-printing` |
| `51dc02e` | `codex/implement-opportunity-normalization-foundation`, `origin/codex/implement-opportunity-normalization-foundation` |
| `16efbb7` | `css-pnl-optimization-v2`, `css-pnl-optimization-v2-local-backup`, `css-pnl-recovery-clean-2026-04-25`, `origin/css-pnl-recovery-clean-2026-04-25` |
| `53753f4` | `pnl-engine-safe-integration`, `origin/pnl-engine-safe-integration` |
| `f5c8ecf` | `audit-world-event`, `feature/css-world-event-intelligence`, `origin/feature/css-world-event-intelligence` |
| `a59a0dc` | `phase71-phone-recovery`, `origin/phase71-phone-recovery` |

## Candidate Branch Detail

These branches contain unique implementation files and should be reviewed in isolated worktrees before any merge.

| Branch | Unique commit evidence | Unique file evidence | Recommendation |
| --- | --- | --- | --- |
| `phase1-persistence-foundation` | `0fae9de PCNRASS: unify cross-asset scanner and orchestrator flow without regression`; `bbda834 PCNRASS: add persistent execution journal foundation`; `0221e58 PCNRASS: add unified risk execution gate foundation` | Adds `backend/app/persistence/*`, `backend/app/orchestration/cross_asset_execution_orchestrator.py`, `backend/app/options/*`, `backend/app/futures/*`, audit ledgers, tests | Highest-value candidate, but large divergence. Cherry-pick by subsystem, not wholesale merge. |
| `PRE_MERGE_SAFETY_2026_05_20` | `e6ab6cd phase1: add IBKR broker bootstrap and reconciliation scaffold`; persistence service commits | Adds persistence DB/migrations/repositories/services, broker readiness/reconciliation, tests | Compare against current persistence/runtime services first. Salvage durable persistence only if not already replaced. |
| `css-dashboard-separation-phase2` | Evidence hashing, notarization, post-pilot archive, dashboard separation commits | Adds `dashboard/runtime/evidence_*`, `dashboard/auth/persistent_session_store.py`, broker conformance and live dry-run certification files | Merge only evidence/dashboard runtime pieces after conflict review. |
| `phase52_visual_validation` | Extends `css-dashboard-separation-phase2` with browser visual governance validation | Same cluster plus visual validation evidence | Prefer this over `css-dashboard-separation-phase2` if visual validation artifacts are desired. |
| `css-must-haves-phase1-2026-05-12` | Single integration commit `03b242f` | Broker registry/credential loader, execution boundary, dashboard web edits, `tests/dashboard/test_frontend_payloads.py` | Small candidate. Review first because low blast radius. |
| `consolidation/pcnrass-mainline` | Governance/user-risk/terms/persistence recovery commits | Mobile dashboard edits plus governance architecture docs | Treat mostly governance/docs; cherry-pick legal/operator docs after current equivalents check. |
| `css-profit-baseline-reference` | Dashboard/PnL/broker gate audit baseline commits | Broker gate audit, session state, PnL/dashboard/auth/security edits | Candidate for historical dashboard/PnL recovery comparison; avoid wholesale merge. |
| `origin/css-profit-baseline-reference` | Older subset of local branch | Same cluster minus two local commits | Superseded by local `css-profit-baseline-reference` for review purposes. |
| `CSS_SLOT_ENGINE_LOCK_2026_04_22` | Slot engine and FBL lock commits | Broad older dashboard/broker/PnL/options/futures edits | Review only if slot engine behavior is missing from current branch. |
| `css-dashboard-recovery-merge` | Dashboard shell/auth/broker controls and PnL baseline commits | Dashboard, broker gate, session, options/futures position edits | Overlaps `css-profit-baseline-reference`; compare before taking anything. |
| `css-audit-fix-phaseA` | Phase A candidate selection, accounting, Coinbase, compounding commits | Account engine, Coinbase adapter, orchestrator backup, dashboard patches | Risky old recovery branch. Salvage only specific account/broker fixes. |
| `recover-full-dashboard-2056` | PCNRASS realism, broker isolation, dashboard/account settlement commits | Account engine, Coinbase balance, dashboard backup scripts, patch scripts | Salvage only if current dashboard/account settlement lacks a proven equivalent. |
| `origin/recover-full-dashboard-2056` | Remote subset of local recovery branch | Similar dashboard/account/broker files | Superseded by local `recover-full-dashboard-2056` plus 4 local commits. |
| `origin/phase-10-posting-screens` | Posting screens maker/checker/limits commits | `postings/*`, `test_maker_screen_builder.py` | Independent backoffice candidate; merge separately from trading/runtime consolidation. |

## Missing Or Unresolved Work

- Live options execution is not present on the authoritative branch. Options execution adapters are dry-run only.
- Live futures execution is not present on the authoritative branch. Futures execution adapters are dry-run only.
- Options broker integration is not present beyond simulator/registry/spec surfaces.
- Futures broker integration is not present beyond simulator/registry/spec surfaces.
- Covered calls, cash-secured puts, Wheel, assignment, and rolling have no complete implementation on the authoritative branch. Covered calls and cash-secured puts appear as scaffolded/intelligence labels only.
- Several historical recovery branches contain executable code that overlaps current files. Direct merge would be high-risk because many branches predate the current authority consolidation.
- `origin/feature/backend-core-wiring` includes backend deletion risk and should not be merged directly.
- `origin/master` is an old unrelated root/history branch and should not be merged directly.

## Safest Consolidation Strategy

1. Freeze `css-evening-consolidation-2026-06-09` as the audit base.
2. Create disposable worktrees for each `CANDIDATE_FOR_MERGE` branch.
3. Start with small, low-blast-radius candidates: `css-must-haves-phase1-2026-05-12`, then `origin/phase-10-posting-screens`.
4. Review `phase1-persistence-foundation` by subsystem: persistence, audit ledger, cross-asset orchestrator, options/futures adapters, tests.
5. Review dashboard/evidence branches as a cluster: `phase52_visual_validation`, `css-dashboard-separation-phase2`, `consolidation/pcnrass-mainline`.
6. Review older dashboard/PnL/account recovery branches only after current runtime tests pass: `css-profit-baseline-reference`, `recover-full-dashboard-2056`, `CSS_SLOT_ENGINE_LOCK_2026_04_22`, `css-dashboard-recovery-merge`, `css-audit-fix-phaseA`.
7. Do not merge duplicate local/remote pairs twice.
8. Do not merge `origin/feature/backend-core-wiring` or `origin/master` directly.
9. For each accepted subsystem, cherry-pick or manually port the minimal files, then run targeted tests before proceeding.
10. Leave branch deletion/pruning decisions until after accepted work is documented and committed on a dedicated consolidation branch.
