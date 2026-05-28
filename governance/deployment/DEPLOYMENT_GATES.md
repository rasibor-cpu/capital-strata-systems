# CSS Deployment Gates

## Required Gates Before Deployment

1. Clean git status.
2. Baseline rollback tag exists.
3. No secrets or .env files tracked.
4. Python compile checks pass.
5. Pytest suite passes.
6. Dashboard smoke test passes.
7. Paper/live mode validation passes.
8. Broker credential validation passes.
9. Governance gates pass.
10. PnL reconciliation passes.
11. Rollback tag created.
12. PCNRASS sign-off completed.

## Deployment Rule
No deployment is allowed unless all gates pass or an explicit governance exception is documented.
