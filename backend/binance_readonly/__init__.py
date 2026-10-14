"""Binance Spot authenticated READ-ONLY access (balances, order history, trade history).

GET-only client restricted to an explicit endpoint allowlist. There is no code path
for orders, cancels, transfers, withdrawals, margin, futures or options. Account
endpoints are refused until an eligibility decision (operator attestation + the
API key's own permission report + account status) has passed.

This package must never be imported by the shadow paper runner (enforced by
backend.shadow_paper.controls.FORBIDDEN_MODULE_PREFIXES).
"""
